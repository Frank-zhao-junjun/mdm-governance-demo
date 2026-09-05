"""Agent that records merge recommendations without executing a merge."""
from collections.abc import Mapping
from typing import Any

from app import models
from app.agents.base import BaseAgent
from app.skills.duplicate_match import evaluate_duplicate_candidates


class DedupAgent(BaseAgent):
    name = "dedup-agent"

    def _execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = str(payload.get("request_id", "")).strip()
        candidate = payload.get("candidate")
        if not request_id or not isinstance(candidate, Mapping):
            raise ValueError("request_id and candidate are required")
        left = candidate.get("left", {})
        right = candidate.get("right", {})
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            raise ValueError("candidate sides must be objects")
        candidate_ids = [str(item["id"]) for item in (left, right) if item.get("id")]
        if len(candidate_ids) < 2:
            raise ValueError("candidate must contain two golden record ids")

        result = evaluate_duplicate_candidates(candidate)
        ticket = models.MergeTicket(
            request_id=request_id,
            candidate_golden_ids=candidate_ids,
            suggested_golden_id=str(left.get("id")),
            evidence_json=result.model_dump(mode="json"),
            trace_id=self.trace_id,
        )
        self.db.add(ticket)
        self.db.commit()
        return {"result": result.model_dump(mode="json"), "ticket_id": ticket.id}
