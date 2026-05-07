"""SQLAlchemy models for Material Master Data Governance."""
import uuid
from datetime import datetime, timezone

def _now_utc():
    return datetime.now(timezone.utc)
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship

from app.core.database import Base


# ========== Enums ==========

class MaterialType(str, PyEnum):
    RAW = "raw"
    SEMI = "semi"
    FINISHED = "finished"
    AUXILIARY = "auxiliary"
    SPARE = "spare"


class ApplicationStatus(str, PyEnum):
    DRAFT = "draft"
    PENDING_ADMIN = "pending_admin"
    PENDING_DEPT = "pending_dept"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class GoldenRecordStatus(str, PyEnum):
    ACTIVE = "active"
    OBSOLETE = "obsolete"


class StepName(str, PyEnum):
    CREATE_DRAFT = "create_draft"
    SAVE_DRAFT = "save_draft"
    SUBMIT = "submit"
    VALIDATE = "validate"
    DEDUP_CHECK = "dedup_check"
    CODE_GENERATE = "code_generate"
    ADMIN_APPROVE = "admin_approve"
    DEPT_APPROVE = "dept_approve"
    CREATE_GR = "create_gr"
    PUBLISH_BTP = "publish_btp"
    SYNC_OM = "sync_om"
    OM_TEST = "om_test"
    REVOKE = "revoke"
    EDIT = "edit"
    REVISE = "revise"


# ========== Models ==========

class MaterialClassification(Base):
    """物料分类（三级：大类 + 中类 + 小类）"""
    __tablename__ = "material_classifications"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_id = Column(String(36), ForeignKey("material_classifications.id"), nullable=True)
    code = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    level = Column(Integer, nullable=False)  # 1=大类, 2=中类, 3=小类
    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)
    
    parent = relationship("MaterialClassification", remote_side=[id], back_populates="children")
    children = relationship("MaterialClassification", back_populates="parent")
    templates = relationship("AttributeTemplate", back_populates="classification")


class AttributeTemplate(Base):
    """属性模板（按分类定义字段）"""
    __tablename__ = "attribute_templates"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    classification_id = Column(String(36), ForeignKey("material_classifications.id"), nullable=False)
    field_name = Column(String(50), nullable=False)
    field_label = Column(String(100), nullable=False)
    field_type = Column(String(20), nullable=False)  # text, number, date, select, boolean
    is_required = Column(Boolean, default=False)
    default_value = Column(String(200), nullable=True)
    options = Column(JSON, nullable=True)  # 下拉选项 ["选项A", "选项B"]
    sort_order = Column(Integer, default=0)
    description = Column(Text, nullable=True)
    
    classification = relationship("MaterialClassification", back_populates="templates")


class MaterialApplication(Base):
    """物料申请单"""
    __tablename__ = "material_applications"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    app_no = Column(String(20), unique=True, nullable=False, index=True)  # 申请编号 SQ-2026-00001
    
    # 基本信息
    material_name = Column(String(200), nullable=False)
    material_desc = Column(Text, nullable=True)
    classification_id = Column(String(36), ForeignKey("material_classifications.id"), nullable=False)
    material_type = Column(Enum(MaterialType), nullable=False)
    
    # 属性值（JSON存储动态字段）
    attribute_values = Column(JSON, nullable=True)
    attachments = Column(JSON, nullable=True)
    
    # 编码
    material_code = Column(String(50), nullable=True, index=True)
    code_rule_id = Column(String(36), nullable=True)
    
    # 状态
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.DRAFT)
    
    # 质量校验结果
    validation_result = Column(JSON, nullable=True)
    validation_passed = Column(Boolean, default=False)
    
    # 重复预检结果
    dedup_result = Column(JSON, nullable=True)
    is_duplicate = Column(Boolean, default=False)
    
    # 申请人信息
    created_by = Column(String(50), nullable=False)
    created_by_name = Column(String(100), nullable=True)
    department = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)
    submitted_at = Column(DateTime, nullable=True)
    
    # 审批信息
    admin_approved_by = Column(String(50), nullable=True)
    admin_approved_at = Column(DateTime, nullable=True)
    admin_approved = Column(Boolean, default=False)
    admin_comment = Column(Text, nullable=True)
    
    dept_approved_by = Column(String(50), nullable=True)
    dept_approved_at = Column(DateTime, nullable=True)
    dept_approved = Column(Boolean, default=False)
    dept_comment = Column(Text, nullable=True)
    
    # 关联
    classification = relationship("MaterialClassification")
    golden_record = relationship("GoldenRecord", back_populates="application", uselist=False)
    audit_logs = relationship("AuditLog", back_populates="application", order_by="AuditLog.executed_at")


