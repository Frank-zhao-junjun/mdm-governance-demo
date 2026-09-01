"""Agent that turns deterministic quality failures into steward tickets."""
from datetime import datetime, timedelta, timezone
from typing import Any

from app import models
from app.agents.base import BaseAgent
from app.skills.quality_rule import check_quality_rules


class QualityAgent(BaseAgent):
    name = "quality-agent"

    def _execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = str(payload.get("request_id", "")).strip()
        entity_type = str(payload.get("entity_type", "")).strip()
        records = payload.get("records", [])
        standards = payload.get("standards", [])
        if not request_id or not entity_type or not isinstance(records, list) or not isinstance(standards, list):
            raise ValueError("request_id, entity_type, records and standards are required")

        result = check_quality_rules(entity_type, records, standards)
        steward = self.db.query(models.GovernanceOwner).filter(
            models.GovernanceOwner.role == "steward",
            models.GovernanceOwner.domain == entity_type,
            models.GovernanceOwner.is_active.is_(True),
        ).first()
        due_at = datetime.now(timezone.utc) + timedelta(days=3)
        tickets = []
        for suggestion in result.suggestions:
            ticket = models.QualityTicket(
                request_id=request_id,
                rule_key=suggestion.evidence.source,
                severity="error" if result.status == "block" else "warning",
                issue_type="quality_rule",
                description=suggestion.suggestion,
                assignee_owner_id=steward.id if steward else None,
                sla_due_at=due_at,
                evidence_json=suggestion.model_dump(mode="json"),
                trace_id=self.trace_id,
            )
            self.db.add(ticket)
            tickets.append(ticket)
        self.db.commit()
        return {"result": result.model_dump(mode="json"), "ticket_ids": [ticket.id for ticket in tickets]}
