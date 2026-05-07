"""Golden Record API."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas, crud
from app.core.database import get_db
from app.core.auth import require_any

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
