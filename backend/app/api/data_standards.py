"""Data standard management API (SPEC §3.1).

Read access: all authenticated roles. Write access: data_admin / admin.
All writes are audited (SPEC §3.0).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.core.auth import require_admin, require_any
from app.core.database import get_db
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/data-standards", tags=["Data Standards"])


@router.get("", response_model=schemas.DataStandardListResponse)
def list_data_standards(
    entity_type: Optional[str] = Query(None, pattern="^(material|supplier|customer)$"),
    sap_table: Optional[str] = Query(None, max_length=50),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(require_any),
    db: Session = Depends(get_db),
):
    """List data standards with optional entity/table filters."""
    _ = user
    items, total = crud.get_data_standards(
        db, entity_type=entity_type, sap_table=sap_table, skip=skip, limit=limit
    )
    return {"total": total, "items": items}


@router.post("", response_model=schemas.DataStandardResponse, status_code=201)
def create_data_standard(
    payload: schemas.DataStandardCreate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a data standard. 409 on (entity_type, sap_table, field_name) conflict."""
    conflict = crud.find_data_standard_conflict(
        db, payload.entity_type, payload.sap_table, payload.field_name
    )
    if conflict:
        raise HTTPException(status_code=409, detail="同（实体, SAP表, 字段）的数据标准已存在")

    standard = crud.create_data_standard(db, payload.model_dump())
    AuditService(db).log(
        step_name=models.StepName.STANDARD_CREATE.value,
        executed_by=user["id"],
        executed_by_name=user["name"],
        details={
            "standard_id": standard.id,
            "entity_type": standard.entity_type,
            "sap_table": standard.sap_table,
            "field_name": standard.field_name,
        },
    )
    return standard


@router.put("/{standard_id}", response_model=schemas.DataStandardResponse)
def update_data_standard(
    standard_id: str,
    payload: schemas.DataStandardUpdate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update editable fields of a data standard (identity keys are immutable)."""
    standard = crud.get_data_standard(db, standard_id)
    if not standard:
        raise HTTPException(status_code=404, detail="数据标准不存在")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="未提供可更新字段")

    standard = crud.update_data_standard(db, standard, update_data)
    AuditService(db).log(
        step_name=models.StepName.STANDARD_UPDATE.value,
        executed_by=user["id"],
        executed_by_name=user["name"],
        details={
            "standard_id": standard.id,
            "entity_type": standard.entity_type,
            "sap_table": standard.sap_table,
            "field_name": standard.field_name,
            "fields": sorted(update_data.keys()),
        },
    )
    return standard


@router.delete("/{standard_id}", status_code=204)
def delete_data_standard(
    standard_id: str,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a data standard. 409 while referenced by quality check rules."""
    standard = crud.get_data_standard(db, standard_id)
    if not standard:
        raise HTTPException(status_code=404, detail="数据标准不存在")

    ref_count = crud.count_rules_referencing_standard(db, standard_id)
    if ref_count:
        raise HTTPException(
            status_code=409,
            detail=f"该标准被 {ref_count} 条质量检测规则引用，请先解除引用",
        )

    deleted = {
        "standard_id": standard.id,
        "entity_type": standard.entity_type,
        "sap_table": standard.sap_table,
        "field_name": standard.field_name,
    }
    crud.delete_data_standard(db, standard)
    AuditService(db).log(
        step_name=models.StepName.STANDARD_DELETE.value,
        executed_by=user["id"],
        executed_by_name=user["name"],
        details=deleted,
    )
