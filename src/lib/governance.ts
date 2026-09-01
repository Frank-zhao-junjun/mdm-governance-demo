/**
 * 存量数据治理字典与表单校验（SPEC §1.5 属性分类 / §2.1 数据标准 / §3.0 权限）。
 *
 * 这里的约束与 backend/app/schemas.py 中 DataStandardBase 的 Pydantic 规则保持一致，
 * 目的是在提交前就地提示，而不是等后端返回 422。
 */
import type {
  DataStandard,
  DataStandardCreatePayload,
  DataStandardUpdatePayload,
  EntityType,
  StandardDataType,
  StandardSource,
  UserRole,
} from '@/types/api';

export const ENTITY_TYPE_OPTIONS: { value: EntityType; label: string }[] = [
  { value: 'material', label: '物料' },
  { value: 'supplier', label: '供应商' },
  { value: 'customer', label: '客户' },
];

export const ENTITY_TYPE_LABELS: Record<EntityType, string> = {
  material: '物料',
  supplier: '供应商',
  customer: '客户',
};

/** schemas.DataStandardBase.data_type pattern: ^(string|number|date|enum|boolean|amount|text)$ */
export const DATA_TYPE_OPTIONS: { value: StandardDataType; label: string }[] = [
  { value: 'string', label: '字符串 string' },
  { value: 'number', label: '数字 number' },
  { value: 'date', label: '日期 date' },
  { value: 'enum', label: '枚举 enum' },
  { value: 'boolean', label: '布尔 boolean' },
  { value: 'amount', label: '金额 amount' },
  { value: 'text', label: '文本 text' },
];

export const DATA_TYPE_LABELS: Record<StandardDataType, string> = {
  string: '字符串',
  number: '数字',
  date: '日期',
  enum: '枚举',
  boolean: '布尔',
  amount: '金额',
  text: '文本',
};

/** schemas.DataStandardBase.standard_source pattern: ^(sap|industry|internal)$ */
export const STANDARD_SOURCE_OPTIONS: { value: StandardSource; label: string }[] = [
  { value: 'sap', label: 'SAP 标准' },
  { value: 'industry', label: '行业标准' },
  { value: 'internal', label: '内部制度' },
];

export const STANDARD_SOURCE_LABELS: Record<StandardSource, string> = {
  sap: 'SAP 标准',
  industry: '行业标准',
  internal: '内部制度',
};

export const ROLE_LABELS: Record<UserRole, string> = {
  applicant: '普通用户',
  dept_approver: '部门用户',
  data_admin: '数据管理员',
  admin: '管理员',
};

/**
 * SAP 表候选（SPEC §10 附录）。后端 GET /api/data-standards 只提供 entity_type/sap_table
 * 两个精确过滤参数，没有 distinct 表清单接口，因此下拉以附录目录为准，
 * 并与当前已加载结果中出现的表名合并；表单侧仍允许自由输入任意 SAP 表名。
 */
export const SAP_TABLE_CATALOG: Record<EntityType, string[]> = {
  material: ['MARA', 'MAKT', 'MARC', 'MARD'],
  supplier: ['BUT000', 'BUT020', 'BUT0BANK', 'LFA1'],
  customer: ['KNA1', 'BUT000', 'BUT020'],
};

export function sapTableOptions(
  entityType: EntityType | 'all',
  loadedItems: DataStandard[],
): string[] {
  const base =
    entityType === 'all'
      ? [...SAP_TABLE_CATALOG.material, ...SAP_TABLE_CATALOG.supplier, ...SAP_TABLE_CATALOG.customer]
      : SAP_TABLE_CATALOG[entityType];
  const seen = new Set(base);
  for (const item of loadedItems) {
    if (item.sap_table) seen.add(item.sap_table);
  }
  return Array.from(seen).sort((a, b) => a.localeCompare(b));
}

// ========== 长度/取值上限（与 Pydantic Field 约束一致） ==========

export const LIMITS = {
  sapTable: 50,
  fieldName: 100,
  fieldLabel: 200,
  pattern: 200,
  owner: 50,
  maxLengthMin: 1,
  maxLengthMax: 10000,
} as const;

