"""Pydantic schemas for the stock-data governance service."""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ========== Data Standards (SPEC §3.1) ==========

class DataStandardBase(BaseModel):
    entity_type: str = Field(..., pattern="^(material|supplier|customer)$")
    sap_table: Optional[str] = Field(None, max_length=50)
    field_name: str = Field(..., min_length=1, max_length=100)
    field_label: str = Field(..., min_length=1, max_length=200)
    data_type: str = Field(..., pattern="^(string|number|date|enum|boolean|amount|text)$")
    max_length: Optional[int] = Field(None, ge=1, le=10000)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    enum_values: Optional[List[str]] = None
    required: bool = False
    pattern: Optional[str] = Field(None, max_length=200)
    unique: bool = False
    business_attrs: Optional[Dict[str, Any]] = None
    owner: Optional[str] = Field(None, max_length=50)
    standard_source: Optional[str] = Field(None, pattern="^(sap|industry|internal)$")
    dept_scope: Optional[List[str]] = None
    description: Optional[str] = None
    sap_field_desc: Optional[str] = None


class DataStandardCreate(DataStandardBase):
    metadata_field_id: Optional[str] = None  # 关联元数据字段；传入时核心字段以登记册为准带入
    # 传 metadata_field_id 时 field_label 可省略（回填登记册标签）；否则保持必填
    field_label: Optional[str] = Field(None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def _require_label_without_registry_link(self):
        """未关联元数据字段时 field_label 必填（保持旧行为不变）。"""
        if not self.metadata_field_id and not self.field_label:
            raise ValueError("未关联元数据字段时 field_label 必填")
        return self


class DataStandardUpdate(BaseModel):
    field_label: Optional[str] = Field(None, min_length=1, max_length=200)
    data_type: Optional[str] = Field(None, pattern="^(string|number|date|enum|boolean|amount|text)$")
    max_length: Optional[int] = Field(None, ge=1, le=10000)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    enum_values: Optional[List[str]] = None
    required: Optional[bool] = None
    pattern: Optional[str] = Field(None, max_length=200)
    unique: Optional[bool] = None
    business_attrs: Optional[Dict[str, Any]] = None
    owner: Optional[str] = Field(None, max_length=50)
    standard_source: Optional[str] = Field(None, pattern="^(sap|industry|internal)$")
    dept_scope: Optional[List[str]] = None
    description: Optional[str] = None
    sap_field_desc: Optional[str] = None
    metadata_field_id: Optional[str] = None  # 传入时按登记册带入核心字段；显式 null 解除关联


class DataStandardResponse(DataStandardBase):
    id: str
    metadata_field_id: Optional[str] = None
    metadata_field_label: Optional[str] = None    # 关联元数据字段标签（api 层装配带出，可空）
    metadata_view_section: Optional[str] = None   # 关联元数据字段视图分区（api 层装配带出，可空）
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DataStandardListResponse(BaseModel):
    total: int
    items: List[DataStandardResponse]


# ========== Quality Checks (SPEC §3.2) ==========

_ENTITY_PATTERN = "^(material|supplier|customer)$"


class QualityCheckRunRequest(BaseModel):
    entity_type: str = Field(..., pattern=_ENTITY_PATTERN)
    entity_ids: Optional[List[str]] = None
    rule_ids: Optional[List[str]] = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "entity_type": "material",
                    "entity_ids": None,
                    "rule_ids": None,
                }
            ]
        }
    )


class QualityCheckRunResponse(BaseModel):
    batch_id: str
    total_checked: int
    passed: int
    failed: int
    skipped: int = 0  # 无数据源跳过的检查数（Phase 2 设计决策 3）


class QualityCheckRuleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    entity_type: str
    rule_type: str
    field_name: Optional[str] = None
    standard_id: Optional[str] = None
    severity: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QualityCheckRuleListResponse(BaseModel):
    total: int
    items: List[QualityCheckRuleResponse]


class QualityCheckBatchSummaryResponse(BaseModel):
    id: str
    entity_type: str
    total_entities: int
    total_checks: int
    passed: int
    failed: int
    skipped_checks: int = 0
    rule_ids: Optional[List[str]] = None
    triggered_by: str
    started_at: datetime
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class QualityCheckBatchListResponse(BaseModel):
    total: int
    items: List[QualityCheckBatchSummaryResponse]


