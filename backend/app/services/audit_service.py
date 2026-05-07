"""Audit service for full-chain traceability."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app import crud, models


class AuditService:
    """Record every step of the material lifecycle."""
    
    STEP_LABELS = {
        "create_draft": "创建草稿",
        "save_draft": "保存草稿",
        "submit": "提交申请",
        "validate": "质量校验",
        "dedup_check": "重复预检",
        "code_generate": "编码生成",
        "admin_approve": "管理员审批",
        "dept_approve": "使用部门审批",
        "create_gr": "创建Golden Record",
        "publish_btp": "BTP发布",
        "sync_om": "OpenMetadata同步",
        "om_test": "质量测试",
        "revoke": "撤销",
        "edit": "编辑",
        "revise": "修订",
    }
    
    STATUS_LABELS = {
        "success": "成功",
        "failed": "失败",
        "pending": "处理中",
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def _generate_step_id(self, app_no: str, step_name: str) -> str:
        """Generate step ID: SQ-2026-00001-S1"""
        existing = self.db.query(models.AuditLog).filter(
            models.AuditLog.step_id.like(f"{app_no}-S%")
        ).count()
        return f"{app_no}-S{existing + 1}"
    
    def log(self,
            application_id: Optional[str],
            step_name: str,
            executed_by: str,
            executed_by_name: str,
            status: str,
            details: Optional[Dict[str, Any]] = None,
            error_message: Optional[str] = None,
            golden_record_id: Optional[str] = None) -> models.AuditLog:
        """Create an audit log entry."""
        
        app = None
        app_no = "UNKNOWN"
        if application_id:
            app = crud.get_application(self.db, application_id)
            if app:
                app_no = app.app_no
        
        step_id = self._generate_step_id(app_no, step_name)
        
        log_entry = crud.create_audit_log(
            db=self.db,
            step_id=step_id,
            application_id=application_id,
            golden_record_id=golden_record_id,
            step_name=step_name,
            step_label=self.STEP_LABELS.get(step_name, step_name),
            executed_by=executed_by,
            executed_by_name=executed_by_name,
            status=status,
            status_label=self.STATUS_LABELS.get(status, status),
            details=details,
            error_message=error_message
        )
        
        return log_entry
    
    def get_application_trace(self, application_id: str) -> list:
        """Get full audit trace for an application."""
        logs = crud.get_application_audit_logs(self.db, application_id)
        return [
            {
                "step_id": log.step_id,
                "step_name": log.step_name.value,
                "step_label": log.step_label,
                "executed_by": log.executed_by,
                "executed_by_name": log.executed_by_name,
                "executed_at": log.executed_at.isoformat(),
                "status": log.status,
                "status_label": log.status_label,
                "details": log.details,
                "error_message": log.error_message
            }
            for log in logs
        ]
