"""Quality check API (SPEC §3.2).

Run: data_admin / admin only; rules/results/batches/report: all authenticated
roles (SPEC §3.0 permission matrix). Runs are audited with
StepName.QUALITY_RUN; skipped / rule_errors details go into audit details
(Phase 2 设计决策 3: 明细不落批次表，避免破坏「结果表只存失败项」).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.core.auth import require_admin, require_any
from app.core.database import get_db
from app.services import quality_runner
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/quality-checks", tags=["Quality Checks"])

_ENTITY_PATTERN = "^(material|supplier|customer)$"
_SEVERITIES = ("error", "warning", "info")


@router.post(
    "/run",
    response_model=schemas.QualityCheckRunResponse,
    summary="执行质量检测批次（同步，≤5,000 实体）",
    responses={
        400: {"description": "超批量上限 / 无可执行规则 / 无匹配实体"},
        403: {"description": "权限不足（需 admin / data_admin）"},
    },
)
def run_quality_check(
    payload: schemas.QualityCheckRunRequest,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Execute a quality check batch (SPEC §5: sync, ≤5,000 entities per run)."""
    try:
        batch, result = quality_runner.run_batch(
            db,
            entity_type=payload.entity_type,
            entity_ids=payload.entity_ids,
            rule_ids=payload.rule_ids,
            triggered_by=user["id"],
        )
    except quality_runner.EntityLimitExceeded as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except quality_runner.NoExecutableRules as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except quality_runner.NoMatchingEntities as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    summary = result.summary()
    AuditService(db).log(
        step_name=models.StepName.QUALITY_RUN.value,
        executed_by=user["id"],
        executed_by_name=user["name"],
        details={
            "batch_id": batch.id,
            "entity_type": batch.entity_type,
            "total_entities": batch.total_entities,
            "total_checks": batch.total_checks,
            "passed": batch.passed,
            "failed": batch.failed,
            "skipped_checks": batch.skipped_checks,
            "skipped_fields": summary["skipped_fields"],
            "rule_errors": summary["rule_errors"],
            "rule_ids": batch.rule_ids,
            "scope": "ids" if payload.entity_ids else "all",
        },
    )
    return {
        "batch_id": batch.id,
        "total_checked": batch.total_checks,
        "passed": batch.passed,
        "failed": batch.failed,
        "skipped": batch.skipped_checks,
    }


@router.get(
    "/rules",
    response_model=schemas.QualityCheckRuleListResponse,
    summary="质量检测规则列表",
)
def list_rules(
    entity_type: Optional[str] = Query(None, pattern=_ENTITY_PATTERN),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(require_any),
    db: Session = Depends(get_db),
):
    """List quality check rules (read-only; all authenticated roles)."""
    _ = user
    items, total = crud.get_quality_check_rules(
        db, entity_type=entity_type, skip=skip, limit=limit
    )
    return {"total": total, "items": items}


