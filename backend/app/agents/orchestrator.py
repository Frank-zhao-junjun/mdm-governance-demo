"""Serialized and idempotent orchestration for governance agents."""
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from app import models
from app.agents.quality_agent import QualityAgent
from app.agents.standard_agent import StandardAgent
from app.core.llm_gateway import LLMGateway
from sqlalchemy.orm import Session


class GovernanceOrchestrator:
    """Coordinates read-only advice and ticket creation; never executes a merge."""

    _execution_lock = Lock()

    def __init__(self, db: Session, llm: LLMGateway):
        self.db = db
        self.llm = llm

    def run_incremental(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = str(payload.get("request_id", "")).strip()
        if not request_id:
            raise ValueError("request_id is required")
        with self._execution_lock:
            if self._request_exists(request_id):
                return {"idempotent": True, "request_id": request_id}
            standard_result = StandardAgent(self.db, self.llm).run(payload)
            quality_result = QualityAgent(self.db, self.llm).run(payload)
            return {
                "idempotent": False,
                "standard": standard_result,
                "quality": quality_result,
            }

    def escalate_overdue_tickets(self, now: datetime | None = None) -> int:
        """Escalate open tickets at three and seven elapsed days."""
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is not None:
            current = current.astimezone(timezone.utc).replace(tzinfo=None)
        changed = 0
        open_tickets = self.db.query(models.QualityTicket).filter(
            models.QualityTicket.status.notin_([
                models.TicketStatus.DONE,
                models.TicketStatus.REJECTED,
            ])
        ).all()
        for ticket in open_tickets:
            created = ticket.created_at
            if created is None:
                continue
            if created.tzinfo is not None:
                created = created.astimezone(timezone.utc).replace(tzinfo=None)
            elapsed_days = (current - created).total_seconds() / 86_400
            level = None
            if elapsed_days >= 7:
                level = models.EscalationLevel.COMMITTEE
            elif elapsed_days >= 3:
                level = models.EscalationLevel.DEPT_HEAD
            if level and ticket.escalated_level != level:
                ticket.escalated_level = level
                changed += 1
        if changed:
            self.db.commit()
        return changed

    def _request_exists(self, request_id: str) -> bool:
        return (
            self.db.query(models.QualityTicket).filter(models.QualityTicket.request_id == request_id).first()
            is not None
            or self.db.query(models.MergeTicket).filter(models.MergeTicket.request_id == request_id).first()
            is not None
        )