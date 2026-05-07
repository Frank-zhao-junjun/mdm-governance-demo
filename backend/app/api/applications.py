"""Material Application API - Full lifecycle management with auth and transactions."""
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone
import shutil
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import schemas, crud, models
from app.core.database import get_db
from app.core.auth import (
    get_current_user, require_applicant, require_admin, require_dept_approver,
    create_access_token
)
from app.services.material_validator import MaterialValidator
from app.services.duplicate_detector import DuplicateDetector
from app.services.code_generator import CodeGenerator
from app.services.audit_service import AuditService
from app.services.btp_mock import BTPMockService
from app.services.openmetadata_sync import OpenMetadataSync

router = APIRouter(prefix="/api/applications", tags=["Applications"])
UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "applications"


def _safe_filename(filename: str) -> str:
    return Path(filename).name.replace("/", "_").replace("\\", "_") or "attachment"


@router.get("/", response_model=List[schemas.ApplicationResponse])
def list_applications(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    user: dict = Depends(require_applicant),
    db: Session = Depends(get_db)
):
    """List material applications with optional filters."""
    # Validate pagination params
    if skip < 0:
        raise HTTPException(status_code=400, detail="skip must be >= 0")
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    
    # Non-admin users can only see their own applications
    created_by_filter = user["id"] if user["role"] == "applicant" else None
    
    return crud.get_applications(db, status=status, created_by=created_by_filter, skip=skip, limit=limit)


@router.get("/{app_id}", response_model=schemas.ApplicationResponse)
def get_application(
    app_id: str,
    user: dict = Depends(require_applicant),
    db: Session = Depends(get_db)
):
    """Get application details."""
    item = crud.get_application(db, app_id)
    if not item:
        raise HTTPException(status_code=404, detail="申请单不存在")
    
    # Authorization: applicants can only view their own
    if user["role"] == "applicant" and item.created_by != user["id"]:
        raise HTTPException(status_code=403, detail="无权查看此申请单")
    
    return item


@router.post("/{app_id}/attachments")
def upload_application_attachment(
    app_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(require_applicant),
    db: Session = Depends(get_db)
):
    """Upload drawing or supporting attachment for an application draft."""
    app = crud.get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="申请单不存在")

    if user["role"] == "applicant" and app.created_by != user["id"]:
        raise HTTPException(status_code=403, detail="无权编辑此申请单")

    if app.status != models.ApplicationStatus.DRAFT:
        raise HTTPException(status_code=400, detail="只有草稿状态可以上传附件")

    attachment_id = str(uuid.uuid4())
    original_name = _safe_filename(file.filename or "attachment")
    stored_name = f"{attachment_id}-{original_name}"
    app_dir = UPLOAD_ROOT / app_id
    app_dir.mkdir(parents=True, exist_ok=True)
    file_path = app_dir / stored_name

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    size = file_path.stat().st_size
    attachment = {
        "id": attachment_id,
        "original_name": original_name,
        "stored_name": stored_name,
        "content_type": file.content_type or "application/octet-stream",
        "size": size,
        "uploaded_by": user["id"],
        "uploaded_by_name": user.get("name"),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "download_url": f"/api/applications/{app_id}/attachments/{attachment_id}",
    }

    attachments = list(app.attachments or [])
    attachments.append(attachment)
    crud.update_application(db, app_id, {"attachments": attachments})

    audit = AuditService(db)
    audit.log(
        application_id=app.id,
        step_name="save_draft",
        executed_by=user["id"],
        executed_by_name=user["name"],
        status="success",
        details={"attachment": {"id": attachment_id, "original_name": original_name, "size": size}}
    )

    return attachment


