/** 存量数据治理前端类型定义（与 backend/app/schemas.py 字段一一对应） */

// ========== 认证 ==========

export type UserRole = 'applicant' | 'admin' | 'data_admin' | 'dept_approver';

export interface User {
  id: string;
  name: string;
  role: UserRole;
  department: string;
}

// ========== 数据标准（SPEC §2.1 / §3.1） ==========

export type EntityType = 'material' | 'supplier' | 'customer';

/** 与 schemas.DataStandardBase.data_type 的 pattern 一致 */
export type StandardDataType =
  | 'string'
  | 'number'
  | 'date'
  | 'enum'
  | 'boolean'
  | 'amount'
  | 'text';

/** 与 schemas.DataStandardBase.standard_source 的 pattern 一致 */
export type StandardSource = 'sap' | 'industry' | 'internal';

/** 业务属性（标准主题 / 标准小类等展示型元数据），落 data_standards.business_attrs JSON 列 */
export interface DataStandardBusinessAttrs {
  standard_topic?: string | null;
  standard_subcategory?: string | null;
  [key: string]: unknown;
}

/** POST /api/data-standards 请求体（= schemas.DataStandardCreate） */
export interface DataStandardCreatePayload {
  entity_type: EntityType;
  sap_table?: string | null;
  field_name: string;
  field_label: string;
  data_type: StandardDataType;
  max_length?: number | null;
  min_value?: number | null;
  max_value?: number | null;
  enum_values?: string[] | null;
  required?: boolean;
  pattern?: string | null;
  unique?: boolean;
  business_attrs?: DataStandardBusinessAttrs | null;
  owner?: string | null;
  standard_source?: StandardSource | null;
  dept_scope?: string[] | null;
  description?: string | null;
  sap_field_desc?: string | null;
  /** 关联的元数据字段 ID（可空；非空时后端以登记册为准带入身份键与类型属性） */
  metadata_field_id?: string | null;
}

/**
 * PUT /api/data-standards/{id} 请求体（= schemas.DataStandardUpdate）。
 * 注意：entity_type / sap_table / field_name 为身份键，后端不接受更新；
 * metadata_field_id 允许变更（改挂/解除关联），非空时后端仍以登记册为准带入。
 */
export interface DataStandardUpdatePayload {
  field_label?: string | null;
  data_type?: StandardDataType | null;
  max_length?: number | null;
  min_value?: number | null;
  max_value?: number | null;
  enum_values?: string[] | null;
  required?: boolean | null;
  pattern?: string | null;
  unique?: boolean | null;
  business_attrs?: DataStandardBusinessAttrs | null;
  owner?: string | null;
  standard_source?: StandardSource | null;
  dept_scope?: string[] | null;
  description?: string | null;
  sap_field_desc?: string | null;
  /** 关联的元数据字段 ID（可空；置 null 表示解除关联） */
  metadata_field_id?: string | null;
}

/** GET /api/data-standards 响应项（= schemas.DataStandardResponse） */
export interface DataStandard extends DataStandardCreatePayload {
  id: string;
  entity_type: EntityType;
  field_name: string;
  field_label: string;
  data_type: StandardDataType;
  required: boolean;
  unique: boolean;
  /** 关联的元数据字段 ID（可空） */
  metadata_field_id?: string | null;
  /** 关联元数据字段标签（api 层装配带出，可空） */
  metadata_field_label?: string | null;
  /** 关联元数据字段视图分区（api 层装配带出，可空） */
  metadata_view_section?: string | null;
  created_at: string;
  updated_at: string;
}

/** GET /api/data-standards 响应（= schemas.DataStandardListResponse） */
export interface DataStandardListResponse {
  total: number;
  items: DataStandard[];
}

/** GET /api/data-standards 查询参数 */
export interface DataStandardQuery {
  entity_type?: EntityType;
  sap_table?: string;
  skip?: number;
  limit?: number;
}

// ========== AI Governance Copilot ==========

export type GovernanceTicketType = 'quality' | 'merge';
export type GovernanceTicketStatus = 'draft' | 'pending' | 'approved' | 'rejected' | 'executing' | 'done' | 'failed';

