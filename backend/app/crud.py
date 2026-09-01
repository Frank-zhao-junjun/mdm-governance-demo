"""CRUD operations for the stock-data governance service."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app import models


# ========== Data Standards ==========

def get_data_standards(
    db: Session,
    entity_type: Optional[str] = None,
    sap_table: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[models.DataStandard], int]:
    query = db.query(models.DataStandard)
    if entity_type:
        query = query.filter(models.DataStandard.entity_type == entity_type)
    if sap_table:
        query = query.filter(models.DataStandard.sap_table == sap_table)
    total = query.count()
    items = (
        query.order_by(
            models.DataStandard.entity_type,
            models.DataStandard.sap_table,
            models.DataStandard.field_name,
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def get_data_standard(db: Session, standard_id: str) -> Optional[models.DataStandard]:
    return db.query(models.DataStandard).filter(models.DataStandard.id == standard_id).first()


def find_data_standard_conflict(db: Session, entity_type: str, sap_table: Optional[str], field_name: str) -> Optional[models.DataStandard]:
    query = db.query(models.DataStandard).filter(
        models.DataStandard.entity_type == entity_type,
        models.DataStandard.field_name == field_name,
    )
    if sap_table:
        query = query.filter(models.DataStandard.sap_table == sap_table)
    else:
        query = query.filter(models.DataStandard.sap_table.is_(None))
    return query.first()


def create_data_standard(db: Session, data: dict) -> models.DataStandard:
    item = models.DataStandard(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_data_standard(db: Session, standard: models.DataStandard, data: dict) -> models.DataStandard:
    for key, value in data.items():
        setattr(standard, key, value)
    db.commit()
    db.refresh(standard)
    return standard


def count_rules_referencing_standard(db: Session, standard_id: str) -> int:
    return (
        db.query(models.QualityCheckRule)
        .filter(models.QualityCheckRule.standard_id == standard_id)
        .count()
    )


def delete_data_standard(db: Session, standard: models.DataStandard) -> None:
    db.delete(standard)
    db.commit()


# ========== Quality Checks ==========

def get_quality_check_rules(
    db: Session,
    entity_type: Optional[str] = None,
    rule_ids: Optional[List[str]] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[models.QualityCheckRule], int]:
    """List rules. rule_ids 为空 = 全部启用规则；指定 ids 不过滤 is_active（未启用由引擎记为不可执行）。"""
    query = db.query(models.QualityCheckRule)
    if entity_type:
        query = query.filter(models.QualityCheckRule.entity_type == entity_type)
    if rule_ids:
        query = query.filter(models.QualityCheckRule.id.in_(rule_ids))
    else:
        query = query.filter(models.QualityCheckRule.is_active.is_(True))
    total = query.count()
    items = (
        query.order_by(
            models.QualityCheckRule.entity_type,
            models.QualityCheckRule.field_name,
            models.QualityCheckRule.rule_type,
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def get_quality_check_rules_by_ids(db: Session, rule_ids: List[str]) -> List[models.QualityCheckRule]:
    if not rule_ids:
        return []
    return (
        db.query(models.QualityCheckRule)
        .filter(models.QualityCheckRule.id.in_(rule_ids))
        .all()
    )


def count_material_records(db: Session, entity_ids: Optional[List[str]] = None) -> int:
    query = db.query(models.MaterialRecord)
    if entity_ids:
        query = query.filter(models.MaterialRecord.id.in_(entity_ids))
    return query.count()


def count_partner_records(db: Session, entity_type: str, entity_ids: Optional[List[str]] = None) -> int:
    query = db.query(models.PartnerRecord).filter(
        models.PartnerRecord.entity_type == entity_type
    )
    if entity_ids:
        query = query.filter(models.PartnerRecord.id.in_(entity_ids))
    return query.count()


def get_quality_check_results(
    db: Session,
    entity_type: str,
    entity_id: Optional[str] = None,
    severity: Optional[str] = None,
    batch_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[models.QualityCheckResult], int]:
    query = db.query(models.QualityCheckResult).filter(
        models.QualityCheckResult.entity_type == entity_type
    )
    if entity_id:
        query = query.filter(models.QualityCheckResult.entity_id == entity_id)
    if severity:
        query = query.filter(models.QualityCheckResult.severity == severity)
    if batch_id:
        query = query.filter(models.QualityCheckResult.batch_id == batch_id)
    total = query.count()
    items = (
        query.order_by(
            models.QualityCheckResult.checked_at.desc(),
            models.QualityCheckResult.id,
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def get_quality_check_batches(
    db: Session,
    entity_type: str,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[models.QualityCheckBatch], int]:
    query = db.query(models.QualityCheckBatch).filter(
        models.QualityCheckBatch.entity_type == entity_type
    )
    total = query.count()
    items = (
        query.order_by(
            models.QualityCheckBatch.started_at.desc(),
            models.QualityCheckBatch.id,
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def get_quality_check_batch(db: Session, batch_id: str) -> Optional[models.QualityCheckBatch]:
    return (
        db.query(models.QualityCheckBatch)
        .filter(models.QualityCheckBatch.id == batch_id)
        .first()
    )


def get_latest_quality_check_batch(db: Session, entity_type: str) -> Optional[models.QualityCheckBatch]:
    return (
        db.query(models.QualityCheckBatch)
        .filter(models.QualityCheckBatch.entity_type == entity_type)
        .order_by(
            models.QualityCheckBatch.started_at.desc(),
            models.QualityCheckBatch.id.desc(),
        )
        .first()
    )


# ========== Stock Records ==========

def get_material_records(db: Session, entity_ids: Optional[List[str]] = None, limit: int = 10_000) -> List[models.MaterialRecord]:
    query = db.query(models.MaterialRecord)
    if entity_ids:
        query = query.filter(models.MaterialRecord.id.in_(entity_ids))
    return query.limit(limit).all()


def get_partner_records(db: Session, entity_type: Optional[str] = None, entity_ids: Optional[List[str]] = None, limit: int = 10_000) -> List[models.PartnerRecord]:
    query = db.query(models.PartnerRecord)
    if entity_type:
        query = query.filter(models.PartnerRecord.entity_type == entity_type)
    if entity_ids:
        query = query.filter(models.PartnerRecord.id.in_(entity_ids))
    return query.limit(limit).all()


# ========== Audit Logs ==========

def create_audit_log(db: Session, **kwargs) -> models.AuditLog:
    db_item = models.AuditLog(**kwargs)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def get_audit_logs(db: Session, skip: int = 0, limit: int = 100) -> List[models.AuditLog]:
    return (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.executed_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
