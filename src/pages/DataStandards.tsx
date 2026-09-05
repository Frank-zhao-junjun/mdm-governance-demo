import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, Pencil, Trash2, Search, RefreshCw } from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
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
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import DataStandardFormDialog from '@/components/standards/DataStandardFormDialog';

import { api, canWrite } from '@/lib/api';
import {
  DATA_TYPE_LABELS,
  ENTITY_TYPE_LABELS,
  ENTITY_TYPE_OPTIONS,
  STANDARD_SOURCE_LABELS,
  sapTableOptions,
} from '@/lib/governance';
import type { DataStandard, DataStandardListResponse, EntityType } from '@/types/api';

/** Radix Select 不允许 value=""，过滤项用哨兵表示「不限」 */
const ALL = 'all';
const DEFAULT_LIMIT = 20;
const LIMIT_OPTIONS = [20, 50, 100, 200];

/** 取值约束列：长度 / 值域 / 枚举汇总为徽标，完整内容放 title 悬浮 */
function ruleBadges(standard: DataStandard) {
  const rules: { label: string; title: string }[] = [];
  if (standard.max_length != null) {
    rules.push({ label: `长度≤${standard.max_length}`, title: `最大长度: ${standard.max_length}` });
  }
  if (standard.min_value != null || standard.max_value != null) {
    const min = standard.min_value ?? '-∞';
    const max = standard.max_value ?? '+∞';
    rules.push({ label: `范围 ${min}~${max}`, title: `取值范围: ${min} ~ ${max}` });
  }
  if (standard.enum_values && standard.enum_values.length > 0) {
    rules.push({
      label: `${standard.enum_values.length} 枚举`,
      title: `枚举值: ${standard.enum_values.join(' / ')}`,
    });
  }
  return rules;
}

/** business_attrs 中的标准主题 / 标准小类（SPEC §1.5.1） */
function businessSummary(standard: DataStandard): string {
  const attrs = standard.business_attrs || {};
  const topic = typeof attrs.standard_topic === 'string' ? attrs.standard_topic : '';
  const subcategory =
    typeof attrs.standard_subcategory === 'string' ? attrs.standard_subcategory : '';
  return [topic, subcategory].filter(Boolean).join(' / ');
}

/**
 * 后端 DateTime 列存的是无偏移量的 UTC 值，序列化结果不带 Z；
 * 这里补齐时区，避免按本地时区误读。
 */