@router.get(
    "/results",
    response_model=schemas.QualityCheckResultListResponse,
    summary="质量检测结果列表（仅存失败项）",
)
def list_results(
    entity_type: str = Query(..., pattern=_ENTITY_PATTERN),
    entity_id: Optional[str] = Query(None, max_length=36),
    severity: Optional[str] = Query(None, pattern="^(error|warning|info)$"),
    batch_id: Optional[str] = Query(None, max_length=36),
    field_name: Optional[str] = Query(None, max_length=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(require_any),
    db: Session = Depends(get_db),
):
    """List failed check results (SPEC §2.6: only failures are persisted)."""
    _ = user
    items, total = crud.get_quality_check_results(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        severity=severity,
        batch_id=batch_id,
        field_name=field_name,
        skip=skip,
        limit=limit,
    )
    return {"total": total, "items": items}


@router.get(
    "/batches",
    response_model=schemas.QualityCheckBatchListResponse,
    summary="质量检测批次列表（最新在前）",
)
def list_batches(
    entity_type: str = Query(..., pattern=_ENTITY_PATTERN),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(require_any),
    db: Session = Depends(get_db),
):
    """List check batches, newest first (SPEC §6.3 批次选择器数据源)."""
    _ = user
    items, total = crud.get_quality_check_batches(db, entity_type=entity_type, skip=skip, limit=limit)
    return {"total": total, "items": items}


@router.get(
    "/report",
    response_model=schemas.QualityCheckReportResponse,
    summary="质量检测批次报告（批次统计 + 失败分布）",
    responses={404: {"description": "检测批次不存在"}},
)
def get_report(
    entity_type: str = Query(..., pattern=_ENTITY_PATTERN),
    batch_id: Optional[str] = Query(None, max_length=36),
    user: dict = Depends(require_any),
    db: Session = Depends(get_db),
):
    """Batch report (SPEC §3.2): stats from batch row, distribution from results."""
    _ = user
    batch = (
        crud.get_quality_check_batch(db, batch_id)
        if batch_id
        else crud.get_latest_quality_check_batch(db, entity_type)
    )
    if batch is None or batch.entity_type != entity_type:
        raise HTTPException(status_code=404, detail="检测批次不存在")

    # 失败分布按严重程度聚合（三档补 0）
    severity_rows = (
        db.query(models.QualityCheckResult.severity, func.count())
        .filter(models.QualityCheckResult.batch_id == batch.id)
        .group_by(models.QualityCheckResult.severity)
        .all()
    )
    by_severity = {severity: 0 for severity in _SEVERITIES}
    for severity, count in severity_rows:
        if severity in by_severity:
            by_severity[severity] = count

    # 按规则统计：覆盖批次全部规则（含 failed=0）；total=批次实体数（设计决策 4）
    failed_by_rule = dict(
        db.query(models.QualityCheckResult.rule_id, func.count())
        .filter(models.QualityCheckResult.batch_id == batch.id)
        .group_by(models.QualityCheckResult.rule_id)
        .all()
    )
    rule_rows = crud.get_quality_check_rules_by_ids(db, batch.rule_ids or [])
    rules = {rule.id: rule for rule in rule_rows}
    by_rule = []
    for rule_id in batch.rule_ids or []:
        rule = rules.get(rule_id)
        failed = failed_by_rule.get(rule_id, 0)
        total = batch.total_entities
        by_rule.append(
            {
                "rule_id": rule_id,
                "rule_name": rule.name if rule else rule_id,
                "total": total,
                "failed": failed,
                "pass_rate": round((total - failed) / total, 4) if total else 1.0,
            }
        )

    # Top 问题：按 (field_name, rule_id) 聚合取前 10；issue_type 经规则表获得
    top_rows = (
        db.query(
            models.QualityCheckResult.field_name,
            models.QualityCheckResult.rule_id,
            func.count(),
            func.min(models.QualityCheckResult.message),
        )
        .filter(models.QualityCheckResult.batch_id == batch.id)
        .group_by(models.QualityCheckResult.field_name, models.QualityCheckResult.rule_id)
        .order_by(func.count().desc())
        .limit(10)
        .all()
    )
    top_issues = [
        {
            "field_name": field_name,
            "issue_count": count,
            "issue_type": rules.get(rule_id).rule_type.value if rules.get(rule_id) else None,
            "message": message,
        }
        for field_name, rule_id, count, message in top_rows
    ]

    pass_rate = (
        round(batch.passed / batch.total_checks, 4) if batch.total_checks else 1.0
    )
    return {
        "batch_id": batch.id,
        "entity_type": batch.entity_type,
        "total_entities": batch.total_entities,
        "total_checks": batch.total_checks,
        "passed": batch.passed,
        "failed": batch.failed,
        "pass_rate": pass_rate,
        "by_severity": by_severity,
        "by_rule": by_rule,
        "top_issues": top_issues,
    }
