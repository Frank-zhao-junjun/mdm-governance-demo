"""字段访问层 / Entity field accessor（SPEC §4）。

检测引擎不直接查各实体表，统一走本模块，屏蔽三类实体（material / supplier /
customer）的存量存储差异：身份字段（编码、名称）冗余为表列，其余字段落在
`attributes` JSON，键名与数据标准 `field_name` 一致。

两条必须守住的语义（SPEC §4.1、§5 验收"无数据源字段跳过且有记录"）：

1. **"有数据源但本行未填" ≠ "本系统没有该字段的数据源"**。
   前者 `key_present=False` 且 `skipped=False`，由 null 规则判为完整性问题；
   后者（如 MARC.WERKS / MARD.LGORT / MAKT.SPRAS）必须返回 `skipped=True` 并
   带上原因，**绝不能**当成空值参与校验——否则每轮检测都会造出一批"必填字段
   为空"的假告警。
2. 本模块是"字段 → 数据源"的唯一裁决点：规则引擎与 API 层都通过这里取值，
   新增实体或新增冗余列只改 `MATERIAL_FIELD_COLUMNS` / `PARTNER_FIELD_COLUMNS`
   / `NO_SOURCE_FIELDS` 三张表。

映射优先级：列映射（§4.1、§10.1/§10.2 中标注的冗余列）**优先于** `attributes`。
`material_name` / `partner_name` 等冗余列是 SPEC 声明的数据源，attributes 里若
出现同名键也不改变数据源归属（避免冗余列与 JSON 双写不一致时结果不可预期）。

本模块纯函数部分（`describe_source` / `resolve`）不碰数据库；
`EntityFieldAccessor` 只额外负责取实体，不缓存、不写库。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Optional, Sequence

MATERIAL = "material"
SUPPLIER = "supplier"
CUSTOMER = "customer"

PARTNER_ENTITY_TYPES = frozenset({SUPPLIER, CUSTOMER})
KNOWN_ENTITY_TYPES = frozenset({MATERIAL}) | PARTNER_ENTITY_TYPES

#: 单次检测/列举的实体上限（SPEC §5 同步执行：单次限 5000，超出返回 400 提示分批）。
#: 存量总量不受此限制——10,000 条种子数据仍合法，只是必须分批扫描。
MAX_ENTITIES = 5_000

ATTRIBUTES = "attributes"

#: 物料身份字段 → material_records 冗余列（SPEC §4.1、§10.1）
MATERIAL_FIELD_COLUMNS = {
    "MATNR": "material_code",
    "MAKTX": "material_name",
}

#: BP 身份字段 → partner_records 冗余列（SPEC §4.2、§10.2）
#: LIFNR（供应商编号）/ KUNNR（客户编号）/ PARTNER（BP 编号）都是 partner_code
PARTNER_FIELD_COLUMNS = {
    "LIFNR": "partner_code",
    "KUNNR": "partner_code",
    "PARTNER": "partner_code",
    "NAME1": "partner_name",
}

#: 标准可定义、但本系统没有存量数据源的字段（SPEC §4.1、§10.1）：
#: 工厂/采购/库存/MRP 视图与语言维度不进入 material_records，检测时跳过并记录。
NO_SOURCE_FIELDS: dict[str, frozenset[str]] = {
    MATERIAL: frozenset({"WERKS", "EKGRP", "DISMM", "LGORT", "SPRAS"}),
    SUPPLIER: frozenset(),
    CUSTOMER: frozenset(),
}

UNKNOWN_ENTITY_REASON = "本系统未定义该实体类型的存量存储，无数据源"


def _reason_for(entity_type: str, field_name: str) -> str:
    return (
        f"字段 {field_name} 在 {entity_type} 存量数据中无数据源"
        "（SAP 视图字段未进入本系统存储），已跳过检测"
    )


# ========== 值语义 ==========

def is_blank(value: Any) -> bool:
    """空值判定：None 与纯空白字符串视为空；0 / False 是合法值，不视为空。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def display_value(value: Any, limit: int = 500) -> str:
    """把任意取值渲染成结果表可存的字符串（SPEC §2.6 field_value ≤ 500）。"""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    if len(text) > limit:
        return text[:limit]
    return text


# ========== 结果对象 ==========

