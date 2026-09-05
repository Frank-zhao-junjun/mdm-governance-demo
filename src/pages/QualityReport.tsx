import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
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

import { api } from '@/lib/api';
import { ENTITY_TYPE_OPTIONS } from '@/lib/governance';
import {
  CHART_COLORS,
  RULE_TYPE_LABELS,
  SEVERITY_LABELS,
  formatPercent,
  formatTimestamp,
} from '@/lib/quality';
import type {
  CheckSeverity,
  EntityType,
  QualityCheckBatch,
  QualityCheckBatchListResponse,
  QualityReport as QualityReportData,
} from '@/types/api';

/** 批次选择哨兵：不传 batch_id，后端取该实体最新批次 */
const LATEST = 'latest';

function parseEntityTypeParam(raw: string | null): EntityType {
  return ENTITY_TYPE_OPTIONS.some((option) => option.value === raw)
    ? (raw as EntityType)
    : 'material';
}

const QualityReport: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const entityType = parseEntityTypeParam(searchParams.get('entity_type'));
  const batchParam = searchParams.get('batch_id') ?? LATEST;

  const [batches, setBatches] = useState<QualityCheckBatch[]>([]);
  const [report, setReport] = useState<QualityReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const reportUrl = useMemo(() => {
    const params = new URLSearchParams();
    params.set('entity_type', entityType);
    if (batchParam !== LATEST) params.set('batch_id', batchParam);
    return `/api/quality-checks/report?${params.toString()}`;
  }, [entityType, batchParam]);

  useEffect(() => {
    let cancelled = false;
    api<QualityReportData>(reportUrl, { silentError: true })
      .then((res) => {
        if (cancelled) return;
        setReport(res);
        setLoadError(null);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setReport(null);
        setLoadError(err instanceof Error ? err.message : '报告加载失败');
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reportUrl]);

  const loadBatches = useCallback(
    () =>
      api<QualityCheckBatchListResponse>(
        `/api/quality-checks/batches?entity_type=${entityType}&limit=50`,
        { silentError: true },
      ),
    [entityType],
  );

  useEffect(() => {
    let cancelled = false;
    loadBatches()
      .then((res) => {
        if (!cancelled) setBatches(res.items);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [loadBatches]);

  const changeEntityType = (value: EntityType) => {
    const params = new URLSearchParams(searchParams);
    params.set('entity_type', value);
    params.delete('batch_id'); // 切实体回到最新批次
    setLoading(true);
    setSearchParams(params);
  };

  const changeBatch = (value: string) => {
    const params = new URLSearchParams(searchParams);
    if (value === LATEST) params.delete('batch_id');
    else params.set('batch_id', value);
    setLoading(true);
    setSearchParams(params);
  };

  const currentBatch = useMemo(
    () => batches.find((batch) => batch.id === report?.batch_id) ?? null,
    [batches, report],
  );

  // 图表数据（recharts）
  const passedFailedData = useMemo(() => {
    if (!report) return [];
    return [
      { name: '通过', value: report.passed },
      { name: '失败', value: report.failed },
    ];
  }, [report]);

  const severityData = useMemo(() => {
    if (!report) return [];
    return (Object.keys(report.by_severity) as CheckSeverity[])
      .map((severity) => ({
        name: SEVERITY_LABELS[severity] ?? severity,
        value: report.by_severity[severity],
        color:
          severity === 'error'
            ? CHART_COLORS.error
            : severity === 'warning'
              ? CHART_COLORS.warning
              : CHART_COLORS.info,
      }))
      .filter((item) => item.value > 0);
  }, [report]);

  return (
    <div className="space-y-4">
      {/* 选择器 */}
      <div className="flex flex-wrap items-center gap-4">
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
          <Label className="text-xs text-gray-500">检测批次</Label>
          <Select value={batchParam} onValueChange={changeBatch}>
            <SelectTrigger size="sm" className="w-72">
              <SelectValue placeholder="最新批次" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={LATEST}>最新批次</SelectItem>
              {batches.map((batch) => (
                <SelectItem key={batch.id} value={batch.id}>
                  {batch.id.slice(0, 8)} · {formatTimestamp(batch.started_at)} · 失败 {batch.failed}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Link
          className="ml-auto text-sm font-medium text-blue-700 underline underline-offset-2 hover:text-blue-900"
          to={`/quality/checks?entity_type=${entityType}`}
        >
          ← 返回执行检测
        </Link>
      </div>

      {loadError && !loading ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-8 text-center text-sm text-destructive">
          <p className="mb-3">报告加载失败：{loadError}</p>
          <p className="text-xs text-gray-500">
            该实体可能还没有任何检测批次：请先到「质量检测」页执行一次检测。
          </p>
        </div>
      ) : loading ? (
        <div className="flex justify-center rounded-lg border border-gray-200 bg-white py-24">
          <Spinner className="size-6" />
        </div>
      ) : report === null ? (
        <div className="rounded-lg border border-gray-200 bg-white">
          <Empty>
            <EmptyHeader>
              <EmptyTitle>暂无检测报告</EmptyTitle>
              <EmptyDescription>
                该实体还没有任何检测批次：请先到「质量检测」页执行一次检测，再回到这里查看报告。
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        </div>
      ) : (
        <>
          {/* 批次摘要 + 统计卡 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {ENTITY_TYPE_OPTIONS.find((o) => o.value === report.entity_type)?.label ??
                  report.entity_type}{' '}
                质量检测报告
              </CardTitle>
              <CardDescription>
                批次 {report.batch_id}
                {currentBatch
                  ? ` · 执行人 ${currentBatch.triggered_by} · 执行时间 ${formatTimestamp(currentBatch.started_at)}`
                  : ''}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-center">
                  <div className="text-2xl font-semibold text-gray-800">{report.total_entities}</div>
                  <div className="mt-1 text-xs text-gray-500">检测实体数</div>
                </div>
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-center">
                  <div className="text-2xl font-semibold text-gray-800">{report.total_checks}</div>
                  <div className="mt-1 text-xs text-gray-500">检查项</div>
                </div>
                <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-center">
                  <div className="text-2xl font-semibold text-green-700">{report.passed}</div>
                  <div className="mt-1 text-xs text-gray-500">通过</div>
                </div>
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-center">
                  <div className="text-2xl font-semibold text-red-700">{report.failed}</div>
                  <div className="mt-1 text-xs text-gray-500">失败</div>
                </div>
                <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-center">
                  <div className="text-2xl font-semibold text-blue-700">
                    {formatPercent(report.pass_rate)}
                  </div>
                  <div className="mt-1 text-xs text-gray-500">通过率</div>
                </div>
              </div>

              {/* 环形图：通过/失败 + 严重程度分布 */}
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="mb-2 text-sm font-medium text-gray-700">检查结果分布</div>
                  <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={passedFailedData}
                          dataKey="value"
                          nameKey="name"
                          innerRadius={55}
                          outerRadius={80}
                          paddingAngle={2}
                        >
                          <Cell fill={CHART_COLORS.passed} />
                          <Cell fill={CHART_COLORS.failed} />
                        </Pie>
                        <Tooltip />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                <div className="rounded-lg border border-gray-200 p-3">
                  <div className="mb-2 text-sm font-medium text-gray-700">失败严重程度分布</div>
                  {severityData.length === 0 ? (
                    <div className="flex h-56 items-center justify-center text-sm text-gray-400">
                      本批次无失败明细
                    </div>
                  ) : (
                    <div className="h-56">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={severityData}
                            dataKey="value"
                            nameKey="name"
                            innerRadius={55}
                            outerRadius={80}
                            paddingAngle={2}
                          >
                            {severityData.map((item) => (
                              <Cell key={item.name} fill={item.color} />
                            ))}
                          </Pie>
                          <Tooltip />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 按规则统计 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">按规则统计</CardTitle>
              <CardDescription>
                每个规则的检查范围 = 批次全部实体（{report.total_entities} 条）；仅失败明细入库，
                规则失败数从结果表聚合
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto rounded-lg border border-gray-200">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>规则</TableHead>
                      <TableHead>检查范围</TableHead>
                      <TableHead className="text-right">失败</TableHead>
                      <TableHead>通过率</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {report.by_rule.map((stat) => (
                      <TableRow key={stat.rule_id}>
                        <TableCell className="whitespace-nowrap text-sm">{stat.rule_name}</TableCell>
                        <TableCell className="whitespace-nowrap text-sm text-gray-500">
                          {stat.total} 项
                        </TableCell>
                        <TableCell className="text-right">
                          <Badge
                            className={
                              stat.failed > 0
                                ? 'border-red-200 bg-red-100 font-normal text-red-800'
                                : 'border-gray-200 bg-gray-100 font-normal text-gray-600'
                            }
                          >
                            {stat.failed}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Progress value={stat.pass_rate * 100} className="h-2 w-32" />
                            <span className="whitespace-nowrap text-xs text-gray-500">
                              {formatPercent(stat.pass_rate)}
                            </span>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          {/* Top 问题 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Top 问题</CardTitle>
              <CardDescription>按「字段 × 规则」聚合失败明细，最多展示 10 条</CardDescription>
            </CardHeader>
            <CardContent>
              {report.top_issues.length === 0 ? (
                <div className="rounded-lg border border-gray-200 px-4 py-8 text-center text-sm text-gray-400">
                  本批次无失败明细
                </div>
              ) : (
                <div className="overflow-x-auto rounded-lg border border-gray-200">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>字段</TableHead>
                        <TableHead>规则类型</TableHead>
                        <TableHead className="text-right">失败数</TableHead>
                        <TableHead>样例问题描述</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {report.top_issues.map((issue) => (
                        <TableRow
                          key={`${issue.field_name ?? 'none'}-${issue.issue_type ?? 'none'}`}
                        >
                          <TableCell className="whitespace-nowrap font-mono text-xs font-medium">
                            {issue.field_name ?? '—'}
                          </TableCell>
                          <TableCell>
                            {issue.issue_type ? (
                              <Badge variant="secondary" className="font-normal">
                                {RULE_TYPE_LABELS[issue.issue_type] ?? issue.issue_type}
                              </Badge>
                            ) : (
                              '—'
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            <span className="font-semibold text-red-700">{issue.issue_count}</span>
                          </TableCell>
                          <TableCell className="max-w-96 text-sm">{issue.message ?? '—'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
};

export default QualityReport;
