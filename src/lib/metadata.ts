/**
 * 元数据管理字典与表单校验（字段登记册 / 实体治理属性 / 业务术语）。
 *
 * 这里的约束与 backend/app/schemas.py 中 MetadataField* / MetadataEntity* /
 * GlossaryTerm* 的 Pydantic 规则保持一致，目的是在提交前就地提示，
 * 而不是等后端返回 422。本文件零网络代码，请求由页面通过 api() 直接发起。
 */
import {
  DATA_TYPE_OPTIONS,
  ENTITY_TYPE_OPTIONS,
  splitList,
} from '@/lib/governance';
import type {
  EntityType,
  GlossaryTerm,
  GlossaryTermCreatePayload,
  GlossaryTermUpdatePayload,
  MetadataEntity,
  MetadataEntityUpdatePayload,
  MetadataField,
  MetadataFieldCreatePayload,
  MetadataFieldUpdatePayload,
  MetadataSource,
  SensitivityLevel,
  StandardDataType,
} from '@/types/api';

/** schemas.MetadataFieldBase.standard_source pattern: ^(sap|ariba_slp|internal)$ */
export const METADATA_SOURCE_OPTIONS: { value: MetadataSource; label: string }[] = [
  { value: 'sap', label: 'SAP 标准' },
  { value: 'ariba_slp', label: 'Ariba SLP' },
  { value: 'internal', label: '内部自定义' },
];

export const METADATA_SOURCE_LABELS: Record<MetadataSource, string> = {
  sap: 'SAP 标准',
  ariba_slp: 'Ariba SLP',
  internal: '内部自定义',
};

/** schemas.MetadataEntityBase.sensitivity_level pattern: ^(public|internal|confidential)$ */
export const SENSITIVITY_OPTIONS: { value: SensitivityLevel; label: string }[] = [
  { value: 'public', label: '公开' },
  { value: 'internal', label: '内部' },
  { value: 'confidential', label: '机密' },
];

export const SENSITIVITY_LABELS: Record<SensitivityLevel, string> = {
  public: '公开',
  internal: '内部',
  confidential: '机密',
};

// ========== 长度/取值上限（与 Pydantic Field 约束一致） ==========

export const METADATA_LIMITS = {
  sapTable: 50,
  fieldName: 100,
  fieldLabel: 200,
  viewSection: 100,
  displayName: 200,
  dataOwner: 50,
  dept: 100,
  term: 200,
  maxLengthMin: 1,
  maxLengthMax: 10000,
} as const;

function trimmedOrNull(raw: string): string | null {
  const value = raw.trim();
  return value || null;
}

/** 表单错误字典：任一字段有错误信息即视为不通过 */
export function hasFieldFormErrors(errors: Partial<Record<string, string>>): boolean {
  return Object.values(errors).some(Boolean);
}

// ========== 字段登记册表单 ==========

export interface FieldFormValues {
  entity_type: EntityType;
  sap_table: string;
  field_name: string;
  field_label: string;
  data_type: StandardDataType;
  max_length: string;
  view_section: string;
  business_definition: string;
  standard_source: '' | MetadataSource;
  must_govern: boolean;
  glossary_term_id: string;
  is_active: boolean;
}

export type FieldFormErrors = Partial<Record<keyof FieldFormValues, string>>;

export function emptyFieldForm(entityType: EntityType = 'material'): FieldFormValues {
  return {
    entity_type: entityType,
    sap_table: '',
    field_name: '',
    field_label: '',
    data_type: 'string',
    max_length: '',
    view_section: '',
    business_definition: '',
    standard_source: '',
    must_govern: false,
    glossary_term_id: '',
    is_active: true,
  };
}

export function fieldFormFromField(field: MetadataField): FieldFormValues {
  return {
    entity_type: field.entity_type,
    sap_table: field.sap_table ?? '',
    field_name: field.field_name,
    field_label: field.field_label,
    data_type: field.data_type,
    max_length: field.max_length == null ? '' : String(field.max_length),
    view_section: field.view_section ?? '',
    business_definition: field.business_definition ?? '',
    standard_source: field.standard_source ?? '',
    must_govern: !!field.must_govern,
    glossary_term_id: field.glossary_term_id ?? '',
    is_active: !!field.is_active,
  };
}

