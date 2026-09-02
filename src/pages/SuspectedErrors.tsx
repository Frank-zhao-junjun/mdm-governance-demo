import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Eye, Play, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';

import { api, canWrite } from '@/lib/api';
import { ENTITY_TYPE_OPTIONS } from '@/lib/governance';
import { SEVERITY_LABELS, formatTimestamp, severityBadgeClass } from '@/lib/quality';
import {
  DETECTABLE_ERROR_TYPES,
  ERROR_TYPE_LABELS,
  ERROR_TYPE_OPTIONS,
  RESOLUTION_OPTIONS,
  RESOLUTION_TEMPLATES,
  STATUS_LABELS,
  STATUS_OPTIONS,
  statusBadgeClass,
} from '@/lib/suspected';
import type {
  EntityType,
  SuspectedDetectPayload,
  SuspectedDetectResponse,
  SuspectedError,
  SuspectedErrorListResponse,
  SuspectedErrorStatus,
  SuspectedErrorType,
  SuspectedResolvePayload,
  SuspectedResolveStatus,
} from '@/types/api';

/** Radix Select 不允许 value=""，过滤项用哨兵表示「不限」 */
const ALL = 'all';
const DEFAULT_LIMIT = 20;
const LIMIT_OPTIONS = [20, 50, 100, 200];

/** 详情弹窗里已专门渲染的证据键，剩余键值走兜底列表 */
const RENDERED_EVIDENCE_KEYS = new Set([
  'strategy',
  'rule',
  'rule_code',
  'rule_label',
  'violation',
  'reason',
  'similarity',
  'field',
  'column',
  'entity_code',
  'entity_name',
  'matched_code',
  'matched_name',
  'suggestion',
  'keeper_rule',
]);

function formatSimilarity(value: unknown): string {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—';
}

/** 行内关键证据摘要（供表格「依据」列鼠标悬停） */
function evidenceSummary(item: SuspectedError): string {
  const d = item.details;
  if (!d) return item.description ?? '';
  if (item.error_type === 'duplicate') {
    return d.suggestion ?? d.reason ?? item.description ?? '';
  }
  return d.violation ?? d.rule_label ?? item.description ?? '';
}

