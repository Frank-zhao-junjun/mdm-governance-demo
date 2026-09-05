import { useCallback, useEffect, useState } from 'react';
import { Activity, CheckCircle2, CircleAlert, RefreshCw } from 'lucide-react';
import { Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Spinner } from '@/components/ui/spinner';
import { api } from '@/lib/api';
import type { GovernanceReport } from '@/types/api';

const EMPTY: GovernanceReport = { quality_score: 0, duplicate_rate: 0, pending_todos: 0, agent_activity: 0 };

export default function GovernanceDashboard() {
  const [report, setReport] = useState<GovernanceReport>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setLoading(true);
    try { setReport(await api<GovernanceReport>('/api/governance/report', { silentError: true })); setError(null); }
    catch (cause) { setError(cause instanceof Error ? cause.message : '治理报告加载失败'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void Promise.resolve().then(load); }, [load]);
  const chart = [{ name: '质量分', value: report.quality_score, fill: '#0f766e' }, { name: '待改善', value: 100 - report.quality_score, fill: '#e2e8f0' }];
  return <div className="space-y-5">
    <div className="flex items-center justify-between"><p className="text-sm text-muted-foreground">质量、重复风险与人工治理工作量的当前快照。</p><Button size="sm" variant="outline" onClick={() => void load()}><RefreshCw />刷新</Button></div>
    {loading ? <div className="flex justify-center py-20"><Spinner className="size-6" /></div> : error ? <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">治理报告加载失败：{error}</div> : <>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><Metric icon={<CheckCircle2 className="text-teal-700" />} label="质量分" value={`${report.quality_score}%`} /><Metric icon={<CircleAlert className="text-amber-600" />} label="重复率" value={`${report.duplicate_rate}%`} /><Metric icon={<Activity className="text-sky-700" />} label="待办裁决" value={String(report.pending_todos)} /><Metric icon={<Activity className="text-violet-700" />} label="Agent 活动" value={String(report.agent_activity)} /></div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_19rem]"><Card><CardHeader><CardTitle className="text-base">治理质量构成</CardTitle></CardHeader><CardContent className="h-60"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={chart} dataKey="value" nameKey="name" innerRadius={62} outerRadius={88} paddingAngle={2} /><Tooltip /></PieChart></ResponsiveContainer></CardContent></Card><Card><CardHeader><CardTitle className="text-base">治理口径</CardTitle></CardHeader><CardContent className="space-y-3 text-sm text-muted-foreground"><p>质量分由已识别质量工单与当前存量记录计算。</p><p>重复率反映归并建议工单相对存量的比例。</p><p>指标随裁决和工单状态变动后由 API 刷新。</p></CardContent></Card></div>
    </>}
  </div>;
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return <Card><CardContent className="flex items-center gap-3 p-4"><div className="rounded-md bg-slate-100 p-2">{icon}</div><div><p className="text-xs text-muted-foreground">{label}</p><p className="text-2xl font-semibold text-slate-800">{value}</p></div></CardContent></Card>;
}