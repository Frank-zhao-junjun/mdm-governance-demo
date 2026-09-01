import { useCallback, useEffect, useState } from 'react';
import { Bot, RefreshCw } from 'lucide-react';
import { format } from 'date-fns';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { api } from '@/lib/api';
import type { AgentTrace, GovernanceTicket, TodoListResponse } from '@/types/api';

function date(value: string) { const parsed = new Date(value.endsWith('Z') ? value : `${value}Z`); return Number.isNaN(parsed.getTime()) ? value : format(parsed, 'yyyy-MM-dd HH:mm'); }

export default function AgentActivity() {
  const [items, setItems] = useState<{ ticket: GovernanceTicket; trace: AgentTrace | null }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { setLoading(true); try { const todos = await api<TodoListResponse>('/api/copilot/todos', { silentError: true }); const details = await Promise.all(todos.items.map(async (ticket) => { const data = await api<{ trace: AgentTrace | null }>(`/api/evidence/${ticket.ticket_type}/${ticket.id}`, { silentError: true }); return { ticket, trace: data.trace }; })); setItems(details); setError(null); } catch (cause) { setError(cause instanceof Error ? cause.message : '活动流加载失败'); } finally { setLoading(false); } }, []);
  useEffect(() => { void Promise.resolve().then(load); }, [load]);
  if (loading) return <div className="flex justify-center py-20"><Spinner className="size-6" /></div>;
  return <div className="space-y-4"><div className="flex items-center justify-between"><p className="text-sm text-muted-foreground">Agent 每次运行均保留输入摘要、模型版本与裁决快照。</p><Button size="sm" variant="outline" onClick={() => void load()}><RefreshCw />刷新</Button></div>{error ? <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div> : items.length === 0 ? <div className="rounded-lg border bg-white p-10 text-center text-sm text-muted-foreground">暂无可展示的 Agent 活动</div> : <ol className="border-l border-slate-200 pl-5">{items.map(({ ticket, trace }) => <li key={ticket.id} className="relative pb-6"><span className="absolute -left-[29px] top-0 flex size-5 items-center justify-center rounded-full bg-sky-100"><Bot className="size-3 text-sky-700" /></span><div className="rounded-lg border bg-white p-4"><div className="flex flex-wrap justify-between gap-2"><h3 className="font-medium">{trace?.agent_name ?? '未关联 Agent trace'}</h3><time className="text-xs text-muted-foreground">{date(ticket.created_at)}</time></div><p className="mt-2 text-sm text-muted-foreground">{trace?.input_summary ?? `工单 ${ticket.request_id}`}</p><div className="mt-3 flex flex-wrap gap-2 text-xs"><span className="rounded bg-slate-100 px-2 py-1">Trace: {ticket.trace_id ?? '—'}</span><span className="rounded bg-slate-100 px-2 py-1">模型: {trace?.model_version ?? '—'}</span></div></div></li>)}</ol>}</div>;
}