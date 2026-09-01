import { useCallback, useEffect, useState } from 'react';
import { Building2, RefreshCw, Scale } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Spinner } from '@/components/ui/spinner';
import { api } from '@/lib/api';
import type { GovernanceTicket } from '@/types/api';

interface ClusterResponse { total: number; items: Array<GovernanceTicket & { factory_agreements_json?: Record<string, string> | null; candidate_golden_ids?: string[] }>; }

export default function DisputeView() {
  const [items, setItems] = useState<ClusterResponse['items']>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { setLoading(true); try { const response = await api<ClusterResponse>('/api/governance/clusters', { silentError: true }); setItems(response.items.filter((item) => item.factory_agreements_json && Object.values(item.factory_agreements_json).includes('oppose'))); setError(null); } catch (cause) { setError(cause instanceof Error ? cause.message : '争议工单加载失败'); } finally { setLoading(false); } }, []);
  useEffect(() => { void Promise.resolve().then(load); }, [load]);
  if (loading) return <div className="flex justify-center py-20"><Spinner className="size-6" /></div>;
  return <div className="space-y-4"><div className="flex items-center justify-between"><p className="text-sm text-muted-foreground">跨工厂分歧进入会签与治理委员会裁决，不能由 Agent 自动归并。</p><Button size="sm" variant="outline" onClick={() => void load()}><RefreshCw />刷新</Button></div>{error ? <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div> : items.length === 0 ? <div className="rounded-lg border bg-white p-10 text-center text-sm text-muted-foreground">没有待处理的跨工厂争议</div> : items.map((item) => <Card key={item.id}><CardHeader><CardTitle className="flex items-center gap-2 text-base"><Scale className="size-5 text-amber-600" />归并争议 <Badge variant="outline">{item.status}</Badge></CardTitle></CardHeader><CardContent><p className="text-sm text-muted-foreground">候选记录：{item.candidate_golden_ids?.join(' / ') ?? '—'}</p><div className="mt-4 grid gap-3 sm:grid-cols-2">{Object.entries(item.factory_agreements_json ?? {}).map(([factory, decision]) => <div key={factory} className="flex items-center justify-between rounded-md border p-3"><span className="flex items-center gap-2 text-sm"><Building2 className="size-4 text-slate-500" />工厂 {factory}</span><Badge className={decision === 'agree' ? 'bg-emerald-700 hover:bg-emerald-700' : 'bg-rose-700 hover:bg-rose-700'}>{decision === 'agree' ? '同意归并' : '反对归并'}</Badge></div>)}</div><p className="mt-4 text-sm text-amber-700">当前需双方 Owner 会签，并由治理委员会保留最终裁决与证据快照。</p></CardContent></Card>)}</div>;
}