@router.get("/{app_id}/attachments/{attachment_id}")
def download_application_attachment(
    app_id: str,
    attachment_id: str,
    user: dict = Depends(require_applicant),
    db: Session = Depends(get_db)
):
    """Download an uploaded application attachment."""
    app = crud.get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="申请单不存在")

    if user["role"] == "applicant" and app.created_by != user["id"]:
        raise HTTPException(status_code=403, detail="无权查看此申请单")

    attachment = next((item for item in (app.attachments or []) if item.get("id") == attachment_id), None)
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")

    file_path = UPLOAD_ROOT / app_id / attachment["stored_name"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="附件文件不存在")

    return FileResponse(
        file_path,
        media_type=attachment.get("content_type") or "application/octet-stream",
        filename=attachment.get("original_name") or "attachment"
    )


@router.post("/", response_model=schemas.ApplicationResponse)
def create_application(
    data: schemas.ApplicationCreate,
    user: dict = Depends(require_applicant),
    db: Session = Depends(get_db)
):
    """Create a new material application (draft)."""
    app = crud.create_application(db, data, user["id"], user["name"])
    
    # Log audit
    audit = AuditService(db)
    audit.log(
        application_id=app.id,
        step_name="create_draft",
        executed_by=user["id"],
        executed_by_name=user["name"],
        status="success",
        details={"app_no": app.app_no}
    )
    
    return app


@router.put("/{app_id}/draft")
def save_draft(
    app_id: str,
    data: schemas.ApplicationDraftSave,
    user: dict = Depends(require_applicant),
    db: Session = Depends(get_db)
):
    """Save application draft."""
    app = crud.get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="申请单不存在")
    
    # Authorization check
    if user["role"] == "applicant" and app.created_by != user["id"]:
        raise HTTPException(status_code=403, detail="无权编辑此申请单")
    
    if app.status != models.ApplicationStatus.DRAFT:
        raise HTTPException(status_code=400, detail="只有草稿状态可以保存")
    
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    app = crud.update_application(db, app_id, update_data)
    
    # Log audit
    audit = AuditService(db)
    audit.log(
        application_id=app.id,
        step_name="save_draft",
        executed_by=user["id"],
        executed_by_name=user["name"],
        status="success"
    )
    
    return {"success": True, "message": "草稿已保存", "application": app}


