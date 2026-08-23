"""Golden Record API."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas, crud
from app.core.database import get_db
from app.core.auth import require_any, require_admin

router = APIRouter(prefix="/api/golden-records", tags=["Golden Records"])


@router.get("/", response_model=List[schemas.GoldenRecordResponse])
def list_golden_records(
    skip: int = 0,
    limit: int = 100,
    user: dict = Depends(require_any),
    db: Session = Depends(get_db)
):
    """List all Golden Records with pagination."""
    if skip < 0:
        raise HTTPException(status_code=400, detail="skip must be >= 0")
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    return crud.get_golden_records(db, skip=skip, limit=limit)


@router.get("/{gr_id}", response_model=schemas.GoldenRecordResponse)
def get_golden_record(
    gr_id: str,
    user: dict = Depends(require_any),
    db: Session = Depends(get_db)
):
    """Get a Golden Record by ID."""
    item = crud.get_golden_record(db, gr_id)
    if not item:
        raise HTTPException(status_code=404, detail="Golden Record不存在")
    return item


@router.get("/code/{material_code}", response_model=schemas.GoldenRecordResponse)
def get_golden_record_by_code(
    material_code: str,
    user: dict = Depends(require_any),
    db: Session = Depends(get_db)
):
    """Get a Golden Record by material code."""
    item = crud.get_golden_record_by_code(db, material_code)
    if not item:
        raise HTTPException(status_code=404, detail="物料编码不存在")
    return item


@router.get("/{gr_id}/versions", response_model=List[schemas.GoldenRecordVersionResponse])
def list_golden_record_versions(
    gr_id: str,
    user: dict = Depends(require_any),
    db: Session = Depends(get_db),
):
    if not crud.get_golden_record(db, gr_id):
        raise HTTPException(status_code=404, detail="Golden Record不存在")
    return crud.get_golden_record_versions(db, gr_id)


@router.post("/{gr_id}/revisions", response_model=schemas.GoldenRecordVersionResponse)
def create_revision(
    gr_id: str,
    data: schemas.GoldenRecordVersionCreate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    version = crud.create_golden_record_revision(db, gr_id, data, user["id"])
    if not version:
        raise HTTPException(status_code=400, detail="当前 Golden Record 不允许修订")
    return version


@router.post("/{gr_id}/versions/{version_id}/approve", response_model=schemas.GoldenRecordVersionResponse)
def approve_revision(
    gr_id: str,
    version_id: str,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    version = crud.approve_golden_record_version(db, version_id, user["id"])
    if not version or version.golden_record_id != gr_id:
        raise HTTPException(status_code=400, detail="修订版本不存在或状态不正确")
    return version


@router.post("/{gr_id}/versions/{version_id}/publish", response_model=schemas.GoldenRecordVersionResponse)
def publish_revision(
    gr_id: str,
    version_id: str,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    version = crud.publish_golden_record_version(db, version_id, user["id"])
    if not version or version.golden_record_id != gr_id:
        raise HTTPException(status_code=400, detail="修订版本不存在或状态不正确")
    return version


@router.post("/{gr_id}/invalidation", response_model=schemas.GoldenRecordVersionResponse)
def request_invalidation(
    gr_id: str,
    reason: str,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    version = crud.create_golden_record_invalidation(db, gr_id, reason, user["id"])
    if not version:
        raise HTTPException(status_code=400, detail="当前 Golden Record 不允许失效")
    return version


@router.post("/{gr_id}/versions/{version_id}/invalidation-approve", response_model=schemas.GoldenRecordVersionResponse)
def approve_invalidation(
    gr_id: str,
    version_id: str,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    version = crud.approve_golden_record_invalidation(db, version_id, user["id"])
    if not version or version.golden_record_id != gr_id:
        raise HTTPException(status_code=400, detail="失效申请不存在或状态不正确")
    return version


@router.post("/{gr_id}/rollback", response_model=schemas.GoldenRecordVersionResponse)
def rollback_record(
    gr_id: str,
    reason: str = "回滚到上一已发布版本",
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    version = crud.rollback_golden_record(db, gr_id, user["id"], reason)
    if not version:
        raise HTTPException(status_code=400, detail="当前 Golden Record 没有可回滚的上一版本")
    return version
