/**
 * 质量检测字典与展示辅助（SPEC §3.2）。
 *
 * RULE_TYPE_LABELS 与 backend/app/services/rule_derivation.py 的同名字典一致；
 * 严重程度三档与 backend/app/api/quality_checks.py 的 _SEVERITIES 一致。
 */
import { format } from 'date-fns';

import { splitList } from '@/lib/governance';
import type { CheckSeverity, RuleType } from '@/types/api';

export const RULE_TYPE_LABELS: Record<RuleType, string> = {
  null_check: '必填检查',
  format_check: '格式检查',
  range_check: '值域检查',
  length_check: '长度检查',
  unique_check: '唯一性检查',
};

export const SEVERITY_LABELS: Record<CheckSeverity, string> = {
  error: '错误',
  warning: '警告',
  info: '提示',
};

export const SEVERITY_OPTIONS: { value: CheckSeverity; label: string }[] = [
  { value: 'error', label: '错误' },
  { value: 'warning', label: '警告' },
  { value: 'info', label: '提示' },
];

/** 严重程度徽标配色（与 DataStandards 的必填/唯一徽标风格一致） */
export function severityBadgeClass(severity: CheckSeverity): string {
  switch (severity) {
    case 'error':
      return 'border-red-200 bg-red-100 text-red-800';
    case 'warning':
      return 'border-amber-200 bg-amber-100 text-amber-800';
    default:
      return 'border-gray-200 bg-gray-100 text-gray-600';
  }
}

/** 0~1 的通过率 → 百分比字符串（后端 pass_rate 口径 round(..., 4)） */
export function formatPercent(rate: number): string {
  if (!Number.isFinite(rate)) return '—';
  return `${(rate * 100).toFixed(2)}%`;
}

/** 图表配色：通过/失败 + 三档严重程度 */
export const CHART_COLORS = {
  passed: '#16a34a',
  failed: '#dc2626',
  error: '#dc2626',
  warning: '#d97706',
  info: '#6b7280',
} as const;

/** 实体 ID 文本框 → 数组（复用 splitList 的逗号/换行分隔去重逻辑） */
export function parseEntityIds(raw: string): string[] {
  return splitList(raw);
}

/**
 * 后端 DateTime 列存的是无偏移量的 UTC 值，序列化结果不带 Z；
 * 补齐时区后再格式化（与 DataStandards.formatTimestamp 同源）。
 */
export function formatTimestamp(raw: string | null | undefined): string {
  if (!raw) return '—';
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(raw) ? raw : `${raw}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return raw;
  return format(date, 'yyyy-MM-dd HH:mm');
}
