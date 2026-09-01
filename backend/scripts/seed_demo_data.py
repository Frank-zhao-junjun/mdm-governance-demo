#!/usr/bin/env python3
"""Seed repeatable AI-governance demo data without touching business records."""
import argparse
import os
import random
import sys
from typing import Any

from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models
from app.core.database import SessionLocal, engine

SEED = 20_260_902
MIN_RECORDS = 32
DEMO_SOURCE = "demo_seed"


def _attributes(index: int, randomizer: random.Random) -> dict[str, Any]:
    material_type = "ROH" if index % 2 else "HALB"
    return {
        "MTART": material_type,
        "MEINS": "PC",
        "MATKL": "001" if material_type == "ROH" else "002",
        "BRGEW": round(randomizer.uniform(0.01, 12.0), 3),
        "NTGEW": round(randomizer.uniform(0.01, 11.5), 3),
        "GEWEI": "KG",
    }


def _special_records(randomizer: random.Random) -> list[models.MaterialRecord]:
    records = [
        models.MaterialRecord(
            material_code="DM000001",
            material_name="Hex bolt M8x30 galvanized 10.9",
            attributes={**_attributes(1, randomizer), "STRENGTH_GRADE": "10.9"},
            source_system=DEMO_SOURCE,
        ),
        models.MaterialRecord(
            material_code="DM000002",
            material_name="Hex bolt M8x30 galvanized 8.8",
            attributes={**_attributes(2, randomizer), "STRENGTH_GRADE": "8.8"},
            source_system=DEMO_SOURCE,
        ),
        models.MaterialRecord(
            material_code="DM000003",
            material_name="Steel wire 1 kilogram",
            attributes={**_attributes(3, randomizer), "MEINS": "G", "CONVERSION_FACTOR": 1000},
            source_system=DEMO_SOURCE,
        ),
        models.MaterialRecord(
            material_code="DM000004",
            material_name="Temporary bearing record",
            attributes={"MTART": "HALB", "MATKL": "002"},
            source_system=DEMO_SOURCE,
        ),
    ]
    for number in range(5, 17):
        records.append(models.MaterialRecord(
            material_code=f"DM{number:06d}",
            material_name=f"Demo bearing 620{number:02d}",
            attributes=_attributes(number, randomizer),
            source_system=DEMO_SOURCE,
        ))
    for cluster in range(8):
        first = 17 + cluster * 2
        name = f"Demo duplicate fastener cluster {cluster + 1:02d}"
        for number in (first, first + 1):
            records.append(models.MaterialRecord(
                material_code=f"DM{number:06d}",
                material_name=name,
                attributes=_attributes(number, randomizer),
                source_system=DEMO_SOURCE,
            ))
    return records


def _demo_owners() -> list[models.GovernanceOwner]:
    return [
        models.GovernanceOwner(role="owner", name="FA Owner", department="Factory A", domain="material", email="fa.owner@demo.local"),
        models.GovernanceOwner(role="owner", name="FB Owner", department="Factory B", domain="material", email="fb.owner@demo.local"),
        models.GovernanceOwner(role="steward", name="Demo Steward", department="Data Governance", domain="material", email="steward@demo.local"),
        models.GovernanceOwner(role="approver", name="Demo Approver", department="Governance Committee", domain="material", email="approver@demo.local"),
    ]


def _clear_demo_data(db: Session) -> None:
    db.query(models.MergeTicket).filter(models.MergeTicket.request_id.like("demo-%")).delete(synchronize_session=False)
    db.query(models.QualityTicket).filter(models.QualityTicket.request_id.like("demo-%")).delete(synchronize_session=False)
    db.query(models.GovernanceOwner).filter(models.GovernanceOwner.email.like("%@demo.local")).delete(synchronize_session=False)
    db.query(models.DataStandard).filter(models.DataStandard.standard_source == "demo").delete(synchronize_session=False)
    db.query(models.MaterialRecord).filter(models.MaterialRecord.source_system == DEMO_SOURCE).delete(synchronize_session=False)
    db.commit()


def seed_demo_data(db: Session, total_records: int = 10_000, reset: bool = False) -> dict[str, int | bool]:
    """Create deterministic demo records, duplicate clusters, and a factory dispute."""
    if total_records < MIN_RECORDS:
        raise ValueError(f"total_records must be at least {MIN_RECORDS}")
    existing_count = db.query(models.MaterialRecord).filter(
        models.MaterialRecord.source_system == DEMO_SOURCE
    ).count()
    if existing_count and not reset:
        return {"created": False, "material_records": existing_count}
    if reset:
        _clear_demo_data(db)

    randomizer = random.Random(SEED)
    records = _special_records(randomizer)
    used_numbers = {int(record.material_code[2:]) for record in records}
    next_number = 1
    while len(records) < total_records:
        if next_number not in used_numbers:
            records.append(models.MaterialRecord(
                material_code=f"DM{next_number:06d}",
                material_name=f"Demo material {next_number:06d}",
                attributes=_attributes(next_number, randomizer),
                source_system=DEMO_SOURCE,
            ))
        next_number += 1

    db.add_all(records)
    db.add(models.DataStandard(
        entity_type="material",
        sap_table="MARA_DEMO",
        field_name="MEINS",
        field_label="Base unit",
        data_type="enum",
        enum_values=["KG", "G", "PC", "M"],
        required=True,
        standard_source="demo",
        business_attrs={
            "unit_aliases": {"kilogram": "KG", "piece": "PC"},
            "conversion_factors": {"KG": 1000, "G": 1},
        },
    ))
    db.add_all(_demo_owners())
    db.add(models.MergeTicket(
        request_id="demo-factory-dispute-001",
        candidate_golden_ids=["DM000001", "DM000002"],
        suggested_golden_id="DM000001",
        evidence_json={"level": "L1", "reason": "strength-grade conflict"},
        factory_agreements_json={"FA": "agree", "FB": "oppose"},
        status=models.TicketStatus.PENDING,
    ))
    db.commit()
    return {"created": True, "material_records": len(records)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed repeatable AI-governance demo data.")
    parser.add_argument("--reset", action="store_true", help="replace only prior demo_seed data")
    parser.add_argument("--records", type=int, default=10_000, help="number of demo material records")
    args = parser.parse_args()
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        summary = seed_demo_data(db, total_records=args.records, reset=args.reset)
        print(f"Demo seed created={summary['created']} material_records={summary['material_records']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()