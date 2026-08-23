"""Dashboard and health API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import schemas, crud
from app.core.database import get_db
from app.core.auth import require_any, require_admin
from app.services.btp_mock import BTPMockService
from app.services.openmetadata_sync import OpenMetadataSync

router = APIRouter(tags=["Dashboard"])


@router.get("/api/dashboard")
def dashboard(
    user: dict = Depends(require_any),
    db: Session = Depends(get_db)
):
    """Get dashboard statistics."""
    stats = crud.get_dashboard_stats(db)
    recent_apps = crud.get_applications(db, skip=0, limit=5)
    recent_logs = crud.get_audit_logs(db, skip=0, limit=10)
    
    return {
        "stats": stats,
        "recent_applications": [schemas.ApplicationResponse.model_validate(a) for a in recent_apps],
        "recent_audit_logs": [schemas.AuditLogResponse.model_validate(l) for l in recent_logs]
    }


@router.get("/api/health")
def health_check():
    """System health check."""
    btp = BTPMockService()
    om = OpenMetadataSync()
    
    return {
        "status": "healthy",
        "services": {
            "api": "online",
            "database": "connected",
            "btp_mock": btp.health_check(),
            "openmetadata": om.health_check()
        }
    }


@router.get("/api/btp-mock/health")
def btp_mock_health(
    user: dict = Depends(require_any)
):
    """BTP Mock service health."""
    btp = BTPMockService()
    return btp.health_check()


@router.get("/api/publish-sync-tasks", response_model=list[schemas.PublishSyncTaskResponse])
def publish_sync_tasks(
    application_id: str | None = None,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return crud.get_publish_sync_tasks(db, application_id=application_id)


@router.post("/api/publish-sync-tasks/recover-timeouts")
def recover_publish_timeouts(
    timeout_minutes: int = Query(default=15, ge=1, le=1440),
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    recovered = crud.recover_timed_out_publish_tasks(db, timeout_minutes)
    return {
        "success": True,
        "recovered_count": len(recovered),
        "tasks": [schemas.PublishSyncTaskResponse.model_validate(task) for task in recovered],
    }


@router.post("/api/publish-sync-tasks/{task_id}/retry", response_model=schemas.PublishSyncTaskResponse)
def retry_publish_task(
    task_id: str,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    task = crud.retry_publish_sync_task(db, task_id)
    if not task:
        raise HTTPException(status_code=400, detail="任务不存在、状态不可重试或已达到最大重试次数")
    return task
