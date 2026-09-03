"""CRUD operations for the stock-data governance service."""
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, or_
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

def get_material_records(db: Session, entity_ids: Optional[List[str]] = None, limit: int = 5_000) -> List[models.MaterialRecord]:
    query = db.query(models.MaterialRecord)
    if entity_ids:
        query = query.filter(models.MaterialRecord.id.in_(entity_ids))
    return query.limit(limit).all()


def get_partner_records(db: Session, entity_type: Optional[str] = None, entity_ids: Optional[List[str]] = None, limit: int = 5_000) -> List[models.PartnerRecord]:
    query = db.query(models.PartnerRecord)
    if entity_type:
        query = query.filter(models.PartnerRecord.entity_type == entity_type)
    if entity_ids:
        query = query.filter(models.PartnerRecord.id.in_(entity_ids))
    return query.limit(limit).all()


# ========== Suspected Errors (SPEC §3.3) ==========

def get_suspected_error(db: Session, error_id: str) -> Optional[models.SuspectedError]:
    return (
        db.query(models.SuspectedError)
        .filter(models.SuspectedError.id == error_id)
        .first()
    )


def list_suspected_errors(
    db: Session,
    entity_type: str,
    error_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[models.SuspectedError], int]:
    query = db.query(models.SuspectedError).filter(
        models.SuspectedError.entity_type == entity_type
    )
    if error_type:
        query = query.filter(models.SuspectedError.error_type == error_type)
    if status:
        query = query.filter(models.SuspectedError.status == status)
    total = query.count()
    items = (
        query.order_by(models.SuspectedError.detected_at.desc(), models.SuspectedError.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def get_suspected_errors_by_entity_type(db: Session, entity_type: str) -> List[models.SuspectedError]:
    """一次预载该实体类型全部疑似错误行（§2.7 重检去重三键映射用）。"""
    return (
        db.query(models.SuspectedError)
        .filter(models.SuspectedError.entity_type == entity_type)
        .all()
    )


def existing_entity_ids(db: Session, entity_type: str, entity_ids: List[str]) -> set:
    """传入 id 集合中仍存在且 active 的记录 id（自动关闭判定用，一次查询）。"""
    ids = [str(i) for i in entity_ids if str(i)]
    if not ids:
        return set()
    if entity_type == "material":
        rows = (
            db.query(models.MaterialRecord.id)
            .filter(
                models.MaterialRecord.id.in_(ids),
                models.MaterialRecord.status == "active",
            )
            .all()
        )
    elif entity_type in ("supplier", "customer"):
        rows = (
            db.query(models.PartnerRecord.id)
            .filter(
                models.PartnerRecord.entity_type == entity_type,
                models.PartnerRecord.id.in_(ids),
                models.PartnerRecord.status == "active",
            )
            .all()
        )
    else:
        return set()
    return {row[0] for row in rows}


# ========== Data Import (SPEC Phase 4.1) ==========

def map_partner_records_by_code(
    db: Session, entity_type: str, codes: List[str]
) -> Dict[str, models.PartnerRecord]:
    """按 partner_code 批量取存量记录，供导入 upsert 一次查询定位（键为 partner_code）。"""
    unique_codes = {str(c) for c in codes if str(c)}
    if not unique_codes:
        return {}
    rows = (
        db.query(models.PartnerRecord)
        .filter(
            models.PartnerRecord.entity_type == entity_type,
            models.PartnerRecord.partner_code.in_(unique_codes),
        )
        .all()
    )
    return {row.partner_code: row for row in rows}


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


# ========== Metadata ==========

def get_metadata_fields(
    db: Session,
    entity_type: Optional[str] = None,
    view_section: Optional[str] = None,
    must_govern: Optional[bool] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[models.MetadataField], int]:
    query = db.query(models.MetadataField)
    if entity_type:
        query = query.filter(models.MetadataField.entity_type == entity_type)
    if view_section:
        query = query.filter(models.MetadataField.view_section == view_section)
    if must_govern is not None:
        query = query.filter(models.MetadataField.must_govern.is_(must_govern))
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(
            models.MetadataField.field_name.ilike(like),
            models.MetadataField.field_label.ilike(like),
        ))
    total = query.count()
    items = (
        query.order_by(
            models.MetadataField.entity_type,
            models.MetadataField.sap_table,
            models.MetadataField.field_name,
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total


def get_metadata_field(db: Session, field_id: str) -> Optional[models.MetadataField]:
    return db.query(models.MetadataField).filter(models.MetadataField.id == field_id).first()


def get_metadata_fields_by_ids(db: Session, field_ids: List[str]) -> List[models.MetadataField]:
    """按 id 集合批量取元数据字段（数据标准响应装配用，一次查询避免 N+1）。"""
    if not field_ids:
        return []
    return (
        db.query(models.MetadataField)
        .filter(models.MetadataField.id.in_(field_ids))
        .all()
    )


def find_metadata_field_conflict(db: Session, entity_type: str, sap_table: Optional[str], field_name: str) -> Optional[models.MetadataField]:
    query = db.query(models.MetadataField).filter(
        models.MetadataField.entity_type == entity_type,
        models.MetadataField.field_name == field_name,
    )
    if sap_table:
        query = query.filter(models.MetadataField.sap_table == sap_table)
    else:
        query = query.filter(models.MetadataField.sap_table.is_(None))
    return query.first()


def create_metadata_field(db: Session, data: dict) -> models.MetadataField:
    item = models.MetadataField(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_metadata_field(db: Session, field: models.MetadataField, data: dict) -> models.MetadataField:
    for key, value in data.items():
        setattr(field, key, value)
    db.commit()
    db.refresh(field)
    return field


def get_metadata_entities(db: Session) -> List[models.MetadataEntity]:
    return (
        db.query(models.MetadataEntity)
        .order_by(models.MetadataEntity.entity_type)
        .all()
    )


def get_metadata_entity(db: Session, entity_type: str) -> Optional[models.MetadataEntity]:
    return (
        db.query(models.MetadataEntity)
        .filter(models.MetadataEntity.entity_type == entity_type)
        .first()
    )


def update_metadata_entity(db: Session, entity: models.MetadataEntity, data: dict) -> models.MetadataEntity:
    for key, value in data.items():
        setattr(entity, key, value)
    db.commit()
    db.refresh(entity)
    return entity


def get_glossary_terms(db: Session) -> List[models.GlossaryTerm]:
    return (
        db.query(models.GlossaryTerm)
        .order_by(models.GlossaryTerm.term)
        .all()
    )


def create_glossary_term(db: Session, data: dict) -> models.GlossaryTerm:
    item = models.GlossaryTerm(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_glossary_term(db: Session, term: models.GlossaryTerm, data: dict) -> models.GlossaryTerm:
    for key, value in data.items():
        setattr(term, key, value)
    db.commit()
    db.refresh(term)
    return term


def count_standards_by_field_ids(db: Session, field_ids: List[str]) -> Dict[str, int]:
    """按元数据字段 id 批量统计引用它的数据标准数（一次 GROUP BY，避免列表端点 N+1）。"""
    if not field_ids:
        return {}
    rows = (
        db.query(models.DataStandard.metadata_field_id, func.count())
        .filter(models.DataStandard.metadata_field_id.in_(field_ids))
        .group_by(models.DataStandard.metadata_field_id)
        .all()
    )
    return {row[0]: row[1] for row in rows}


def get_glossary_terms_by_ids(db: Session, term_ids: List[str]) -> Dict[str, models.GlossaryTerm]:
    """按 id 集合批量取业务术语并建 id → 术语映射（字段登记册装配用，一次 IN 查询）。"""
    if not term_ids:
        return {}
    rows = (
        db.query(models.GlossaryTerm)
        .filter(models.GlossaryTerm.id.in_(term_ids))
        .all()
    )
    return {row.id: row for row in rows}


def count_fields_by_glossary_term_ids(db: Session, term_ids: List[str]) -> Dict[str, int]:
    """按术语 id 批量统计关联的元数据字段数（glossary 列表与写响应共用口径，一次 GROUP BY）。"""
    if not term_ids:
        return {}
    rows = (
        db.query(models.MetadataField.glossary_term_id, func.count())
        .filter(models.MetadataField.glossary_term_id.in_(term_ids))
        .group_by(models.MetadataField.glossary_term_id)
        .all()
    )
    return {row[0]: row[1] for row in rows}
