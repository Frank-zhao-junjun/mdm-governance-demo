"""Human adjudication APIs for AI governance recommendations."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.auth import require_dept_approver, require_any
from app.core.database import get_db

router = APIRouter(prefix="/api/copilot", tags=["Governance Copilot"])


def _ticket(ticket_type: str, ticket_id: str, db: Session):
    model = {"quality": models.QualityTicket, "merge": models.MergeTicket}.get(ticket_type)
    if model is None:
        raise HTTPException(status_code=404, detail="未知工单类型")
    ticket = db.get(model, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="治理工单不存在")
    return ticket


def _status(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _ticket_view(ticket: Any, ticket_type: str) -> dict[str, Any]:
    return {
        "id": ticket.id,
        "ticket_type": ticket_type,
        "request_id": ticket.request_id,
        "status": _status(ticket.status),
        "evidence_json": ticket.evidence_json,
        "trace_id": ticket.trace_id,
        "created_at": ticket.created_at,
    }


@router.get("/todos")
def list_todos(
    ticket_type: str | None = Query(None, pattern="^(quality|merge)$"),
    user: dict = Depends(require_any),
    db: Session = Depends(get_db),
):
    """Return pending human decisions; the client can apply owner/steward views."""
    _ = user
    pending = [models.TicketStatus.DRAFT, models.TicketStatus.PENDING]
    items: list[dict[str, Any]] = []
    if ticket_type in (None, "quality"):
        items.extend(_ticket_view(ticket, "quality") for ticket in db.query(models.QualityTicket).filter(
            models.QualityTicket.status.in_(pending)
        ).all())
    if ticket_type in (None, "merge"):
        items.extend(_ticket_view(ticket, "merge") for ticket in db.query(models.MergeTicket).filter(
            models.MergeTicket.status.in_(pending)
        ).all())
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return {"total": len(items), "items": items}


@router.post("/{ticket_type}/{ticket_id}/approve")
def approve_ticket(
    ticket_type: str,
    ticket_id: str,
    payload: schemas.TicketDecisionRequest,
    user: dict = Depends(require_dept_approver),
    db: Session = Depends(get_db),
):
    return _decide(ticket_type, ticket_id, "approve", payload, user, db)


@router.post("/{ticket_type}/{ticket_id}/reject")
def reject_ticket(
    ticket_type: str,
    ticket_id: str,
    payload: schemas.TicketDecisionRequest,
    user: dict = Depends(require_dept_approver),
    db: Session = Depends(get_db),
):
    return _decide(ticket_type, ticket_id, "reject", payload, user, db)


@router.post("/{ticket_type}/{ticket_id}/overturn")
def overturn_ticket(
    ticket_type: str,
    ticket_id: str,
    payload: schemas.TicketDecisionRequest,
    user: dict = Depends(require_dept_approver),
    db: Session = Depends(get_db),
):
    return _decide(ticket_type, ticket_id, "overturn", payload, user, db)


def _decide(ticket_type: str, ticket_id: str, action: str, payload: schemas.TicketDecisionRequest, user: dict, db: Session):
    ticket = _ticket(ticket_type, ticket_id, db)
    if ticket_type == "merge" and (not payload.opinion or not payload.confirmed):
        raise HTTPException(status_code=422, detail="高风险归并裁决必须填写意见并二次确认")
    snapshot = {
        "status": _status(ticket.status),
        "evidence_json": ticket.evidence_json,
        "trace_id": ticket.trace_id,
    }
    db.add(models.ApprovalEvidence(
        ticket_type=ticket_type,
        ticket_id=ticket.id,
        approver_id=user["id"],
        action=action,
        opinion=payload.opinion,
        snapshot_json=snapshot,
    ))
    ticket.status = {
        "approve": models.TicketStatus.APPROVED,
        "reject": models.TicketStatus.REJECTED,
        "overturn": models.TicketStatus.PENDING,
    }[action]
    if hasattr(ticket, "decided_by"):
        ticket.decided_by = user["id"]
        ticket.decision_opinion = payload.opinion
    db.commit()
    return {"ticket": _ticket_view(ticket, ticket_type), "action": action}


@router.get("/accountability")
def accountability(
    ticket_id: str = Query(..., min_length=1, max_length=36),
    user: dict = Depends(require_any),
    db: Session = Depends(get_db),
):
    _ = user
    ticket = db.get(models.QualityTicket, ticket_id)
    ticket_type = "quality"
    if ticket is None:
        ticket = db.get(models.MergeTicket, ticket_id)
        ticket_type = "merge"
    if ticket is None:
        raise HTTPException(status_code=404, detail="治理工单不存在")
    trace = db.query(models.AgentTrace).filter(models.AgentTrace.trace_id == ticket.trace_id).first()
    evidence = db.query(models.ApprovalEvidence).filter(
        models.ApprovalEvidence.ticket_id == ticket_id
    ).order_by(models.ApprovalEvidence.created_at.asc()).all()
    return {"ticket": _ticket_view(ticket, ticket_type), "trace": trace, "approval_evidence": evidence}