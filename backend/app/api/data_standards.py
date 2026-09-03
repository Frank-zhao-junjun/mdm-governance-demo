"""Data standard management API (SPEC §3.1).

Read access: all authenticated roles. Write access: data_admin / admin.
All writes are audited (SPEC §3.0).
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.core.auth import require_admin, require_any
from app.core.database import get_db
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/data-standards", tags=["Data Standards"])


def _metadata_field_map(
    db: Session, standards: List[models.DataStandard]
) -> Dict[str, models.MetadataField]:
    """批量取标准关联的元数据字段并建 id → 字段映射（列表端点一次查询，避免 N+1）。"""
    ids = {s.metadata_field_id for s in standards if s.metadata_field_id}
    if not ids:
        return {}
    return {f.id: f for f in crud.get_metadata_fields_by_ids(db, list(ids))}


def _to_standard_response(
    standard: models.DataStandard, field_map: Dict[str, models.MetadataField]
) -> dict:
    """组装标准响应：带出关联元数据字段的标签 / 视图分区（无关联时为 None）。"""
    item = schemas.DataStandardResponse.model_validate(standard).model_dump()
    field = field_map.get(standard.metadata_field_id)
    item["metadata_field_label"] = field.field_label if field else None
    item["metadata_view_section"] = field.view_section if field else None
    return item


def _apply_metadata_field(db: Session, data: dict, label_explicit: bool) -> None:
    """传 metadata_field_id 时以登记册为准带入核心字段（就地改写 data）。

    登记册字段不存在抛 404；entity_type / sap_table / field_name / data_type /
    max_length 一律以登记册为准覆盖；field_label 仅在调用方未显式给出时回填。
    """
    field = crud.get_metadata_field(db, data["metadata_field_id"])
    if field is None:
        raise HTTPException(status_code=404, detail="关联的元数据字段不存在")
    data.update(
        entity_type=field.entity_type,
        sap_table=field.sap_table,
        field_name=field.field_name,
        data_type=field.data_type,
        max_length=field.max_length,
    )
    if not label_explicit:
        data["field_label"] = field.field_label


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
    field_map = _metadata_field_map(db, items)
    return {
        "total": total,
        "items": [_to_standard_response(s, field_map) for s in items],
    }


@router.post("", response_model=schemas.DataStandardResponse, status_code=201)
def create_data_standard(
    payload: schemas.DataStandardCreate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a data standard. 409 on (entity_type, sap_table, field_name) conflict.

    传 metadata_field_id 时先按登记册带入核心字段，唯一键检查在带入之后执行。
    """
    data = payload.model_dump()
    if payload.metadata_field_id:
        _apply_metadata_field(db, data, label_explicit=payload.field_label is not None)

    conflict = crud.find_data_standard_conflict(
        db, data["entity_type"], data["sap_table"], data["field_name"]
    )
    if conflict:
        raise HTTPException(status_code=409, detail="同（实体, SAP表, 字段）的数据标准已存在")

    standard = crud.create_data_standard(db, data)
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
    return _to_standard_response(standard, _metadata_field_map(db, [standard]))


@router.put("/{standard_id}", response_model=schemas.DataStandardResponse)
def update_data_standard(
    standard_id: str,
    payload: schemas.DataStandardUpdate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update editable fields of a data standard.

    常规更新身份键不可变；传 metadata_field_id 时按登记册带入核心字段（可能
    改写身份键），此时唯一键检查在带入之后执行（排除自身，撞他条返回 409）。
    """
    standard = crud.get_data_standard(db, standard_id)
    if not standard:
        raise HTTPException(status_code=404, detail="数据标准不存在")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="未提供可更新字段")

    if update_data.get("metadata_field_id"):
        _apply_metadata_field(db, update_data, label_explicit="field_label" in update_data)
        conflict = crud.find_data_standard_conflict(
            db, update_data["entity_type"], update_data["sap_table"], update_data["field_name"]
        )
        if conflict and conflict.id != standard.id:
            raise HTTPException(status_code=409, detail="同（实体, SAP表, 字段）的数据标准已存在")

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
    return _to_standard_response(standard, _metadata_field_map(db, [standard]))


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
