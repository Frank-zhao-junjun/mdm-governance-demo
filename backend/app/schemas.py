"""Pydantic schemas for API request/response models."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


# ========== Enums ==========

class MaterialType(str, Enum):
    RAW = "raw"
    SEMI = "semi"
    FINISHED = "finished"
    AUXILIARY = "auxiliary"
    SPARE = "spare"


class ApplicationStatus(str, Enum):
    DRAFT = "draft"
    PENDING_ADMIN = "pending_admin"
    PENDING_DEPT = "pending_dept"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


# ========== Classification ==========

class ClassificationBase(BaseModel):
    code: str = Field(..., max_length=10)
    name: str = Field(..., max_length=100)
    level: int = Field(..., ge=1, le=3)
    parent_id: Optional[str] = None
    description: Optional[str] = None


class ClassificationCreate(ClassificationBase):
    pass


class ClassificationResponse(ClassificationBase):
    id: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    children: List["ClassificationResponse"] = []
    
    model_config = ConfigDict(from_attributes=True)


ClassificationResponse.model_rebuild()


# ========== Attribute Template ==========

class AttributeTemplateBase(BaseModel):
    classification_id: str
    field_name: str = Field(..., max_length=50)
    field_label: str = Field(..., max_length=100)
    field_type: str = Field(..., pattern="^(text|number|date|select|boolean)$")
    is_required: bool = False
    default_value: Optional[str] = None
    options: Optional[List[str]] = None
    sort_order: int = 0
    description: Optional[str] = None


class AttributeTemplateCreate(AttributeTemplateBase):
    pass


class AttributeTemplateResponse(AttributeTemplateBase):
    id: str
    
    model_config = ConfigDict(from_attributes=True)


# ========== Material Application ==========

class ApplicationBase(BaseModel):
    material_name: str = Field(..., max_length=200)
    material_desc: Optional[str] = None
    classification_id: str
    material_type: MaterialType
    attribute_values: Optional[Dict[str, Any]] = None
    attachments: Optional[List[Dict[str, Any]]] = None


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationDraftSave(BaseModel):
    id: Optional[str] = None
    material_name: Optional[str] = None
    material_desc: Optional[str] = None
    classification_id: Optional[str] = None
    material_type: Optional[MaterialType] = None
    attribute_values: Optional[Dict[str, Any]] = None
    attachments: Optional[List[Dict[str, Any]]] = None


class ApplicationSubmit(BaseModel):
    id: str


class ApplicationApprove(BaseModel):
    comment: Optional[str] = None
    approved: bool = True


class ValidationResult(BaseModel):
    passed: bool
    checks: List[Dict[str, Any]] = []
    errors: List[str] = []


class DedupResult(BaseModel):
    is_duplicate: bool
    confidence: float = 0.0
    similar_materials: List[Dict[str, Any]] = []


class ApplicationResponse(ApplicationBase):
    id: str
    app_no: str
    material_code: Optional[str] = None
    status: ApplicationStatus
    validation_passed: bool
    is_duplicate: bool
    validation_result: Optional[Dict[str, Any]] = None
    dedup_result: Optional[Dict[str, Any]] = None
    created_by: str
    created_by_name: Optional[str] = None
    department: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = None
    admin_approved: bool
    admin_approved_by: Optional[str] = None
    admin_approved_at: Optional[datetime] = None
    admin_comment: Optional[str] = None
    dept_approved: bool
    dept_approved_by: Optional[str] = None
    dept_approved_at: Optional[datetime] = None
    dept_comment: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ========== Code Rule ==========

class CodeRuleBase(BaseModel):
    name: str
    pattern: str
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    seq_length: int = 5
    classification_id: Optional[str] = None
    is_active: bool = True


class CodeRuleCreate(CodeRuleBase):
    pass


class CodeRuleResponse(CodeRuleBase):
    id: str
    current_seq: int = 0
    description: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ========== Golden Record ==========

class GoldenRecordBase(BaseModel):
    material_code: str
    material_name: str
    material_desc: Optional[str] = None
    classification_id: str
    attribute_values: Optional[Dict[str, Any]] = None
    material_type: MaterialType


class GoldenRecordResponse(GoldenRecordBase):
    id: str
    application_id: Optional[str] = None
    classification_path: Optional[str] = None
    status: str
    version: int = 1
    revision: int = 1
    btp_published: bool = False
    btp_published_at: Optional[datetime] = None
    om_synced: bool = False
    om_synced_at: Optional[datetime] = None
    om_entity_fqn: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ========== Audit Log ==========

class AuditLogResponse(BaseModel):
    id: str
    step_id: str
    step_name: str
    step_label: str
    executed_by: str
    executed_by_name: Optional[str] = None
    executed_at: datetime
    status: str
    status_label: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ========== Dashboard ==========

class DashboardStats(BaseModel):
    total_applications: int
    pending_admin: int
    pending_dept: int
    approved: int
    rejected: int
    published: int
    total_golden_records: int
    total_classifications: int
    recent_applications: List[ApplicationResponse] = []
    recent_audit_logs: List[AuditLogResponse] = []
