"""Suspected error API (SPEC §3.3).

Detect / resolve: data_admin / admin only; list: all authenticated roles
(SPEC §3.0 permission matrix). Runs are audited with
StepName.ERROR_DETECT / ERROR_RESOLVE（两段提交模式：编排层提交数据、
API 层写审计，沿用 quality_checks 范式）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.core.auth import require_admin, require_any
from app.core.database import get_db
from app.services import duplicate_detector, suspected_error_runner
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/suspected-errors", tags=["Suspected Errors"])

_ERROR_TYPE_PATTERN = "^(duplicate|naming|classification|unit)$"
_STATUS_PATTERN = "^(pending|confirmed|resolved|false_positive)$"


@router.post("/detect", response_model=schemas.SuspectedErrorDetectResponse)
def detect_suspected_errors(
    payload: schemas.SuspectedErrorDetectRequest,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Execute suspected-error detection with §2.7 dedup semantics (SPEC §3.3)."""
    try:
        counters = suspected_error_runner.detect_suspected_errors(
            db,
            entity_type=payload.entity_type,
            error_types=payload.error_types,
            entity_ids=payload.entity_ids,
            detected_by=user["id"],
        )
    except suspected_error_runner.UnsupportedErrorType as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except duplicate_detector.DuplicateDetectionLimitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    AuditService(db).log(
        step_name=models.StepName.ERROR_DETECT.value,
        executed_by=user["id"],
        executed_by_name=user["name"],
        details={
            "entity_type": payload.entity_type,
            "error_types": payload.error_types or sorted(suspected_error_runner.SUPPORTED_ERROR_TYPES),
            "scope": "ids" if payload.entity_ids else "all",
            **counters,
        },
    )
    return counters


@router.get("/", response_model=schemas.SuspectedErrorListResponse)
def list_suspected_errors(
    entity_type: str = Query(..., pattern=schemas._ENTITY_PATTERN),
    error_type: Optional[str] = Query(None, pattern=_ERROR_TYPE_PATTERN),
    status: Optional[str] = Query(None, pattern=_STATUS_PATTERN),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(require_any),
    db: Session = Depends(get_db),
):
    """List suspected errors, newest first (read-only; all authenticated roles)."""
    _ = user
    items, total = crud.list_suspected_errors(
        db,
        entity_type=entity_type,
        error_type=error_type,
        status=status,
        skip=skip,
        limit=limit,
    )
    return {"total": total, "items": items}


@router.post("/{error_id}/resolve", response_model=schemas.SuspectedErrorResponse)
def resolve_suspected_error(
    error_id: str,
    payload: schemas.SuspectedErrorResolveRequest,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Resolve one suspected error (SPEC §3.3; resolved_by comes from JWT)."""
    row = crud.get_suspected_error(db, error_id)
    if row is None:
        raise HTTPException(status_code=404, detail="疑似错误不存在")

    from_status = row.status
    row.status = payload.status
    row.resolved_by = user["id"]
    row.resolved_at = models._now_utc()
    if payload.resolution_note is not None:
        row.resolution_note = payload.resolution_note
    db.commit()
    db.refresh(row)

    AuditService(db).log(
        step_name=models.StepName.ERROR_RESOLVE.value,
        executed_by=user["id"],
        executed_by_name=user["name"],
        details={
            "suspected_error_id": row.id,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "error_type": row.error_type,
            "from_status": from_status,
            "to_status": row.status,
            "note": payload.resolution_note,
        },
    )
    return row