export interface GovernanceTicket {
  id: string;
  ticket_type: GovernanceTicketType;
  request_id: string;
  status: GovernanceTicketStatus;
  evidence_json: Record<string, unknown> | null;
  trace_id: string | null;
  created_at: string;
}

export interface TodoListResponse {
  total: number;
  items: GovernanceTicket[];
}

export interface GovernanceReport {
  quality_score: number;
  duplicate_rate: number;
  pending_todos: number;
  agent_activity: number;
}

export interface AgentTrace {
  id: string;
  trace_id: string;
  agent_name: string;
  model_version: string | null;
  input_summary: string;
  evidence_refs_json: unknown;
  decision_snapshot_json: unknown;
  created_at: string;
}

export interface ApprovalEvidence {
  id: string;
  ticket_type: GovernanceTicketType;
  ticket_id: string;
  approver_id: string;
  action: 'approve' | 'reject' | 'overturn';
  opinion: string | null;
  snapshot_json: Record<string, unknown> | null;
  created_at: string;
}

export interface AccountabilityResponse {
  ticket: GovernanceTicket;
  trace: AgentTrace | null;
  approval_evidence: ApprovalEvidence[];
}

export interface GovernanceOwner {
  id: string;
  role: 'owner' | 'steward' | 'approver';
  name: string;
  department: string;
  domain: string;
  email: string;
  is_active: boolean;
}

// ========== 质量检测（SPEC §3.2 / §5） ==========

/** 与 backend/app/models.py RuleType 落库名一致（v1 五种规则） */
export type RuleType = 'null_check' | 'format_check' | 'range_check' | 'length_check' | 'unique_check';

/** 与 backend quality_checks.py _SEVERITIES 三档一致 */
export type CheckSeverity = 'error' | 'warning' | 'info';

/** POST /api/quality-checks/run 请求体（= schemas.QualityCheckRunRequest） */
export interface QualityRunPayload {
  entity_type: EntityType;
  entity_ids?: string[] | null;
  rule_ids?: string[] | null;
}

/** POST /api/quality-checks/run 响应（= schemas.QualityCheckRunResponse） */
export interface QualityRunResponse {
  batch_id: string;
  total_checked: number;
  passed: number;
  failed: number;
  /** 无数据源跳过的检查数（Phase 2 设计决策 3） */
  skipped: number;
}