class CodeRule(Base):
    """编码规则"""
    __tablename__ = "code_rules"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    pattern = Column(String(200), nullable=False)  # 编码模板：{大类}-{小类}-{流水}
    prefix = Column(String(10), nullable=True)
    suffix = Column(String(10), nullable=True)
    current_seq = Column(Integer, default=0)
    seq_length = Column(Integer, default=5)
    classification_id = Column(String(36), ForeignKey("material_classifications.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)


class GoldenRecord(Base):
    """物料主数据 Golden Record"""
    __tablename__ = "golden_records"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String(36), ForeignKey("material_applications.id"), unique=True)
    
    # 编码
    material_code = Column(String(50), unique=True, nullable=False, index=True)
    material_name = Column(String(200), nullable=False)
    material_desc = Column(Text, nullable=True)
    
    # 分类
    classification_id = Column(String(36), ForeignKey("material_classifications.id"), nullable=False)
    classification_path = Column(String(200), nullable=True)
    
    # 属性值
    attribute_values = Column(JSON, nullable=True)
    material_type = Column(Enum(MaterialType), nullable=False)
    
    # 状态
    status = Column(Enum(GoldenRecordStatus), default=GoldenRecordStatus.ACTIVE)
    
    # 版本控制
    version = Column(Integer, default=1)
    revision = Column(Integer, default=1)
    
    # 发布信息
    btp_published = Column(Boolean, default=False)
    btp_published_at = Column(DateTime, nullable=True)
    btp_sync_id = Column(String(50), nullable=True)
    
    om_synced = Column(Boolean, default=False)
    om_synced_at = Column(DateTime, nullable=True)
    om_entity_fqn = Column(String(200), nullable=True)
    
    # 审计
    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=_now_utc)
    updated_by = Column(String(50), nullable=True)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)
    
    # 关联
    application = relationship("MaterialApplication", back_populates="golden_record")
    classification = relationship("MaterialClassification")


class AuditLog(Base):
    """全链路审计日志"""
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    step_id = Column(String(20), nullable=False, index=True)  # SQ-2026-00001-S1
    
    # 关联
    application_id = Column(String(36), ForeignKey("material_applications.id"), nullable=True)
    golden_record_id = Column(String(36), ForeignKey("golden_records.id"), nullable=True)
    
    # 步骤信息
    step_name = Column(Enum(StepName), nullable=False)
    step_label = Column(String(50), nullable=False)
    
    # 执行信息
    executed_by = Column(String(50), nullable=False)
    executed_by_name = Column(String(100), nullable=True)
    executed_at = Column(DateTime, default=_now_utc)
    
    # 状态
    status = Column(String(20), nullable=False)  # success, failed, pending
    status_label = Column(String(50), nullable=True)
    
    # 详情
    details = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # 关联
    application = relationship("MaterialApplication", back_populates="audit_logs")


class ExternalSystemLog(Base):
    """外部系统交互日志（OpenMetadata / BTP）"""
    __tablename__ = "external_system_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    system_name = Column(String(20), nullable=False)  # openmetadata, btp
    operation = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=True)  # material, supplier
    entity_id = Column(String(50), nullable=True)
    
    request_payload = Column(JSON, nullable=True)
    response_payload = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False)  # success, failed, timeout
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    
    executed_at = Column(DateTime, default=_now_utc)
    duration_ms = Column(Integer, nullable=True)
