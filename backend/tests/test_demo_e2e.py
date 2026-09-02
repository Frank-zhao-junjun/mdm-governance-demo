"""End-to-end acceptance test for the AI-enhanced governance demo (TC-AIG-012)."""
import time

import pytest

from app import models
from app.agents.dedup_agent import DedupAgent
from app.agents.orchestrator import GovernanceOrchestrator
from app.core.llm_gateway import LLMGateway
from app.services import quality_runner
from scripts.seed_demo_data import seed_demo_data


def test_tc_aig_012_ten_unfamiliar_records_are_all_suggested_or_ticketed_and_adjudicated(data_client, db):
    """Every incoming defect has a suggestion or a ticket; merge remains human-controlled."""
    seed_demo_data(db, total_records=40)
    steward = db.query(models.GovernanceOwner).filter(
        models.GovernanceOwner.email == "steward@demo.local"
    ).one()
    records = [
        models.MaterialRecord(
            material_code=f"M{number:05d}",
            material_name=f"临时紧固件样例 {number}",
            attributes={"MTART": "ROH"},
            source_system="customer_validation",
        )
        for number in range(20001, 20011)
    ]
    standard = models.DataStandard(
        entity_type="material",
        sap_table="MARA",
        field_name="MEINS",
        field_label="基本计量单位",
        data_type="enum",
        enum_values=["PC", "KG"],
        required=True,
    )
    db.add_all(records)
    db.commit()
    initial_material_count = db.query(models.MaterialRecord).count()
    orchestrator = GovernanceOrchestrator(db, LLMGateway(mode="mock"))

    incremental = orchestrator.run_incremental({
        "request_id": "demo-live-validation-001",
        "entity_type": "material",
        "records": records,
        "standards": [standard],
        "items": [{"name": record.material_name, "attributes": record.attributes} for record in records],
        "attribute_standard": {"required_fields": ["MEINS"]},
    })

    standard_items = incremental["standard"]["items"]
    quality_tickets = db.query(models.QualityTicket).filter(
        models.QualityTicket.request_id == "demo-live-validation-001"
    ).all()
    assert incremental["idempotent"] is False
    assert len(standard_items) == 10
    assert all(item["attributes"]["suggestions"] for item in standard_items)
    assert len(quality_tickets) == 10
    assert {ticket.assignee_owner_id for ticket in quality_tickets} == {steward.id}
    assert db.query(models.MaterialRecord).count() == initial_material_count

    strength_conflict = {
        record.material_code: record
        for record in db.query(models.MaterialRecord).filter(
            models.MaterialRecord.material_code.in_(["DM000001", "DM000002"])
        ).all()
    }
    merge = DedupAgent(db, LLMGateway(mode="mock")).run({
        "request_id": "demo-strength-conflict-001",
        "candidate": {
            "left": {"id": strength_conflict["DM000001"].id, "name": "M8x30 bolt", "strength": "10.9"},
            "right": {"id": strength_conflict["DM000002"].id, "name": "M8x30 bolt", "strength": "8.8"},
            "llm_suggestion": "merge",
        },
    })
    merge_ticket_id = merge["ticket_id"]
    unapproved = data_client.post("/api/governance/merge-execute", json={"ticket_id": merge_ticket_id})
    pending_report = data_client.get("/api/governance/report").json()
    approval = data_client.post(
        f"/api/copilot/merge/{merge_ticket_id}/approve",
        json={"opinion": "强度等级冲突，不执行物理归并，仅保留裁决记录。", "confirmed": True},
    )
    ready = data_client.post("/api/governance/merge-execute", json={"ticket_id": merge_ticket_id})
    accountability = data_client.get("/api/copilot/accountability", params={"ticket_id": merge_ticket_id})
    final_report = data_client.get("/api/governance/report").json()

    assert merge["result"]["conflicts"][0]["level"] == "L1"
    assert merge["result"]["conflicts"][0]["message"] == "不建议合并"
    assert unapproved.status_code == 409
    assert approval.status_code == 200
    assert ready.status_code == 200 and ready.json()["status"] == "ready"
    assert db.query(models.MaterialRecord).count() == initial_material_count
    assert accountability.status_code == 200
    evidence = accountability.json()["approval_evidence"]
    assert evidence[0]["snapshot_json"]["trace_id"] == merge["trace_id"]
    assert pending_report["pending_todos"] == final_report["pending_todos"] + 1
    assert final_report["agent_activity"] >= 3


def test_s6_ten_thousand_seed_records_complete_a_quality_scan_within_five_minutes(db):
    """S6: the 10,000-record demo stock is fully scanned in SPEC-compliant 5,000 batches."""
    seed_demo_data(db)
    standard = db.query(models.DataStandard).filter(
        models.DataStandard.standard_source == "demo",
        models.DataStandard.field_name == "MEINS",
    ).one()
    db.add(models.QualityCheckRule(
        name="Demo base-unit completeness",
        entity_type="material",
        rule_type=models.RuleType.NULL_CHECK,
        field_name="MEINS",
        standard_id=standard.id,
        rule_config={},
    ))
    db.commit()

    all_ids = [row[0] for row in db.query(models.MaterialRecord.id).all()]
    assert len(all_ids) == 10_000

    with pytest.raises(quality_runner.EntityLimitExceeded):
        quality_runner.run_batch(db, "material", triggered_by="demo-e2e")

    started = time.perf_counter()
    scanned = 0
    failed_total = 0
    for offset in range(0, len(all_ids), 5_000):
        batch, result = quality_runner.run_batch(
            db,
            "material",
            entity_ids=all_ids[offset:offset + 5_000],
            triggered_by="demo-e2e",
        )
        assert batch.total_entities == 5_000
        assert result.total_entities == 5_000
        scanned += batch.total_entities
        failed_total += batch.failed
    elapsed = time.perf_counter() - started

    assert scanned == 10_000
    assert failed_total >= 1
    assert elapsed < 300, f"10,000 条存量分批扫描超过 5 分钟：{elapsed:.2f}s"