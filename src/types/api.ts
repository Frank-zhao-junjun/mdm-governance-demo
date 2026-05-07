/** Common API types for the MDM Governance frontend */

export interface User {
  id: string;
  name: string;
  role: 'applicant' | 'admin' | 'data_admin' | 'dept_approver';
  department: string;
}

export interface Classification {
  id: string;
  code: string;
  name: string;
  level: number;
  description?: string;
  children?: Classification[];
}

export interface AttributeTemplate {
  id: string;
  classification_id: string;
  field_name: string;
  field_label: string;
  field_type: 'text' | 'number' | 'date' | 'select' | 'boolean';
  is_required: boolean;
  options?: string[];
  default_value?: string;
  description?: string;
}

export interface ValidationCheck {
  check: string;
  passed: boolean;
  message: string;
}

export interface ValidationResult {
  passed: boolean;
  checks: ValidationCheck[];
  errors: string[];
}

export interface DedupResult {
  is_duplicate: boolean;
  confidence: number;
  similar_materials: Array<{
    material_code: string;
    material_name: string;
    similarity: number;
    reason: string;
  }>;
}

export interface ApplicationAttachment {
  id: string;
  original_name: string;
  stored_name?: string;
  content_type: string;
  size: number;
  uploaded_by: string;
  uploaded_by_name?: string;
  uploaded_at: string;
  download_url: string;
}

export type ApplicationStatus = 
  | 'draft' 
  | 'pending_admin' 
  | 'pending_dept' 
  | 'approved' 
  | 'rejected' 
  | 'published';

export interface Application {
  id: string;
  app_no: string;
  material_name: string;
  material_desc?: string;
  material_code?: string;
  classification_id: string;
  material_type: 'raw' | 'semi' | 'finished' | 'auxiliary' | 'spare';
  attribute_values?: Record<string, any>;
  attachments?: ApplicationAttachment[];
  status: ApplicationStatus;
  validation_passed: boolean;
  is_duplicate: boolean;
  validation_result?: ValidationResult;
  dedup_result?: DedupResult;
  created_by: string;
  created_by_name?: string;
  department?: string;
  created_at: string;
  updated_at: string;
  submitted_at?: string;
  admin_approved: boolean;
  admin_approved_by?: string;
  admin_approved_at?: string;
  admin_comment?: string;
  dept_approved: boolean;
  dept_approved_by?: string;
  dept_approved_at?: string;
  dept_comment?: string;
}

export interface GoldenRecord {
  id: string;
  application_id?: string;
  material_code: string;
  material_name: string;
  material_desc?: string;
  classification_id: string;
  classification_path?: string;
  material_type: string;
  status: 'active' | 'obsolete';
  version: number;
  revision: number;
  btp_published: boolean;
  btp_published_at?: string;
  om_synced: boolean;
  om_synced_at?: string;
  om_entity_fqn?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface AuditLog {
  id: string;
  step_id: string;
  step_name: string;
  step_label: string;
  executed_by: string;
  executed_by_name?: string;
  executed_at: string;
  status: 'success' | 'failed' | 'pending';
  status_label?: string;
  details?: Record<string, any>;
  error_message?: string;
}

export interface ApiResponse<T> {
  success: boolean;
  message?: string;
  data?: T;
  error?: string;
}

export interface DashboardStats {
  stats: {
    total_applications: number;
    pending_admin: number;
    pending_dept: number;
    approved: number;
    rejected: number;
    published: number;
    total_golden_records: number;
    total_classifications: number;
  };
  recent_applications: Application[];
  recent_audit_logs: AuditLog[];
}

export interface MetadataCatalogItem {
  id: string;
  application_id?: string;
  material_code: string;
  material_name: string;
  material_type: string;
  classification_path?: string;
  attribute_count: number;
  status: string;
  version: number;
  revision: number;
  btp_published: boolean;
  btp_published_at?: string;
  om_synced: boolean;
  om_synced_at?: string;
  om_entity_fqn: string;
  created_at: string;
}

export interface MetadataLineageNode {
  id: string;
  label: string;
  type: 'source' | 'application' | 'golden_record' | 'external';
  subtitle?: string;
}

export interface MetadataLineageEdge {
  from: string;
  to: string;
  label: string;
}

export interface MetadataQualityTest {
  id: string;
  material_code: string;
  test_name: string;
  status: 'passed' | 'failed';
  message?: string;
  executed_at: string;
  source: string;
}

export interface MetadataTraceSummary {
  application_id: string;
  app_no: string;
  material_name: string;
  material_code?: string;
  status: ApplicationStatus;
  step_count: number;
  last_step?: string;
  last_status?: 'success' | 'failed' | 'pending';
  last_executed_at?: string;
}

export interface MetadataGovernanceOverview {
  openmetadata: {
    status: 'connected' | 'disconnected' | 'disabled';
    message?: string;
    version?: string;
    error?: string;
  };
  summary: {
    metadata_assets: number;
    om_synced: number;
    btp_published: number;
    quality_tests: number;
    traceable_applications: number;
  };
  catalog: MetadataCatalogItem[];
  lineage: {
    nodes: MetadataLineageNode[];
    edges: MetadataLineageEdge[];
  };
  quality_tests: MetadataQualityTest[];
  traces: MetadataTraceSummary[];
}
