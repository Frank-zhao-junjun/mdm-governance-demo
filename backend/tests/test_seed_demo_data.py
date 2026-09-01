"""Tests for repeatable AI-governance demo seed data (TC-AIG-003/005/008)."""
from app import models
from scripts.seed_demo_data import seed_demo_data


def test_seed_demo_data_creates_reproducible_materials_and_governance_scenarios(db):
    summary = seed_demo_data(db, total_records=40)

    records = db.query(models.MaterialRecord).filter(
        models.MaterialRecord.source_system == "demo_seed"
    ).all()
    dispute = db.query(models.MergeTicket).filter(
        models.MergeTicket.request_id == "demo-factory-dispute-001"
    ).one()

    assert summary["material_records"] == 40
    assert len(records) == 40
    assert len({record.material_code for record in records}) == 40
    assert db.query(models.GovernanceOwner).filter(
        models.GovernanceOwner.email.like("%@demo.local")
    ).count() == 4
    assert dispute.factory_agreements_json == {"FA": "agree", "FB": "oppose"}


def test_seed_demo_data_defaults_to_ten_thousand_material_records(db):
    summary = seed_demo_data(db)

    assert summary == {"created": True, "material_records": 10_000}
    assert db.query(models.MaterialRecord).filter(
        models.MaterialRecord.source_system == "demo_seed"
    ).count() == 10_000


def test_seed_demo_data_includes_strength_unit_and_duplicate_cluster_samples(db):
    seed_demo_data(db, total_records=40)
    records = {
        record.material_code: record
        for record in db.query(models.MaterialRecord).filter(
            models.MaterialRecord.source_system == "demo_seed"
        )
    }

    assert records["DM000001"].attributes["STRENGTH_GRADE"] == "10.9"
    assert records["DM000002"].attributes["STRENGTH_GRADE"] == "8.8"
    assert records["DM000003"].attributes["CONVERSION_FACTOR"] == 1000
    assert records["DM000003"].attributes["MEINS"] == "G"
    assert records["DM000017"].material_name == records["DM000018"].material_name


def test_seed_demo_data_is_idempotent_and_reset_replaces_only_demo_records(db):
    original = models.MaterialRecord(
        material_code="M10001",
        material_name="Existing material",
        attributes={},
        source_system="mock_sap",
    )
    db.add(original)
    db.commit()

    first = seed_demo_data(db, total_records=40)
    second = seed_demo_data(db, total_records=40)
    reset = seed_demo_data(db, total_records=40, reset=True)

    assert first["created"] is True
    assert second["created"] is False
    assert reset["created"] is True
    assert db.query(models.MaterialRecord).filter(
        models.MaterialRecord.source_system == "demo_seed"
    ).count() == 40
    assert db.query(models.MaterialRecord).filter(
        models.MaterialRecord.material_code == "M10001"
    ).one().source_system == "mock_sap"