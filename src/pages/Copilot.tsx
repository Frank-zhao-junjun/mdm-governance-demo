import { useCallback, useEffect, useState } from 'react';
import { Check, RefreshCw, Scale, ShieldAlert, X } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Spinner } from '@/components/ui/spinner';
import { Textarea } from '@/components/ui/textarea';
import { api } from '@/lib/api';
import type { GovernanceTicket, TodoListResponse } from '@/types/api';

const STATUS_LABELS: Record<GovernanceTicket['status'], string> = {
  draft: '待裁决', pending: '待处理', approved: '已批准', rejected: '已驳回',
  executing: '执行中', done: '已完成', failed: '执行失败',
};

function level(ticket: GovernanceTicket) {
  const evidence = ticket.evidence_json;
  return typeof evidence?.level === 'string' ? evidence.level : ticket.ticket_type === 'merge' ? 'L1' : 'L2';
}

const RESULT_STATUS_LABELS: Record<string, string> = {
  pass: '通过', warn: '警告', block: '阻断', suggest: '建议',
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

// 证据快照结构化渲染：质量工单为 SkillSuggestion，归并工单为 SkillResult（见 backend/app/skills/common.py）
function EvidenceView({ ticket }: { ticket: GovernanceTicket }) {
  const evidence = ticket.evidence_json;
  if (!evidence) return <p className="text-muted-foreground">未提供证据快照</p>;
  // SkillSuggestion：{ field, suggestion, evidence: { level, source, detail } }
  if (typeof evidence.suggestion === 'string') {
    const inner = asRecord(evidence.evidence);
    return <ul className="space-y-1 text-muted-foreground">
      {typeof evidence.field === 'string' && <li>字段：{evidence.field}</li>}
      <li>建议：{evidence.suggestion}</li>
      {inner && typeof inner.detail === 'string' && <li>依据：{inner.detail}{typeof inner.source === 'string' ? `（${inner.source}）` : ''}</li>}
    </ul>;
  }
  // SkillResult：{ status, suggestions, conflicts }
  if (typeof evidence.status === 'string') {
    const conflicts = (Array.isArray(evidence.conflicts) ? evidence.conflicts : []).map(asRecord).filter((c): c is Record<string, unknown> => c !== null);
    const suggestions = (Array.isArray(evidence.suggestions) ? evidence.suggestions : []).map(asRecord).filter((s): s is Record<string, unknown> => s !== null);
    return <ul className="space-y-1 text-muted-foreground">
      <li>结论：{RESULT_STATUS_LABELS[evidence.status] ?? evidence.status}</li>
      {conflicts.map((c, i) => <li key={`c${i}`}>冲突：{[c.message, c.detail].filter((v): v is string => typeof v === 'string').join(' — ')}</li>)}
      {suggestions.map((s, i) => typeof s.suggestion === 'string' && <li key={`s${i}`}>建议：{typeof s.field === 'string' ? `${s.field}：` : ''}{s.suggestion}</li>)}
    </ul>;
  }
  return <pre className="whitespace-pre-wrap break-all text-xs text-muted-foreground">{JSON.stringify(evidence, null, 2)}</pre>;
}

export default function Copilot() {
  const [todos, setTodos] = useState<GovernanceTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [opinion, setOpinion] = useState<Record<string, string>>({});
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState<string | null>(null);

  const loadTodos = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api<TodoListResponse>('/api/copilot/todos', { silentError: true });
      setTodos(response.items);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '裁决待办加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void Promise.resolve().then(loadTodos); }, [loadTodos]);

  const decide = async (ticket: GovernanceTicket, action: 'approve' | 'reject' | 'overturn') => {
    const isMerge = ticket.ticket_type === 'merge';
    if (isMerge && (!opinion[ticket.id]?.trim() || !confirmed[ticket.id])) {
      toast.error('归并属于高风险裁决，需填写意见并完成二次确认');
      return;
    }
    setSubmitting(ticket.id);
    try {
      await api(`/api/copilot/${ticket.ticket_type}/${ticket.id}/${action}`, {
        method: 'POST',
        body: JSON.stringify({ opinion: opinion[ticket.id] || undefined, confirmed: confirmed[ticket.id] || false }),
      });
      toast.success(action === 'approve' ? '裁决已批准并留痕' : action === 'reject' ? '建议已驳回并留痕' : '工单已改判并留痕');
      await loadTodos();
    } catch {
      // api() reports the server error in the notification surface.
    } finally {
      setSubmitting(null);
    }
  };

  if (loading) return <div className="flex justify-center py-20"><Spinner className="size-6" /></div>;
  if (error) return <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">待办加载失败：{error}<Button className="ml-3" size="sm" variant="outline" onClick={() => void loadTodos()}>重试</Button></div>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><p className="text-sm text-muted-foreground">所有建议均需责任人裁决。高风险归并须意见与二次确认。</p></div>
        <Button variant="outline" size="sm" onClick={() => void loadTodos()}><RefreshCw />刷新</Button>
      </div>
      {todos.length === 0 ? <div className="rounded-lg border bg-white p-10 text-center text-sm text-muted-foreground">当前没有待裁决工单</div> : todos.map((ticket) => {
        const isMerge = ticket.ticket_type === 'merge';
        return <article key={ticket.id} className="rounded-lg border bg-white p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-center gap-2"><Scale className={isMerge ? 'size-5 text-amber-600' : 'size-5 text-sky-600'} /><h3 className="font-semibold">{isMerge ? '归并建议裁决' : '质量整改裁决'}</h3><Badge variant="outline">{STATUS_LABELS[ticket.status]}</Badge></div>
            <Badge className={level(ticket) === 'L1' ? 'bg-emerald-700 hover:bg-emerald-700' : 'bg-amber-600 hover:bg-amber-600'}>{level(ticket)} 证据</Badge>
          </div>
          <div className="mt-4 grid gap-4 text-sm md:grid-cols-3">
            <section><p className="mb-1 font-medium text-slate-700">证据链</p><div className="break-words"><EvidenceView ticket={ticket} /></div></section>
            <section><p className="mb-1 font-medium text-slate-700">风险标注</p><p className="flex items-center gap-1 text-muted-foreground">{isMerge && <ShieldAlert className="size-4 text-amber-600" />}{isMerge ? '高风险：归并不会自动执行' : '中风险：需指派整改责任人'}</p></section>
            <section><p className="mb-1 font-medium text-slate-700">替代选项</p><p className="text-muted-foreground">{isMerge ? '驳回建议，保留两条记录；或改判后补充证据。' : '驳回并补充规则，或改判为人工复核。'}</p></section>
          </div>
          {isMerge && <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3"><Textarea value={opinion[ticket.id] || ''} onChange={(event) => setOpinion((current) => ({ ...current, [ticket.id]: event.target.value }))} placeholder="填写归并裁决依据" /><label className="mt-3 flex items-center gap-2 text-sm"><Checkbox checked={confirmed[ticket.id] || false} onCheckedChange={(value) => setConfirmed((current) => ({ ...current, [ticket.id]: value === true }))} />我已核对证据并确认该高风险裁决</label></div>}
          <div className="mt-4 flex flex-wrap gap-2"><Button size="sm" disabled={submitting === ticket.id} onClick={() => void decide(ticket, 'approve')}><Check />批准</Button><Button size="sm" variant="outline" disabled={submitting === ticket.id} onClick={() => void decide(ticket, 'reject')}><X />驳回</Button><Button size="sm" variant="ghost" disabled={submitting === ticket.id} onClick={() => void decide(ticket, 'overturn')}>改判</Button></div>
        </article>;
      })}
    </div>
  );
}