export function validateFieldForm(values: FieldFormValues): FieldFormErrors {
  const errors: FieldFormErrors = {};

  if (!ENTITY_TYPE_OPTIONS.some((item) => item.value === values.entity_type)) {
    errors.entity_type = '实体类型必须是 material / supplier / customer';
  }

  if (!DATA_TYPE_OPTIONS.some((item) => item.value === values.data_type)) {
    errors.data_type = '数据类型不在允许的枚举范围内';
  }

  const fieldName = values.field_name.trim();
  if (!fieldName) {
    errors.field_name = '字段名不能为空';
  } else if (fieldName.length > METADATA_LIMITS.fieldName) {
    errors.field_name = `字段名长度不能超过 ${METADATA_LIMITS.fieldName} 个字符`;
  }

  const fieldLabel = values.field_label.trim();
  if (!fieldLabel) {
    errors.field_label = '字段中文标签不能为空';
  } else if (fieldLabel.length > METADATA_LIMITS.fieldLabel) {
    errors.field_label = `字段中文标签长度不能超过 ${METADATA_LIMITS.fieldLabel} 个字符`;
  }

  if (values.sap_table.trim().length > METADATA_LIMITS.sapTable) {
    errors.sap_table = `SAP 表名长度不能超过 ${METADATA_LIMITS.sapTable} 个字符`;
  }

  const maxLengthRaw = values.max_length.trim();
  if (maxLengthRaw) {
    const maxLength = Number(maxLengthRaw);
    if (!Number.isInteger(maxLength)) {
      errors.max_length = '最大长度必须是整数';
    } else if (
      maxLength < METADATA_LIMITS.maxLengthMin ||
      maxLength > METADATA_LIMITS.maxLengthMax
    ) {
      errors.max_length = `最大长度必须在 ${METADATA_LIMITS.maxLengthMin} 到 ${METADATA_LIMITS.maxLengthMax} 之间`;
    }
  }

  if (values.view_section.trim().length > METADATA_LIMITS.viewSection) {
    errors.view_section = `视图分区长度不能超过 ${METADATA_LIMITS.viewSection} 个字符`;
  }

  if (
    values.standard_source &&
    !METADATA_SOURCE_OPTIONS.some((item) => item.value === values.standard_source)
  ) {
    errors.standard_source = '标准来源必须是 sap / ariba_slp / internal';
  }

  return errors;
}

export function toFieldCreatePayload(values: FieldFormValues): MetadataFieldCreatePayload {
  return {
    entity_type: values.entity_type,
    sap_table: trimmedOrNull(values.sap_table),
    field_name: values.field_name.trim(),
    field_label: values.field_label.trim(),
    data_type: values.data_type,
    max_length: values.max_length.trim() ? Number(values.max_length) : null,
    view_section: trimmedOrNull(values.view_section),
    business_definition: trimmedOrNull(values.business_definition),
    standard_source: values.standard_source || null,
    must_govern: values.must_govern,
    glossary_term_id: trimmedOrNull(values.glossary_term_id),
    is_active: values.is_active,
  };
}

/**
 * PUT 请求体：后端 MetadataFieldUpdate 不接受 entity_type / sap_table / field_name，
 * 这三个身份键在编辑对话框中只读展示。
 */
export function toFieldUpdatePayload(values: FieldFormValues): MetadataFieldUpdatePayload {
  const created = toFieldCreatePayload(values);
  return {
    field_label: created.field_label,
    data_type: created.data_type,
    max_length: created.max_length,
    view_section: created.view_section,
    business_definition: created.business_definition,
    standard_source: created.standard_source,
    must_govern: created.must_govern,
    glossary_term_id: created.glossary_term_id,
    is_active: created.is_active,
  };
}

// ========== 实体治理属性表单 ==========

export interface EntityFormValues {
  entity_type: EntityType;
  display_name: string;
  business_definition: string;
  data_owner: string;
  dept: string;
  tags: string;
  sensitivity_level: '' | SensitivityLevel;
}

export type EntityFormErrors = Partial<Record<keyof EntityFormValues, string>>;