class QualityCheckResultResponse(BaseModel):
    id: str
    rule_id: str
    batch_id: str
    entity_id: str
    entity_type: str
    field_name: Optional[str] = None
    field_value: Optional[str] = None
    severity: str
    message: Optional[str] = None
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QualityCheckResultListResponse(BaseModel):
    total: int
    items: List[QualityCheckResultResponse]


class ReportRuleStat(BaseModel):
    rule_id: str
    rule_name: str
    total: int
    failed: int
    pass_rate: float


class ReportTopIssue(BaseModel):
    field_name: Optional[str] = None
    issue_count: int
    issue_type: Optional[str] = None
    message: Optional[str] = None


class QualityCheckReportResponse(BaseModel):
    batch_id: str
    entity_type: str
    total_entities: int
    total_checks: int
    passed: int
    failed: int
    pass_rate: float
    by_severity: Dict[str, int]
    by_rule: List[ReportRuleStat]
    top_issues: List[ReportTopIssue]


# ========== Suspected Errors (SPEC §3.3) ==========

SuspectedErrorType = Literal["duplicate", "naming", "classification", "unit"]


class SuspectedErrorDetectRequest(BaseModel):
    entity_type: str = Field(..., pattern=_ENTITY_PATTERN)
    error_types: Optional[List[SuspectedErrorType]] = None
    entity_ids: Optional[List[str]] = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "entity_type": "material",
                    "error_types": ["duplicate", "naming"],
                    "entity_ids": None,
                }
            ]
        }
    )


class SuspectedErrorDetectResponse(BaseModel):
    """重检去重结果（SPEC §2.7）：新建 / 刷新 pending / 误报白名单跳过 / 实体消失自动关闭。"""
    created: int
    refreshed: int
    skipped_false_positive: int
    auto_closed: int
    total_pending: int


class SuspectedErrorResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    entity_label: Optional[str] = None
    error_type: str
    severity: str
    title: str
    description: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    status: str
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    matched_entity_id: Optional[str] = None
    detected_at: datetime
    detected_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SuspectedErrorListResponse(BaseModel):
    total: int
    items: List[SuspectedErrorResponse]


class SuspectedErrorResolveRequest(BaseModel):
    # resolved_by 由 JWT 提供，不接受请求体传入（SPEC §3.3）
    status: str = Field(..., pattern="^(confirmed|resolved|false_positive)$")
    resolution_note: Optional[str] = Field(None, max_length=2000)


# ========== Data Import (SPEC Phase 4.1) ==========

class ImportRowError(BaseModel):
    """单行导入失败明细（验收：格式错误行返回明细报告）。row 为 CSV 数据行号，从 1 起（不含表头）。"""
    row: int
    field: Optional[str] = None
    message: str


class PartnerImportResponse(BaseModel):
    entity_type: str
    filename: str
    total_rows: int
    created: int
    updated: int
    failed: int
    errors: List[ImportRowError]


# ========== AI Governance Copilot (TC-AIG-004/009/011) ==========

class TicketDecisionRequest(BaseModel):
    opinion: Optional[str] = Field(None, max_length=2000)
    confirmed: bool = False


class MergeExecuteRequest(BaseModel):
    ticket_id: str = Field(..., min_length=1, max_length=36)

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"ticket_id": "mt-0001"}]}
    )


class GovernanceOwnerCreate(BaseModel):
    role: str = Field(..., pattern="^(owner|steward|approver)$")
    name: str = Field(..., min_length=1, max_length=100)
    department: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(..., min_length=1, max_length=50)
    email: str = Field(..., min_length=3, max_length=254)
    is_active: bool = True


class GovernanceOwnerUpdate(BaseModel):
    role: Optional[str] = Field(None, pattern="^(owner|steward|approver)$")
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    department: Optional[str] = Field(None, min_length=1, max_length=100)
    domain: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[str] = Field(None, min_length=3, max_length=254)
    is_active: Optional[bool] = None


# ========== Metadata (元数据管理) ==========

_METADATA_SOURCE_PATTERN = "^(sap|ariba_slp|internal)$"
_DATA_TYPE_PATTERN = "^(string|number|date|enum|boolean|amount|text)$"
_SENSITIVITY_PATTERN = "^(public|internal|confidential)$"


