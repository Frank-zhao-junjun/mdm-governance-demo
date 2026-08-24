"""Governance rule management API for data governance administrators."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.core.auth import require_any, require_admin
from app.core.database import get_db

router = APIRouter(prefix="/api/governance-rules", tags=["Governance Rules"])


@router.get("/", response_model=List[schemas.GovernanceRuleResponse])
def list_governance_rules(
    user: dict = Depends(require_any),
    db: Session = Depends(get_db),
):
    """List active and inactive governance rules."""
    _ = user
    rules = db.query(models.GovernanceRule).order_by(
        models.GovernanceRule.category,
        models.GovernanceRule.rule_key,
    ).all()
    return rules


@router.put("/{rule_key}", response_model=schemas.GovernanceRuleResponse)
def update_governance_rule(
    rule_key: str,
    payload: schemas.GovernanceRuleUpdate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update governance policy configuration for one rule."""
    _ = user
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="未提供可更新字段")

    updated = crud.update_governance_rule(db, rule_key, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="治理规则不存在")
    return updated
