"""CRUD operations for all entities."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, text, update

from app import models, schemas
from datetime import datetime, timezone, timedelta


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


def claim_application_for_publish(db: Session, app_id: str) -> bool:
    """Atomically reserve an approved application for one publish attempt."""
    result = db.execute(
        update(models.MaterialApplication)
        .where(
            models.MaterialApplication.id == app_id,
            models.MaterialApplication.status == models.ApplicationStatus.APPROVED,
            models.MaterialApplication.published_at.is_(None),
        )
        .values(status=models.ApplicationStatus.PUBLISHING)
    )
    db.commit()
    return result.rowcount == 1


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


def get_governance_rules(db: Session) -> List[models.GovernanceRule]:
    return db.query(models.GovernanceRule).filter(
        models.GovernanceRule.is_active == True
    ).all()


def get_governance_rule(db: Session, rule_key: str) -> Optional[models.GovernanceRule]:
    return db.query(models.GovernanceRule).filter(
        models.GovernanceRule.rule_key == rule_key
    ).first()


def get_governance_rule_map(db: Session) -> dict[str, models.GovernanceRule]:
    return {rule.rule_key: rule for rule in get_governance_rules(db)}


def increment_seq(db: Session, rule_id: str) -> int:
    """Atomically increment and return the sequence number.

    Single-statement UPDATE...RETURNING: the increment and the read happen in one
    atomic step, so concurrent callers can never observe the same value.
    """
    result = db.execute(
        text("UPDATE code_rules SET current_seq = current_seq + 1 WHERE id = :id RETURNING current_seq"),
        {"id": rule_id}
    )
    row = result.fetchone()
    db.commit()
    return row[0] if row else 0


# ========== 金标数据 ==========

def create_golden_record(db: Session, data: schemas.GoldenRecordBase, application_id: str, user_id: str) -> models.GoldenRecord:
    db_item = models.GoldenRecord(
        application_id=application_id,
        created_by=user_id,
        **data.model_dump()
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    db.add(models.GoldenRecordVersion(
        golden_record_id=db_item.id,
        version_number=1,
        material_code=db_item.material_code,
        material_name=db_item.material_name,
        material_desc=db_item.material_desc,
        classification_id=db_item.classification_id,
        attribute_values=db_item.attribute_values,
        material_type=db_item.material_type,
        status=models.GoldenRecordVersionStatus.PUBLISHED,
        change_type="initial",
        change_reason="初始发布",
        created_by=user_id,
        published_at=datetime.now(timezone.utc),
    ))
    db.commit()
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


def get_golden_record_versions(db: Session, gr_id: str) -> List[models.GoldenRecordVersion]:
    return db.query(models.GoldenRecordVersion).filter(
        models.GoldenRecordVersion.golden_record_id == gr_id
    ).order_by(models.GoldenRecordVersion.version_number).all()


def create_golden_record_revision(
    db: Session,
    gr_id: str,
    data: schemas.GoldenRecordVersionCreate,
    user_id: str,
) -> Optional[models.GoldenRecordVersion]:
    record = get_golden_record(db, gr_id)
    if not record or record.status != models.GoldenRecordStatus.ACTIVE:
        return None
    parent = db.query(models.GoldenRecordVersion).filter(
        models.GoldenRecordVersion.golden_record_id == gr_id,
    ).order_by(models.GoldenRecordVersion.version_number.desc()).first()
    if not parent:
        return None

    values = data.model_dump(exclude_none=True)
    version = models.GoldenRecordVersion(
        golden_record_id=gr_id,
        parent_version_id=parent.id,
        version_number=parent.version_number + 1,
        material_code=parent.material_code,
        material_name=values.get("material_name", parent.material_name),
        material_desc=values.get("material_desc", parent.material_desc),
        classification_id=values.get("classification_id", parent.classification_id),
        attribute_values=values.get("attribute_values", parent.attribute_values),
        material_type=values.get("material_type", parent.material_type),
        status=models.GoldenRecordVersionStatus.PENDING_APPROVAL,
        change_type="revision",
        change_reason=data.change_reason,
        created_by=user_id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def approve_golden_record_version(
    db: Session, version_id: str, user_id: str
) -> Optional[models.GoldenRecordVersion]:
    version = db.query(models.GoldenRecordVersion).filter(
        models.GoldenRecordVersion.id == version_id,
        models.GoldenRecordVersion.status == models.GoldenRecordVersionStatus.PENDING_APPROVAL,
        models.GoldenRecordVersion.change_type == "revision",
    ).first()
    if not version:
        return None
    version.status = models.GoldenRecordVersionStatus.APPROVED
    version.approved_by = user_id
    version.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(version)
    return version


def publish_golden_record_version(
    db: Session, version_id: str, user_id: str
) -> Optional[models.GoldenRecordVersion]:
    version = db.query(models.GoldenRecordVersion).filter(
        models.GoldenRecordVersion.id == version_id,
        models.GoldenRecordVersion.status == models.GoldenRecordVersionStatus.APPROVED,
        models.GoldenRecordVersion.change_type == "revision",
    ).first()
    if not version:
        return None
    record = get_golden_record(db, version.golden_record_id)
    if not record or record.status != models.GoldenRecordStatus.ACTIVE:
        return None
    record.material_name = version.material_name
    record.material_desc = version.material_desc
    record.classification_id = version.classification_id
    record.attribute_values = version.attribute_values
    record.material_type = version.material_type
    record.version = version.version_number
    record.revision = version.version_number
    record.updated_by = user_id
    version.status = models.GoldenRecordVersionStatus.PUBLISHED
    version.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(version)
    return version


def create_golden_record_invalidation(
    db: Session, gr_id: str, reason: str, user_id: str
) -> Optional[models.GoldenRecordVersion]:
    record = get_golden_record(db, gr_id)
    if not record or record.status != models.GoldenRecordStatus.ACTIVE:
        return None
    parent = db.query(models.GoldenRecordVersion).filter(
        models.GoldenRecordVersion.golden_record_id == gr_id,
    ).order_by(models.GoldenRecordVersion.version_number.desc()).first()
    if not parent:
        return None
    version = models.GoldenRecordVersion(
        golden_record_id=gr_id,
        parent_version_id=parent.id,
        version_number=parent.version_number + 1,
        material_code=parent.material_code,
        material_name=parent.material_name,
        material_desc=parent.material_desc,
        classification_id=parent.classification_id,
        attribute_values=parent.attribute_values,
        material_type=parent.material_type,
        status=models.GoldenRecordVersionStatus.PENDING_APPROVAL,
        change_type="invalidation",
        change_reason=reason,
        created_by=user_id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def approve_golden_record_invalidation(
    db: Session, version_id: str, user_id: str
) -> Optional[models.GoldenRecordVersion]:
    version = db.query(models.GoldenRecordVersion).filter(
        models.GoldenRecordVersion.id == version_id,
        models.GoldenRecordVersion.status == models.GoldenRecordVersionStatus.PENDING_APPROVAL,
        models.GoldenRecordVersion.change_type == "invalidation",
    ).first()
    if not version:
        return None
    record = get_golden_record(db, version.golden_record_id)
    if not record or record.status != models.GoldenRecordStatus.ACTIVE:
        return None
    record.status = models.GoldenRecordStatus.OBSOLETE
    record.updated_by = user_id
    version.status = models.GoldenRecordVersionStatus.INVALIDATED
    version.approved_by = user_id
    version.approved_at = datetime.now(timezone.utc)
    version.published_at = version.approved_at
    db.commit()
    db.refresh(version)
    return version


def rollback_golden_record(
    db: Session, gr_id: str, user_id: str, reason: str
) -> Optional[models.GoldenRecordVersion]:
    record = get_golden_record(db, gr_id)
    if not record or record.status != models.GoldenRecordStatus.ACTIVE or record.version <= 1:
        return None
    target = db.query(models.GoldenRecordVersion).filter(
        models.GoldenRecordVersion.golden_record_id == gr_id,
        models.GoldenRecordVersion.version_number == record.version - 1,
        models.GoldenRecordVersion.status == models.GoldenRecordVersionStatus.PUBLISHED,
    ).first()
    if not target:
        return None
    next_version = record.version + 1
    rollback = models.GoldenRecordVersion(
        golden_record_id=gr_id,
        parent_version_id=target.id,
        version_number=next_version,
        material_code=target.material_code,
        material_name=target.material_name,
        material_desc=target.material_desc,
        classification_id=target.classification_id,
        attribute_values=target.attribute_values,
        material_type=target.material_type,
        status=models.GoldenRecordVersionStatus.ROLLED_BACK,
        change_type="rollback",
        change_reason=reason,
        created_by=user_id,
        approved_by=user_id,
        approved_at=datetime.now(timezone.utc),
        published_at=datetime.now(timezone.utc),
    )
    record.material_name = target.material_name
    record.material_desc = target.material_desc
    record.classification_id = target.classification_id
    record.attribute_values = target.attribute_values
    record.material_type = target.material_type
    record.version = next_version
    record.revision = next_version
    record.updated_by = user_id
    db.add(rollback)
    db.commit()
    db.refresh(rollback)
    return rollback


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


def create_publish_sync_task(
    db: Session, application_id: str, golden_record_id: str, system_name: str, operation: str
) -> models.PublishSyncTask:
    task = models.PublishSyncTask(
        application_id=application_id,
        golden_record_id=golden_record_id,
        system_name=system_name,
        operation=operation,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_publish_sync_tasks(db: Session, application_id: Optional[str] = None) -> List[models.PublishSyncTask]:
    query = db.query(models.PublishSyncTask)
    if application_id:
        query = query.filter(models.PublishSyncTask.application_id == application_id)
    return query.order_by(desc(models.PublishSyncTask.created_at)).all()


def update_publish_sync_task(db: Session, task_id: str, data: dict) -> Optional[models.PublishSyncTask]:
    task = db.query(models.PublishSyncTask).filter(models.PublishSyncTask.id == task_id).first()
    if not task:
        return None
    for key, value in data.items():
        setattr(task, key, value)
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task


def retry_publish_sync_task(db: Session, task_id: str) -> Optional[models.PublishSyncTask]:
    task = db.query(models.PublishSyncTask).filter(
        models.PublishSyncTask.id == task_id,
        models.PublishSyncTask.status.in_(("failed", "timeout")),
    ).first()
    if not task or task.attempt_count >= task.max_attempts:
        return None
    task.status = "pending"
    task.next_retry_at = datetime.now(timezone.utc)
    task.last_error = None
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task


def recover_timed_out_publish_tasks(db: Session, timeout_minutes: int = 15) -> List[models.PublishSyncTask]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    tasks = db.query(models.PublishSyncTask).filter(
        models.PublishSyncTask.status == "running",
        models.PublishSyncTask.started_at < cutoff,
    ).all()
    now = datetime.now(timezone.utc)
    for task in tasks:
        task.status = "timeout"
        task.last_error = f"任务超过 {timeout_minutes} 分钟未完成"
        task.next_retry_at = now
        task.updated_at = now
    db.commit()
    return tasks


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
