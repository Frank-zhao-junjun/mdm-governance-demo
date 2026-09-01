import React, { useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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
import { Textarea } from '@/components/ui/textarea';
import { ApiError, api } from '@/lib/api';
import {
  DATA_TYPE_OPTIONS,
  ENTITY_TYPE_OPTIONS,
  LIMITS,
  STANDARD_SOURCE_OPTIONS,
  emptyForm,
  formFromStandard,
  hasFormErrors,
  toCreatePayload,
  toUpdatePayload,
  validateStandardForm,
  type StandardFormErrors,
  type StandardFormValues,
} from '@/lib/governance';
import type { DataStandard, EntityType, StandardDataType, StandardSource } from '@/types/api';

/** Radix Select 不允许 value=""，用哨兵表示「未指定」 */
const SOURCE_NONE = '__none__';

/** SAP 表输入框的候选提示（datalist id，页面内唯一） */
const SAP_TABLE_DATALIST_ID = 'sap-table-suggestions';

interface DataStandardFormDialogProps {
  open: boolean;
  mode: 'create' | 'edit';
  /** 编辑时的原始标准；新建时传 null */
  standard: DataStandard | null;
  /** 新建时的默认实体类型（跟随当前实体筛选） */
  defaultEntityType: EntityType;
  /** SAP 表候选，用于输入提示 */
  sapTableSuggestions: string[];
  onOpenChange: (open: boolean) => void;
  /** 保存成功后回调（父组件据此刷新列表） */
  onSaved: (saved: DataStandard) => void;
}

interface DataStandardFormProps extends DataStandardFormDialogProps {
  /** 关闭对话框（Radix 会在关闭时卸载内容，因此表单每次打开都是全新状态） */
  onClose: () => void;
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="mt-1 text-xs text-destructive">{message}</p>;
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-sm font-semibold text-gray-700 sm:col-span-2">
      {children}
      <span className="ml-2 text-xs font-normal text-gray-400">
        {children === '管理属性' ? 'SPEC §1.5.3' : children === '业务属性' ? 'SPEC §1.5.1' : ''}
      </span>
    </h3>
  );
}

/**
 * 表单本体。作为 DialogContent 的子组件挂载：Radix 在关闭时卸载内容，
 * 因此 useState 惰性初始值即可保证「每次打开都是最新记录」，无需在 effect 里重置。
 */
