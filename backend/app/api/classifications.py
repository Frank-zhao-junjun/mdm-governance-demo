"""Classification and Attribute Template API."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schemas, crud
from app.core.database import get_db
from app.core.auth import require_any

router = APIRouter(prefix="/api/classifications", tags=["Classifications"])


@router.get("/", response_model=List[schemas.ClassificationResponse])
def list_classifications(
    level: int = None,
    parent_id: str = None,
    user: dict = Depends(require_any),
    db: Session = Depends(get_db)
):
    """List all material classifications."""
    if level and level not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="level must be 1, 2 or 3")
    if level or parent_id is not None:
        return crud.get_classifications(db, level=level, parent_id=parent_id)
    return crud.get_classification_tree(db)


@router.get("/{classification_id}", response_model=schemas.ClassificationResponse)
def get_classification(
    classification_id: str,
    user: dict = Depends(require_any),
    db: Session = Depends(get_db)
):
    """Get a classification by ID."""
    item = crud.get_classification(db, classification_id)
    if not item:
        raise HTTPException(status_code=404, detail="分类不存在")
    return item


@router.post("/", response_model=schemas.ClassificationResponse)
def create_classification(
    data: schemas.ClassificationCreate,
    user: dict = Depends(require_any),
    db: Session = Depends(get_db)
):
    """Create a new classification."""
    return crud.create_classification(db, data)


@router.get("/{classification_id}/templates", response_model=List[schemas.AttributeTemplateResponse])
def get_templates(
    classification_id: str,
    user: dict = Depends(require_any),
    db: Session = Depends(get_db)
):
    """Get attribute templates for a classification."""
    return crud.get_attribute_templates(db, classification_id)


@router.post("/{classification_id}/templates", response_model=schemas.AttributeTemplateResponse)
def create_template(
    classification_id: str,
    data: schemas.AttributeTemplateCreate,
    user: dict = Depends(require_any),
    db: Session = Depends(get_db)
):
    """Create an attribute template for a classification."""
    data.classification_id = classification_id
    return crud.create_attribute_template(db, data)
