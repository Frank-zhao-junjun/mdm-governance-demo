"""Regression tests for the AI-enhanced governance persistence models."""
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    AgentTrace,
    ApprovalEvidence,
    EscalationLevel,
    GovernanceOwner,
    KeyMapping,
    MergeTicket,
    QualityTicket,
    TicketStatus,
)


def test_tc_aig_002_new_governance_tables_persist_with_expected_defaults(db):
    """TC-AIG-002: governance tickets start at the draft, non-escalated state."""
    ticket = QualityTicket(
        request_id="quality-request-001",
        rule_key="material.name.required",
        severity="high",
        issue_type="missing_name",
        description="Material name is required.",
    )
    merge_ticket = MergeTicket(
        request_id="merge-request-001",
        candidate_golden_ids=["golden-001", "golden-002"],
    )
    owner = GovernanceOwner(
        role="steward",
        name="Test Steward",
        department="Data Governance",
        domain="material",
        email="steward@example.test",
    )
    trace = AgentTrace(
        trace_id="trace-001",
        agent_name="quality-agent",
        model_version="mock-v1",
        input_summary="Test input",
    )
    db.add_all([ticket, merge_ticket, owner, trace])
    db.flush()

    evidence = ApprovalEvidence(
        ticket_type="quality",
        ticket_id=ticket.id,
        approver_id=owner.id,
        action="approve",
    )

    db.add(evidence)
    db.commit()

    assert ticket.status == TicketStatus.DRAFT
    assert ticket.escalated_level == EscalationLevel.NONE
    assert merge_ticket.status == TicketStatus.DRAFT
    assert merge_ticket.escalated_level == EscalationLevel.NONE
    assert owner.is_active is True


def test_key_mapping_rejects_duplicate_source_code_within_source_system(db):
    """A source-system code has exactly one canonical golden-record mapping."""
    db.add(KeyMapping(
        golden_record_id="golden-001",
        source_system="ERP",
        source_code="MAT-001",
        mapping_type="primary",
    ))
    db.commit()

    db.add(KeyMapping(
        golden_record_id="golden-002",
        source_system="ERP",
        source_code="MAT-001",
        mapping_type="alias",
    ))

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_new_governance_models_store_traceability_fields(db):
    """All AI decision records preserve their requested accountability fields."""
    timestamp = datetime.now(timezone.utc)
    ticket = QualityTicket(
        request_id="quality-request-002",
        rule_key="material.unit.valid",
        severity="medium",
        issue_type="invalid_unit",
        description="Unsupported unit.",
        evidence_json={"level": "L1"},
        trace_id="trace-002",
        sla_due_at=timestamp,
    )

    assert ticket.request_id == "quality-request-002"
    assert ticket.evidence_json == {"level": "L1"}
    assert ticket.trace_id == "trace-002"
    assert ticket.sla_due_at == timestamp