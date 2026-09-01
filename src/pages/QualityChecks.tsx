import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Play, RefreshCw } from 'lucide-react';
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
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
import {
  RULE_TYPE_LABELS,
  SEVERITY_LABELS,
  SEVERITY_OPTIONS,
  formatTimestamp,
  parseEntityIds,
  severityBadgeClass,
} from '@/lib/quality';
import type {
  CheckSeverity,
  EntityType,
  QualityCheckBatch,
  QualityCheckBatchListResponse,
  QualityCheckResult,
  QualityCheckResultListResponse,
  QualityCheckRule,
  QualityCheckRuleListResponse,
  QualityRunPayload,
  QualityRunResponse,
} from '@/types/api';

/** Radix Select 不允许 value=""，过滤项用哨兵表示「不限」 */
const ALL = 'all';
const DEFAULT_LIMIT = 20;
const LIMIT_OPTIONS = [20, 50, 100, 200];

/** 批次选择项的展示标签 */
function batchLabel(batch: QualityCheckBatch): string {
  return `${batch.id.slice(0, 8)} · ${formatTimestamp(batch.started_at)} · 失败 ${batch.failed}`;
}

const QualityChecks: React.FC = () => {
  const writable = useMemo(() => canWrite(), []);
  const [searchParams] = useSearchParams();

  // 执行卡：实体类型 + 规则多选（默认全选，design 决策 2 的 rules 端点供给）
  const [entityType, setEntityType] = useState<EntityType>(() =>
    ENTITY_TYPE_OPTIONS.some((option) => option.value === searchParams.get('entity_type'))
      ? (searchParams.get('entity_type') as EntityType)
      : 'material',
  );
  const [rules, setRules] = useState<QualityCheckRule[]>([]);
  const [rulesLoading, setRulesLoading] = useState(true);
  const [rulesError, setRulesError] = useState<string | null>(null);
  const [selectedRuleIds, setSelectedRuleIds] = useState<Set<string>>(new Set());

  const [scope, setScope] = useState<'all' | 'ids'>('all');
  const [entityIdsText, setEntityIdsText] = useState('');
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<QualityRunResponse | null>(null);

  // 结果卡：批次 / 严重程度筛选 + skip / limit 分页
  const [batches, setBatches] = useState<QualityCheckBatch[]>([]);
  const [batchFilter, setBatchFilter] = useState<string>(ALL);
  const [severityFilter, setSeverityFilter] = useState<CheckSeverity | typeof ALL>(ALL);
  const [limit, setLimit] = useState<number>(DEFAULT_LIMIT);
  const [skip, setSkip] = useState<number>(0);
  const [items, setItems] = useState<QualityCheckResult[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // ===== 规则加载（实体类型变化时回读） =====

  const loadRules = useCallback(
    (type: EntityType) =>
      api<QualityCheckRuleListResponse>(`/api/quality-checks/rules?entity_type=${type}&limit=500`, {
        silentError: true,
      }),
    [],
  );

  useEffect(() => {
    let cancelled = false;
    loadRules(entityType)
      .then((res) => {
        if (cancelled) return;
        setRules(res.items);
        // 默认全选启用规则；不传 rule_ids 时后端同样走「全部启用」路径
        setSelectedRuleIds(new Set(res.items.filter((r) => r.is_active).map((r) => r.id)));
        setRulesError(null);
        setRulesLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setRules([]);
        setRulesError(err instanceof Error ? err.message : '检测规则加载失败');
        setRulesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [entityType, loadRules]);

  const changeEntityType = (value: EntityType) => {
    setEntityType(value);
    setRulesLoading(true);
    setSelectedRuleIds(new Set());
    setLastRun(null);
    setRunError(null);
    // 结果列表回到「全部批次」首页
    setBatchFilter(ALL);
    setSeverityFilter(ALL);
    setSkip(0);
  };

  const toggleRule = (id: string, checked: boolean) => {
    setSelectedRuleIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  // ===== 批次列表（筛选下拉 + 执行后刷新） =====

  const loadBatches = useCallback(
    () =>
      api<QualityCheckBatchListResponse>(
        `/api/quality-checks/batches?entity_type=${entityType}&limit=50`,
        { silentError: true },
      ),
    [entityType],
  );

  const reloadBatches = useCallback(() => {
    loadBatches()
      .then((res) => setBatches(res.items))
      .catch(() => setBatches([]));
  }, [loadBatches]);

  useEffect(() => {
    reloadBatches();
  }, [reloadBatches]);

  // ===== 结果列表 =====

  const buildResultsQuery = useCallback(() => {
    const params = new URLSearchParams();
    params.set('entity_type', entityType);
    if (batchFilter !== ALL) params.set('batch_id', batchFilter);
    if (severityFilter !== ALL) params.set('severity', severityFilter);
    params.set('skip', String(skip));
    params.set('limit', String(limit));
    return params.toString();
  }, [entityType, batchFilter, severityFilter, skip, limit]);

  const loadResults = useCallback(
    () =>
      api<QualityCheckResultListResponse>(
        `/api/quality-checks/results?${buildResultsQuery()}`,
        { silentError: true },
      ),
    [buildResultsQuery],
  );

  const applyResult = useCallback((result: QualityCheckResultListResponse) => {
    setItems(result.items);
    setTotal(result.total);
    setLoadError(null);
    setLoading(false);
  }, []);

  const applyError = useCallback((err: unknown) => {
    setItems([]);
    setTotal(0);
    setLoadError(err instanceof Error ? err.message : '检测结果加载失败');
    setLoading(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadResults()
      .then((result) => {
        if (!cancelled) applyResult(result);
      })
      .catch((err: unknown) => {
        if (!cancelled) applyError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [loadResults, applyResult, applyError]);

  const reloadResults = useCallback(() => {
    setLoading(true);
    loadResults().then(applyResult).catch(applyError);
  }, [applyError, applyResult, loadResults]);

  const ruleById = useMemo(() => new Map(rules.map((r) => [r.id, r])), [rules]);

  // ===== 执行 =====

  const runChecks = async () => {
    setRunning(true);
    setRunError(null);
    try {
      const payload: QualityRunPayload = { entity_type: entityType };
      // 只勾选子集时显式传 rule_ids；全选/未选由按钮禁用兜底，走后端默认路径
      if (selectedRuleIds.size > 0 && selectedRuleIds.size < rules.length) {
        payload.rule_ids = Array.from(selectedRuleIds);
      }
      if (scope === 'ids') {
        const ids = parseEntityIds(entityIdsText);
        if (!ids.length) {
          setRunError('请至少输入一个实体 ID（每行一个）');
          return;
        }
        payload.entity_ids = ids;
      }
      const res = await api<QualityRunResponse>('/api/quality-checks/run', {
        method: 'POST',
        body: JSON.stringify(payload),
        silentError: true,
      });
      setLastRun(res);
      toast.success(
        `检测完成：${res.total_checked} 项检查，失败 ${res.failed}` +
          (res.skipped ? `，无数据源跳过 ${res.skipped}` : ''),
      );
      // 结果卡直接切到本次批次，同时刷新批次下拉
      setBatchFilter(res.batch_id);
      reloadBatches();
    } catch (err) {
      setRunError(err instanceof Error ? err.message : '检测执行失败');
    } finally {
      setRunning(false);
    }
  };

  const currentPage = Math.floor(skip / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const rangeStart = total === 0 ? 0 : skip + 1;
  const rangeEnd = Math.min(skip + limit, total);

  return (
    <div className="space-y-4">
      {/* ===== 执行卡 ===== */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">执行质量检测</CardTitle>
          <CardDescription>
            按数据标准派生的规则（SPEC §2.4）对存量记录执行 null / format / range / length /
            unique 五类检查，只保留失败明细
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

            <div className="flex items-center gap-2">
              <Label className="text-xs text-gray-500">检测范围</Label>
              <Tabs value={scope} onValueChange={(v) => setScope(v as 'all' | 'ids')}>
                <TabsList>
                  <TabsTrigger value="all">全部存量记录</TabsTrigger>
                  <TabsTrigger value="ids">指定实体 ID</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </div>

          {scope === 'ids' && (
            <div className="space-y-1.5">
              <Label className="text-xs text-gray-500">实体 ID（每行一个，逗号/换行分隔）</Label>
              <Textarea
                rows={3}
                placeholder="粘贴要检测的实体 ID，例如：&#10;550e8400-e29b-41d4-a716-446655440000"
                value={entityIdsText}
                onChange={(e) => setEntityIdsText(e.target.value)}
              />
            </div>
          )}

          {/* 规则多选 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs text-gray-500">
                检测规则（{selectedRuleIds.size} / {rules.length}）
              </Label>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={rulesLoading || selectedRuleIds.size === rules.length}
                  onClick={() => setSelectedRuleIds(new Set(rules.map((r) => r.id)))}
                >
                  全选
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={rulesLoading || selectedRuleIds.size === 0}
                  onClick={() => setSelectedRuleIds(new Set())}
                >
                  清空
                </Button>
              </div>
            </div>
            {rulesLoading ? (
              <div className="flex justify-center rounded-lg border border-gray-200 bg-white py-8">
                <Spinner className="size-5" />
              </div>
            ) : rulesError ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                规则加载失败：{rulesError}
              </div>
            ) : rules.length === 0 ? (
              <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm text-gray-500">
                该实体类型暂无可用规则：请先在数据标准管理中为该实体配置标准（必填 / 正则 /
                值域 / 长度 / 唯一），系统会派生对应检测规则。
              </div>
            ) : (
              <div className="grid gap-x-8 gap-y-1 rounded-lg border border-gray-200 bg-white px-4 py-3 sm:grid-cols-2">
                {rules.map((rule) => (
                  <label
                    key={rule.id}
                    className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 hover:bg-gray-50"
                  >
                    <Checkbox
                      className="mt-0.5"
                      checked={selectedRuleIds.has(rule.id)}
                      onCheckedChange={(checked) => toggleRule(rule.id, checked === true)}
                    />
                    <span className="text-sm">
                      <span className="font-mono text-xs font-medium">{rule.field_name ?? '—'}</span>{' '}
                      {rule.name}
                    </span>
                    <Badge variant="secondary" className="ml-auto shrink-0 font-normal">
                      {RULE_TYPE_LABELS[rule.rule_type] ?? rule.rule_type}
                    </Badge>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              onClick={() => void runChecks()}
              disabled={!writable || running || rulesLoading || selectedRuleIds.size === 0}
            >
              {running ? <Spinner className="size-4" /> : <Play />}
              {running ? '检测中...' : '开始检测'}
            </Button>
            {!writable && (
              <span className="text-sm text-gray-400">
                当前角色为只读：仅数据管理员 / 管理员可执行质量检测
              </span>
            )}
            {writable && selectedRuleIds.size === 0 && (
              <span className="text-sm text-gray-400">请至少勾选一条检测规则</span>
            )}
            {runError && <span className="text-sm text-destructive">{runError}</span>}
          </div>

          {lastRun && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
              <span>
                上次执行：检查 {lastRun.total_checked} 项，通过 {lastRun.passed}，失败{' '}
                <span className="font-semibold text-red-700">{lastRun.failed}</span>
                {lastRun.skipped ? `，无数据源跳过 ${lastRun.skipped}` : ''}
              </span>
              <Link
                className="ml-auto font-medium text-blue-700 underline underline-offset-2 hover:text-blue-900"
                to={`/quality/checks/report?entity_type=${entityType}&batch_id=${lastRun.batch_id}`}
              >
                查看报告 →
              </Link>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ===== 结果卡 ===== */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">检测结果（仅失败明细）</CardTitle>
          <CardDescription>
            通过项不落库；跳过项（无数据源字段）在批次统计与审计日志中记录
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Label className="text-xs text-gray-500">批次</Label>
              <Select
                value={batchFilter}
                onValueChange={(value) => {
                  setLoading(true);
                  setBatchFilter(value);
                  setSkip(0);
                }}
              >
                <SelectTrigger size="sm" className="w-64">
                  <SelectValue placeholder="全部批次" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>全部批次</SelectItem>
                  {batches.map((batch) => (
                    <SelectItem key={batch.id} value={batch.id}>
                      {batchLabel(batch)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <Label className="text-xs text-gray-500">严重程度</Label>
              <Select
                value={severityFilter}
                onValueChange={(value) => {
                  setLoading(true);
                  setSeverityFilter(value as CheckSeverity | typeof ALL);
                  setSkip(0);
                }}
              >
                <SelectTrigger size="sm" className="w-28">
                  <SelectValue placeholder="全部" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>全部</SelectItem>
                  {SEVERITY_OPTIONS.map((option) => (
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

            <Button variant="outline" size="icon" title="刷新" onClick={reloadResults}>
              {loading ? <Spinner className="size-4" /> : <RefreshCw />}
            </Button>

            <span className="ml-auto text-sm text-gray-500">
              共 {total} 条失败记录，本页第 {rangeStart}–{rangeEnd} 条
            </span>
          </div>

          {loadError && !loading ? (
            <div className="flex items-center justify-between gap-4 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              <span>检测结果加载失败：{loadError}</span>
              <Button variant="outline" size="sm" onClick={reloadResults}>
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
                  <EmptyTitle>
                    {batchFilter !== ALL ? '该批次无失败明细' : '暂无检测结果'}
                  </EmptyTitle>
                  <EmptyDescription>
                    {writable
                      ? '在上方选择实体与规则后执行检测；通过项与跳过项不在此列。'
                      : '等待数据管理员执行检测后，失败明细会出现在这里。'}
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>字段</TableHead>
                    <TableHead>规则类型</TableHead>
                    <TableHead>严重程度</TableHead>
                    <TableHead>实体 ID</TableHead>
                    <TableHead>字段值</TableHead>
                    <TableHead>问题描述</TableHead>
                    <TableHead>检测时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item) => {
                    const rule = ruleById.get(item.rule_id);
                    return (
                      <TableRow key={item.id}>
                        <TableCell className="whitespace-nowrap font-mono text-xs font-medium">
                          {item.field_name ?? '—'}
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-sm">
                          {rule ? (RULE_TYPE_LABELS[rule.rule_type] ?? rule.rule_type) : '—'}
                        </TableCell>
                        <TableCell>
                          <Badge
                            className={`border font-normal ${severityBadgeClass(item.severity)}`}
                          >
                            {SEVERITY_LABELS[item.severity] ?? item.severity}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-44 truncate font-mono text-xs text-gray-500" title={item.entity_id}>
                          {item.entity_id}
                        </TableCell>
                        <TableCell className="max-w-40 truncate font-mono text-xs" title={item.field_value ?? ''}>
                          {item.field_value ?? '—'}
                        </TableCell>
                        <TableCell className="max-w-72 text-sm">{item.message ?? '—'}</TableCell>
                        <TableCell className="whitespace-nowrap text-xs text-gray-500">
                          {formatTimestamp(item.checked_at)}
                        </TableCell>
                      </TableRow>
                    );
                  })}
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
    </div>
  );
};

export default QualityChecks;
