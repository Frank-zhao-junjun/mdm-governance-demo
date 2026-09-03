"""元数据实体总览装配服务：为实体补充字段治理计数。"""
from typing import Dict, List

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
