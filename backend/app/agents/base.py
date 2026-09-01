"""Common execution discipline for governance Agents."""
from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.core.llm_gateway import LLMGateway


def _json_safe(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


class BaseAgent(ABC):
    """Template method for traceable governance Agent execution."""

    name = "base-agent"

    def __init__(self, db: Session, llm: LLMGateway):
        self.db = db
        self.llm = llm
        self.trace_id = uuid4().hex

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute once and always persist an accountability trace."""
        try:
            result = self._execute(payload)
            response = {"status": "success", "trace_id": self.trace_id, **_json_safe(result)}
            self._write_trace(payload, response)
            return response
        except Exception as error:
            response = {
                "status": "failed",
                "trace_id": self.trace_id,
                "error": "治理 Agent 执行失败",
            }
            self._write_trace(payload, response)
            return response

    @abstractmethod
    def _execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Implement the Agent-specific operation."""

    def _write_trace(self, payload: dict[str, Any], result: dict[str, Any]) -> None:
        trace = models.AgentTrace(
            trace_id=self.trace_id,
            agent_name=self.name,
            model_version="mock-governance-v1" if self.llm.mode == "mock" else "deepseek-chat",
            input_summary=f"payload keys: {', '.join(sorted(payload.keys()))}",
            evidence_refs_json={"request_id": payload.get("request_id")},
            decision_snapshot_json=_json_safe(result),
        )
        self.db.add(trace)
        self.db.commit()
