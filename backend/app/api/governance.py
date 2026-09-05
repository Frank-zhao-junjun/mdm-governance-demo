"""Aggregate governance reports and merge execution gate."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.auth import require_admin, require_any
from app.core.database import get_db
from app.skills.merge_executor import prepare_merge_execution

router = APIRouter(prefix="/api/governance", tags=["Governance"])


@router.get("/report", summary="治理总览报告（质量分 / 重复率 / 待办 / Agent 活动）")
def governance_report(user: dict = Depends(require_any), db: Session = Depends(get_db)):
    _ = user
    material_count = db.query(models.MaterialRecord).count()
    quality_tickets = db.query(models.QualityTicket).count()
    merge_tickets = db.query(models.MergeTicket).count()
    pending = db.query(models.QualityTicket).filter(models.QualityTicket.status.in_([
        models.TicketStatus.DRAFT, models.TicketStatus.PENDING,
    ])).count() + db.query(models.MergeTicket).filter(models.MergeTicket.status.in_([
        models.TicketStatus.DRAFT, models.TicketStatus.PENDING,
    ])).count()
    return {
        "quality_score": round(max(0, 100 - (quality_tickets / max(material_count, 1) * 100)), 2),
        "duplicate_rate": round(merge_tickets / max(material_count, 1) * 100, 2),
        "pending_todos": pending,
        "agent_activity": db.query(models.AgentTrace).count(),
    }


@router.get("/clusters", summary="重复簇（归并工单）列表")
def merge_clusters(user: dict = Depends(require_any), db: Session = Depends(get_db)):
    _ = user
    tickets = db.query(models.MergeTicket).all()
    return {"total": len(tickets), "items": tickets}


@router.post(
    "/merge-execute",
    summary="归并执行预检（仅返回 ready，实际归并由外部执行器执行）",
    responses={
        403: {"description": "权限不足（需 admin / data_admin）"},
        404: {"description": "归并工单不存在"},
        409: {"description": "归并工单尚未批准，禁止执行"},
    },
)
def merge_execute(
    payload: schemas.MergeExecuteRequest,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ = user
    ticket = db.get(models.MergeTicket, payload.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="归并工单不存在")
    result = prepare_merge_execution({
        "status": ticket.status.value,
        "candidate_golden_ids": ticket.candidate_golden_ids,
    })
    if result.status != "pass":
        raise HTTPException(status_code=409, detail="归并工单尚未批准，禁止执行")
    return {"ticket_id": ticket.id, "status": "ready", "message": "已通过人工批准，等待外部执行器处理"}