// ========== 表单模型 ==========

export interface StandardFormValues {
  entity_type: EntityType;
  sap_table: string;
  field_name: string;
  field_label: string;
  data_type: StandardDataType;
  max_length: string;
  min_value: string;
  max_value: string;
  enum_values: string;
  required: boolean;
  pattern: string;
  unique: boolean;
  standard_topic: string;
  standard_subcategory: string;
  owner: string;
  standard_source: '' | StandardSource;
  dept_scope: string;
  description: string;
  sap_field_desc: string;
}

export type StandardFormErrors = Partial<Record<keyof StandardFormValues, string>>;

export function emptyForm(entityType: EntityType = 'material'): StandardFormValues {
  return {
    entity_type: entityType,
    sap_table: '',
    field_name: '',
    field_label: '',
    data_type: 'string',
    max_length: '',
    min_value: '',
    max_value: '',
    enum_values: '',
    required: false,
    pattern: '',
    unique: false,
    standard_topic: '',
    standard_subcategory: '',
    owner: '',
    standard_source: '',
    dept_scope: '',
    description: '',
    sap_field_desc: '',
  };
}

export function formFromStandard(standard: DataStandard): StandardFormValues {
  const attrs = standard.business_attrs || {};
  return {
    entity_type: standard.entity_type,
    sap_table: standard.sap_table ?? '',
    field_name: standard.field_name,
    field_label: standard.field_label,
    data_type: standard.data_type,
    max_length: standard.max_length == null ? '' : String(standard.max_length),
    min_value: standard.min_value == null ? '' : String(standard.min_value),
    max_value: standard.max_value == null ? '' : String(standard.max_value),
    enum_values: (standard.enum_values ?? []).join('，'),
    required: !!standard.required,
    pattern: standard.pattern ?? '',
    unique: !!standard.unique,
    standard_topic: typeof attrs.standard_topic === 'string' ? attrs.standard_topic : '',
    standard_subcategory:
      typeof attrs.standard_subcategory === 'string' ? attrs.standard_subcategory : '',
    owner: standard.owner ?? '',
    standard_source: standard.standard_source ?? '',
    dept_scope: (standard.dept_scope ?? []).join('，'),
    description: standard.description ?? '',
    sap_field_desc: standard.sap_field_desc ?? '',
  };
}

/** 逗号（中英文）或换行分隔的文本 → 去重去空的字符串数组 */
export function splitList(raw: string): string[] {
  const parts = raw
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
  return Array.from(new Set(parts));
}

function validateStandardNumber(raw: string, label: string): string | null {
  if (!raw.trim()) return null;
  return Number.isFinite(Number(raw)) ? null : `${label}必须是数字`;
}

