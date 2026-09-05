"""Evidence-chain lookup API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.core.auth import require_any
from app.core.database import get_db

router = APIRouter(prefix="/api/evidence", tags=["Governance Evidence"])


@router.get(
    "/{ticket_type}/{ticket_id}",
    summary="工单证据链查询（证据 JSON + Agent trace）",
    responses={404: {"description": "未知工单类型 / 治理工单不存在"}},
)
def get_evidence(ticket_type: str, ticket_id: str, user: dict = Depends(require_any), db: Session = Depends(get_db)):
    _ = user
    model = {"quality": models.QualityTicket, "merge": models.MergeTicket}.get(ticket_type)
    if model is None:
        raise HTTPException(status_code=404, detail="未知工单类型")
    ticket = db.get(model, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="治理工单不存在")
    trace = db.query(models.AgentTrace).filter(models.AgentTrace.trace_id == ticket.trace_id).first()
    return {"ticket_id": ticket.id, "ticket_type": ticket_type, "evidence_json": ticket.evidence_json, "trace": trace}