/** GET /api/quality-checks/rules 响应项（= schemas.QualityCheckRuleResponse） */
export interface QualityCheckRule {
  id: string;
  name: string;
  description: string | null;
  entity_type: EntityType;
  rule_type: RuleType;
  field_name: string | null;
  standard_id: string | null;
  severity: CheckSeverity;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** GET /api/quality-checks/rules 响应（= schemas.QualityCheckRuleListResponse） */
export interface QualityCheckRuleListResponse {
  total: number;
  items: QualityCheckRule[];
}

/** GET /api/quality-checks/batches 响应项（= schemas.QualityCheckBatchSummaryResponse） */
export interface QualityCheckBatch {
  id: string;
  entity_type: EntityType;
  total_entities: number;
  total_checks: number;
  passed: number;
  failed: number;
  skipped_checks: number;
  rule_ids: string[] | null;
  triggered_by: string;
  started_at: string;
  finished_at: string | null;
}

/** GET /api/quality-checks/batches 响应（= schemas.QualityCheckBatchListResponse） */
export interface QualityCheckBatchListResponse {
  total: number;
  items: QualityCheckBatch[];
}

/** GET /api/quality-checks/results 响应项（= schemas.QualityCheckResultResponse） */
export interface QualityCheckResult {
  id: string;
  rule_id: string;
  batch_id: string;
  entity_id: string;
  entity_type: EntityType;
  field_name: string | null;
  field_value: string | null;
  severity: CheckSeverity;
  message: string | null;
  checked_at: string;
}

/** GET /api/quality-checks/results 响应（= schemas.QualityCheckResultListResponse） */
export interface QualityCheckResultListResponse {
  total: number;
  items: QualityCheckResult[];
}

/** 按规则统计（= schemas.ReportRuleStat；total 口径 = 批次实体数，设计决策 4） */
export interface QualityReportRuleStat {
  rule_id: string;
  rule_name: string;
  total: number;
  failed: number;
  pass_rate: number;
}

/** Top 问题（= schemas.ReportTopIssue） */
export interface QualityReportTopIssue {
  field_name: string | null;
  issue_count: number;
  issue_type: RuleType | null;
  message: string | null;
}

/** GET /api/quality-checks/report 响应（= schemas.QualityCheckReportResponse） */
export interface QualityReport {
  batch_id: string;
  entity_type: EntityType;
  total_entities: number;
  total_checks: number;
  passed: number;
  failed: number;
  pass_rate: number;
  by_severity: Record<CheckSeverity, number>;
  by_rule: QualityReportRuleStat[];
  top_issues: QualityReportTopIssue[];
}

// ========== 疑似错误（SPEC §2.7 / §3.3） ==========

/** 与 backend schemas.SuspectedErrorType 一致（v1 仅 duplicate / naming 有检测数据源） */
export type SuspectedErrorType = 'duplicate' | 'naming' | 'classification' | 'unit';

/** 与 schemas.SuspectedErrorResolveRequest.status pattern 一致 */
export type SuspectedErrorStatus = 'pending' | 'confirmed' | 'resolved' | 'false_positive';

/** 处理对话框可选目标状态（后端只接受 confirmed / resolved / false_positive） */
export type SuspectedResolveStatus = 'confirmed' | 'resolved' | 'false_positive';

/** POST /api/suspected-errors/detect 请求体（= schemas.SuspectedErrorDetectRequest） */
export interface SuspectedDetectPayload {
  entity_type: EntityType;
  error_types?: SuspectedErrorType[] | null;
  entity_ids?: string[] | null;
}

/** POST /api/suspected-errors/detect 响应（= schemas.SuspectedErrorDetectResponse） */
export interface SuspectedDetectResponse {
  created: number;
  refreshed: number;
  skipped_false_positive: number;
  auto_closed: number;
  total_pending: number;
}

/** 判定依据（= SuspectedError.details，取自检测器 finding.evidence） */
export interface SuspectedErrorDetails {
  strategy?: string;
  rule?: string;
  reason?: string;
  similarity?: number;
  field?: string;
  entity_code?: string;
  entity_name?: string;
  matched_code?: string;
  matched_name?: string;
  suggestion?: string;
  keeper_rule?: string;
  shared_tokens?: string[];
  rule_code?: string;
  rule_label?: string;
  violation?: string;
  [key: string]: unknown;
}

/** GET /api/suspected-errors 响应项（= schemas.SuspectedErrorResponse） */
export interface SuspectedError {
  id: string;
  entity_type: EntityType;
  entity_id: string;
  entity_label: string | null;
  error_type: SuspectedErrorType;
  severity: CheckSeverity;
  title: string;
  description: string | null;
  details: SuspectedErrorDetails | null;
  status: SuspectedErrorStatus;
  resolved_by: string | null;
  resolved_at: string | null;
  resolution_note: string | null;
  matched_entity_id: string | null;
  detected_at: string;
  detected_by: string | null;
}

/** GET /api/suspected-errors 响应（= schemas.SuspectedErrorListResponse） */
export interface SuspectedErrorListResponse {
  total: number;
  items: SuspectedError[];
}

/** POST /api/suspected-errors/{id}/resolve 请求体（= schemas.SuspectedErrorResolveRequest） */
export interface SuspectedResolvePayload {
  status: SuspectedResolveStatus;
  resolution_note?: string | null;
}

// ========== 元数据管理 ==========

/** 与 schemas.MetadataFieldBase.standard_source 的 pattern 一致 */
export type MetadataSource = 'sap' | 'ariba_slp' | 'internal';

/** 与 schemas.MetadataEntityBase.sensitivity_level 的 pattern 一致 */
export type SensitivityLevel = 'public' | 'internal' | 'confidential';

/** GET /api/metadata/fields 响应项（= schemas.MetadataFieldResponse） */
export interface MetadataField {
  id: string;
  entity_type: EntityType;
  sap_table: string | null;
  field_name: string;
  field_label: string;
  data_type: StandardDataType;
  max_length: number | null;
  view_section: string | null;
  business_definition: string | null;
  /** schemas 中为 Optional（列可空），响应可能为 null */
  standard_source: MetadataSource | null;
  must_govern: boolean;
  glossary_term_id: string | null;
  /** 关联业务术语名（GET 列表端点装配带出，可空） */
  glossary_term_name: string | null;
  /** 引用该字段的数据标准数（GET 列表端点装配带出） */
  standard_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** GET /api/metadata/fields 响应（= schemas.MetadataFieldListResponse） */
export interface MetadataFieldListResponse {
  total: number;
  items: MetadataField[];
}

/** GET /api/metadata/fields 查询参数（与后端 list_metadata_fields 同名映射） */
export interface MetadataFieldQuery {
  entity_type?: EntityType;
  view_section?: string;
  must_govern?: boolean;
  keyword?: string;
  skip?: number;
  limit?: number;
}

/** POST /api/metadata/fields 请求体（= schemas.MetadataFieldCreate） */
export interface MetadataFieldCreatePayload {
  entity_type: EntityType;
  sap_table?: string | null;
  field_name: string;
  field_label: string;
  data_type: StandardDataType;
  max_length?: number | null;
  view_section?: string | null;
  business_definition?: string | null;
  standard_source?: MetadataSource | null;
  must_govern?: boolean;
  glossary_term_id?: string | null;
  is_active?: boolean;
}

/**
 * PUT /api/metadata/fields/{id} 请求体（= schemas.MetadataFieldUpdate）。
 * 全可选；entity_type / sap_table / field_name 为身份键，后端不接受更新。
 */
export interface MetadataFieldUpdatePayload {
  field_label?: string | null;
  data_type?: StandardDataType | null;
  max_length?: number | null;
  view_section?: string | null;
  business_definition?: string | null;
  standard_source?: MetadataSource | null;
  must_govern?: boolean | null;
  glossary_term_id?: string | null;
  is_active?: boolean | null;
}

/** GET /api/metadata/entities 响应项（= schemas.MetadataEntityResponse，计数字段由 service 装配） */
export interface MetadataEntity {
  id: string;
  entity_type: EntityType;
  display_name: string;
  business_definition: string | null;
  data_owner: string | null;
  dept: string | null;
  tags: string[] | null;
  sensitivity_level: SensitivityLevel | null;
  /** 该实体下 must_govern=True 的元数据字段数 */
  governed_field_count: number;
  /** 该实体下元数据字段总数 */
  total_field_count: number;
  created_at: string;
  updated_at: string;
}

/** PUT /api/metadata/entities/{entity_type} 请求体（= schemas.MetadataEntityUpdate，全可选） */
export interface MetadataEntityUpdatePayload {
  display_name?: string | null;
  business_definition?: string | null;
  data_owner?: string | null;
  dept?: string | null;
  tags?: string[] | null;
  sensitivity_level?: SensitivityLevel | null;
}

/** GET /api/metadata/glossary 响应项（= schemas.GlossaryTermResponse；该端点直接返回数组） */
export interface GlossaryTerm {
  id: string;
  term: string;
  definition: string;
  aliases: string[] | null;
  /** 关联的元数据字段数（列表与写响应均装配真实计数） */
  field_count: number;
  created_at: string;
  updated_at: string;
}

/** POST /api/metadata/glossary 请求体（= schemas.GlossaryTermCreate） */
export interface GlossaryTermCreatePayload {
  term: string;
  definition: string;
  aliases?: string[] | null;
}

/** PUT /api/metadata/glossary/{id} 请求体（= schemas.GlossaryTermUpdate；term 名称不可变） */
export interface GlossaryTermUpdatePayload {
  definition?: string | null;
  aliases?: string[] | null;
}