export function validateStandardForm(values: StandardFormValues): StandardFormErrors {
  const errors: StandardFormErrors = {};

  if (!ENTITY_TYPE_OPTIONS.some((item) => item.value === values.entity_type)) {
    errors.entity_type = '实体类型必须是 material / supplier / customer';
  }

  if (!DATA_TYPE_OPTIONS.some((item) => item.value === values.data_type)) {
    errors.data_type = '数据类型不在允许的枚举范围内';
  }

  const fieldName = values.field_name.trim();
  if (!fieldName) {
    errors.field_name = '字段名不能为空';
  } else if (fieldName.length > LIMITS.fieldName) {
    errors.field_name = `字段名长度不能超过 ${LIMITS.fieldName} 个字符`;
  }

  const fieldLabel = values.field_label.trim();
  if (!fieldLabel) {
    errors.field_label = '字段中文标签不能为空';
  } else if (fieldLabel.length > LIMITS.fieldLabel) {
    errors.field_label = `字段中文标签长度不能超过 ${LIMITS.fieldLabel} 个字符`;
  }

  if (values.sap_table.trim().length > LIMITS.sapTable) {
    errors.sap_table = `SAP 表名长度不能超过 ${LIMITS.sapTable} 个字符`;
  }

  const maxLengthRaw = values.max_length.trim();
  if (maxLengthRaw) {
    const maxLength = Number(maxLengthRaw);
    if (!Number.isInteger(maxLength)) {
      errors.max_length = '最大长度必须是整数';
    } else if (maxLength < LIMITS.maxLengthMin || maxLength > LIMITS.maxLengthMax) {
      errors.max_length = `最大长度必须在 ${LIMITS.maxLengthMin} 到 ${LIMITS.maxLengthMax} 之间`;
    }
  }

  const minValueError = validateStandardNumber(values.min_value, '最小值');
  if (minValueError) errors.min_value = minValueError;
  const maxValueError = validateStandardNumber(values.max_value, '最大值');
  if (maxValueError) errors.max_value = maxValueError;

  const pattern = values.pattern.trim();
  if (pattern.length > LIMITS.pattern) {
    errors.pattern = `正则表达式长度不能超过 ${LIMITS.pattern} 个字符`;
  } else if (pattern) {
    try {
      new RegExp(pattern);
    } catch {
      errors.pattern = '正则表达式无法编译，请检查语法';
    }
  }

  if (values.owner.trim().length > LIMITS.owner) {
    errors.owner = `标准定义人长度不能超过 ${LIMITS.owner} 个字符`;
  }

  if (
    values.standard_source &&
    !STANDARD_SOURCE_OPTIONS.some((item) => item.value === values.standard_source)
  ) {
    errors.standard_source = '标准来源必须是 sap / industry / internal';
  }

  return errors;
}

export function hasFormErrors(errors: StandardFormErrors): boolean {
  return Object.keys(errors).length > 0;
}

/** business_attrs 仅在有内容时提交，避免把 {"standard_topic": ""} 这类空壳写入 JSON 列 */
function buildBusinessAttrs(values: StandardFormValues): DataStandardCreatePayload['business_attrs'] {
  const topic = values.standard_topic.trim();
  const subcategory = values.standard_subcategory.trim();
  if (!topic && !subcategory) return null;
  return {
    standard_topic: topic || null,
    standard_subcategory: subcategory || null,
  };
}

function trimmedOrNull(raw: string): string | null {
  const value = raw.trim();
  return value || null;
}

export function toCreatePayload(values: StandardFormValues): DataStandardCreatePayload {
  const enums = splitList(values.enum_values);
  const depts = splitList(values.dept_scope);
  return {
    entity_type: values.entity_type,
    sap_table: trimmedOrNull(values.sap_table),
    field_name: values.field_name.trim(),
    field_label: values.field_label.trim(),
    data_type: values.data_type,
    max_length: values.max_length.trim() ? Number(values.max_length) : null,
    min_value: values.min_value.trim() ? Number(values.min_value) : null,
    max_value: values.max_value.trim() ? Number(values.max_value) : null,
    enum_values: enums.length ? enums : null,
    required: values.required,
    pattern: trimmedOrNull(values.pattern),
    unique: values.unique,
    business_attrs: buildBusinessAttrs(values),
    owner: trimmedOrNull(values.owner),
    standard_source: values.standard_source || null,
    dept_scope: depts.length ? depts : null,
    description: trimmedOrNull(values.description),
    sap_field_desc: trimmedOrNull(values.sap_field_desc),
  };
}

/**
 * PUT 请求体：后端 DataStandardUpdate 不接受 entity_type / sap_table / field_name，
 * 这三个身份键在编辑对话框中只读展示。
 */
export function toUpdatePayload(values: StandardFormValues): DataStandardUpdatePayload {
  const created = toCreatePayload(values);
  return {
    field_label: created.field_label,
    data_type: created.data_type,
    max_length: created.max_length,
    min_value: created.min_value,
    max_value: created.max_value,
    enum_values: created.enum_values,
    required: created.required,
    pattern: created.pattern,
    unique: created.unique,
    business_attrs: created.business_attrs,
    owner: created.owner,
    standard_source: created.standard_source,
    dept_scope: created.dept_scope,
    description: created.description,
    sap_field_desc: created.sap_field_desc,
  };
}
