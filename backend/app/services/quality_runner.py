"""质量检测批次编排（SPEC §5 run 流程 + Phase 2 设计决策 6）。

介于 API 与纯函数引擎之间，只做四件事：
限额校验（5,000 实体上限）→ 规则装配（只走 quality_check_rules 行路径，
设计决策 1）→ 取存量记录 → 执行引擎 → 批次统计 + 失败明细**同一事务**落库。

审计由 API 层完成（沿用 data_standards 的两段提交模式）；
skipped / rule_errors 明细不进批次表，由 API 层写入审计 details（设计决策 3）。
"""
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app import crud, models
from app.services import entity_accessor, quality_engine


class QualityRunError(Exception):
    """检测无法执行（API 层映射为 400）。"""


class EntityLimitExceeded(QualityRunError):
    def __init__(self, count: int):
        self.count = count
        super().__init__(
            f"单次最多检测 {entity_accessor.MAX_ENTITIES} 实体，当前 {count} 条，"
            "请分批执行或指定 entity_ids"
        )


class NoExecutableRules(QualityRunError):
    def __init__(self, entity_type: str):
        super().__init__(f"实体类型 {entity_type} 没有可执行的检测规则，请先配置规则")


class NoMatchingEntities(QualityRunError):
    def __init__(self, entity_type: str):
        super().__init__(f"实体类型 {entity_type} 未匹配到任何存量记录")


def _norm_ids(entity_ids: Optional[Sequence[str]]) -> Optional[List[str]]:
    ids = [str(i) for i in entity_ids] if entity_ids else []
    return ids or None


def count_entities(
    db: Session,
    entity_type: str,
    entity_ids: Optional[Sequence[str]] = None,
) -> int:
    """实体计数（5,000 上限校验用；按 entity_ids 过滤时同样只数子集）。"""
    ids = _norm_ids(entity_ids)
    if entity_type == entity_accessor.MATERIAL:
        return crud.count_material_records(db, entity_ids=ids)
    if entity_type in entity_accessor.PARTNER_ENTITY_TYPES:
        return crud.count_partner_records(db, entity_type=entity_type, entity_ids=ids)
    raise ValueError(f"未知实体类型: {entity_type}")


def load_rule_rows(
    db: Session,
    entity_type: str,
    rule_ids: Optional[Sequence[str]] = None,
) -> List[models.QualityCheckRule]:
    """取规则行：rule_ids 为空 = 全部启用规则；恒过滤 entity_type。"""
    ids = _norm_ids(rule_ids)
    items, _total = crud.get_quality_check_rules(
        db, entity_type=entity_type, rule_ids=ids, skip=0, limit=500
    )
    return items


def _standards_map(
    db: Session,
    entity_type: str,
    rule_rows: List[models.QualityCheckRule],
) -> Dict[str, models.DataStandard]:
    """rule.standard_id → DataStandard 映射；list 之外逐条补查（防御）。"""
    accessor = entity_accessor.EntityFieldAccessor(db)
    standards_map = {s.id: s for s in accessor.list_standards(entity_type=entity_type)}
    for row in rule_rows:
        if row.standard_id and row.standard_id not in standards_map:
            standard = crud.get_data_standard(db, row.standard_id)
            if standard is not None:
                standards_map[standard.id] = standard
    return standards_map


def build_descriptors(
    rule_rows: List[models.QualityCheckRule],
    standards_map: Dict[str, models.DataStandard],
) -> List[quality_engine.RuleDescriptor]:
    """规则行 → 引擎描述符；不可执行（未启用/未知类型/无标准约束）返回 None 被滤除。"""
    descriptors: List[quality_engine.RuleDescriptor] = []
    for row in rule_rows:
        standard = standards_map.get(row.standard_id) if row.standard_id else None
        descriptor = quality_engine.check_from_rule_row(row, standard)
        if descriptor is not None:
            descriptors.append(descriptor)
    return descriptors


def run_batch(
    db: Session,
    entity_type: str,
    entity_ids: Optional[Sequence[str]] = None,
    rule_ids: Optional[Sequence[str]] = None,
    triggered_by: str = "system",
) -> Tuple[models.QualityCheckBatch, quality_engine.QualityRunResult]:
    """执行一次质量检测批次（SPEC §5.1 同步语义）。

    返回 (batch, result)：批次统计 + 失败明细已在**同一事务**提交；
    result 携带 skipped / rule_errors 明细供 API 层写审计。
    """
    ids = _norm_ids(entity_ids)

    # 1. 限额校验：5,000 上限、指定 ids 未命中
    total = count_entities(db, entity_type, ids)
    if total > entity_accessor.MAX_ENTITIES:
        raise EntityLimitExceeded(total)
    if ids and total == 0:
        raise NoMatchingEntities(entity_type)

    # 2. 规则装配：只走规则行路径（设计决策 1，保证 finding.rule_id 非空）
    rule_rows = load_rule_rows(db, entity_type, rule_ids)
    if not rule_rows:
        raise NoExecutableRules(entity_type)
    descriptors = build_descriptors(rule_rows, _standards_map(db, entity_type, rule_rows))
    if not descriptors:
        raise NoExecutableRules(entity_type)

    # 3. 取实体 + 执行（引擎纯函数，绝不抛异常打断整批）
    records = entity_accessor.EntityFieldAccessor(db).list_entities(entity_type, ids)
    result = quality_engine.run_quality_checks(entity_type, records, rules=descriptors)

    # 4. 批次统计 + 失败明细同一事务落库（硬性验收）
    now = models._now_utc()
    batch = models.QualityCheckBatch(
        entity_type=entity_type,
        total_entities=result.total_entities,
        total_checks=result.total_checks,
        passed=result.passed,
        failed=result.failed,
        skipped_checks=result.skipped_checks,
        rule_ids=[r.id for r in rule_rows],
        triggered_by=triggered_by,
        started_at=now,
        finished_at=now,
    )
    db.add(batch)
    db.flush()  # 取 batch.id 供结果行 FK

    for finding in result.findings:
        if not finding.rule_id:
            # 设计决策 1 保证不该发生；违反即回滚整批，不落半写数据
            db.rollback()
            raise RuntimeError("finding 缺少 rule_id，违反结果表 NOT NULL 契约")
        db.add(
            models.QualityCheckResult(
                rule_id=finding.rule_id,
                batch_id=batch.id,
                entity_id=finding.entity_id,
                entity_type=finding.entity_type or entity_type,
                field_name=finding.field_name,
                field_value=(finding.field_value or "")[:500],
                severity=finding.severity,
                message=finding.message,
                checked_at=now,
            )
        )
    db.commit()
    return batch, result
