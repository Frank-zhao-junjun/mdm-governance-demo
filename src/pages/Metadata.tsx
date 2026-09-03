/**
 * 元数据管理页面（三 Tab：实体总览 / 字段登记册 / 业务术语）。
 *
 * 骨架沿用 DataStandards.tsx：手写 useState + useCallback + useEffect（cancelled 标志）
 * 数据获取，loadError / loading / Empty 三分支渲染，请求全部 api<T>(..., { silentError: true })，
 * 写按钮由 canWrite() 控制。表单沿用 DataStandardFormDialog.tsx 的 useState + 手写校验模式
 * （{open && <Form ...>} 条件挂载重置，ApiError 400/404/409 就地展示）。
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Pencil, Plus, RefreshCw, Search } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';

import { ApiError, api, canWrite } from '@/lib/api';
import {
  DATA_TYPE_LABELS,
  DATA_TYPE_OPTIONS,
  ENTITY_TYPE_LABELS,
  ENTITY_TYPE_OPTIONS,
} from '@/lib/governance';
import {
  METADATA_LIMITS,
  METADATA_SOURCE_LABELS,
  METADATA_SOURCE_OPTIONS,
  SENSITIVITY_LABELS,
  SENSITIVITY_OPTIONS,
  emptyEntityForm,
  emptyFieldForm,
  emptyGlossaryForm,
  entityFormFromEntity,
  fieldFormFromField,
  glossaryFormFromTerm,
  hasFieldFormErrors,
  toEntityUpdatePayload,
  toFieldCreatePayload,
  toFieldUpdatePayload,
  toGlossaryCreatePayload,
  toGlossaryUpdatePayload,
  validateEntityForm,
  validateFieldForm,
  validateGlossaryForm,
  type EntityFormErrors,
  type EntityFormValues,
  type FieldFormErrors,
  type FieldFormValues,
  type GlossaryFormErrors,
  type GlossaryFormValues,
} from '@/lib/metadata';
import type {
  EntityType,
  GlossaryTerm,
  MetadataEntity,
  MetadataField,
  MetadataFieldListResponse,
  MetadataFieldQuery,
  MetadataSource,
  SensitivityLevel,
  StandardDataType,
} from '@/types/api';

/** Radix Select 不允许 value=""，过滤项用哨兵表示「全部 / 不限」 */
const ALL = 'all';
/** 表单内可选字段（标准来源 / 敏感级别 / 关联术语）的「未指定」哨兵 */
const NONE = '__none__';
const DEFAULT_LIMIT = 20;
const LIMIT_OPTIONS = [20, 50, 100, 200];

type MetadataTab = 'entities' | 'fields' | 'glossary';

/** 敏感级别徽标配色：confidential 红 / internal 黄 / public 灰 */
const SENSITIVITY_BADGE_CLASS: Record<SensitivityLevel, string> = {
  confidential: 'border-red-200 bg-red-100 text-red-800',
  internal: 'border-amber-200 bg-amber-100 text-amber-800',
  public: 'border-gray-200 bg-gray-100 text-gray-700',
};

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="mt-1 text-xs text-destructive">{message}</p>;
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="text-sm font-semibold text-gray-700 sm:col-span-2">{children}</h3>;
}

/** 三分支渲染的错误分支（与 DataStandards.tsx 保持一致） */
function LoadErrorBox({ label, error, onRetry }: { label: string; error: string; onRetry: () => void }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
      <span>
        {label}加载失败：{error}
      </span>
      <Button variant="outline" size="sm" onClick={onRetry}>
        重试
      </Button>
    </div>
  );
}

function LoadingBox() {
  return (
    <div className="flex justify-center rounded-lg border border-gray-200 bg-white py-16">
      <Spinner className="size-6" />
    </div>
  );
}

/** 空态分支：包一层与表格一致的白色卡片 */
function EmptyBox({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      <Empty>
        <EmptyHeader>
          <EmptyTitle>{title}</EmptyTitle>
          <EmptyDescription>{description}</EmptyDescription>
        </EmptyHeader>
      </Empty>
    </div>
  );
}

// ========== 实体总览 ==========

interface EntityFormDialogProps {
  open: boolean;
  /** 编辑目标实体（实体仅支持编辑，无新建端点） */
  entity: MetadataEntity | null;
  onOpenChange: (open: boolean) => void;
  /** 保存成功后回调（父组件据此刷新列表） */
  onSaved: () => void;
}

interface EntityFormProps extends EntityFormDialogProps {
  /** 关闭对话框（Radix 关闭时卸载内容，表单每次打开都是全新状态） */
  onClose: () => void;
}

