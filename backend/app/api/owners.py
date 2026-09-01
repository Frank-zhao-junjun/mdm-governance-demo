"""Governance owner directory API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.auth import require_admin, require_any
from app.core.database import get_db

router = APIRouter(prefix="/api/owners", tags=["Governance Owners"])


@router.get("")
def list_owners(user: dict = Depends(require_any), db: Session = Depends(get_db)):
    _ = user
    return db.query(models.GovernanceOwner).order_by(models.GovernanceOwner.name).all()


@router.post("", status_code=201)
def create_owner(payload: schemas.GovernanceOwnerCreate, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    _ = user
    owner = models.GovernanceOwner(**payload.model_dump())
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


@router.put("/{owner_id}")
def update_owner(owner_id: str, payload: schemas.GovernanceOwnerUpdate, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    _ = user
    owner = db.get(models.GovernanceOwner, owner_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="治理责任人不存在")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="未提供可更新字段")
    for field, value in changes.items():
        setattr(owner, field, value)
    db.commit()
    db.refresh(owner)
    return owner


@router.delete("/{owner_id}", status_code=204)
def delete_owner(owner_id: str, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    _ = user
    owner = db.get(models.GovernanceOwner, owner_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="治理责任人不存在")
    db.delete(owner)
    db.commit()