export function emptyEntityForm(entityType: EntityType = 'material'): EntityFormValues {
  return {
    entity_type: entityType,
    display_name: '',
    business_definition: '',
    data_owner: '',
    dept: '',
    tags: '',
    sensitivity_level: '',
  };
}

export function entityFormFromEntity(entity: MetadataEntity): EntityFormValues {
  return {
    entity_type: entity.entity_type,
    display_name: entity.display_name,
    business_definition: entity.business_definition ?? '',
    data_owner: entity.data_owner ?? '',
    dept: entity.dept ?? '',
    tags: (entity.tags ?? []).join('，'),
    sensitivity_level: entity.sensitivity_level ?? '',
  };
}

export function validateEntityForm(values: EntityFormValues): EntityFormErrors {
  const errors: EntityFormErrors = {};

  const displayName = values.display_name.trim();
  if (!displayName) {
    errors.display_name = '实体显示名不能为空';
  } else if (displayName.length > METADATA_LIMITS.displayName) {
    errors.display_name = `实体显示名长度不能超过 ${METADATA_LIMITS.displayName} 个字符`;
  }

  if (values.data_owner.trim().length > METADATA_LIMITS.dataOwner) {
    errors.data_owner = `数据负责人长度不能超过 ${METADATA_LIMITS.dataOwner} 个字符`;
  }

  if (values.dept.trim().length > METADATA_LIMITS.dept) {
    errors.dept = `责任部门长度不能超过 ${METADATA_LIMITS.dept} 个字符`;
  }

  if (
    values.sensitivity_level &&
    !SENSITIVITY_OPTIONS.some((item) => item.value === values.sensitivity_level)
  ) {
    errors.sensitivity_level = '敏感级别必须是 public / internal / confidential';
  }

  return errors;
}

/**
 * PUT 请求体：实体仅有更新端点（按 entity_type 定位），entity_type 为身份键不可变。
 */
export function toEntityUpdatePayload(values: EntityFormValues): MetadataEntityUpdatePayload {
  const tags = splitList(values.tags);
  return {
    display_name: values.display_name.trim(),
    business_definition: trimmedOrNull(values.business_definition),
    data_owner: trimmedOrNull(values.data_owner),
    dept: trimmedOrNull(values.dept),
    tags: tags.length ? tags : null,
    sensitivity_level: values.sensitivity_level || null,
  };
}

// ========== 业务术语表单 ==========

export interface GlossaryFormValues {
  term: string;
  definition: string;
  aliases: string;
}

export type GlossaryFormErrors = Partial<Record<keyof GlossaryFormValues, string>>;

export function emptyGlossaryForm(): GlossaryFormValues {
  return {
    term: '',
    definition: '',
    aliases: '',
  };
}

export function glossaryFormFromTerm(term: GlossaryTerm): GlossaryFormValues {
  return {
    term: term.term,
    definition: term.definition,
    aliases: (term.aliases ?? []).join('，'),
  };
}

export function validateGlossaryForm(values: GlossaryFormValues): GlossaryFormErrors {
  const errors: GlossaryFormErrors = {};

  const term = values.term.trim();
  if (!term) {
    errors.term = '术语名称不能为空';
  } else if (term.length > METADATA_LIMITS.term) {
    errors.term = `术语名称长度不能超过 ${METADATA_LIMITS.term} 个字符`;
  }

  if (!values.definition.trim()) {
    errors.definition = '术语定义不能为空';
  }

  return errors;
}

export function toGlossaryCreatePayload(values: GlossaryFormValues): GlossaryTermCreatePayload {
  const aliases = splitList(values.aliases);
  return {
    term: values.term.trim(),
    definition: values.definition.trim(),
    aliases: aliases.length ? aliases : null,
  };
}

/**
 * PUT 请求体：后端 GlossaryTermUpdate 不接受 term（名称不可变），
 * term 在编辑对话框中只读展示。
 */
export function toGlossaryUpdatePayload(values: GlossaryFormValues): GlossaryTermUpdatePayload {
  const aliases = splitList(values.aliases);
  return {
    definition: values.definition.trim(),
    aliases: aliases.length ? aliases : null,
  };
}