class MetadataFieldBase(BaseModel):
    entity_type: str = Field(..., pattern=_ENTITY_PATTERN)
    sap_table: Optional[str] = Field(None, max_length=50)
    field_name: str = Field(..., min_length=1, max_length=100)
    field_label: str = Field(..., min_length=1, max_length=200)
    data_type: str = Field(..., pattern=_DATA_TYPE_PATTERN)
    max_length: Optional[int] = Field(None, ge=1, le=10000)
    view_section: Optional[str] = Field(None, max_length=100)
    business_definition: Optional[str] = None
    standard_source: Optional[str] = Field(None, pattern=_METADATA_SOURCE_PATTERN)
    must_govern: bool = False
    glossary_term_id: Optional[str] = None
    is_active: bool = True


class MetadataFieldCreate(MetadataFieldBase):
    pass


class MetadataFieldUpdate(BaseModel):
    field_label: Optional[str] = Field(None, min_length=1, max_length=200)
    data_type: Optional[str] = Field(None, pattern=_DATA_TYPE_PATTERN)
    max_length: Optional[int] = Field(None, ge=1, le=10000)
    view_section: Optional[str] = Field(None, max_length=100)
    business_definition: Optional[str] = None
    standard_source: Optional[str] = Field(None, pattern=_METADATA_SOURCE_PATTERN)
    must_govern: Optional[bool] = None
    glossary_term_id: Optional[str] = None
    is_active: Optional[bool] = None


class MetadataFieldResponse(MetadataFieldBase):
    id: str
    glossary_term_name: Optional[str] = None  # 关联业务术语名（GET 列表端点批量装配带出，可空）
    standard_count: int = 0                   # 引用该字段的数据标准数（GET 列表端点批量装配带出）
    # 字段治理状态（enrich_field_governance 装配；POST/PUT 单条响应亦走同一口径）
    quality_rule_count: int = 0               # 经标准关联的质量规则数（无规则 = 未纳入规则治理）
    latest_batch_id: Optional[str] = None     # 该实体最近一次检测批次 id（从未检测为 None）
    latest_batch_failed: int = 0              # 最新批次中该字段失败数（0 = 达标，>0 = 待修复）
    latest_checked_at: Optional[datetime] = None  # 最新批次执行时间
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MetadataFieldListResponse(BaseModel):
    total: int
    items: List[MetadataFieldResponse]


class MetadataEntityBase(BaseModel):
    entity_type: str = Field(..., pattern=_ENTITY_PATTERN)
    display_name: str = Field(..., min_length=1, max_length=200)
    business_definition: Optional[str] = None
    data_owner: Optional[str] = Field(None, max_length=50)
    dept: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    sensitivity_level: Optional[str] = Field(None, pattern=_SENSITIVITY_PATTERN)


class MetadataEntityUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    business_definition: Optional[str] = None
    data_owner: Optional[str] = Field(None, max_length=50)
    dept: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    sensitivity_level: Optional[str] = Field(None, pattern=_SENSITIVITY_PATTERN)


class MetadataEntityResponse(MetadataEntityBase):
    id: str
    governed_field_count: int  # 该实体下 must_govern=True 的元数据字段数（service 装配）
    total_field_count: int     # 该实体下元数据字段总数（service 装配）
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GlossaryTermBase(BaseModel):
    term: str = Field(..., min_length=1, max_length=200)
    definition: str = Field(..., min_length=1)
    aliases: Optional[List[str]] = None


class GlossaryTermCreate(GlossaryTermBase):
    pass


class GlossaryTermUpdate(BaseModel):
    definition: Optional[str] = Field(None, min_length=1)
    aliases: Optional[List[str]] = None


class GlossaryTermResponse(GlossaryTermBase):
    id: str
    field_count: int = 0  # 关联的元数据字段数（列表与写响应均装配真实计数）
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ========== Records 存量纠正（字段治理闭环修复环节） ==========

class RecordFieldFixRequest(BaseModel):
    field_name: str = Field(..., min_length=1, max_length=100)
    # None / 空串表示清除该字段键（仅允许标准非必填字段；必填与编码列拒绝）
    value: Any = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"field_name": "material_desc", "value": "不锈钢法兰 DN50 PN16"}
            ]
        }
    )


class RecordFieldFixResponse(BaseModel):
    record_id: str
    entity_type: str
    field_name: str     # 规范化字段名（以数据标准登记为准）
    old_value: Any = None
    new_value: Any = None
    updated_at: datetime
