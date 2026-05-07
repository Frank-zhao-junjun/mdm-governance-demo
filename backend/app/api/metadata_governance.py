"""Metadata governance API for catalog, lineage, quality, and traceability views."""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, models
from app.core.auth import require_any
from app.core.database import get_db
from app.services.openmetadata_sync import OpenMetadataSync

router = APIRouter(prefix="/api/metadata-governance", tags=["Metadata Governance"])


def _classification_path(db: Session, classification_id: str) -> str:
    parts: List[str] = []
    current = crud.get_classification(db, classification_id)
    while current:
        parts.append(f"{current.name} ({current.code})")
        current = crud.get_classification(db, current.parent_id) if current.parent_id else None
    return " / ".join(reversed(parts))


def _latest_log(logs: List[models.AuditLog], step_name: str) -> Optional[models.AuditLog]:
    for log in reversed(logs):
        if log.step_name.value == step_name:
            return log
    return None


@router.get("/overview")
def get_metadata_governance_overview(
    user: dict = Depends(require_any),
    db: Session = Depends(get_db)
):
    """Return a dashboard-friendly metadata governance overview."""
    records = crud.get_golden_records(db, limit=500)
    applications = crud.get_applications(db, limit=500)
    audit_logs = crud.get_audit_logs(db, limit=500)
    logs_by_application: Dict[str, List[models.AuditLog]] = {}
    for log in sorted(audit_logs, key=lambda item: item.executed_at):
        if log.application_id:
            logs_by_application.setdefault(log.application_id, []).append(log)

    catalog = []
    quality_tests = []
    lineage_nodes = [
        {"id": "source-applications", "label": "物料申请", "type": "source"},
        {"id": "btp", "label": "BTP", "type": "external"},
        {"id": "openmetadata", "label": "OpenMetadata", "type": "external"},
    ]
    lineage_edges = []

    for record in records:
        app = record.application
        app_id = app.id if app else record.application_id
        gr_node_id = f"gr-{record.id}"
        app_node_id = f"app-{app_id}" if app_id else None
        classification_path = record.classification_path or _classification_path(db, record.classification_id)
        logs = logs_by_application.get(app_id, []) if app_id else []
        validate_log = _latest_log(logs, "validate")
        om_test_log = _latest_log(logs, "om_test")

        catalog.append({
            "id": record.id,
            "application_id": app_id,
            "material_code": record.material_code,
            "material_name": record.material_name,
            "material_type": record.material_type.value,
            "classification_path": classification_path,
            "attribute_count": len(record.attribute_values or {}),
            "status": record.status.value,
            "version": record.version,
            "revision": record.revision,
            "btp_published": record.btp_published,
            "btp_published_at": record.btp_published_at.isoformat() if record.btp_published_at else None,
            "om_synced": record.om_synced,
            "om_synced_at": record.om_synced_at.isoformat() if record.om_synced_at else None,
            "om_entity_fqn": record.om_entity_fqn or f"RalphLoop.Material.{record.material_code}",
            "created_at": record.created_at.isoformat(),
        })

        if app_node_id:
            lineage_nodes.append({
                "id": app_node_id,
                "label": app.app_no if app else app_id,
                "type": "application",
                "subtitle": app.material_name if app else record.material_name,
            })
            lineage_edges.append({"from": app_node_id, "to": gr_node_id, "label": "审批通过后生成"})

        lineage_nodes.append({
            "id": gr_node_id,
            "label": record.material_code,
            "type": "golden_record",
            "subtitle": record.material_name,
        })
        if record.btp_published:
            lineage_edges.append({"from": gr_node_id, "to": "btp", "label": "发布"})
        if record.om_synced or record.om_entity_fqn:
            lineage_edges.append({"from": gr_node_id, "to": "openmetadata", "label": "同步元数据"})

        if validate_log and validate_log.details:
            quality_tests.append({
                "id": f"validate-{record.id}",
                "material_code": record.material_code,
                "test_name": "申请质量校验",
                "status": "passed" if validate_log.details.get("passed") else "failed",
                "message": "; ".join(validate_log.details.get("errors") or []) or "质量规则通过",
                "executed_at": validate_log.executed_at.isoformat(),
                "source": "RalphLoop Validator",
            })
        if om_test_log and om_test_log.details:
            for index, result in enumerate(om_test_log.details.get("results") or []):
                quality_tests.append({
                    "id": f"om-{record.id}-{index}",
                    "material_code": record.material_code,
                    "test_name": result.get("test_name", "OpenMetadata质量测试"),
                    "status": "passed" if result.get("passed") else "failed",
                    "message": result.get("message"),
                    "executed_at": om_test_log.executed_at.isoformat(),
                    "source": "OpenMetadata",
                })

    traces = []
    for app in applications:
        logs = logs_by_application.get(app.id, [])
        traces.append({
            "application_id": app.id,
            "app_no": app.app_no,
            "material_name": app.material_name,
            "material_code": app.material_code,
            "status": app.status.value,
            "step_count": len(logs),
            "last_step": logs[-1].step_label if logs else None,
            "last_status": logs[-1].status if logs else None,
            "last_executed_at": logs[-1].executed_at.isoformat() if logs else None,
        })

    synced_count = sum(1 for item in catalog if item["om_synced"])
    return {
        "openmetadata": OpenMetadataSync().health_check(),
        "summary": {
            "metadata_assets": len(catalog),
            "om_synced": synced_count,
            "btp_published": sum(1 for item in catalog if item["btp_published"]),
            "quality_tests": len(quality_tests),
            "traceable_applications": sum(1 for item in traces if item["step_count"] > 0),
        },
        "catalog": catalog,
        "lineage": {"nodes": lineage_nodes, "edges": lineage_edges},
        "quality_tests": quality_tests,
        "traces": traces,
    }