@dataclass(frozen=True)
class FieldSource:
    """某个（entity_type, field_name）的数据源声明，与具体某一行数据无关。"""

    entity_type: str
    field_name: str
    kind: str  # 'column' | 'attributes' | 'none'
    column: Optional[str] = None
    reason: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.kind != "none"


@dataclass(frozen=True)
class AccessResult:
    """一条记录上一个字段的取值结果。

    三个正交状态：
    - `skipped=True`：本系统没有该字段的数据源（不校验，只记录）
    - `key_present=False, skipped=False`：有数据源但本行未填 → null 规则可判失败
    - `key_present=True`：取到值（`is_blank(value)` 仍可能为真，如空串）
    """

    field_name: str
    value: Any = None
    source: Optional[FieldSource] = None
    key_present: bool = False

    @property
    def skipped(self) -> bool:
        return self.source is None or self.source.kind == "none"

    @property
    def reason(self) -> Optional[str]:
        if not self.skipped:
            return None
        return self.source.reason if self.source else UNKNOWN_ENTITY_REASON

    @property
    def is_blank(self) -> bool:
        return is_blank(self.value)

    @property
    def source_kind(self) -> Optional[str]:
        return None if self.source is None else self.source.kind


# ========== 纯函数 API ==========

def _columns_for(entity_type: str) -> Optional[dict[str, str]]:
    if entity_type == MATERIAL:
        return MATERIAL_FIELD_COLUMNS
    if entity_type in PARTNER_ENTITY_TYPES:
        return PARTNER_FIELD_COLUMNS
    return None


def describe_source(entity_type: Optional[str], field_name: Optional[str]) -> FieldSource:
    """声明式回答："这个实体类型的这个字段，数据源是什么？"""
    field = (field_name or "").strip()
    etype = entity_type or ""
    columns = _columns_for(etype)
    if columns is None:
        return FieldSource(etype, field, "none", reason=UNKNOWN_ENTITY_REASON)
    if not field:
        return FieldSource(etype, field, "none", reason="标准未定义 field_name，无数据源")
    # SAP 字段名按惯例大写，匹配一律大小写不敏感（结果仍回显标准里的原值）
    key = field.upper()
    column = columns.get(key)
    if column:
        return FieldSource(etype, field, "column", column=column)
    if key in NO_SOURCE_FIELDS.get(etype, frozenset()):
        return FieldSource(etype, field, "none", reason=_reason_for(etype, field))
    return FieldSource(etype, field, "attributes")


def supports_field(entity_type: Optional[str], field_name: Optional[str]) -> bool:
    """该字段是否有数据源（False 表示检测必须跳过并记录）。"""
    return describe_source(entity_type, field_name).available


def read_value(
    record: Any,
    field_name: str,
    entity_type: Optional[str] = None,
    source: Optional[FieldSource] = None,
) -> AccessResult:
    """从一条存量记录中取出标准字段 `field_name` 的值。

    `entity_type` 省略时从记录自身推断（MaterialRecord → material，
    PartnerRecord → 其 `entity_type` 列）。`source` 可由调用方预先用
    `describe_source` 算好后传入，避免批量检测时逐行重复推导。
    """
    field = (field_name or "").strip()
    etype = entity_type or entity_type_of(record) or ""
    src = source if source is not None else describe_source(etype, field)
    if not src.available:
        return AccessResult(field, None, src, False)

    if src.kind == "column":
        value = getattr(record, src.column or "", None)
        return AccessResult(field, value, src, value is not None)

    attributes = getattr(record, ATTRIBUTES, None)
    if not isinstance(attributes, dict):
        attributes = {}
    if field in attributes:
        return AccessResult(field, attributes[field], src, True)
    # attributes 是数据源，但本行没有这个键：属于"未填"，不是"无数据源"
    return AccessResult(field, None, src, False)


#: SPEC §4 语义的别名：`resolve(entity_type, record, field_name)`
def resolve(entity_type: Optional[str], record: Any, field_name: str) -> AccessResult:
    return read_value(record, field_name, entity_type)


def entity_type_of(record: Any) -> Optional[str]:
    """从记录对象反推实体类型（PartnerRecord 自带 entity_type 列）。"""
    if hasattr(record, "material_code"):
        return MATERIAL
    partner_type = getattr(record, "entity_type", None)
    if partner_type in PARTNER_ENTITY_TYPES:
        return str(partner_type)
    if hasattr(record, "partner_code"):
        return SUPPLIER
    return None


