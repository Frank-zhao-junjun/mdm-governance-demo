"""API contracts for AI-governance adjudication (TC-AIG-004/009/010/011)."""
from app import models


def _merge_ticket(db, *, status=models.TicketStatus.DRAFT):
    ticket = models.MergeTicket(
        request_id="merge-api-request-001",
        candidate_golden_ids=["golden-001", "golden-002"],
        suggested_golden_id="golden-001",
        evidence_json={"level": "L1", "detail": "duplicate candidate"},
        status=status,
        trace_id="trace-api-001",
    )
    trace = models.AgentTrace(
        trace_id="trace-api-001",
        agent_name="dedup-agent",
        model_version="mock-governance-v1",
        input_summary="candidate cluster",
        evidence_refs_json=["rule:duplicate"],
        decision_snapshot_json={"status": "block"},
    )
    db.add_all([ticket, trace])
    db.commit()
    return ticket


def test_unapproved_merge_execution_is_rejected_without_material_mutation(data_client, db):
    ticket = _merge_ticket(db)
    original_count = db.query(models.MaterialRecord).count()

    response = data_client.post("/api/governance/merge-execute", json={"ticket_id": ticket.id})

    assert response.status_code == 409
    assert db.query(models.MaterialRecord).count() == original_count


def test_high_risk_approval_requires_opinion_and_confirmation(data_client, db):
    ticket = _merge_ticket(db)

    missing_opinion = data_client.post(f"/api/copilot/merge/{ticket.id}/approve", json={"confirmed": True})
    missing_confirmation = data_client.post(
        f"/api/copilot/merge/{ticket.id}/approve", json={"opinion": "Evidence supports review."},
    )
    approved = data_client.post(
        f"/api/copilot/merge/{ticket.id}/approve",
        json={"opinion": "Evidence supports review.", "confirmed": True},
    )

    assert missing_opinion.status_code == 422
    assert missing_confirmation.status_code == 422
    assert approved.status_code == 200
    db.refresh(ticket)
    assert ticket.status == models.TicketStatus.APPROVED
    evidence = db.query(models.ApprovalEvidence).one()
    assert evidence.action == "approve"
    assert evidence.snapshot_json["evidence_json"]["level"] == "L1"


def test_accountability_returns_ticket_trace_and_approval_snapshot(data_client, db):
    ticket = _merge_ticket(db)
    data_client.post(
        f"/api/copilot/merge/{ticket.id}/approve",
        json={"opinion": "Approved after review.", "confirmed": True},
    )

    response = data_client.get("/api/copilot/accountability", params={"ticket_id": ticket.id})

    assert response.status_code == 200
    body = response.json()
    assert body["ticket"]["id"] == ticket.id
    assert body["trace"]["trace_id"] == "trace-api-001"
    assert body["approval_evidence"][0]["snapshot_json"]["status"] == "draft"


def test_todos_governance_report_and_owner_crud_are_authenticated(data_client, db):
    ticket = _merge_ticket(db)
    owner_payload = {
        "role": "steward",
        "name": "API Steward",
        "department": "Governance",
        "domain": "material",
        "email": "api.steward@example.test",
    }

    created = data_client.post("/api/owners", json=owner_payload)
    todos = data_client.get("/api/copilot/todos")
    report = data_client.get("/api/governance/report")
    evidence = data_client.get(f"/api/evidence/merge/{ticket.id}")

    assert created.status_code == 201
    assert todos.status_code == 200 and todos.json()["total"] == 1
    assert todos.json()["items"][0]["id"] == ticket.id
    assert report.status_code == 200 and report.json()["pending_todos"] == 1
    assert evidence.status_code == 200 and evidence.json()["evidence_json"]["level"] == "L1"