function formatTimestamp(raw: string): string {
  if (!raw) return '—';
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(raw) ? raw : `${raw}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return raw;
  return format(date, 'yyyy-MM-dd HH:mm');
}

const DataStandards: React.FC = () => {
  const writable = useMemo(() => canWrite(), []);

  // 深链（元数据治理状态 / 字段跳转）：?entity_type=&field_name= 仅做一次性初始值，不订阅 URL
  const [searchParams] = useSearchParams();
  const initialType = searchParams.get('entity_type');
  const initialField = searchParams.get('field_name');

  // 过滤 / 分页状态：全部映射到后端查询参数 entity_type / sap_table / skip / limit（SPEC §3.1）
  const [entityType, setEntityType] = useState<EntityType | typeof ALL>(() =>
    ENTITY_TYPE_OPTIONS.some((option) => option.value === initialType)
      ? (initialType as EntityType)
      : ALL,
  );
  const [sapTable, setSapTable] = useState<string>(ALL);
  const [limit, setLimit] = useState<number>(DEFAULT_LIMIT);
  const [skip, setSkip] = useState<number>(0);
  // 深链字段名注入就地搜索框（当前页内过滤；实体预选后单页容得下全部标准）
  const [keyword, setKeyword] = useState(() => (initialField && initialField.length > 0 ? initialField : ''));

  const [items, setItems] = useState<DataStandard[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');
  const [formStandard, setFormStandard] = useState<DataStandard | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<DataStandard | null>(null);
  const [deleting, setDeleting] = useState(false);

  const buildQuery = useCallback(() => {
    const params = new URLSearchParams();
    if (entityType !== ALL) params.set('entity_type', entityType);
    if (sapTable !== ALL) params.set('sap_table', sapTable);
    params.set('skip', String(skip));
    params.set('limit', String(limit));
    return params.toString();
  }, [entityType, sapTable, skip, limit]);

  /** 异步回读：列表数据、total 与分页都由后端决定 */
  const loadList = useCallback(
    () =>
      api<DataStandardListResponse>(`/api/data-standards?${buildQuery()}`, {
        silentError: true,
      }),
    [buildQuery],
  );

  const applyResult = useCallback((result: DataStandardListResponse) => {
    setItems(result.items);
    setTotal(result.total);
    setLoadError(null);
    setLoading(false);
  }, []);

  const applyError = useCallback((err: unknown) => {
    setItems([]);
    setTotal(0);
    setLoadError(err instanceof Error ? err.message : '数据标准加载失败');
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

  /** 过滤条件未变时的显式刷新（刷新按钮 / 写操作回读） */
  const reload = useCallback(() => {
    setLoading(true);
    loadList().then(applyResult).catch(applyError);
  }, [applyError, applyResult, loadList]);

  const tableOptions = useMemo(() => sapTableOptions(entityType, items), [entityType, items]);

  /** 搜索框只做当前页内的就地过滤（后端未提供模糊搜索参数） */
  const visibleItems = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    if (!kw) return items;
    return items.filter((item) => {
      const haystack = [
        item.field_name,
        item.field_label,
        item.sap_table,
        item.pattern,
        item.owner,
        item.description,
        (item.enum_values ?? []).join(' '),
        (item.dept_scope ?? []).join(' '),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(kw);
    });
  }, [items, keyword]);

  const currentPage = Math.floor(skip / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const rangeStart = total === 0 ? 0 : skip + 1;
  const rangeEnd = Math.min(skip + limit, total);

  const openCreate = () => {
    setFormMode('create');
    setFormStandard(null);
    setFormOpen(true);
  };

  const openEdit = (standard: DataStandard) => {
    setFormMode('edit');
    setFormStandard(standard);
    setFormOpen(true);
  };

  const handleSaved = () => {
    if (formMode === 'edit') {
      reload();
      return;
    }
    // 新建后回到首页（列表按 实体 / SAP 表 / 字段名 排序），确保新记录可见
    if (skip === 0) reload();
    else setSkip(0);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await api<void>(`/api/data-standards/${deleteTarget.id}`, { method: 'DELETE' });
      toast.success(`已删除标准 ${deleteTarget.field_name}`);
      setDeleteTarget(null);
      // 删掉本页最后一条时回退一页，避免停在空页
      if (items.length === 1 && skip > 0) setSkip(Math.max(0, skip - limit));
      else reload();
    } catch {
      // 404 / 409（被质量检测规则引用）等原因由 api() 全局 toast 提示，对话框保持打开
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* 筛选栏 */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <Tabs
            value={entityType}
            onValueChange={(value) => {
              setLoading(true);
              setEntityType(value as EntityType | typeof ALL);
              setSapTable(ALL);
              setSkip(0);
            }}
          >
            <TabsList>
              <TabsTrigger value={ALL}>全部实体</TabsTrigger>
              {ENTITY_TYPE_OPTIONS.map((option) => (
                <TabsTrigger key={option.value} value={option.value}>
                  {option.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <div className="flex items-center gap-2">
            <Label className="text-xs text-gray-500">SAP 表</Label>
            <Select
              value={sapTable}
              onValueChange={(value) => {
                setLoading(true);
                setSapTable(value);
                setSkip(0);
              }}
            >
              <SelectTrigger size="sm" className="w-36">
                <SelectValue placeholder="全部表" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>全部表</SelectItem>
                {tableOptions.map((table) => (
                  <SelectItem key={table} value={table}>
                    {table}
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

          <div className="relative ml-auto w-full max-w-xs">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gray-400" />
            <Input
              className="pl-9"
              placeholder="在当前结果中搜索字段/标签/正则"
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
              新建标准
            </Button>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-gray-500">
          <span>
            共 {total} 条数据标准，本页第 {rangeStart}–{rangeEnd} 条
            {keyword.trim() ? `（当前结果命中 ${visibleItems.length} 条）` : ''}
          </span>
          {!writable && (
            <span className="text-gray-400">
              当前角色为只读：仅数据管理员 / 管理员可新建、编辑与删除数据标准
            </span>
          )}
        </div>
      </div>

      {/* 标准列表 */}
      {loadError && !loading ? (
        <div className="flex items-center justify-between gap-4 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          <span>数据标准加载失败：{loadError}</span>
          <Button variant="outline" size="sm" onClick={reload}>
            重试
          </Button>
        </div>
      ) : loading ? (
        <div className="flex justify-center rounded-lg border border-gray-200 bg-white py-16">
          <Spinner className="size-6" />
        </div>
      ) : visibleItems.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white">
          <Empty>
            <EmptyHeader>
              <EmptyTitle>{items.length === 0 ? '暂无数据标准' : '当前结果无匹配'}</EmptyTitle>
              <EmptyDescription>
                {items.length === 0
                  ? '调整实体或 SAP 表筛选条件；数据管理员可新建第一条数据标准。'
                  : '清空搜索框或翻页查看其他标准。'}
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>字段名</TableHead>
                <TableHead>中文标签</TableHead>
                <TableHead>实体</TableHead>
                <TableHead>SAP 表</TableHead>
                <TableHead>数据类型</TableHead>
                <TableHead>必填</TableHead>
                <TableHead>唯一</TableHead>
                <TableHead>正则</TableHead>
                <TableHead>取值约束</TableHead>
                <TableHead>标准定义人</TableHead>
                <TableHead>标准来源</TableHead>
                <TableHead>应用部门</TableHead>
                <TableHead>更新时间</TableHead>
                {writable && <TableHead className="text-right">操作</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleItems.map((item) => {
                const badges = ruleBadges(item);
                return (
                  <TableRow key={item.id}>
                    <TableCell className="font-mono text-xs font-medium">
                      {item.field_name}
                    </TableCell>
                    <TableCell>
                      <div className="whitespace-nowrap text-sm">{item.field_label}</div>
                      {businessSummary(item) && (
                        <div className="text-xs text-gray-400">{businessSummary(item)}</div>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">
                        {ENTITY_TYPE_LABELS[item.entity_type] ?? item.entity_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs">{item.sap_table ?? '—'}</TableCell>
                    <TableCell className="whitespace-nowrap text-sm">
                      {DATA_TYPE_LABELS[item.data_type] ?? item.data_type}
                    </TableCell>
                    <TableCell>
                      {item.required ? (
                        <Badge className="border border-amber-200 bg-amber-100 font-normal text-amber-800">
                          必填
                        </Badge>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {item.unique ? (
                        <Badge className="border border-blue-200 bg-blue-100 font-normal text-blue-800">
                          唯一
                        </Badge>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {item.pattern ? (
                        <code
                          className="block max-w-52 truncate rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs"
                          title={item.pattern}
                        >
                          {item.pattern}
                        </code>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex max-w-56 flex-wrap gap-1">
                        {badges.map((rule) => (
                          <Badge
                            key={rule.label}
                            variant="outline"
                            title={rule.title}
                            className="font-normal"
                          >
                            {rule.label}
                          </Badge>
                        ))}
                        {badges.length === 0 && <span className="text-xs text-gray-400">—</span>}
                      </div>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm">
                      {item.owner ?? '—'}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm">
                      {item.standard_source ? STANDARD_SOURCE_LABELS[item.standard_source] : '—'}
                    </TableCell>
                    <TableCell className="max-w-40 text-xs text-gray-500">
                      {item.dept_scope?.length ? item.dept_scope.join('、') : '—'}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-gray-500">
                      {formatTimestamp(item.updated_at)}
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
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            className="text-red-600 hover:text-red-700"
                            title="删除"
                            onClick={() => setDeleteTarget(item)}
                          >
                            <Trash2 />
                          </Button>
                        </div>
                      </TableCell>
                    )}
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

      {/* 新建 / 编辑对话框 */}
      <DataStandardFormDialog
        open={formOpen}
        mode={formMode}
        standard={formStandard}
        defaultEntityType={entityType === ALL ? 'material' : entityType}
        sapTableSuggestions={tableOptions}
        onOpenChange={setFormOpen}
        onSaved={handleSaved}
      />

      {/* 删除确认 */}
      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除数据标准</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget
                ? `确定删除「${
                    ENTITY_TYPE_LABELS[deleteTarget.entity_type] ?? deleteTarget.entity_type
                  } / ${deleteTarget.sap_table ?? '—'} / ${deleteTarget.field_name}（${
                    deleteTarget.field_label
                  }）」吗？该操作会写入审计日志，且不可撤销。`
                : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              disabled={deleting}
              onClick={(event) => {
                event.preventDefault();
                void confirmDelete();
              }}
            >
              {deleting && <Spinner />}
              {deleting ? '删除中...' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default DataStandards;
