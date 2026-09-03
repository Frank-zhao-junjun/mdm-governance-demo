"""Audit service for governance write operations (SPEC §3.0)."""
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app import crud, models


class AuditService:
    """Record every governance write operation with actor and evidence."""

    STEP_LABELS = {
        "standard_create": "创建数据标准",
        "standard_update": "更新数据标准",
        "standard_delete": "删除数据标准",
        "quality_run": "执行质量检测",
        "error_detect": "执行疑似错误检测",
        "error_resolve": "处理疑似错误",
        "data_import": "导入存量数据",
        "metadata_entity_update": "更新元数据实体",
        "metadata_field_create": "创建元数据字段",
        "metadata_field_update": "更新元数据字段",
        "glossary_create": "创建业务术语",
        "glossary_update": "更新业务术语",
    }

    STATUS_LABELS = {
        "success": "成功",
        "failed": "失败",
    }

    def __init__(self, db: Session):
        self.db = db

    def _generate_step_id(self, step_name: str) -> str:
        existing = self.db.query(models.AuditLog).filter(
            models.AuditLog.step_name == step_name
        ).count()
        return f"GOV-{step_name.upper()}-{existing + 1:05d}"

    def log(
        self,
        step_name: str | models.StepName,
        executed_by: str,
        executed_by_name: str,
        status: str = "success",
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> models.AuditLog:
        """Create an audit log entry for one governance operation."""
        value = step_name.value if isinstance(step_name, models.StepName) else step_name
        return crud.create_audit_log(
            db=self.db,
            step_id=self._generate_step_id(value),
            step_name=models.StepName(value),
            step_label=self.STEP_LABELS.get(value, value),
            executed_by=executed_by,
            executed_by_name=executed_by_name,
            status=status,
            status_label=self.STATUS_LABELS.get(status, status),
            details=details,
            error_message=error_message,
        )