function EntityForm({ entity, onSaved, onClose }: EntityFormProps) {
  const [values, setValues] = useState<EntityFormValues>(() =>
    entity ? entityFormFromEntity(entity) : emptyEntityForm(),
  );
  const [errors, setErrors] = useState<EntityFormErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const setField = <K extends keyof EntityFormValues>(key: K, value: EntityFormValues[K]) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => (prev[key] ? { ...prev, [key]: undefined } : prev));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting || !entity) return;

    const nextErrors = validateEntityForm(values);
    setErrors(nextErrors);
    if (hasFieldFormErrors(nextErrors)) {
      setServerError(null);
      return;
    }
    setSubmitting(true);
    setServerError(null);
    try {
      await api<MetadataEntity>(`/api/metadata/entities/${entity.entity_type}`, {
        method: 'PUT',
        body: JSON.stringify(toEntityUpdatePayload(values)),
        silentError: true,
      });
      toast.success(`实体「${values.display_name.trim()}」治理属性已更新`);
      onSaved();
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : '保存失败';
      const status = err instanceof ApiError ? err.status : 0;
      if (status === 400 || status === 404) {
        // 400 未提供可更新字段 / 404 实体不存在 —— 就地提示
        setServerError(message);
      } else {
        toast.error(message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="mt-2">
      <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
        <SectionTitle>基本信息</SectionTitle>

        <div>
          <Label htmlFor="meta_entity_display_name">实体显示名 *</Label>
          <Input
            id="meta_entity_display_name"
            value={values.display_name}
            onChange={(e) => setField('display_name', e.target.value)}
            maxLength={METADATA_LIMITS.displayName}
            placeholder="如 物料主数据"
          />
          <FieldError message={errors.display_name} />
        </div>

        <div>
          <Label htmlFor="meta_entity_sensitivity">敏感级别</Label>
          <Select
            value={values.sensitivity_level || NONE}
            onValueChange={(next) =>
              setField('sensitivity_level', next === NONE ? '' : (next as SensitivityLevel))
            }
          >
            <SelectTrigger id="meta_entity_sensitivity" className="w-full">
              <SelectValue placeholder="选择敏感级别" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>未指定</SelectItem>
              {SENSITIVITY_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}（{option.value}）
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldError message={errors.sensitivity_level} />
        </div>

        <SectionTitle>治理责任</SectionTitle>

        <div>
          <Label htmlFor="meta_entity_owner">数据负责人</Label>
          <Input
            id="meta_entity_owner"
            value={values.data_owner}
            onChange={(e) => setField('data_owner', e.target.value)}
            maxLength={METADATA_LIMITS.dataOwner}
            placeholder="如 张三"
          />
          <FieldError message={errors.data_owner} />
        </div>

        <div>
          <Label htmlFor="meta_entity_dept">责任部门</Label>
          <Input
            id="meta_entity_dept"
            value={values.dept}
            onChange={(e) => setField('dept', e.target.value)}
            maxLength={METADATA_LIMITS.dept}
            placeholder="如 采购部"
          />
          <FieldError message={errors.dept} />
        </div>

        <div className="sm:col-span-2">
          <Label htmlFor="meta_entity_tags">标签</Label>
          <Input
            id="meta_entity_tags"
            value={values.tags}
            onChange={(e) => setField('tags', e.target.value)}
            placeholder="多个标签用逗号分隔，如 核心主数据, 采购域"
          />
          <p className="mt-1 text-xs text-gray-400">以逗号或换行分隔，提交时转为字符串数组。</p>
          <FieldError message={errors.tags} />
        </div>

        <div className="sm:col-span-2">
          <Label htmlFor="meta_entity_definition">业务定义</Label>
          <Textarea
            id="meta_entity_definition"
            value={values.business_definition}
            onChange={(e) => setField('business_definition', e.target.value)}
            rows={3}
            placeholder="实体的业务含义与治理范围"
          />
        </div>

        {serverError && (
          <div
            role="alert"
            className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive sm:col-span-2"
          >
            {serverError}
          </div>
        )}
      </div>

      <DialogFooter className="mt-6">
        <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
          取消
        </Button>
        <Button type="submit" disabled={submitting} className="bg-blue-600 hover:bg-blue-700">
          {submitting && <Spinner />}
          {submitting ? '保存中...' : '保存修改'}
        </Button>
      </DialogFooter>
    </form>
  );
}

const EntityFormDialog: React.FC<EntityFormDialogProps> = (props) => {
  const { open, entity, onOpenChange } = props;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] gap-0 overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>编辑实体治理属性</DialogTitle>
          <DialogDescription>
            {entity
              ? `实体类型 ${entity.entity_type}（${
                  ENTITY_TYPE_LABELS[entity.entity_type] ?? entity.entity_type
                }）为身份键，不可修改。`
              : ''}
          </DialogDescription>
        </DialogHeader>
        {open && <EntityForm {...props} onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
};

function EntitiesPanel({ writable }: { writable: boolean }) {
  const [entities, setEntities] = useState<MetadataEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [editTarget, setEditTarget] = useState<MetadataEntity | null>(null);
  const [formOpen, setFormOpen] = useState(false);

  /** 实体总览端点直接返回数组（计数字段由后端装配） */
  const loadEntities = useCallback(
    () => api<MetadataEntity[]>('/api/metadata/entities', { silentError: true }),
    [],
  );

  const applyResult = useCallback((result: MetadataEntity[]) => {
    setEntities(result);
    setLoadError(null);
    setLoading(false);
  }, []);

  const applyError = useCallback((err: unknown) => {
    setEntities([]);
    setLoadError(err instanceof Error ? err.message : '实体总览加载失败');
    setLoading(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadEntities()
      .then((result) => {
        if (!cancelled) applyResult(result);
      })
      .catch((err: unknown) => {
        if (!cancelled) applyError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [loadEntities, applyResult, applyError]);

  const reload = useCallback(() => {
    setLoading(true);
    loadEntities().then(applyResult).catch(applyError);
  }, [applyError, applyResult, loadEntities]);

  const openEdit = (entity: MetadataEntity) => {
    setEditTarget(entity);
    setFormOpen(true);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-gray-500">
          共 {entities.length} 个实体的治理属性
          {!writable && '（当前角色为只读：仅数据管理员 / 管理员可编辑）'}
        </span>
        <Button variant="outline" size="icon" title="刷新" onClick={reload}>
          {loading ? <Spinner className="size-4" /> : <RefreshCw />}
        </Button>
      </div>

      {loadError && !loading ? (
        <LoadErrorBox label="实体总览" error={loadError} onRetry={reload} />
      ) : loading ? (
        <LoadingBox />
      ) : entities.length === 0 ? (
        <EmptyBox
          title="暂无实体元数据"
          description="后端尚未登记实体级治理属性；可通过 PUT /api/metadata/entities/{entity_type} 初始化。"
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {entities.map((entity) => (
            <Card key={entity.entity_type} className="gap-3">
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <CardTitle>{entity.display_name}</CardTitle>
                    <p className="mt-1 font-mono text-xs text-gray-400">{entity.entity_type}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    {entity.sensitivity_level && (
                      <Badge
                        className={`border font-normal ${
                          SENSITIVITY_BADGE_CLASS[entity.sensitivity_level]
                        }`}
                      >
                        {SENSITIVITY_LABELS[entity.sensitivity_level]}
                      </Badge>
                    )}
                    {writable && (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        title="编辑治理属性"
                        onClick={() => openEdit(entity)}
                      >
                        <Pencil />
                      </Button>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="line-clamp-3 min-h-10 text-sm text-gray-600" title={entity.business_definition ?? ''}>
                  {entity.business_definition ?? '（未填写业务定义）'}
                </p>
                <div className="flex flex-wrap gap-1">
                  {(entity.tags ?? []).map((tag) => (
                    <Badge key={tag} variant="outline" className="font-normal">
                      {tag}
                    </Badge>
                  ))}
                </div>
                <div className="flex items-center justify-between border-t border-gray-100 pt-3 text-xs text-gray-500">
                  <span>
                    负责人 {entity.data_owner ?? '—'} · {entity.dept ?? '—'}
                  </span>
                  <span className="font-medium text-gray-700">
                    必须治理 {entity.governed_field_count} / 共 {entity.total_field_count} 字段
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <EntityFormDialog
        open={formOpen}
        entity={editTarget}
        onOpenChange={setFormOpen}
        onSaved={reload}
      />
    </div>
  );
}

// ========== 字段登记册 ==========

interface FieldFormDialogProps {
  open: boolean;
  mode: 'create' | 'edit';
  /** 编辑时的原始字段；新建时传 null */
  field: MetadataField | null;
  /** 新建时的默认实体类型（跟随当前实体筛选） */
  defaultEntityType: EntityType;
  /** 术语下拉候选（来自 GET /api/metadata/glossary） */
  glossaryTerms: GlossaryTerm[];
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}

interface FieldFormProps extends FieldFormDialogProps {
  onClose: () => void;
}

function FieldForm({ mode, field, defaultEntityType, glossaryTerms, onSaved, onClose }: FieldFormProps) {
  const isEdit = mode === 'edit';
  const [values, setValues] = useState<FieldFormValues>(() =>
    field ? fieldFormFromField(field) : emptyFieldForm(defaultEntityType),
  );
  const [errors, setErrors] = useState<FieldFormErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const setField = <K extends keyof FieldFormValues>(key: K, value: FieldFormValues[K]) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => (prev[key] ? { ...prev, [key]: undefined } : prev));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;

    const nextErrors = validateFieldForm(values);
    setErrors(nextErrors);
    if (hasFieldFormErrors(nextErrors)) {
      setServerError(null);
      return;
    }
    setSubmitting(true);
    setServerError(null);
    try {
      if (isEdit) {
        if (!field) {
          setServerError('缺少元数据字段 ID，无法保存');
          return;
        }
        await api<MetadataField>(`/api/metadata/fields/${field.id}`, {
          method: 'PUT',
          body: JSON.stringify(toFieldUpdatePayload(values)),
          silentError: true,
        });
      } else {
        await api<MetadataField>('/api/metadata/fields', {
          method: 'POST',
          body: JSON.stringify(toFieldCreatePayload(values)),
          silentError: true,
        });
      }
      toast.success(isEdit ? '元数据字段已更新' : '元数据字段已登记');
      onSaved();
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : '保存失败';
      const status = err instanceof ApiError ? err.status : 0;
      if (status === 400 || status === 404 || status === 409) {
        // 409 同（实体, SAP表, 字段）已存在 / 400 未提供可更新字段 / 404 字段不存在 —— 就地提示
        setServerError(message);
      } else {
        toast.error(message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="mt-2">
      <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
        <SectionTitle>标识信息</SectionTitle>

        <div>
          <Label htmlFor="meta_field_entity_type">实体类型 *</Label>
          <Select
            value={values.entity_type}
            onValueChange={(next) => setField('entity_type', next as EntityType)}
            disabled={isEdit}
          >
            <SelectTrigger id="meta_field_entity_type" className="w-full">
              <SelectValue placeholder="选择实体类型" />
            </SelectTrigger>
            <SelectContent>
              {ENTITY_TYPE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}（{option.value}）
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldError message={errors.entity_type} />
        </div>

        <div>
          <Label htmlFor="meta_field_sap_table">SAP 表</Label>
          <Input
            id="meta_field_sap_table"
            value={values.sap_table}
            onChange={(e) => setField('sap_table', e.target.value)}
            maxLength={METADATA_LIMITS.sapTable}
            disabled={isEdit}
            placeholder="如 MARA / BUT000 / KNA1（可留空）"
            className="disabled:bg-gray-100 disabled:text-gray-500"
          />
          <FieldError message={errors.sap_table} />
        </div>

        <div>
          <Label htmlFor="meta_field_name">字段名 *</Label>
          <Input
            id="meta_field_name"
            value={values.field_name}
            onChange={(e) => setField('field_name', e.target.value)}
            maxLength={METADATA_LIMITS.fieldName}
            disabled={isEdit}
            placeholder="如 MATNR / NAME1"
            className="font-mono disabled:bg-gray-100 disabled:text-gray-500"
          />
          <FieldError message={errors.field_name} />
        </div>

        <div>
          <Label htmlFor="meta_field_label">字段中文标签 *</Label>
          <Input
            id="meta_field_label"
            value={values.field_label}
            onChange={(e) => setField('field_label', e.target.value)}
            maxLength={METADATA_LIMITS.fieldLabel}
            placeholder="如 物料编码"
          />
          <FieldError message={errors.field_label} />
        </div>

        <SectionTitle>数据属性</SectionTitle>

        <div>
          <Label htmlFor="meta_field_data_type">数据类型 *</Label>
          <Select
            value={values.data_type}
            onValueChange={(next) => setField('data_type', next as StandardDataType)}
          >
            <SelectTrigger id="meta_field_data_type" className="w-full">
              <SelectValue placeholder="选择数据类型" />
            </SelectTrigger>
            <SelectContent>
              {DATA_TYPE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldError message={errors.data_type} />
        </div>

        <div>
          <Label htmlFor="meta_field_max_length">最大长度</Label>
          <Input
            id="meta_field_max_length"
            type="number"
            min={METADATA_LIMITS.maxLengthMin}
            max={METADATA_LIMITS.maxLengthMax}
            value={values.max_length}
            onChange={(e) => setField('max_length', e.target.value)}
            placeholder={`${METADATA_LIMITS.maxLengthMin} ~ ${METADATA_LIMITS.maxLengthMax}`}
          />
          <FieldError message={errors.max_length} />
        </div>

        <div>
          <Label htmlFor="meta_field_view_section">视图分区</Label>
          <Input
            id="meta_field_view_section"
            value={values.view_section}
            onChange={(e) => setField('view_section', e.target.value)}
            maxLength={METADATA_LIMITS.viewSection}
            placeholder="如 基本视图 / 采购视图"
          />
          <FieldError message={errors.view_section} />
        </div>

        <div>
          <Label htmlFor="meta_field_source">标准来源</Label>
          <Select
            value={values.standard_source || NONE}
            onValueChange={(next) =>
              setField('standard_source', next === NONE ? '' : (next as MetadataSource))
            }
          >
            <SelectTrigger id="meta_field_source" className="w-full">
              <SelectValue placeholder="选择标准来源" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>未指定</SelectItem>
              {METADATA_SOURCE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}（{option.value}）
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldError message={errors.standard_source} />
        </div>

        <SectionTitle>治理属性</SectionTitle>

        <div className="flex items-center justify-between gap-4 rounded-md border border-gray-200 px-3 py-2">
          <Label htmlFor="meta_field_must_govern" className="cursor-pointer">
            必须治理
          </Label>
          <Switch
            id="meta_field_must_govern"
            checked={values.must_govern}
            onCheckedChange={(checked) => setField('must_govern', checked)}
          />
        </div>

        <div className="flex items-center justify-between gap-4 rounded-md border border-gray-200 px-3 py-2">
          <Label htmlFor="meta_field_is_active" className="cursor-pointer">
            启用
          </Label>
          <Switch
            id="meta_field_is_active"
            checked={values.is_active}
            onCheckedChange={(checked) => setField('is_active', checked)}
          />
        </div>

        <div className="sm:col-span-2">
          <Label htmlFor="meta_field_glossary_term">关联业务术语</Label>
          <Select
            value={values.glossary_term_id || NONE}
            onValueChange={(next) => setField('glossary_term_id', next === NONE ? '' : next)}
          >
            <SelectTrigger id="meta_field_glossary_term" className="w-full">
              <SelectValue placeholder="选择业务术语" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>无关联</SelectItem>
              {glossaryTerms.map((term) => (
                <SelectItem key={term.id} value={term.id}>
                  {term.term}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="mt-1 text-xs text-gray-400">
            选项来自业务术语表；术语表为空时仅可保持「无关联」。
          </p>
          <FieldError message={errors.glossary_term_id} />
        </div>

        <div className="sm:col-span-2">
          <Label htmlFor="meta_field_definition">业务定义</Label>
          <Textarea
            id="meta_field_definition"
            value={values.business_definition}
            onChange={(e) => setField('business_definition', e.target.value)}
            rows={2}
            placeholder="字段的业务含义与口径说明"
          />
        </div>

        {serverError && (
          <div
            role="alert"
            className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive sm:col-span-2"
          >
            {serverError}
          </div>
        )}
      </div>

      <DialogFooter className="mt-6">
        <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
          取消
        </Button>
        <Button type="submit" disabled={submitting} className="bg-blue-600 hover:bg-blue-700">
          {submitting && <Spinner />}
          {submitting ? '保存中...' : isEdit ? '保存修改' : '登记字段'}
        </Button>
      </DialogFooter>
    </form>
  );
}

const FieldFormDialog: React.FC<FieldFormDialogProps> = (props) => {
  const { open, mode, onOpenChange } = props;
  const isEdit = mode === 'edit';
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] gap-0 overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? '编辑元数据字段' : '登记元数据字段'}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? '实体类型、SAP 表与字段名为身份键，不可修改。'
              : '实体类型 + SAP 表 + 字段名构成唯一键，重复登记将返回 409。'}
          </DialogDescription>
        </DialogHeader>
        {open && <FieldForm {...props} onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
};

function FieldsPanel({ writable }: { writable: boolean }) {
  // 过滤 / 分页状态：映射到后端查询参数 entity_type / view_section / must_govern / keyword / skip / limit
  const [entityType, setEntityType] = useState<EntityType | typeof ALL>(ALL);
  const [viewSection, setViewSection] = useState<string>(ALL);
  /** 「只看必须治理」默认开启；关闭时不传 must_govern 参数（= 不限） */
  const [mustGovernOnly, setMustGovernOnly] = useState(true);
  const [keyword, setKeyword] = useState('');
  /** 关键词防抖后的生效值（避免逐键击发请求） */
  const [appliedKeyword, setAppliedKeyword] = useState('');
  const [limit, setLimit] = useState<number>(DEFAULT_LIMIT);
  const [skip, setSkip] = useState<number>(0);

  const [items, setItems] = useState<MetadataField[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  /** 术语下拉候选：失败不阻断登记册（仅下拉缺少选项） */
  const [glossaryTerms, setGlossaryTerms] = useState<GlossaryTerm[]>([]);

  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');
  const [formField, setFormField] = useState<MetadataField | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setAppliedKeyword(keyword.trim());
      setSkip(0);
      setLoading(true);
    }, 300);
    return () => clearTimeout(timer);
  }, [keyword]);

  useEffect(() => {
    let cancelled = false;
    api<GlossaryTerm[]>('/api/metadata/glossary', { silentError: true })
      .then((result) => {
        if (!cancelled) setGlossaryTerms(result);
      })
      .catch(() => {
        /* 术语列表加载失败不影响字段登记册主流程 */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const buildQuery = useCallback(() => {
    // 先用 MetadataFieldQuery 类型构造（键名与后端端点参数对齐），再序列化
    const query: MetadataFieldQuery = { skip, limit };
    if (entityType !== ALL) query.entity_type = entityType;
    if (viewSection !== ALL) query.view_section = viewSection;
    // 布尔参数序列化为字符串；开关关闭时省略参数表示「不限」
    if (mustGovernOnly) query.must_govern = true;
    if (appliedKeyword) query.keyword = appliedKeyword;
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      params.set(key, String(value));
    }
    return params.toString();
  }, [entityType, viewSection, mustGovernOnly, appliedKeyword, skip, limit]);

  const loadList = useCallback(
    () =>
      api<MetadataFieldListResponse>(`/api/metadata/fields?${buildQuery()}`, {
        silentError: true,
      }),
    [buildQuery],
  );

  const applyResult = useCallback((result: MetadataFieldListResponse) => {
    setItems(result.items);
    setTotal(result.total);
    setLoadError(null);
    setLoading(false);
  }, []);

  const applyError = useCallback((err: unknown) => {
    setItems([]);
    setTotal(0);
    setLoadError(err instanceof Error ? err.message : '字段登记册加载失败');
    setLoading(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadList()
      .then((result) => {
        if (!cancelled) applyResult(result);
      })
      .catch((err: unknown) => {
        if (!cancelled) applyError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [loadList, applyResult, applyError]);

  const reload = useCallback(() => {
    setLoading(true);
    loadList().then(applyResult).catch(applyError);
  }, [applyError, applyResult, loadList]);

  /** 视图分组选项：由当前已加载数据的 view_section 去重生成 */
  const viewSectionOptions = useMemo(() => {
    const sections = new Set<string>();
    for (const item of items) {
      if (item.view_section) sections.add(item.view_section);
    }
    if (viewSection !== ALL) sections.add(viewSection);
    return Array.from(sections).sort();
  }, [items, viewSection]);

  const currentPage = Math.floor(skip / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const rangeStart = total === 0 ? 0 : skip + 1;
  const rangeEnd = Math.min(skip + limit, total);

  const openCreate = () => {
    setFormMode('create');
    setFormField(null);
    setFormOpen(true);
  };

  const openEdit = (field: MetadataField) => {
    setFormMode('edit');
    setFormField(field);
    setFormOpen(true);
  };

  const handleSaved = () => {
    if (formMode === 'edit') {
      reload();
      return;
    }
    // 新建后回到首页，确保新记录可见
    if (skip === 0) reload();
    else setSkip(0);
  };

  return (
    <div className="space-y-4">
      {/* 筛选栏 */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Label className="text-xs text-gray-500">实体类型</Label>
            <Select
              value={entityType}
              onValueChange={(value) => {
                setLoading(true);
                setEntityType(value as EntityType | typeof ALL);
                setSkip(0);
              }}
            >
              <SelectTrigger size="sm" className="w-32">
                <SelectValue placeholder="全部实体" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>全部实体</SelectItem>
                {ENTITY_TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <Label className="text-xs text-gray-500">视图分组</Label>
            <Select
              value={viewSection}
              onValueChange={(value) => {
                setLoading(true);
                setViewSection(value);
                setSkip(0);
              }}
            >
              <SelectTrigger size="sm" className="w-36">
                <SelectValue placeholder="全部视图" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>全部视图</SelectItem>
                {viewSectionOptions.map((section) => (
                  <SelectItem key={section} value={section}>
                    {section}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <Switch
              id="meta_fields_must_govern"
              checked={mustGovernOnly}
              onCheckedChange={(checked) => {
                setLoading(true);
                setMustGovernOnly(checked);
                setSkip(0);
              }}
            />
            <Label htmlFor="meta_fields_must_govern" className="cursor-pointer text-xs text-gray-500">
              只看必须治理
            </Label>
          </div>

          <div className="flex items-center gap-2">
            <Label className="text-xs text-gray-500">每页</Label>
            <Select
              value={String(limit)}
              onValueChange={(value) => {
                setLoading(true);
                setLimit(Number(value));
                setSkip(0);
              }}
            >
              <SelectTrigger size="sm" className="w-20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LIMIT_OPTIONS.map((size) => (
                  <SelectItem key={size} value={String(size)}>
                    {size}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="relative ml-auto w-full max-w-xs">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gray-400" />
            <Input
              className="pl-9"
              placeholder="搜索字段名 / 中文标签"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
            />
          </div>

          <Button variant="outline" size="icon" title="刷新" onClick={reload}>
            {loading ? <Spinner className="size-4" /> : <RefreshCw />}
          </Button>

          {writable && (
            <Button onClick={openCreate}>
              <Plus />
              登记新字段
            </Button>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-gray-500">
          <span>
            共 {total} 条元数据字段，本页第 {rangeStart}–{rangeEnd} 条
          </span>
          {!writable && (
            <span className="text-gray-400">
              当前角色为只读：仅数据管理员 / 管理员可登记与编辑元数据字段
            </span>
          )}
        </div>
      </div>

      {/* 字段列表 */}
      {loadError && !loading ? (
        <LoadErrorBox label="字段登记册" error={loadError} onRetry={reload} />
      ) : loading ? (
        <LoadingBox />
      ) : items.length === 0 ? (
        <EmptyBox
          title="暂无元数据字段"
          description="调整筛选条件或关闭「只看必须治理」；数据管理员可登记第一条元数据字段。"
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>字段名</TableHead>
                <TableHead>中文标签</TableHead>
                <TableHead>实体</TableHead>
                <TableHead>SAP 表</TableHead>
                <TableHead>视图</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>来源</TableHead>
                <TableHead>必须治理</TableHead>
                <TableHead>关联术语</TableHead>
                <TableHead>标准数</TableHead>
                <TableHead>业务定义</TableHead>
                {writable && <TableHead className="text-right">操作</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id} className={item.is_active ? '' : 'opacity-60'}>
                  <TableCell className="font-mono text-xs font-medium">{item.field_name}</TableCell>
                  <TableCell className="whitespace-nowrap text-sm">{item.field_label}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">
                      {ENTITY_TYPE_LABELS[item.entity_type] ?? item.entity_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{item.sap_table ?? '—'}</TableCell>
                  <TableCell className="whitespace-nowrap text-sm">
                    {item.view_section ?? '—'}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-normal">
                      {DATA_TYPE_LABELS[item.data_type] ?? item.data_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-sm">
                    {item.standard_source ? (
                      <Badge variant="secondary" className="font-normal">
                        {METADATA_SOURCE_LABELS[item.standard_source]}
                      </Badge>
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {item.must_govern ? (
                      <Badge className="border border-amber-200 bg-amber-100 font-normal text-amber-800">
                        是
                      </Badge>
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-sm">
                    {item.glossary_term_name ? (
                      item.glossary_term_name
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {item.standard_count > 0 ? (
                      <Badge variant="secondary" className="font-normal">
                        {item.standard_count}
                      </Badge>
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </TableCell>
                  <TableCell className="max-w-56 text-xs text-gray-500">
                    {item.business_definition ? (
                      <span className="block truncate" title={item.business_definition}>
                        {item.business_definition}
                      </span>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  {writable && (
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          title="编辑"
                          onClick={() => openEdit(item)}
                        >
                          <Pencil />
                        </Button>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* 分页（skip / limit） */}
      <div className="flex items-center justify-between text-sm text-gray-500">
        <span>
          第 {currentPage} / {totalPages} 页
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={loading || skip <= 0}
            onClick={() => {
              setLoading(true);
              setSkip(Math.max(0, skip - limit));
            }}
          >
            上一页
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={loading || skip + limit >= total}
            onClick={() => {
              setLoading(true);
              setSkip(skip + limit);
            }}
          >
            下一页
          </Button>
        </div>
      </div>

      <FieldFormDialog
        open={formOpen}
        mode={formMode}
        field={formField}
        defaultEntityType={entityType === ALL ? 'material' : entityType}
        glossaryTerms={glossaryTerms}
        onOpenChange={setFormOpen}
        onSaved={handleSaved}
      />
    </div>
  );
}

// ========== 业务术语 ==========

interface GlossaryFormDialogProps {
  open: boolean;
  mode: 'create' | 'edit';
  /** 编辑时的原始术语；新建时传 null */
  term: GlossaryTerm | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}

interface GlossaryFormProps extends GlossaryFormDialogProps {
  onClose: () => void;
}

function GlossaryForm({ mode, term, onSaved, onClose }: GlossaryFormProps) {
  const isEdit = mode === 'edit';
  const [values, setValues] = useState<GlossaryFormValues>(() =>
    term ? glossaryFormFromTerm(term) : emptyGlossaryForm(),
  );
  const [errors, setErrors] = useState<GlossaryFormErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const setField = <K extends keyof GlossaryFormValues>(key: K, value: GlossaryFormValues[K]) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => (prev[key] ? { ...prev, [key]: undefined } : prev));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;

    const nextErrors = validateGlossaryForm(values);
    setErrors(nextErrors);
    if (hasFieldFormErrors(nextErrors)) {
      setServerError(null);
      return;
    }
    setSubmitting(true);
    setServerError(null);
    try {
      if (isEdit) {
        if (!term) {
          setServerError('缺少术语 ID，无法保存');
          return;
        }
        await api<GlossaryTerm>(`/api/metadata/glossary/${term.id}`, {
          method: 'PUT',
          body: JSON.stringify(toGlossaryUpdatePayload(values)),
          silentError: true,
        });
      } else {
        await api<GlossaryTerm>('/api/metadata/glossary', {
          method: 'POST',
          body: JSON.stringify(toGlossaryCreatePayload(values)),
          silentError: true,
        });
      }
      toast.success(isEdit ? '业务术语已更新' : '业务术语已创建');
      onSaved();
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : '保存失败';
      const status = err instanceof ApiError ? err.status : 0;
      if (status === 400 || status === 404 || status === 409) {
        // 409 术语已存在 / 400 未提供可更新字段 / 404 术语不存在 —— 就地提示
        setServerError(message);
      } else {
        toast.error(message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="mt-2">
      <div className="grid grid-cols-1 gap-4">
        <div>
          <Label htmlFor="meta_glossary_term">术语名称 *</Label>
          <Input
            id="meta_glossary_term"
            value={values.term}
            onChange={(e) => setField('term', e.target.value)}
            maxLength={METADATA_LIMITS.term}
            disabled={isEdit}
            placeholder="如 物料编码"
            className="disabled:bg-gray-100 disabled:text-gray-500"
          />
          <FieldError message={errors.term} />
        </div>

        <div>
          <Label htmlFor="meta_glossary_definition">术语定义 *</Label>
          <Textarea
            id="meta_glossary_definition"
            value={values.definition}
            onChange={(e) => setField('definition', e.target.value)}
            rows={3}
            placeholder="术语的业务定义与使用口径"
          />
          <FieldError message={errors.definition} />
        </div>

        <div>
          <Label htmlFor="meta_glossary_aliases">别名</Label>
          <Input
            id="meta_glossary_aliases"
            value={values.aliases}
            onChange={(e) => setField('aliases', e.target.value)}
            placeholder="多个别名用逗号分隔，如 物料号, 料号"
          />
          <p className="mt-1 text-xs text-gray-400">以逗号或换行分隔，提交时转为字符串数组。</p>
          <FieldError message={errors.aliases} />
        </div>

        {serverError && (
          <div
            role="alert"
            className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
          >
            {serverError}
          </div>
        )}
      </div>

      <DialogFooter className="mt-6">
        <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
          取消
        </Button>
        <Button type="submit" disabled={submitting} className="bg-blue-600 hover:bg-blue-700">
          {submitting && <Spinner />}
          {submitting ? '保存中...' : isEdit ? '保存修改' : '新增术语'}
        </Button>
      </DialogFooter>
    </form>
  );
}

const GlossaryFormDialog: React.FC<GlossaryFormDialogProps> = (props) => {
  const { open, mode, onOpenChange } = props;
  const isEdit = mode === 'edit';
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] gap-0 overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? '编辑业务术语' : '新增业务术语'}</DialogTitle>
          <DialogDescription>
            {isEdit ? '术语名称为身份键，不可修改。' : '术语名称全局唯一，重复创建将返回 409。'}
          </DialogDescription>
        </DialogHeader>
        {open && <GlossaryForm {...props} onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
};

function GlossaryPanel({ writable }: { writable: boolean }) {
  const [terms, setTerms] = useState<GlossaryTerm[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');
  const [formTerm, setFormTerm] = useState<GlossaryTerm | null>(null);

  /** 术语端点直接返回数组（field_count 由后端装配） */
  const loadTerms = useCallback(
    () => api<GlossaryTerm[]>('/api/metadata/glossary', { silentError: true }),
    [],
  );

  const applyResult = useCallback((result: GlossaryTerm[]) => {
    setTerms(result);
    setLoadError(null);
    setLoading(false);
  }, []);

  const applyError = useCallback((err: unknown) => {
    setTerms([]);
    setLoadError(err instanceof Error ? err.message : '业务术语加载失败');
    setLoading(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadTerms()
      .then((result) => {
        if (!cancelled) applyResult(result);
      })
      .catch((err: unknown) => {
        if (!cancelled) applyError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [loadTerms, applyResult, applyError]);

  const reload = useCallback(() => {
    setLoading(true);
    loadTerms().then(applyResult).catch(applyError);
  }, [applyError, applyResult, loadTerms]);

  const openCreate = () => {
    setFormMode('create');
    setFormTerm(null);
    setFormOpen(true);
  };

  const openEdit = (term: GlossaryTerm) => {
    setFormMode('edit');
    setFormTerm(term);
    setFormOpen(true);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-gray-500">
          共 {terms.length} 条业务术语
          {!writable && '（当前角色为只读：仅数据管理员 / 管理员可新增与编辑术语）'}
        </span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" title="刷新" onClick={reload}>
            {loading ? <Spinner className="size-4" /> : <RefreshCw />}
          </Button>
          {writable && (
            <Button onClick={openCreate}>
              <Plus />
              新增术语
            </Button>
          )}
        </div>
      </div>

      {loadError && !loading ? (
        <LoadErrorBox label="业务术语" error={loadError} onRetry={reload} />
      ) : loading ? (
        <LoadingBox />
      ) : terms.length === 0 ? (
        <EmptyBox
          title="暂无业务术语"
          description="数据管理员可新增第一条业务术语；术语可在字段登记册中关联到元数据字段。"
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>术语</TableHead>
                <TableHead>定义</TableHead>
                <TableHead>别名</TableHead>
                <TableHead>关联字段数</TableHead>
                {writable && <TableHead className="text-right">操作</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {terms.map((term) => (
                <TableRow key={term.id}>
                  <TableCell className="whitespace-nowrap text-sm font-medium">{term.term}</TableCell>
                  <TableCell className="max-w-md text-sm text-gray-600">
                    <span className="line-clamp-2" title={term.definition}>
                      {term.definition}
                    </span>
                  </TableCell>
                  <TableCell className="max-w-52">
                    <div className="flex flex-wrap gap-1">
                      {(term.aliases ?? []).map((alias) => (
                        <Badge key={alias} variant="outline" className="font-normal">
                          {alias}
                        </Badge>
                      ))}
                      {(term.aliases ?? []).length === 0 && (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    {term.field_count > 0 ? (
                      <Badge variant="secondary" className="font-normal">
                        {term.field_count}
                      </Badge>
                    ) : (
                      <span className="text-xs text-gray-400">0</span>
                    )}
                  </TableCell>
                  {writable && (
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          title="编辑"
                          onClick={() => openEdit(term)}
                        >
                          <Pencil />
                        </Button>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <GlossaryFormDialog
        open={formOpen}
        mode={formMode}
        term={formTerm}
        onOpenChange={setFormOpen}
        onSaved={reload}
      />
    </div>
  );
}

// ========== 页面入口 ==========

const Metadata: React.FC = () => {
  const writable = useMemo(() => canWrite(), []);
  const [tab, setTab] = useState<MetadataTab>('entities');

  return (
    <div className="space-y-4">
      <Tabs value={tab} onValueChange={(value) => setTab(value as MetadataTab)}>
        <TabsList>
          <TabsTrigger value="entities">实体总览</TabsTrigger>
          <TabsTrigger value="fields">字段登记册</TabsTrigger>
          <TabsTrigger value="glossary">业务术语</TabsTrigger>
        </TabsList>
      </Tabs>

      {tab === 'entities' && <EntitiesPanel writable={writable} />}
      {tab === 'fields' && <FieldsPanel writable={writable} />}
      {tab === 'glossary' && <GlossaryPanel writable={writable} />}
    </div>
  );
};

export default Metadata;
