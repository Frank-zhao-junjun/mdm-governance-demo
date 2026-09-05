"""存量记录修正 API（字段治理闭环·修复环节）。

POST /{entity_type}/{record_id}/fix：admin / data_admin 专属（与 quality run、
疑似错误 resolve 同一权限面，SPEC §3.0 矩阵）。走两段提交模式：服务层提交
数据、API 层写审计（quality_checks / suspected_errors 同范式）。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.auth import require_admin
from app.core.database import get_db
from app.services import entity_accessor, record_fixer
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/records", tags=["Records"])


@router.post(
    "/{entity_type}/{record_id}/fix",
    response_model=schemas.RecordFieldFixResponse,
    summary="存量记录字段级修正（唯一写口，落审计）",
    responses={
        400: {"description": "字段未登记 / 未命中标准 / 必填禁空 / pattern 预校验失败"},
        403: {"description": "权限不足（需 admin / data_admin）"},
        404: {"description": "记录不存在 / 字段未命中任何标准"},
        409: {"description": "编码唯一性冲突"},
    },
)
def fix_record_field(
    entity_type: str,
    record_id: str,
    payload: schemas.RecordFieldFixRequest,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """按数据标准修正一条存量记录的治理字段值（不校验的修正一律 4xx 拒绝）。

    body.value 为 None / 空串表示清除该字段键（仅标准非必填字段；必填字段与
    身份列拒绝）。成功即落库并写审计，修正本身不触发重跑——重跑验证由调用方
    在检测页执行（最新批次该字段失败归零 = 治理闭环证据）。
    """
    if entity_type not in entity_accessor.KNOWN_ENTITY_TYPES:
        raise HTTPException(status_code=404, detail="记录不存在")

    try:
        result = record_fixer.fix_record_field(
            db,
            entity_type=entity_type,
            record_id=record_id,
            field_name=payload.field_name,
            value=payload.value,
        )
    except record_fixer.RecordNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except record_fixer.RecordFixError as exc:
        status_code = 409 if isinstance(exc, record_fixer.CodeConflict) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    AuditService(db).log(
        step_name=models.StepName.RECORD_FIELD_UPDATE.value,
        executed_by=user["id"],
        executed_by_name=user["name"],
        details={
            "record_id": result["record_id"],
            "entity_type": result["entity_type"],
            "field_name": result["field_name"],
            "old_value": result["old_value"],
            "new_value": result["new_value"],
        },
    )
    return result
