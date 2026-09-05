"""存量数据导入 API（SPEC §7 Phase 4.1）。

上游业务系统负责创建与分发（SPEC §1.4），本系统只接收存量数据，因此
导入端点是 partner_records 的批量写入口（存量纠正期新增行级修正端点
POST /api/records/{entity_type}/{record_id}/fix，属字段级治理写口，见
record_fixer；两者均为 data_admin / admin 权限）。写权限限 data_admin /
admin（SPEC §3.0 权限矩阵），执行以 StepName.DATA_IMPORT 审计。

沿用 quality_checks / suspected_errors 的两段提交模式：importer 提交
数据，API 层写审计。
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.auth import require_admin
from app.core.database import get_db
from app.services import csv_importer
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/data-import", tags=["Data Import"])


@router.post(
    "/partners",
    response_model=schemas.PartnerImportResponse,
    summary="导入供应商 / 客户 CSV（按编码 upsert，≤5,000 行）",
    responses={
        400: {"description": "文件级缺陷：类型 / 大小 / 表头 / 行数超限"},
        403: {"description": "权限不足（需 admin / data_admin）"},
    },
)
async def import_partner_csv(
    file: UploadFile = File(...),
    entity_type: str = Form(..., pattern="^(supplier|customer)$"),
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """导入供应商/客户 CSV，按 (entity_type, partner_code) upsert。

    文件级缺陷（类型/大小/表头/行数超限）整批 400；行级格式错误只计入
    errors 明细，合法行照常入库（验收：格式错误行返回明细报告）。
    """
    content = await file.read()
    try:
        result = csv_importer.import_partners(
            db,
            entity_type=entity_type,
            filename=file.filename or "",
            content_type=file.content_type,
            content=content,
        )
    except csv_importer.CsvImportError as exc:
        AuditService(db).log(
            step_name=models.StepName.DATA_IMPORT.value,
            executed_by=user["id"],
            executed_by_name=user["name"],
            status="failed",
            details={"entity_type": entity_type, "filename": file.filename},
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    AuditService(db).log(
        step_name=models.StepName.DATA_IMPORT.value,
        executed_by=user["id"],
        executed_by_name=user["name"],
        details={
            "entity_type": entity_type,
            "filename": file.filename,
            "total_rows": result.total_rows,
            "created": result.created,
            "updated": result.updated,
            "failed": result.failed,
        },
    )
    return schemas.PartnerImportResponse(
        entity_type=entity_type,
        filename=file.filename or "",
        total_rows=result.total_rows,
        created=result.created,
        updated=result.updated,
        failed=result.failed,
        errors=[
            schemas.ImportRowError(row=e.row, field=e.field, message=e.message)
            for e in result.errors
        ],
    )