function DataStandardForm({
  mode,
  standard,
  defaultEntityType,
  sapTableSuggestions,
  onSaved,
  onClose,
}: DataStandardFormProps) {
  const isEdit = mode === 'edit';
  const [values, setValues] = useState<StandardFormValues>(() =>
    standard ? formFromStandard(standard) : emptyForm(defaultEntityType),
  );
  const [errors, setErrors] = useState<StandardFormErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const setField = <K extends keyof StandardFormValues>(
    key: K,
    value: StandardFormValues[K],
  ) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => (prev[key] ? { ...prev, [key]: undefined } : prev));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;

    const nextErrors = validateStandardForm(values);
    setErrors(nextErrors);
    if (hasFormErrors(nextErrors)) {
      setServerError(null);
      return;
    }
    setSubmitting(true);
    setServerError(null);
    try {
      let saved: DataStandard;
      if (isEdit) {
        if (!standard) {
          setServerError('缺少数据标准 ID，无法保存');
          return;
        }
        saved = await api<DataStandard>(`/api/data-standards/${standard.id}`, {
          method: 'PUT',
          body: JSON.stringify(toUpdatePayload(values)),
          silentError: true,
        });
      } else {
        saved = await api<DataStandard>('/api/data-standards', {
          method: 'POST',
          body: JSON.stringify(toCreatePayload(values)),
          silentError: true,
        });
      }
      toast.success(isEdit ? '数据标准已更新' : '数据标准已创建');
      onSaved(saved);
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : '保存失败';
      const status = err instanceof ApiError ? err.status : 0;
      if (status === 400 || status === 404 || status === 409) {
        // 409 同（实体, SAP表, 字段）已存在 / 400 未提供可更新字段 / 404 记录不存在 —— 就地提示
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
          <Label htmlFor="std_entity_type">实体类型 *</Label>
          <Select
            value={values.entity_type}
            onValueChange={(next) => setField('entity_type', next as EntityType)}
            disabled={isEdit}
          >
            <SelectTrigger id="std_entity_type" className="w-full">
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
          <Label htmlFor="std_sap_table">SAP 表</Label>
          <Input
            id="std_sap_table"
            list={SAP_TABLE_DATALIST_ID}
            value={values.sap_table}
            onChange={(e) => setField('sap_table', e.target.value)}
            maxLength={LIMITS.sapTable}
            disabled={isEdit}
            placeholder="如 MARA / BUT000 / KNA1（可留空）"
            className="disabled:bg-gray-100 disabled:text-gray-500"
          />
          <datalist id={SAP_TABLE_DATALIST_ID}>
            {sapTableSuggestions.map((table) => (
              <option key={table} value={table} />
            ))}
          </datalist>
          <FieldError message={errors.sap_table} />
        </div>

        <div>
          <Label htmlFor="std_field_name">字段名 *</Label>
          <Input
            id="std_field_name"
            value={values.field_name}
            onChange={(e) => setField('field_name', e.target.value)}
            maxLength={LIMITS.fieldName}
            disabled={isEdit}
            placeholder="如 MATNR / NAME1"
            className="font-mono disabled:bg-gray-100 disabled:text-gray-500"
          />
          <FieldError message={errors.field_name} />
        </div>

        <div>
          <Label htmlFor="std_field_label">字段中文标签 *</Label>
          <Input
            id="std_field_label"
            value={values.field_label}
            onChange={(e) => setField('field_label', e.target.value)}
            maxLength={LIMITS.fieldLabel}
            placeholder="如 物料编码"
          />
          <FieldError message={errors.field_label} />
        </div>

        <SectionTitle>数据属性与校验规则</SectionTitle>

        <div>
          <Label htmlFor="std_data_type">数据类型 *</Label>
          <Select
            value={values.data_type}
            onValueChange={(next) => setField('data_type', next as StandardDataType)}
          >
            <SelectTrigger id="std_data_type" className="w-full">
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
          <Label htmlFor="std_max_length">最大长度</Label>
          <Input
            id="std_max_length"
            type="number"
            min={LIMITS.maxLengthMin}
            max={LIMITS.maxLengthMax}
            value={values.max_length}
            onChange={(e) => setField('max_length', e.target.value)}
            placeholder={`${LIMITS.maxLengthMin} ~ ${LIMITS.maxLengthMax}`}
          />
          <FieldError message={errors.max_length} />
        </div>

        <div>
          <Label htmlFor="std_min_value">最小值（值域）</Label>
          <Input
            id="std_min_value"
            type="number"
            step="any"
            value={values.min_value}
            onChange={(e) => setField('min_value', e.target.value)}
            placeholder="如 0"
          />
          <FieldError message={errors.min_value} />
        </div>

        <div>
          <Label htmlFor="std_max_value">最大值（值域）</Label>
          <Input
            id="std_max_value"
            type="number"
            step="any"
            value={values.max_value}
            onChange={(e) => setField('max_value', e.target.value)}
            placeholder="如 999999"
          />
          <FieldError message={errors.max_value} />
        </div>

        <div className="sm:col-span-2">
          <Label htmlFor="std_enum_values">枚举值</Label>
          <Input
            id="std_enum_values"
            value={values.enum_values}
            onChange={(e) => setField('enum_values', e.target.value)}
            placeholder="多个值用逗号分隔，如 KG, G, PC"
          />
          <p className="mt-1 text-xs text-gray-400">以逗号或换行分隔，提交时转为字符串数组。</p>
          <FieldError message={errors.enum_values} />
        </div>

        <div className="sm:col-span-2">
          <Label htmlFor="std_pattern">正则校验（pattern）</Label>
          <Input
            id="std_pattern"
            value={values.pattern}
            onChange={(e) => setField('pattern', e.target.value)}
            maxLength={LIMITS.pattern}
            placeholder="如 ^M\d{5}$"
            className="font-mono"
          />
          <p className="mt-1 text-xs text-gray-400">
            格式校验规则，最长 {LIMITS.pattern} 字符；留空表示不校验格式。
          </p>
          <FieldError message={errors.pattern} />
        </div>

        <div className="flex items-center justify-between gap-4 rounded-md border border-gray-200 px-3 py-2">
          <Label htmlFor="std_required" className="cursor-pointer">
            必填
          </Label>
          <Switch
            id="std_required"
            checked={values.required}
            onCheckedChange={(checked) => setField('required', checked)}
          />
        </div>

        <div className="flex items-center justify-between gap-4 rounded-md border border-gray-200 px-3 py-2">
          <Label htmlFor="std_unique" className="cursor-pointer">
            唯一
          </Label>
          <Switch
            id="std_unique"
            checked={values.unique}
            onCheckedChange={(checked) => setField('unique', checked)}
          />
        </div>

        <SectionTitle>管理属性</SectionTitle>

        <div>
          <Label htmlFor="std_owner">标准定义人</Label>
          <Input
            id="std_owner"
            value={values.owner}
            onChange={(e) => setField('owner', e.target.value)}
            maxLength={LIMITS.owner}
            placeholder="如 钱数据"
          />
          <FieldError message={errors.owner} />
        </div>

        <div>
          <Label htmlFor="std_source">标准来源</Label>
          <Select
            value={values.standard_source || SOURCE_NONE}
            onValueChange={(next) =>
              setField('standard_source', next === SOURCE_NONE ? '' : (next as StandardSource))
            }
          >
            <SelectTrigger id="std_source" className="w-full">
              <SelectValue placeholder="选择标准来源" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={SOURCE_NONE}>未指定</SelectItem>
              {STANDARD_SOURCE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}（{option.value}）
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldError message={errors.standard_source} />
        </div>

        <div className="sm:col-span-2">
          <Label htmlFor="std_dept_scope">应用部门</Label>
          <Input
            id="std_dept_scope"
            value={values.dept_scope}
            onChange={(e) => setField('dept_scope', e.target.value)}
            placeholder="多个部门用逗号分隔，如 采购部, 生产部, 财务部"
          />
          <FieldError message={errors.dept_scope} />
        </div>

        <SectionTitle>业务属性</SectionTitle>

        <div>
          <Label htmlFor="std_topic">标准主题</Label>
          <Input
            id="std_topic"
            value={values.standard_topic}
            onChange={(e) => setField('standard_topic', e.target.value)}
            placeholder="如 物料 / 供应商 / 客户"
          />
          <p className="mt-1 text-xs text-gray-400">写入 business_attrs.standard_topic。</p>
        </div>

        <div>
          <Label htmlFor="std_subcategory">标准小类</Label>
          <Input
            id="std_subcategory"
            value={values.standard_subcategory}
            onChange={(e) => setField('standard_subcategory', e.target.value)}
            placeholder="如 编码 / 名称 / 分类 / 状态"
          />
          <p className="mt-1 text-xs text-gray-400">写入 business_attrs.standard_subcategory。</p>
        </div>

        <div className="sm:col-span-2">
          <Label htmlFor="std_description">业务定义</Label>
          <Textarea
            id="std_description"
            value={values.description}
            onChange={(e) => setField('description', e.target.value)}
            rows={2}
            placeholder="字段的业务含义与约束原因"
          />
        </div>

        <div className="sm:col-span-2">
          <Label htmlFor="std_sap_field_desc">SAP 字段说明</Label>
          <Textarea
            id="std_sap_field_desc"
            value={values.sap_field_desc}
            onChange={(e) => setField('sap_field_desc', e.target.value)}
            rows={2}
            placeholder="SAP 原始字段语义，如 MARA-MATNR"
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
          {submitting ? '保存中...' : isEdit ? '保存修改' : '创建标准'}
        </Button>
      </DialogFooter>
    </form>
  );
}

const DataStandardFormDialog: React.FC<DataStandardFormDialogProps> = (props) => {
  const { open, mode, onOpenChange } = props;
  const isEdit = mode === 'edit';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] gap-0 overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? '编辑数据标准' : '新建数据标准'}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? '实体类型、SAP 表与字段名为身份键，不可修改；唯一约束为（实体类型, SAP 表, 字段名）。'
              : '按 SPEC §2.1 定义字段的数据标准，实体类型 + SAP 表 + 字段名构成唯一键。'}
          </DialogDescription>
        </DialogHeader>
        {open && <DataStandardForm {...props} onClose={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
};

export default DataStandardFormDialog;
