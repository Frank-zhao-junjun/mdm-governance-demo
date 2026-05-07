"""Dashboard and health API."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas, crud
from app.core.database import get_db
from app.core.auth import require_any
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
