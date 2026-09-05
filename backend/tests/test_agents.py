"""Integration tests for AI-governance Agents (TC-AIG-001/002/003/007/011)."""
from datetime import datetime, timedelta, timezone

from app import models
from app.agents.dedup_agent import DedupAgent
from app.agents.quality_agent import QualityAgent
from app.agents.standard_agent import StandardAgent
from app.agents.orchestrator import GovernanceOrchestrator
from app.core.llm_gateway import LLMGateway


def _llm():
    return LLMGateway(mode="mock")


def _required_unit_standard():
    return models.DataStandard(
        entity_type="material",
        sap_table="MARA",
        field_name="MEINS",
        field_label="Base unit",
        data_type="string",
        required=True,
    )


def test_standard_agent_returns_evidence_without_changing_material_records(db):
    record = models.MaterialRecord(
        material_code="M20001",
        material_name="临时螺栓",
        attributes={"MTART": "ROH"},
    )
    db.add(record)
    db.commit()
    initial_material_count = db.query(models.MaterialRecord).count()

    result = StandardAgent(db, _llm()).run({
        "items": [{"name": record.material_name, "attributes": record.attributes}],
        "attribute_standard": {"required_fields": ["MTART", "MEINS"]},
    })

    assert result["status"] == "success"
    assert result["items"][0]["naming"]["status"] == "block"
    assert db.query(models.MaterialRecord).count() == initial_material_count
    assert db.query(models.AgentTrace).count() == 1


def test_quality_agent_creates_a_steward_ticket_with_three_day_sla(db):
    owner = models.GovernanceOwner(
        role="steward",
        name="Data Steward",
        department="Governance",
        domain="material",
        email="steward@example.test",
    )
    record = models.MaterialRecord(material_code="M20002", material_name="Bolt", attributes={})
    db.add_all([owner, record])
    db.commit()

    result = QualityAgent(db, _llm()).run({
        "request_id": "quality-request-001",
        "entity_type": "material",
        "records": [record],
        "standards": [_required_unit_standard()],
    })

    ticket = db.query(models.QualityTicket).one()
    assert result["status"] == "success"
    assert ticket.request_id == "quality-request-001"
    assert ticket.assignee_owner_id == owner.id
    assert ticket.sla_due_at - ticket.created_at <= timedelta(days=3, seconds=1)
    assert ticket.trace_id == result["trace_id"]


def test_dedup_agent_creates_ticket_but_never_merges_a_record(db):
    result = DedupAgent(db, _llm()).run({
        "request_id": "merge-request-001",
        "candidate": {
            "left": {"id": "golden-109", "strength": "10.9"},
            "right": {"id": "golden-88", "strength": "8.8"},
            "llm_suggestion": "merge",
        },
    })

    ticket = db.query(models.MergeTicket).one()
    assert result["status"] == "success"
    assert ticket.candidate_golden_ids == ["golden-109", "golden-88"]
    assert ticket.status == models.TicketStatus.DRAFT
    assert ticket.evidence_json["conflicts"][0]["message"] == "不建议合并"


def test_agent_failure_is_returned_and_persisted_as_a_trace(db):
    result = QualityAgent(db, _llm()).run({"request_id": "invalid-request"})

    trace = db.query(models.AgentTrace).one()
    assert result["status"] == "failed"
    assert trace.decision_snapshot_json["status"] == "failed"


def test_orchestrator_is_idempotent_and_escalates_open_tickets(db):
    owner = models.GovernanceOwner(
        role="steward",
        name="Data Steward",
        department="Governance",
        domain="material",
        email="steward@example.test",
    )
    record = models.MaterialRecord(material_code="M20003", material_name="Bolt", attributes={})
    db.add_all([owner, record])
    db.commit()
    orchestrator = GovernanceOrchestrator(db, _llm())
    payload = {
        "request_id": "incremental-request-001",
        "entity_type": "material",
        "records": [record],
        "standards": [_required_unit_standard()],
        "items": [{"name": record.material_name, "attributes": record.attributes}],
    }

    first = orchestrator.run_incremental(payload)
    second = orchestrator.run_incremental(payload)
    ticket = db.query(models.QualityTicket).one()
    ticket.created_at = datetime.now(timezone.utc) - timedelta(days=8)
    db.commit()

    escalated = orchestrator.escalate_overdue_tickets(now=datetime.now(timezone.utc))

    assert first["idempotent"] is False
    assert second == {"idempotent": True, "request_id": "incremental-request-001"}
    assert db.query(models.QualityTicket).count() == 1
    assert escalated == 1
    assert ticket.escalated_level == models.EscalationLevel.COMMITTEE


def test_orchestrator_escalates_three_day_ticket_to_department_head(db):
    ticket = models.QualityTicket(
        request_id="quality-request-aged",
        rule_key="rule",
        severity="warning",
        issue_type="quality_rule",
        description="Needs remediation.",
        created_at=datetime.now(timezone.utc) - timedelta(days=3),
    )
    db.add(ticket)
    db.commit()

    changed = GovernanceOrchestrator(db, _llm()).escalate_overdue_tickets(
        now=datetime.now(timezone.utc),
    )

    assert changed == 1
    assert ticket.escalated_level == models.EscalationLevel.DEPT_HEAD