const SuspectedErrors: React.FC = () => {
  const writable = useMemo(() => canWrite(), []);

  // 检测卡：实体类型 + 错误类型多选（默认全选）
  const [entityType, setEntityType] = useState<EntityType>('material');
  const [selectedTypes, setSelectedTypes] = useState<Set<SuspectedErrorType>>(
    () => new Set(DETECTABLE_ERROR_TYPES),
  );
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [lastDetect, setLastDetect] = useState<SuspectedDetectResponse | null>(null);

  // 结果卡：错误类型 / 状态筛选 + skip / limit 分页
  const [errorTypeFilter, setErrorTypeFilter] = useState<SuspectedErrorType | typeof ALL>(ALL);
  const [statusFilter, setStatusFilter] = useState<SuspectedErrorStatus | typeof ALL>(ALL);
  const [limit, setLimit] = useState<number>(DEFAULT_LIMIT);
  const [skip, setSkip] = useState<number>(0);
  const [items, setItems] = useState<SuspectedError[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // 详情弹窗 + 处理弹窗
  const [detailItem, setDetailItem] = useState<SuspectedError | null>(null);
  const [resolveItem, setResolveItem] = useState<SuspectedError | null>(null);
  const [resolveStatus, setResolveStatus] = useState<SuspectedResolveStatus>('confirmed');
  const [resolveNote, setResolveNote] = useState('');
  const [resolving, setResolving] = useState(false);
  const [resolveError, setResolveError] = useState<string | null>(null);

  // ===== 结果列表 =====

  const buildListQuery = useCallback(() => {
    const params = new URLSearchParams();
    params.set('entity_type', entityType);
    if (errorTypeFilter !== ALL) params.set('error_type', errorTypeFilter);
    if (statusFilter !== ALL) params.set('status', statusFilter);
    params.set('skip', String(skip));
    params.set('limit', String(limit));
    return params.toString();
  }, [entityType, errorTypeFilter, statusFilter, skip, limit]);

  const loadList = useCallback(
    () =>
      api<SuspectedErrorListResponse>(`/api/suspected-errors/?${buildListQuery()}`, {
        silentError: true,
      }),
    [buildListQuery],
  );

  const applyResult = useCallback((result: SuspectedErrorListResponse) => {
    setItems(result.items);
    setTotal(result.total);
    setLoadError(null);
    setLoading(false);
  }, []);

  const applyError = useCallback((err: unknown) => {
    setItems([]);
    setTotal(0);
    setLoadError(err instanceof Error ? err.message : '疑似错误加载失败');
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

  const reloadList = useCallback(() => {
    setLoading(true);
    loadList().then(applyResult).catch(applyError);
  }, [applyError, applyResult, loadList]);

  const changeEntityType = (value: EntityType) => {
    setEntityType(value);
    setLastDetect(null);
    setRunError(null);
    setErrorTypeFilter(ALL);
    setStatusFilter(ALL);
    setSkip(0);
    setLoading(true);
  };

  const toggleType = (value: SuspectedErrorType, checked: boolean) => {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (checked) next.add(value);
      else next.delete(value);
      return next;
    });
  };

  // ===== 执行检测 =====

  const runDetect = async () => {
    setRunning(true);
    setRunError(null);
    try {
      const payload: SuspectedDetectPayload = {
        entity_type: entityType,
        // 空数组时后端归一为全部支持类型（与全选语义一致）
        error_types: Array.from(selectedTypes),
      };
      const res = await api<SuspectedDetectResponse>('/api/suspected-errors/detect', {
        method: 'POST',
        body: JSON.stringify(payload),
        silentError: true,
      });
      setLastDetect(res);
      toast.success(
        `检测完成：新建 ${res.created}，刷新 ${res.refreshed}` +
          (res.skipped_false_positive ? `，误报跳过 ${res.skipped_false_positive}` : '') +
          (res.auto_closed ? `，自动关闭 ${res.auto_closed}` : ''),
      );
      reloadList();
    } catch (err) {
      setRunError(err instanceof Error ? err.message : '检测执行失败');
    } finally {
      setRunning(false);
    }
  };

  // ===== 处理 =====

  const openResolve = (item: SuspectedError) => {
    setResolveItem(item);
    setResolveStatus('confirmed');
    setResolveNote(RESOLUTION_TEMPLATES.confirmed);
    setResolveError(null);
  };

  const submitResolve = async () => {
    if (!resolveItem) return;
    setResolving(true);
    setResolveError(null);
    try {
      const payload: SuspectedResolvePayload = { status: resolveStatus, resolution_note: resolveNote };
      await api(`/api/suspected-errors/${resolveItem.id}/resolve`, {
        method: 'POST',
        body: JSON.stringify(payload),
        silentError: true,
      });
      toast.success(`已处理：${STATUS_LABELS[resolveStatus]}`);
      setResolveItem(null);
      reloadList();
    } catch (err) {
      setResolveError(err instanceof Error ? err.message : '处理失败');
    } finally {
      setResolving(false);
    }
  };

  const currentPage = Math.floor(skip / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const rangeStart = total === 0 ? 0 : skip + 1;
  const rangeEnd = Math.min(skip + limit, total);

  const detail = detailItem;
  const extraEvidence =
    detail?.details == null
      ? []
      : Object.entries(detail.details).filter(([key]) => !RENDERED_EVIDENCE_KEYS.has(key));

  return (
    <div className="space-y-4">
      {/* ===== 检测卡 ===== */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">执行疑似错误检测</CardTitle>
          <CardDescription>
            基于名称对存量记录检测疑似重复与命名规范违例（SPEC §2.7）：重检自动去重、误报
            白名单、实体消失自动关闭，处理需人工确认
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex items-center gap-2">
              <Label className="text-xs text-gray-500">实体类型</Label>
              <Select value={entityType} onValueChange={(v) => changeEntityType(v as EntityType)}>
                <SelectTrigger size="sm" className="w-36">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ENTITY_TYPE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-4">
              <Label className="text-xs text-gray-500">错误类型</Label>
              {ERROR_TYPE_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className="flex cursor-pointer items-center gap-2 text-sm"
                >
                  <Checkbox
                    checked={selectedTypes.has(option.value)}
                    onCheckedChange={(checked) =>
                      toggleType(option.value, checked === true)
                    }
                  />
                  {option.label}
                </label>
              ))}
              <span className="text-xs text-gray-400">
                classification / unit 类型 v1 无检测数据源
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={() => void runDetect()} disabled={!writable || running}>
              {running ? <Spinner className="size-4" /> : <Play />}
              {running ? '检测中...' : '开始检测'}
            </Button>
            {!writable && (
              <span className="text-sm text-gray-400">
                当前角色为只读：仅数据管理员 / 管理员可执行检测与处理
              </span>
            )}
            {runError && <span className="text-sm text-destructive">{runError}</span>}
          </div>

          {lastDetect && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
              <span>
                上次检测：新建 <span className="font-semibold">{lastDetect.created}</span> · 刷新{' '}
                <span className="font-semibold">{lastDetect.refreshed}</span>
                {lastDetect.skipped_false_positive > 0 && (
                  <>
                    {' '}
                    · 误报跳过 <span className="font-semibold">{lastDetect.skipped_false_positive}</span>
                  </>
                )}
                {lastDetect.auto_closed > 0 && (
                  <>
                    {' '}
                    · 自动关闭 <span className="font-semibold">{lastDetect.auto_closed}</span>
                  </>
                )}
              </span>
              <span className="ml-auto">
                当前待处理{' '}
                <span className="font-semibold text-amber-700">{lastDetect.total_pending}</span> 条
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ===== 结果卡 ===== */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">疑似错误列表</CardTitle>
          <CardDescription>
            检测结论进入人工确认流程：确认 / 解决 / 误报；误报在重检时自动跳过
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Label className="text-xs text-gray-500">错误类型</Label>
              <Select
                value={errorTypeFilter}
                onValueChange={(value) => {
                  setLoading(true);
                  setErrorTypeFilter(value as SuspectedErrorType | typeof ALL);
                  setSkip(0);
                }}
              >
                <SelectTrigger size="sm" className="w-36">
                  <SelectValue placeholder="全部" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>全部</SelectItem>
                  {ERROR_TYPE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <Label className="text-xs text-gray-500">状态</Label>
              <Select
                value={statusFilter}
                onValueChange={(value) => {
                  setLoading(true);
                  setStatusFilter(value as SuspectedErrorStatus | typeof ALL);
                  setSkip(0);
                }}
              >
                <SelectTrigger size="sm" className="w-28">
                  <SelectValue placeholder="全部" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>全部</SelectItem>
                  {STATUS_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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

            <Button variant="outline" size="icon" title="刷新" onClick={reloadList}>
              {loading ? <Spinner className="size-4" /> : <RefreshCw />}
            </Button>

            <span className="ml-auto text-sm text-gray-500">
              共 {total} 条疑似错误，本页第 {rangeStart}–{rangeEnd} 条
            </span>
          </div>

          {loadError && !loading ? (
            <div className="flex items-center justify-between gap-4 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              <span>疑似错误加载失败：{loadError}</span>
              <Button variant="outline" size="sm" onClick={reloadList}>
                重试
              </Button>
            </div>
          ) : loading ? (
            <div className="flex justify-center rounded-lg border border-gray-200 bg-white py-16">
              <Spinner className="size-6" />
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-lg border border-gray-200 bg-white">
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>暂无疑似错误</EmptyTitle>
                  <EmptyDescription>
                    {writable
                      ? '在上方执行检测后，疑似重复与命名规范违例会出现在这里。'
                      : '等待数据管理员执行检测后，疑似错误会出现在这里。'}
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>实体</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>严重程度</TableHead>
                    <TableHead>标题</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>检测时间</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>
                        <div className="max-w-44 truncate text-sm" title={item.entity_label ?? ''}>
                          {item.entity_label ?? '—'}
                        </div>
                        <div className="max-w-44 truncate font-mono text-xs text-gray-500" title={item.entity_id}>
                          {item.entity_id}
                        </div>
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <Badge variant="secondary" className="font-normal">
                          {ERROR_TYPE_LABELS[item.error_type] ?? item.error_type}
                        </Badge>
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <Badge className={`border font-normal ${severityBadgeClass(item.severity)}`}>
                          {SEVERITY_LABELS[item.severity] ?? item.severity}
                        </Badge>
                      </TableCell>
                      <TableCell
                        className="max-w-80 truncate text-sm"
                        title={`${item.title}\n${evidenceSummary(item)}`}
                      >
                        {item.title}
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <Badge className={`border font-normal ${statusBadgeClass(item.status)}`}>
                          {STATUS_LABELS[item.status] ?? item.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-xs text-gray-500">
                        {formatTimestamp(item.detected_at)}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setDetailItem(item)}
                            title="查看判定依据"
                          >
                            <Eye />
                            详情
                          </Button>
                          {writable && (
                            <Button variant="outline" size="sm" onClick={() => openResolve(item)}>
                              处理
                            </Button>
                          )}
                        </div>
                      </TableCell>
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
        </CardContent>
      </Card>

      {/* ===== 详情弹窗（判定依据） ===== */}
      <Dialog open={detail !== null} onOpenChange={(open) => !open && setDetailItem(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle className="pr-8">{detail.title}</DialogTitle>
                <DialogDescription className="flex flex-wrap items-center gap-2 pt-1">
                  <Badge variant="secondary" className="font-normal">
                    {ERROR_TYPE_LABELS[detail.error_type] ?? detail.error_type}
                  </Badge>
                  <Badge className={`border font-normal ${severityBadgeClass(detail.severity)}`}>
                    {SEVERITY_LABELS[detail.severity] ?? detail.severity}
                  </Badge>
                  <Badge className={`border font-normal ${statusBadgeClass(detail.status)}`}>
                    {STATUS_LABELS[detail.status] ?? detail.status}
                  </Badge>
                  <span className="text-xs">
                    检测于 {formatTimestamp(detail.detected_at)}
                    {detail.detected_by ? ` · ${detail.detected_by}` : ''}
                  </span>
                </DialogDescription>
              </DialogHeader>

              {detail.description && (
                <p className="text-sm text-gray-700">{detail.description}</p>
              )}

              <div className="grid gap-x-6 gap-y-2 rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm sm:grid-cols-2">
                <div>
                  <div className="text-xs text-gray-500">问题实体</div>
                  <div className="mt-0.5">
                    {detail.entity_label ?? '—'}
                    <span className="ml-1 font-mono text-xs text-gray-500">({detail.entity_id})</span>
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">匹配实体</div>
                  <div className="mt-0.5">
                    {detail.matched_entity_id ? (
                      <>
                        {detail.details?.matched_name ?? '—'}
                        <span className="ml-1 font-mono text-xs text-gray-500">
                          ({detail.matched_entity_id})
                        </span>
                      </>
                    ) : (
                      '—（单实体问题，无匹配对象）'
                    )}
                  </div>
                </div>
                {detail.details?.similarity !== undefined && (
                  <div>
                    <div className="text-xs text-gray-500">名称相似度</div>
                    <div className="mt-0.5 font-semibold">
                      {formatSimilarity(detail.details.similarity)}
                    </div>
                  </div>
                )}
                {detail.details?.suggestion && (
                  <div>
                    <div className="text-xs text-gray-500">处置建议</div>
                    <div className="mt-0.5 font-medium text-blue-800">{detail.details.suggestion}</div>
                  </div>
                )}
                {detail.details?.keeper_rule && (
                  <div>
                    <div className="text-xs text-gray-500">保留规则</div>
                    <div className="mt-0.5">{detail.details.keeper_rule}</div>
                  </div>
                )}
                {detail.details?.rule_label && (
                  <div>
                    <div className="text-xs text-gray-500">规范条目</div>
                    <div className="mt-0.5">{detail.details.rule_label}</div>
                  </div>
                )}
                {detail.details?.violation && (
                  <div>
                    <div className="text-xs text-gray-500">违反内容</div>
                    <div className="mt-0.5">{detail.details.violation}</div>
                  </div>
                )}
                {detail.details?.reason && (
                  <div>
                    <div className="text-xs text-gray-500">判定理由</div>
                    <div className="mt-0.5">{detail.details.reason}</div>
                  </div>
                )}
              </div>

              {extraEvidence.length > 0 && (
                <div>
                  <div className="mb-1 text-xs font-medium text-gray-500">其余证据</div>
                  <div className="overflow-hidden rounded-lg border border-gray-200">
                    <Table>
                      <TableBody>
                        {extraEvidence.map(([key, value]) => (
                          <TableRow key={key}>
                            <TableCell className="w-40 whitespace-nowrap font-mono text-xs text-gray-500">
                              {key}
                            </TableCell>
                            <TableCell className="break-all text-xs">
                              {typeof value === 'string' ? value : JSON.stringify(value)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              {(detail.resolution_note || detail.resolved_by || detail.resolved_at) && (
                <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-900">
                  <div className="text-xs text-green-700">处理记录</div>
                  <div className="mt-1">
                    {detail.resolved_by ? `处理人 ${detail.resolved_by}` : '系统自动处理'}
                    {detail.resolved_at ? ` · ${formatTimestamp(detail.resolved_at)}` : ''}
                  </div>
                  {detail.resolution_note && (
                    <div className="mt-1 whitespace-pre-wrap">{detail.resolution_note}</div>
                  )}
                </div>
              )}

              <DialogFooter>
                <Button variant="outline" onClick={() => setDetailItem(null)}>
                  关闭
                </Button>
                {writable && (
                  <Button
                    onClick={() => {
                      setDetailItem(null);
                      openResolve(detail);
                    }}
                  >
                    处理此问题
                  </Button>
                )}
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* ===== 处理弹窗 ===== */}
      <Dialog open={resolveItem !== null} onOpenChange={(open) => !open && setResolveItem(null)}>
        <DialogContent className="sm:max-w-lg">
          {resolveItem && (
            <>
              <DialogHeader>
                <DialogTitle>处理疑似错误</DialogTitle>
                <DialogDescription className="pt-1">
                  {resolveItem.title}
                  <span className="ml-2 text-xs text-gray-400">
                    {ERROR_TYPE_LABELS[resolveItem.error_type] ?? resolveItem.error_type}
                  </span>
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label className="text-xs text-gray-500">处理结果</Label>
                  <Select
                    value={resolveStatus}
                    onValueChange={(value) => {
                      const status = value as SuspectedResolveStatus;
                      setResolveStatus(status);
                      setResolveNote(RESOLUTION_TEMPLATES[status]);
                    }}
                  >
                    <SelectTrigger className="w-56">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {RESOLUTION_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs text-gray-500">处理说明（预填模板，可修改）</Label>
                  <Textarea
                    rows={3}
                    value={resolveNote}
                    onChange={(e) => setResolveNote(e.target.value)}
                  />
                </div>

                {resolveError && <p className="text-sm text-destructive">{resolveError}</p>}
              </div>

              <DialogFooter>
                <Button variant="outline" disabled={resolving} onClick={() => setResolveItem(null)}>
                  取消
                </Button>
                <Button onClick={() => void submitResolve()} disabled={resolving}>
                  {resolving ? <Spinner className="size-4" /> : null}
                  {resolving ? '提交中...' : '确认处理'}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default SuspectedErrors;
