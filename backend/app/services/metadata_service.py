"""元数据装配服务：实体总览 + 字段治理状态。"""
from typing import Dict, List, Sequence

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app import crud, models


def get_entity_overview(db: Session) -> List[Dict]:
    """返回每个实体的元数据字段 + governed_field_count/total_field_count 计数。"""
    entities = crud.get_metadata_entities(db)
    counts = {
        entity_type: (governed, total)
        for entity_type, governed, total in db.query(
            models.MetadataField.entity_type,
            func.sum(case((models.MetadataField.must_govern.is_(True), 1), else_=0)),
            func.count(),
        ).group_by(models.MetadataField.entity_type).all()
    }
    overview = []
    for entity in entities:
        governed, total = counts.get(entity.entity_type, (0, 0))
        overview.append({
            "id": entity.id,
            "entity_type": entity.entity_type,
            "display_name": entity.display_name,
            "business_definition": entity.business_definition,
            "data_owner": entity.data_owner,
            "dept": entity.dept,
            "tags": entity.tags,
            "sensitivity_level": entity.sensitivity_level,
            "governed_field_count": governed or 0,
            "total_field_count": total,
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
        })
    return overview


def enrich_field_governance(
    db: Session, fields: Sequence[models.MetadataField]
) -> Dict[str, dict]:
    """为字段登记册装配治理状态四元组（列表/写响应共用口径，列表端点一次调用）。

    返回 {field_id: {quality_rule_count, latest_batch_id, latest_batch_failed,
    latest_checked_at}}。规则数走 rule→standard→metadata_field_id 一次 JOIN 聚合；
    最新批次按本页出现的实体类型各取 1 次；失败数对最新批次 1 次 GROUP BY。
    """
    if not fields:
        return {}
    field_ids = [f.id for f in fields]

    # 治理规则数：经标准关联的质量规则数（无规则 = 未纳入规则治理）
    rule_counts = crud.count_rules_by_field_ids(db, field_ids)

    # 最新批次：本页 distinct 实体各取 1 次（登记册分页时逐页自洽）
    latest_by_type: Dict[str, models.QualityCheckBatch] = {}
    for etype in {f.entity_type for f in fields}:
        batch = crud.get_latest_quality_check_batch(db, etype)
        if batch is not None:
            latest_by_type[etype] = batch

    # 失败数：对最新批次按字段名 GROUP BY（映射键 = SAP field_name，与登记册一致）
    failed_by_field: Dict[str, int] = {}
    for batch in latest_by_type.values():
        failed_by_field.update(crud.count_failed_results_by_field(db, batch.id))

    return {
        f.id: {
            "quality_rule_count": rule_counts.get(f.id, 0),
            "latest_batch_id": (
                latest_by_type[f.entity_type].id if f.entity_type in latest_by_type else None
            ),
            "latest_batch_failed": (
                failed_by_field.get(f.field_name, 0)
                if f.entity_type in latest_by_type
                else 0
            ),
            "latest_checked_at": (
                latest_by_type[f.entity_type].started_at
                if f.entity_type in latest_by_type
                else None
            ),
        }
        for f in fields
    }