def record_id(record: Any) -> str:
    return str(getattr(record, "id", "") or "")


def record_label(record: Any, entity_type: Optional[str] = None) -> str:
    """列表/结果展示用的实体标识：编码优先，取不到时退回主键。"""
    etype = entity_type or entity_type_of(record)
    if etype == MATERIAL:
        code = getattr(record, MATERIAL_FIELD_COLUMNS["MATNR"], None)
    else:
        code = getattr(record, PARTNER_FIELD_COLUMNS["PARTNER"], None)
    if code:
        return str(code)
    return record_id(record)


# ========== 数据库装配层（仅取数，不写库） ==========

class EntityFieldAccessor:
    """SPEC §4 的访问器实现：统一取实体清单与字段值。

    只读：不 add / 不 commit / 不 refresh 实体数据（标准由数据管理员通过
    `crud` 维护，检测结果由调用方持久化）。
    """

    def __init__(self, db: Any):
        self.db = db

    # -- 标准 --

    def list_standards(
        self,
        entity_type: Optional[str] = None,
        sap_table: Optional[str] = None,
        limit: int = 500,
    ) -> Sequence[Any]:
        """取数据标准（委托 `crud.get_data_standards`），供规则引擎构造规则。"""
        from app import crud

        capped = max(1, min(int(limit or 500), 500))
        items, _total = crud.get_data_standards(
            self.db, entity_type=entity_type, sap_table=sap_table, skip=0, limit=capped
        )
        return items

    # -- 实体 --

    def list_entities(
        self,
        entity_type: str,
        entity_ids: Optional[Sequence[str]] = None,
        limit: int = MAX_ENTITIES,
    ) -> list:
        """按实体类型取存量记录（可按 entity_ids 过滤），上限 MAX_ENTITIES。"""
        from app import crud

        ids = [str(i) for i in entity_ids] if entity_ids else None
        capped = max(1, min(int(limit or MAX_ENTITIES), MAX_ENTITIES))
        if entity_type == MATERIAL:
            return crud.get_material_records(self.db, entity_ids=ids, limit=capped)
        if entity_type in PARTNER_ENTITY_TYPES:
            return crud.get_partner_records(
                self.db, entity_type=entity_type, entity_ids=ids, limit=capped
            )
        raise ValueError(UNKNOWN_ENTITY_REASON)

    def iter_entities(
        self,
        entity_type: str,
        entity_ids: Optional[Sequence[str]] = None,
        limit: int = MAX_ENTITIES,
    ) -> Iterator[Any]:
        return iter(self.list_entities(entity_type, entity_ids, limit))

    def get_entity(self, entity_type: str, entity_id: str) -> Optional[Any]:
        from app import models

        if entity_type == MATERIAL:
            return self.db.query(models.MaterialRecord).filter(
                models.MaterialRecord.id == entity_id
            ).first()
        if entity_type in PARTNER_ENTITY_TYPES:
            return self.db.query(models.PartnerRecord).filter(
                models.PartnerRecord.entity_type == entity_type,
                models.PartnerRecord.id == entity_id,
            ).first()
        return None

    # -- 字段 --

    def supports_field(self, entity_type: str, field_name: str) -> bool:
        return supports_field(entity_type, field_name)

    def describe_source(self, entity_type: str, field_name: str) -> FieldSource:
        return describe_source(entity_type, field_name)

    def get_value(
        self,
        entity_type: str,
        record: Any,
        field_name: str,
        source: Optional[FieldSource] = None,
    ) -> AccessResult:
        """已加载记录上的取值（批量检测用这条路径，纯函数，不查库）。"""
        return read_value(record, field_name, entity_type, source)

    def get_field(
        self,
        entity_type: str,
        entity_id: str,
        field_name: str,
    ) -> Optional[Any]:
        """SPEC §4 单点取值：无数据源或记录不存在时返回 None。

        需要区分"无数据源"与"值为空"时请用 `get_value()`。
        """
        record = self.get_entity(entity_type, entity_id)
        if record is None:
            return None
        return read_value(record, field_name, entity_type).value
