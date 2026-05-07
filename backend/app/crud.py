"""CRUD operations for all entities."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, text

from app import models, schemas
from datetime import datetime, timezone


# ========== Classification ==========

def create_classification(db: Session, data: schemas.ClassificationCreate) -> models.MaterialClassification:
    db_item = models.MaterialClassification(**data.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def get_classification(db: Session, classification_id: str) -> Optional[models.MaterialClassification]:
    return db.query(models.MaterialClassification).filter(models.MaterialClassification.id == classification_id).first()


def get_classifications(db: Session, level: Optional[int] = None, parent_id: Optional[str] = None) -> List[models.MaterialClassification]:
    query = db.query(models.MaterialClassification).filter(models.MaterialClassification.is_active == True)
    if level:
        query = query.filter(models.MaterialClassification.level == level)
    if parent_id is not None:
        query = query.filter(models.MaterialClassification.parent_id == parent_id)
    return query.order_by(models.MaterialClassification.code).all()


def get_classification_tree(db: Session) -> List[models.MaterialClassification]:
    """Get all level 1 classifications with children."""
    return db.query(models.MaterialClassification).filter(
        models.MaterialClassification.level == 1,
        models.MaterialClassification.is_active == True
    ).order_by(models.MaterialClassification.code).all()


# ========== Attribute Template ==========

def create_attribute_template(db: Session, data: schemas.AttributeTemplateCreate) -> models.AttributeTemplate:
    db_item = models.AttributeTemplate(**data.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def get_attribute_templates(db: Session, classification_id: str) -> List[models.AttributeTemplate]:
    return db.query(models.AttributeTemplate).filter(
        models.AttributeTemplate.classification_id == classification_id
    ).order_by(models.AttributeTemplate.sort_order).all()


# ========== Application ==========

def generate_app_no(db: Session) -> str:
    """Generate application number: SQ-YYYY-NNNNN"""
    year = datetime.now().year
    prefix = f"SQ-{year}-"
    count = db.query(models.MaterialApplication).filter(
        models.MaterialApplication.app_no.like(f"{prefix}%")
    ).count()
    return f"{prefix}{count + 1:05d}"


def create_application(db: Session, data: schemas.ApplicationCreate, user_id: str, user_name: str) -> models.MaterialApplication:
    db_item = models.MaterialApplication(
        app_no=generate_app_no(db),
        created_by=user_id,
        created_by_name=user_name,
        **data.model_dump(exclude_unset=True)
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def get_application(db: Session, app_id: str) -> Optional[models.MaterialApplication]:
    return db.query(models.MaterialApplication).filter(models.MaterialApplication.id == app_id).first()


def get_applications(
    db: Session,
    status: Optional[str] = None,
    created_by: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[models.MaterialApplication]:
    query = db.query(models.MaterialApplication)
    if status:
        query = query.filter(models.MaterialApplication.status == status)
    if created_by:
        query = query.filter(models.MaterialApplication.created_by == created_by)
    return query.order_by(desc(models.MaterialApplication.created_at)).offset(skip).limit(limit).all()


def update_application(db: Session, app_id: str, data: dict) -> Optional[models.MaterialApplication]:
    db_item = get_application(db, app_id)
    if not db_item:
        return None
    for key, value in data.items():
        setattr(db_item, key, value)
    db_item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_item)
    return db_item


# ========== Code Rule ==========

def create_code_rule(db: Session, data: schemas.CodeRuleCreate) -> models.CodeRule:
    db_item = models.CodeRule(**data.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def get_code_rules(db: Session, classification_id: Optional[str] = None) -> List[models.CodeRule]:
    query = db.query(models.CodeRule).filter(models.CodeRule.is_active == True)
    if classification_id:
        query = query.filter(models.CodeRule.classification_id == classification_id)
    return query.all()


def get_code_rule(db: Session, rule_id: str) -> Optional[models.CodeRule]:
    return db.query(models.CodeRule).filter(models.CodeRule.id == rule_id).first()


def increment_seq(db: Session, rule_id: str) -> int:
    """Atomically increment and return the sequence number.
    
    Uses database-level UPDATE to avoid race conditions in concurrent requests.
    """
    # Atomic increment using raw SQL
    db.execute(
        text("UPDATE code_rules SET current_seq = current_seq + 1 WHERE id = :id"),
        {"id": rule_id}
    )
    db.commit()
    
    # Fetch the updated value
    result = db.execute(
        text("SELECT current_seq FROM code_rules WHERE id = :id"),
        {"id": rule_id}
    )
    row = result.fetchone()
    return row[0] if row else 0


# ========== Golden Record ==========

def create_golden_record(db: Session, data: schemas.GoldenRecordBase, application_id: str, user_id: str) -> models.GoldenRecord:
    db_item = models.GoldenRecord(
        application_id=application_id,
        created_by=user_id,
        **data.model_dump()
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def get_golden_record(db: Session, gr_id: str) -> Optional[models.GoldenRecord]:
    return db.query(models.GoldenRecord).filter(models.GoldenRecord.id == gr_id).first()


def get_golden_record_by_code(db: Session, code: str) -> Optional[models.GoldenRecord]:
    return db.query(models.GoldenRecord).filter(models.GoldenRecord.material_code == code).first()


def get_golden_records(db: Session, skip: int = 0, limit: int = 100) -> List[models.GoldenRecord]:
    return db.query(models.GoldenRecord).order_by(desc(models.GoldenRecord.created_at)).offset(skip).limit(limit).all()


def update_golden_record(db: Session, gr_id: str, data: dict) -> Optional[models.GoldenRecord]:
    db_item = get_golden_record(db, gr_id)
    if not db_item:
        return None
    for key, value in data.items():
        setattr(db_item, key, value)
    db_item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_item)
    return db_item


# ========== Audit Log ==========

def create_audit_log(db: Session, **kwargs) -> models.AuditLog:
    db_item = models.AuditLog(**kwargs)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def get_audit_logs(db: Session, application_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[models.AuditLog]:
    query = db.query(models.AuditLog)
    if application_id:
        query = query.filter(models.AuditLog.application_id == application_id)
    return query.order_by(desc(models.AuditLog.executed_at)).offset(skip).limit(limit).all()


def get_application_audit_logs(db: Session, application_id: str) -> List[models.AuditLog]:
    return db.query(models.AuditLog).filter(
        models.AuditLog.application_id == application_id
    ).order_by(models.AuditLog.executed_at).all()


# ========== External System Log ==========

def create_external_log(db: Session, **kwargs) -> models.ExternalSystemLog:
    db_item = models.ExternalSystemLog(**kwargs)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


# ========== Dashboard Stats ==========

def get_dashboard_stats(db: Session) -> dict:
    return {
        "total_applications": db.query(models.MaterialApplication).count(),
        "pending_admin": db.query(models.MaterialApplication).filter(
            models.MaterialApplication.status == models.ApplicationStatus.PENDING_ADMIN
        ).count(),
        "pending_dept": db.query(models.MaterialApplication).filter(
            models.MaterialApplication.status == models.ApplicationStatus.PENDING_DEPT
        ).count(),
        "approved": db.query(models.MaterialApplication).filter(
            models.MaterialApplication.status == models.ApplicationStatus.APPROVED
        ).count(),
        "rejected": db.query(models.MaterialApplication).filter(
            models.MaterialApplication.status == models.ApplicationStatus.REJECTED
        ).count(),
        "published": db.query(models.MaterialApplication).filter(
            models.MaterialApplication.status == models.ApplicationStatus.PUBLISHED
        ).count(),
        "total_golden_records": db.query(models.GoldenRecord).count(),
        "total_classifications": db.query(models.MaterialClassification).filter(
            models.MaterialClassification.is_active == True
        ).count(),
    }