@router.post("/{app_id}/submit")
def submit_application(
    app_id: str,
    user: dict = Depends(require_applicant),
    db: Session = Depends(get_db)
):
    """Submit application for approval.
    
    Wraps validation + dedup + code generation in a single database transaction.
    """
    app = crud.get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="申请单不存在")
    
    # Authorization check
    if user["role"] == "applicant" and app.created_by != user["id"]:
        raise HTTPException(status_code=403, detail="无权提交此申请单")
    
    if app.status != models.ApplicationStatus.DRAFT:
        raise HTTPException(status_code=400, detail="只有草稿状态可以提交")
    
    audit = AuditService(db)
    
    try:
        # Step 1: Validation
        validator = MaterialValidator(db)
        val_result = validator.validate({
            "material_name": app.material_name,
            "classification_id": app.classification_id,
            "material_type": app.material_type.value,
            "attribute_values": app.attribute_values
        })
        
        audit.log(
            application_id=app.id,
            step_name="validate",
            executed_by="system",
            executed_by_name="系统自动",
            status="success" if val_result["passed"] else "failed",
            details=val_result
        )
        
        if not val_result["passed"]:
            crud.update_application(db, app_id, {
                "validation_result": val_result,
                "validation_passed": False
            })
            raise HTTPException(
                status_code=400,
                detail=f"质量校验未通过: {', '.join(val_result['errors'])}"
            )
        
        # Step 2: Duplicate check
        detector = DuplicateDetector(db)
        dedup_result = detector.check({
            "material_name": app.material_name,
            "classification_id": app.classification_id
        })
        
        audit.log(
            application_id=app.id,
            step_name="dedup_check",
            executed_by="system",
            executed_by_name="系统自动",
            status="success",
            details=dedup_result
        )
        
        # Step 3: Code generation (atomic)
        generator = CodeGenerator(db)
        material_code = generator.generate(
            classification_id=app.classification_id,
            material_type=app.material_type.value
        )
        
        audit.log(
            application_id=app.id,
            step_name="code_generate",
            executed_by="system",
            executed_by_name="系统自动",
            status="success",
            details={"material_code": material_code}
        )
        
        # Single atomic update for all changes
        crud.update_application(db, app_id, {
            "status": models.ApplicationStatus.PENDING_ADMIN,
            "material_code": material_code,
            "validation_result": val_result,
            "validation_passed": True,
            "dedup_result": dedup_result,
            "is_duplicate": dedup_result["is_duplicate"],
            "submitted_at": datetime.now(timezone.utc)
        })
        
        audit.log(
            application_id=app.id,
            step_name="submit",
            executed_by=user["id"],
            executed_by_name=user["name"],
            status="success",
            details={"material_code": material_code}
        )
        
        return {
            "success": True,
            "message": "申请已提交，等待管理员审批",
            "material_code": material_code,
            "validation": val_result,
            "duplicate_check": dedup_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        audit.log(
            application_id=app.id,
            step_name="submit",
            executed_by=user["id"],
            executed_by_name=user["name"],
            status="failed",
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.post("/{app_id}/admin-approve")
def admin_approve(
    app_id: str,
    data: schemas.ApplicationApprove,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Admin approval step."""
    app = crud.get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="申请单不存在")
    
    if app.status != models.ApplicationStatus.PENDING_ADMIN:
        raise HTTPException(status_code=400, detail="当前状态不是待管理员审批")
    
    audit = AuditService(db)
    
    if not data.approved:
        crud.update_application(db, app_id, {
            "status": models.ApplicationStatus.REJECTED,
            "admin_approved": False,
            "admin_approved_by": user["id"],
            "admin_approved_at": datetime.now(timezone.utc),
            "admin_comment": data.comment
        })
        
        audit.log(
            application_id=app.id,
            step_name="admin_approve",
            executed_by=user["id"],
            executed_by_name=user["name"],
            status="failed",
            details={"approved": False, "comment": data.comment}
        )
        
        return {"success": True, "message": "申请已驳回"}
    
    crud.update_application(db, app_id, {
        "status": models.ApplicationStatus.PENDING_DEPT,
        "admin_approved": True,
        "admin_approved_by": user["id"],
        "admin_approved_at": datetime.now(timezone.utc),
        "admin_comment": data.comment
    })
    
    audit.log(
        application_id=app.id,
        step_name="admin_approve",
        executed_by=user["id"],
        executed_by_name=user["name"],
        status="success",
        details={"approved": True, "comment": data.comment}
    )
    
    return {"success": True, "message": "管理员审批通过，等待部门审批"}


@router.post("/{app_id}/dept-approve")
def dept_approve(
    app_id: str,
    data: schemas.ApplicationApprove,
    user: dict = Depends(require_dept_approver),
    db: Session = Depends(get_db)
):
    """Department approval step."""
    app = crud.get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="申请单不存在")
    
    if app.status != models.ApplicationStatus.PENDING_DEPT:
        raise HTTPException(status_code=400, detail="当前状态不是待部门审批")
    
    audit = AuditService(db)
    
    if not data.approved:
        crud.update_application(db, app_id, {
            "status": models.ApplicationStatus.REJECTED,
            "dept_approved": False,
            "dept_approved_by": user["id"],
            "dept_approved_at": datetime.now(timezone.utc),
            "dept_comment": data.comment
        })
        
        audit.log(
            application_id=app.id,
            step_name="dept_approve",
            executed_by=user["id"],
            executed_by_name=user["name"],
            status="failed",
            details={"approved": False, "comment": data.comment}
        )
        
        return {"success": True, "message": "申请已驳回"}
    
    crud.update_application(db, app_id, {
        "status": models.ApplicationStatus.APPROVED,
        "dept_approved": True,
        "dept_approved_by": user["id"],
        "dept_approved_at": datetime.now(timezone.utc),
        "dept_comment": data.comment
    })
    
    audit.log(
        application_id=app.id,
        step_name="dept_approve",
        executed_by=user["id"],
        executed_by_name=user["name"],
        status="success",
        details={"approved": True, "comment": data.comment}
    )
    
    return {"success": True, "message": "部门审批通过，物料已生效"}


@router.post("/{app_id}/publish")
def publish_application(
    app_id: str,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Publish approved application to Golden Record, BTP, and OpenMetadata."""
    app = crud.get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="申请单不存在")
    
    if app.status != models.ApplicationStatus.APPROVED:
        raise HTTPException(status_code=400, detail="申请未通过审批，不能发布")
    
    audit = AuditService(db)
    
    try:
        # Step 1: Create Golden Record
        gr_data = schemas.GoldenRecordBase(
            material_code=app.material_code,
            material_name=app.material_name,
            material_desc=app.material_desc,
            classification_id=app.classification_id,
            attribute_values=app.attribute_values,
            material_type=app.material_type
        )
        
        gr = crud.create_golden_record(
            db, gr_data, application_id=app.id, user_id=app.created_by
        )
        
        audit.log(
            application_id=app.id,
            golden_record_id=gr.id,
            step_name="create_gr",
            executed_by="system",
            executed_by_name="系统自动",
            status="success",
            details={"material_code": gr.material_code}
        )
        
        # Step 2: Publish to BTP
        btp = BTPMockService()
        btp_result = btp.publish(schemas.GoldenRecordResponse.model_validate(gr))
        
        if btp_result["success"]:
            crud.update_golden_record(db, gr.id, {
                "btp_published": True,
                "btp_published_at": datetime.now(timezone.utc),
                "btp_sync_id": btp_result["sync_id"]
            })
        
        audit.log(
            application_id=app.id,
            golden_record_id=gr.id,
            step_name="publish_btp",
            executed_by="system",
            executed_by_name="系统自动",
            status="success" if btp_result["success"] else "failed",
            details=btp_result
        )
        
        # Step 3: Sync to OpenMetadata
        om = OpenMetadataSync()
        om_result = om.sync_material(schemas.GoldenRecordResponse.model_validate(gr))
        
        if om_result["success"]:
            crud.update_golden_record(db, gr.id, {
                "om_synced": True,
                "om_synced_at": datetime.now(timezone.utc),
                "om_entity_fqn": om_result.get("entity_fqn")
            })
        
        audit.log(
            application_id=app.id,
            golden_record_id=gr.id,
            step_name="sync_om",
            executed_by="system",
            executed_by_name="系统自动",
            status="success" if om_result["success"] else "failed",
            details=om_result
        )
        
        # Step 4: Run OM Quality Tests
        test_result = om.run_quality_tests(schemas.GoldenRecordResponse.model_validate(gr))
        
        audit.log(
            application_id=app.id,
            golden_record_id=gr.id,
            step_name="om_test",
            executed_by="system",
            executed_by_name="系统自动",
            status="success" if test_result["all_passed"] else "failed",
            details=test_result
        )
        
        # Update application status
        crud.update_application(db, app_id, {
            "status": models.ApplicationStatus.PUBLISHED
        })
        
        return {
            "success": True,
            "message": "物料已成功发布",
            "material_code": gr.material_code,
            "golden_record_id": gr.id,
            "btp": btp_result,
            "openmetadata": om_result,
            "quality_tests": test_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        audit.log(
            application_id=app.id,
            step_name="publish",
            executed_by=user["id"],
            executed_by_name=user["name"],
            status="failed",
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=f"发布失败: {str(e)}")


@router.get("/{app_id}/audit")
def get_application_audit(
    app_id: str,
    user: dict = Depends(require_applicant),
    db: Session = Depends(get_db)
):
    """Get full audit trace for an application."""
    app = crud.get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="申请单不存在")
    
    # Authorization check
    if user["role"] == "applicant" and app.created_by != user["id"]:
        raise HTTPException(status_code=403, detail="无权查看此申请单")
    
    audit = AuditService(db)
    return {
        "application_id": app_id,
        "app_no": app.app_no,
        "trace": audit.get_application_trace(app_id)
    }
