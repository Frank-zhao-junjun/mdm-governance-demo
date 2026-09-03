"""SQLAlchemy models for the stock-data governance service (SPEC v1.3).

Scope: data standards + quality checks over stock records only.
Application/approval/golden-record/publish flows were removed from this
codebase (SPEC §1.4) — upstream systems own data creation and distribution.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Integer, Boolean, Text, DateTime, Float, ForeignKey,
    JSON, Enum, UniqueConstraint,
)

from app.core.database import Base


def _now_utc():
    return datetime.now(timezone.utc)


# ========== Enums ==========

class StepName(str, PyEnum):
    """Audit step names for governance write operations (SPEC §3.0)."""
    STANDARD_CREATE = "standard_create"
    STANDARD_UPDATE = "standard_update"
    STANDARD_DELETE = "standard_delete"
    QUALITY_RUN = "quality_run"
    ERROR_DETECT = "error_detect"
    ERROR_RESOLVE = "error_resolve"
    DATA_IMPORT = "data_import"
    METADATA_ENTITY_UPDATE = "metadata_entity_update"
    METADATA_FIELD_CREATE = "metadata_field_create"
    METADATA_FIELD_UPDATE = "metadata_field_update"
    GLOSSARY_CREATE = "glossary_create"
    GLOSSARY_UPDATE = "glossary_update"


class RuleType(str, PyEnum):
    """质量检测规则类型（SPEC §2.4）。无 custom_check：可配置 SQL 即注入口子。"""
    NULL_CHECK = "null_check"
    FORMAT_CHECK = "format_check"
    RANGE_CHECK = "range_check"
    LENGTH_CHECK = "length_check"
    UNIQUE_CHECK = "unique_check"
    DUPLICATE_CHECK = "duplicate_check"


class TicketStatus(str, PyEnum):
    """AI 治理工单状态（TC-AIG-002）。"""
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    DONE = "done"
    FAILED = "failed"


class EscalationLevel(str, PyEnum):
    """工单 SLA 升级层级（TC-AIG-007）。"""
    NONE = "none"
    DEPT_HEAD = "dept_head"
    COMMITTEE = "committee"


# ========== Models ==========

class DataStandard(Base):
    """数据标准定义（存量治理唯一规则体系，SPEC §2.1）"""
    __tablename__ = "data_standards"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 实体信息
    entity_type = Column(String(50), nullable=False, index=True)  # material / supplier / customer
    sap_table = Column(String(50), nullable=True)  # MARA / BUT000 / LFA1 / KNA1
    field_name = Column(String(100), nullable=False)  # MATNR / MAKTX / NAME1 等
    field_label = Column(String(200), nullable=False)  # 字段中文标签

    # 数据属性（结构化列，SPEC §1.5.2）
    data_type = Column(String(50), nullable=False)  # string / number / date / enum / boolean / amount / text
    max_length = Column(Integer, nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    enum_values = Column(JSON, nullable=True)  # ["A", "B", "C"]

    # 校验规则
    required = Column(Boolean, default=False)
    pattern = Column(String(200), nullable=True)  # 正则（格式校验）
    unique = Column(Boolean, default=False)

    # 业务属性（展示型元数据进 JSON，SPEC §1.5 承接）
    business_attrs = Column(JSON, nullable=True)  # {"standard_topic": "...", "standard_subcategory": "..."}
    # 管理属性（结构化列，SPEC §1.5 承接）
    owner = Column(String(50), nullable=True)            # 标准定义人
    standard_source = Column(String(20), nullable=True)  # sap / industry / internal
    dept_scope = Column(JSON, nullable=True)             # 应用部门列表

    # 元数据
    description = Column(Text, nullable=True)
    sap_field_desc = Column(Text, nullable=True)
    metadata_field_id = Column(String(36), ForeignKey("metadata_field.id"), nullable=True)  # 关联元数据字段
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)

    __table_args__ = (
        UniqueConstraint("entity_type", "sap_table", "field_name", name="uq_entity_table_field"),
    )


class MaterialRecord(Base):
    """物料主数据存量记录（SAP MARA 风格，SPEC §2.2）"""
    __tablename__ = "material_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    material_code = Column(String(50), nullable=False, index=True)  # MATNR
    material_name = Column(String(200), nullable=False)             # MAKTX 冗余存储
    attributes = Column(JSON, nullable=False, default=dict)         # SAP 字段名 → 值
    source_system = Column(String(50), nullable=False, default="mock_sap")
    status = Column(String(20), nullable=False, default="active")   # active / inactive
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)

    __table_args__ = (
        UniqueConstraint("material_code", name="uq_material_code"),
    )


class PartnerRecord(Base):
    """供应商/客户主数据存量记录（SAP BP 风格，SPEC §2.3）"""
    __tablename__ = "partner_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50), nullable=False, index=True)   # supplier / customer
    partner_code = Column(String(50), nullable=False, index=True)  # LIFNR / KUNNR
    partner_name = Column(String(200), nullable=False)             # NAME1 冗余存储
    attributes = Column(JSON, nullable=False, default=dict)        # SAP 字段名 → 值
    source_system = Column(String(50), nullable=False, default="mock_sap")
    status = Column(String(20), nullable=False, default="active")  # active / inactive
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)

    __table_args__ = (
        UniqueConstraint("entity_type", "partner_code", name="uq_entity_partner_code"),
    )


class QualityCheckRule(Base):
    """质量检测规则（SPEC §2.4）"""
    __tablename__ = "quality_check_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    entity_type = Column(String(50), nullable=False, index=True)
    rule_type = Column(
        Enum(RuleType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    field_name = Column(String(100), nullable=True)
    standard_id = Column(String(36), ForeignKey("data_standards.id"), nullable=True)
    rule_config = Column(JSON, nullable=False)
    severity = Column(String(20), nullable=False, default="error")  # error / warning / info
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)


class QualityCheckBatch(Base):
    """一次质量检测执行的批次记录（SPEC §2.5）"""
    __tablename__ = "quality_check_batches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50), nullable=False, index=True)
    total_entities = Column(Integer, nullable=False)
    total_checks = Column(Integer, nullable=False)
    passed = Column(Integer, nullable=False)
    failed = Column(Integer, nullable=False)
    skipped_checks = Column(Integer, nullable=False, default=0)  # 无数据源跳过的检查数（Phase 2 设计决策 3）
    rule_ids = Column(JSON, nullable=False)
    triggered_by = Column(String(50), nullable=False)
    started_at = Column(DateTime, default=_now_utc)
    finished_at = Column(DateTime, nullable=True)


class QualityCheckResult(Base):
    """质量检测结果，仅持久化未通过项（SPEC §2.6）"""
    __tablename__ = "quality_check_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = Column(String(36), ForeignKey("quality_check_rules.id"), nullable=False)
    batch_id = Column(String(36), ForeignKey("quality_check_batches.id"), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False)
    entity_type = Column(String(50), nullable=False, index=True)
    field_name = Column(String(100), nullable=True)
    field_value = Column(String(500), nullable=True)
    severity = Column(String(20), nullable=False)
    message = Column(Text, nullable=True)
    checked_at = Column(DateTime, default=_now_utc, index=True)


class SuspectedError(Base):
    """疑似错误，进入人工确认流程（SPEC §2.7）"""
    __tablename__ = "suspected_errors"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False)
    entity_label = Column(String(200), nullable=True)

    error_type = Column(String(50), nullable=False)  # duplicate / naming / classification / unit
    severity = Column(String(20), nullable=False, default="warning")
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)

    status = Column(String(20), nullable=False, default="pending")
    resolved_by = Column(String(50), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)
    matched_entity_id = Column(String(36), nullable=True, index=True)

    detected_at = Column(DateTime, default=_now_utc, index=True)
    detected_by = Column(String(50), nullable=True)


class AuditLog(Base):
    """治理操作审计日志（SPEC §3.0）"""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    step_id = Column(String(50), nullable=False, index=True)

    # 步骤信息
    step_name = Column(
        Enum(StepName, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    step_label = Column(String(50), nullable=False)

    # 执行信息
    executed_by = Column(String(50), nullable=False)
    executed_by_name = Column(String(100), nullable=True)
    executed_at = Column(DateTime, default=_now_utc)

    # 状态
    status = Column(String(20), nullable=False)  # success / failed
    status_label = Column(String(50), nullable=True)

    # 详情
    details = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)


class QualityTicket(Base):
    """数据质量问题工单（TC-AIG-002）。"""
    __tablename__ = "quality_ticket"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String(64), nullable=False, index=True)
    application_id = Column(String(36), nullable=True)
    golden_record_id = Column(String(36), nullable=True)
    rule_key = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)
    issue_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(
        Enum(TicketStatus, values_callable=lambda enum: [member.value for member in enum]),
        nullable=False,
        default=TicketStatus.DRAFT,
    )
    assignee_owner_id = Column(String(36), nullable=True)
    sla_due_at = Column(DateTime, nullable=True)
    escalated_level = Column(
        Enum(EscalationLevel, values_callable=lambda enum: [member.value for member in enum]),
        nullable=False,
        default=EscalationLevel.NONE,
    )
    evidence_json = Column(JSON, nullable=True)
    trace_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)


class MergeTicket(Base):
    """金标归并建议及人工裁决工单（TC-AIG-003）。"""
    __tablename__ = "merge_ticket"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String(64), nullable=False, index=True)
    candidate_golden_ids = Column(JSON, nullable=False)
    suggested_golden_id = Column(String(36), nullable=True)
    evidence_json = Column(JSON, nullable=True)
    status = Column(
        Enum(TicketStatus, values_callable=lambda enum: [member.value for member in enum]),
        nullable=False,
        default=TicketStatus.DRAFT,
    )
    factory_agreements_json = Column(JSON, nullable=True)
    escalated_level = Column(
        Enum(EscalationLevel, values_callable=lambda enum: [member.value for member in enum]),
        nullable=False,
        default=EscalationLevel.NONE,
    )
    decided_by = Column(String(36), nullable=True)
    decision_opinion = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    trace_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)


class KeyMapping(Base):
    """源系统编码到金标记录的唯一映射（TC-MAP-001）。"""
    __tablename__ = "key_mapping"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    golden_record_id = Column(String(36), nullable=False, index=True)
    source_system = Column(String(50), nullable=False)
    source_code = Column(String(100), nullable=False)
    mapping_type = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=_now_utc)

    __table_args__ = (
        UniqueConstraint("source_system", "source_code", name="uq_key_mapping_source_code"),
    )


class AgentTrace(Base):
    """Agent 运行与裁决依据快照（TC-AIG-011）。"""
    __tablename__ = "agent_trace"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trace_id = Column(String(64), nullable=False, unique=True, index=True)
    agent_name = Column(String(100), nullable=False)
    model_version = Column(String(100), nullable=True)
    input_summary = Column(Text, nullable=False)
    evidence_refs_json = Column(JSON, nullable=True)
    decision_snapshot_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_now_utc)


class GovernanceOwner(Base):
    """治理责任人、数据管家与审批人目录。"""
    __tablename__ = "governance_owner"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    role = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    domain = Column(String(50), nullable=False)
    email = Column(String(254), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)


class ApprovalEvidence(Base):
    """人工审批操作及当时可见证据的不可变快照。"""
    __tablename__ = "approval_evidence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_type = Column(String(20), nullable=False)
    ticket_id = Column(String(36), nullable=False, index=True)
    approver_id = Column(String(36), nullable=False, index=True)
    action = Column(String(20), nullable=False)
    opinion = Column(Text, nullable=True)
    snapshot_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_now_utc)


class MetadataField(Base):
    """元数据字段定义（实体下 SAP 表字段的业务语义与治理属性）。"""
    __tablename__ = "metadata_field"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50), nullable=False)  # material / supplier / customer
    sap_table = Column(String(50), nullable=True)     # MARA / BUT000 / LFA1 / KNA1
    field_name = Column(String(100), nullable=False)  # MATNR / MAKTX / NAME1 等
    field_label = Column(String(200), nullable=False)  # 字段中文标签
    data_type = Column(String(50), nullable=False)    # string / number / date / enum / boolean / amount / text
    max_length = Column(Integer, nullable=True)
    view_section = Column(String(100), nullable=True)  # 视图分区（如 基本数据 / 采购视图）
    business_definition = Column(Text, nullable=True)
    standard_source = Column(String(20), nullable=True)  # sap / ariba_slp / internal
    must_govern = Column(Boolean, default=False)         # 是否必须治理
    glossary_term_id = Column(String(36), ForeignKey("glossary_term.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)

    __table_args__ = (
        UniqueConstraint("entity_type", "sap_table", "field_name", name="uq_metadata_entity_table_field"),
    )


class MetadataEntity(Base):
    """元数据实体定义（物料/供应商/客户等主数据实体级治理属性）。"""
    __tablename__ = "metadata_entity"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50), nullable=False, unique=True, index=True)
    display_name = Column(String(200), nullable=False)
    business_definition = Column(Text, nullable=True)
    data_owner = Column(String(50), nullable=True)
    dept = Column(String(100), nullable=True)
    tags = Column(JSON, nullable=True)
    sensitivity_level = Column(String(20), nullable=True)  # public / internal / confidential
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)


class GlossaryTerm(Base):
    """业务术语表（元数据字段可引用的统一定义词条）。"""
    __tablename__ = "glossary_term"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    term = Column(String(200), nullable=False, unique=True)
    definition = Column(Text, nullable=False)
    aliases = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)
