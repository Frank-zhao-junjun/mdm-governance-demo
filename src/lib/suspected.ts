/**
 * 疑似错误字典与展示辅助（SPEC §2.7 / §3.3）。
 *
 * 错误类型 / 状态取值与 backend schemas.SuspectedErrorType /
 * SuspectedErrorResolveRequest.status 一致；处置模板取自 SPEC §1.6.3。
 */
import type {
  SuspectedErrorStatus,
  SuspectedErrorType,
  SuspectedResolveStatus,
} from '@/types/api';

/** v1 可检测的错误类型（= backend suspected_error_runner.SUPPORTED_ERROR_TYPES） */
export const DETECTABLE_ERROR_TYPES: SuspectedErrorType[] = ['duplicate', 'naming'];

export const ERROR_TYPE_LABELS: Record<SuspectedErrorType, string> = {
  duplicate: '疑似重复',
  naming: '命名不规范',
  classification: '分类错误',
  unit: '计量单位错误',
};

export const ERROR_TYPE_OPTIONS: { value: SuspectedErrorType; label: string }[] = [
  { value: 'duplicate', label: '疑似重复' },
  { value: 'naming', label: '命名不规范' },
];

export const STATUS_LABELS: Record<SuspectedErrorStatus, string> = {
  pending: '待处理',
  confirmed: '已确认',
  resolved: '已解决',
  false_positive: '误报',
};

export const STATUS_OPTIONS: { value: SuspectedErrorStatus; label: string }[] = [
  { value: 'pending', label: '待处理' },
  { value: 'confirmed', label: '已确认' },
  { value: 'resolved', label: '已解决' },
  { value: 'false_positive', label: '误报' },
];

/** 处理对话框可选目标状态（schemas 三值集合） */
export const RESOLUTION_OPTIONS: { value: SuspectedResolveStatus; label: string }[] = [
  { value: 'confirmed', label: '确认问题' },
  { value: 'resolved', label: '标记已解决' },
  { value: 'false_positive', label: '标记误报' },
];

/** 状态徽标配色：pending 琥珀 / confirmed 红 / resolved 绿 / false_positive 灰 */
export function statusBadgeClass(status: SuspectedErrorStatus): string {
  switch (status) {
    case 'pending':
      return 'border-amber-200 bg-amber-100 text-amber-800';
    case 'confirmed':
      return 'border-red-200 bg-red-100 text-red-800';
    case 'resolved':
      return 'border-green-200 bg-green-100 text-green-800';
    default:
      return 'border-gray-200 bg-gray-100 text-gray-600';
  }
}

/** 处理对话框预填模板（SPEC §1.6.3 处置建议，用户可修改） */
export const RESOLUTION_TEMPLATES: Record<SuspectedResolveStatus, string> = {
  confirmed: '该数据与已存在记录重复，按标准合并/去重。',
  resolved: '修复完成，问题已处理。',
  false_positive: '当前规则对该数据判定存在偏差，需关闭该问题。',
};
