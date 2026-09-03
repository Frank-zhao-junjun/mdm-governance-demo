#!/usr/bin/env python3
"""Seed pending Copilot ruling tickets into the demo database.

Creates one merge ticket with an L1 strength conflict (M10019 vs M10005)
and one incremental governance run over known naming violators, so the
Copilot / disputes pages have real pending work. Idempotent per suffix
(defaults to today); pass a new --suffix to force a fresh batch.
"""
import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models
from app.agents.dedup_agent import DedupAgent
from app.agents.orchestrator import GovernanceOrchestrator
from app.core.database import SessionLocal
from app.core.llm_gateway import LLMGateway

MERGE_PAIR_CODES = ("M10019", "M10005")
NAMING_VIOLATOR_CODES = ("M1234", "MAT-00020", "M10021")
MISSING_MEINS_CODES = ("MDM0001", "MDM0002")
DISPUTE_PAIR_CODES = ("M10010", "M10009")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suffix",
        default=date.today().strftime("%Y%m%d"),
        help="request_id 后缀，默认当天日期；同一天重复执行幂等跳过",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        llm = LLMGateway(mode="mock")
        orchestrator = GovernanceOrchestrator(db, llm)

        standard = db.query(models.DataStandard).filter(
            models.DataStandard.entity_type == "material",
            models.DataStandard.field_name == "MEINS",
        ).first()
        if standard is None:
            print("缺少 material/MEINS 标准，请先运行 python init_db.py")
            return 1

        violators = db.query(models.MaterialRecord).filter(
            models.MaterialRecord.material_code.in_(NAMING_VIOLATOR_CODES),
        ).all()
        if not violators:
            print("未找到命名违例种子物料（M1234 / MAT-00020 / M10021），请先运行 python init_db.py")
            return 1

        detached = [
            models.MaterialRecord(
                material_code=row.material_code,
                material_name=row.material_name,
                attributes=row.attributes or {},
                source_system=row.source_system or "demo_tickets",
            )
            for row in violators
        ]
        detached.extend(
            models.MaterialRecord(
                material_code=code,
                material_name=f"临时紧固件样例 {code[-1]}",
                attributes={"MTART": "ROH"},
                source_system="demo_tickets",
            )
            for code in MISSING_MEINS_CODES
        )
        quality_request_id = f"demo-ticket-quality-{args.suffix}"
        incremental = orchestrator.run_incremental({
            "request_id": quality_request_id,
            "entity_type": "material",
            "records": detached,
            "standards": [standard],
            "items": [
                {"name": row.material_name, "attributes": row.attributes or {}}
                for row in violators
            ],
            "attribute_standard": {"required_fields": ["MEINS"]},
        })
        print(f"[quality] request_id={quality_request_id} idempotent={incremental['idempotent']}")

        merge_request_id = f"demo-ticket-merge-{args.suffix}"
        if db.query(models.MergeTicket).filter(models.MergeTicket.request_id == merge_request_id).count():
            print(f"[merge] request_id={merge_request_id} 已存在，跳过")
        else:
            pair = db.query(models.MaterialRecord).filter(
                models.MaterialRecord.material_code.in_(MERGE_PAIR_CODES),
            ).all()
            if len(pair) != 2:
                print(f"未找到归并对 {MERGE_PAIR_CODES}，请先运行 python init_db.py")
                return 1
            left, right = sorted(pair, key=lambda r: MERGE_PAIR_CODES.index(r.material_code))
            merge = DedupAgent(db, llm).run({
                "request_id": merge_request_id,
                "candidate": {
                    "left": {"id": left.id, "name": left.material_name, "strength": "10.9"},
                    "right": {"id": right.id, "name": right.material_name, "strength": "8.8"},
                },
            })
            print(f"[merge] request_id={merge_request_id} ticket_id={merge.get('ticket_id')}")

        terminal = [models.TicketStatus.DONE, models.TicketStatus.REJECTED]

        dispute_request_id = f"demo-ticket-dispute-{args.suffix}"
        if db.query(models.MergeTicket).filter(models.MergeTicket.request_id == dispute_request_id).count():
            print(f"[dispute] request_id={dispute_request_id} 已存在，跳过")
        else:
            pair = db.query(models.MaterialRecord).filter(
                models.MaterialRecord.material_code.in_(DISPUTE_PAIR_CODES),
            ).all()
            if len(pair) != 2:
                print(f"未找到争议对 {DISPUTE_PAIR_CODES}，跳过跨工厂争议造数（可选场景）")
            else:
                left, right = sorted(pair, key=lambda r: DISPUTE_PAIR_CODES.index(r.material_code))
                db.add(models.MergeTicket(
                    request_id=dispute_request_id,
                    candidate_golden_ids=[left.id, right.id],
                    suggested_golden_id=left.id,
                    evidence_json={
                        "status": "block",
                        "suggestions": [],
                        "conflicts": [{
                            "type": "cross_plant_disagreement",
                            "level": "L1",
                            "message": "跨工厂归并争议",
                            "detail": "FA 同意归并，FB 反对并主张 DN100/DN50 为不同物料",
                        }],
                    },
                    status=models.TicketStatus.PENDING,
                    factory_agreements_json={"FA": "agree", "FB": "oppose"},
                ))
                db.commit()
                print(f"[dispute] request_id={dispute_request_id} 已创建（FA 同意 / FB 反对）")

        pending_merge = db.query(models.MergeTicket).filter(
            models.MergeTicket.status.notin_(terminal),
        ).count()
        pending_quality = db.query(models.QualityTicket).filter(
            models.QualityTicket.status.notin_(terminal),
        ).count()
        print(f"当前待裁决：merge={pending_merge} quality={pending_quality}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
