"""Pydantic schemas for the stock-data governance service."""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    pass


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


class DataStandardResponse(DataStandardBase):
    id: str
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
