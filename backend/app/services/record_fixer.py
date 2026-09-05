"""存量记录字段修正服务（字段治理闭环·修复环节）。

检测引擎只报告失败，不写存量；本模块是**治理字段 → 存量行值**的唯一写口
（编码类 CSV 导入是整行 upsert，不在此列）。修正语义：

- 记录身份 = uuid 主键，永不改；修正对象是治理字段（SAP 字段名），落点由
  `entity_accessor.describe_source` 裁决：column 走冗余列 setattr，attributes
  走 JSON 整体赋新 dict（SQLAlchemy 不追踪就地 mutation）。
- 护栏：字段必须已登记为该实体的数据标准（否则 400「先登记再治理」）；必填
  字段拒绝清空；pattern 预校验与检测引擎同一编译源、同一 search 语义
  （quality_engine.compile_pattern），保证「修复合法 → 重跑该字段必过」；
  编码列唯一冲突预查 + IntegrityError 兜底（并发窗口）。
- pattern 编译失败（非法正则）跳过预校验——与引擎「降级为 rule_errors、不
  猜测语义」同一信任边界；attributes 的 unique 字段不预查（JSON 无法索引查
  重，重跑仍会报 duplicate，不会静默引入污染）。
- 本模块只 commit 数据，不写审计（两段提交模式：API 层负责审计）。
"""
import re
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud, models
from app.services import entity_accessor
from app.services.entity_accessor import FieldSource
from app.services.quality_engine import compile_pattern


class RecordFixError(Exception):
    """修复被护栏拦截（API 层映射为 4xx）。"""


class RecordNotFound(RecordFixError):
    def __init__(self, entity_type: str, record_id: str):
        super().__init__(f"实体类型 {entity_type} 下不存在记录 {record_id}")


class FieldNotGoverned(RecordFixError):
    def __init__(self, entity_type: str, field_name: str, reason: str = ""):
        hint = f"；{reason}" if reason else ""
        super().__init__(
            f"字段 {field_name} 未纳入实体类型 {entity_type} 的治理范围"
            f"（请先登记数据标准）{hint}"
        )


class BlankRequiredValue(RecordFixError):
    def __init__(self, label: str, field_name: str):
        super().__init__(f"{label}（{field_name}）为必填字段，不允许清空")


class PatternViolation(RecordFixError):
    def __init__(self, label: str, field_name: str, pattern: str):
        super().__init__(
            f"{label}（{field_name}）新值不符合数据标准格式，需匹配 {pattern}"
        )


class NonNullableColumn(RecordFixError):
    def __init__(self, label: str, field_name: str):
        super().__init__(
            f"{label}（{field_name}）为存量身份列，不允许清空，请改填新值"
        )


class CodeConflict(RecordFixError):
    def __init__(self, label: str, field_name: str, value: Any):
        super().__init__(
            f"{label}（{field_name}）新值「{value}」已被其他记录占用，编码需全局唯一"
        )


def _load_record(db: Session, entity_type: str, record_id: str) -> Optional[Any]:
    """按实体类型取单条存量记录；未知类型返回 None（与 API 404 语义一致）。"""
    if entity_type == entity_accessor.MATERIAL:
        return crud.get_material_record(db, record_id)
    if entity_type in entity_accessor.PARTNER_ENTITY_TYPES:
        return crud.get_partner_record(db, entity_type, record_id)
    return None


def _unique_conflict(
    db: Session,
    entity_type: str,
    record: Any,
    column: str,
    value: Any,
) -> bool:
    """编码列唯一性预查：新值已被**其他**记录占用即冲突。

    material → material_code 全表唯一；supplier/customer → 各自 entity_type
    内 partner_code 唯一（对齐 uq_entity_partner_code 约束）。
    """
    if column == "material_code":
        row = (
            db.query(models.MaterialRecord)
            .filter(
                models.MaterialRecord.material_code == value,
                models.MaterialRecord.id != record.id,
            )
            .first()
        )
    else:  # partner_code
        row = (
            db.query(models.PartnerRecord)
            .filter(
                models.PartnerRecord.entity_type == entity_type,
                models.PartnerRecord.partner_code == value,
                models.PartnerRecord.id != record.id,
            )
            .first()
        )
    return row is not None


def fix_record_field(
    db: Session,
    entity_type: str,
    record_id: str,
    field_name: str,
    value: Any = None,
) -> dict:
    """按数据标准护栏修正一条存量记录的治理字段值，成功即落库并返回明细。

    `value=None / 空串` 表示清除该字段（仅非必填的 attributes 字段可清；
    必填字段与身份列拒绝，见护栏异常）。
    """
    # 1. 装载记录
    record = _load_record(db, entity_type, record_id)
    if record is None:
        raise RecordNotFound(entity_type, record_id)

    # 2. 查标准：字段名大小写不敏感，规范化名以标准登记为准
    #    （防 SMVendorID 等 camelCase 被 upper() 破坏）
    standard = crud.get_data_standard_for_field(db, entity_type, (field_name or "").strip())
    if standard is None:
        raise FieldNotGoverned(entity_type, (field_name or "").strip())
    canonical = standard.field_name
    label = standard.field_label or canonical

    # 3. 数据源裁决：标准可定义 ≠ 本系统可写（WERKS 等无数据源字段拒绝）
    source: FieldSource = entity_accessor.describe_source(entity_type, canonical)
    if not source.available:
        raise FieldNotGoverned(entity_type, canonical, source.reason or "")

    # 4. 输入归一：字符串去首尾空白后，空 = 清除语义（0/False 是合法值）
    if isinstance(value, str):
        value = value.strip()
    clearing = value is None or value == ""

    # 5. 护栏一：必填字段拒绝清空
    if clearing and standard.required:
        raise BlankRequiredValue(label, canonical)

    # 6. 护栏二：非空新值须过格式预校验（与检测引擎同源同语义）
    if not clearing and standard.pattern:
        try:
            compiled = compile_pattern(standard.pattern)
            if not compiled.search(str(value)):
                raise PatternViolation(label, canonical, standard.pattern)
        except re.error:
            pass  # 非法正则：与引擎一致降级，不猜测语义

    # 7. 落点裁决 + 护栏三（唯一性 / NOT NULL 列禁删）
    old_value = None
    if source.kind == "column":
        column = source.column or ""
        old_value = getattr(record, column, None)
        if clearing:
            # 冗余身份列均为 NOT NULL（material_code/partner_code/material_name/partner_name）
            raise NonNullableColumn(label, canonical)
        if _unique_conflict(db, entity_type, record, column, value):
            raise CodeConflict(label, canonical, value)
        setattr(record, column, value)
    else:  # attributes JSON：整体赋新 dict
        attributes = dict(record.attributes or {})
        if clearing:
            old_value = attributes.pop(canonical, None)
        else:
            old_value = attributes.get(canonical)
            attributes[canonical] = value
        record.attributes = attributes

    # 8. 落库：唯一冲突兜底（预查后的并发窗口）
    try:
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        raise CodeConflict(label, canonical, value) from None

    return {
        "record_id": str(record.id),
        "entity_type": entity_type,
        "field_name": canonical,
        "old_value": old_value,
        "new_value": value if not clearing else None,
        "updated_at": record.updated_at,
    }
