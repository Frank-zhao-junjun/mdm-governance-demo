import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ClipboardList, CheckCircle, XCircle, Clock } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api';
import type { Application, AuditLog } from '@/types/api';

const AuditTrace: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [app, setApp] = useState<Application | null>(null);
  const [audit, setAudit] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api<Application>(`/api/applications/${id}`),
      api<{ trace: AuditLog[] }>(`/api/applications/${id}/audit`),
    ]).then(([appData, auditData]) => {
      setApp(appData);
      setAudit(auditData.trace || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="flex justify-center py-20"><div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"/></div>;

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center gap-3">
        <ClipboardList className="w-6 h-6 text-blue-600" />
        <h2 className="text-xl font-semibold">全链路审计追踪</h2>
      </div>

      {app && (
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div><p className="text-sm text-gray-500">申请编号</p><p className="font-bold text-lg">{app.app_no}</p></div>
            <div><p className="text-sm text-gray-500">物料名称</p><p className="font-medium">{app.material_name}</p></div>
            <div><p className="text-sm text-gray-500">物料编码</p><p className="font-medium">{app.material_code || '-'}</p></div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle className="text-base">审计日志 ({audit.length} 条)</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-3">
            {audit.map((log, i) => (
              <div key={i} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                {log.status === 'success' ? (
                  <CheckCircle className="w-5 h-5 text-green-500 mt-0.5" />
                ) : log.status === 'failed' ? (
                  <XCircle className="w-5 h-5 text-red-500 mt-0.5" />
                ) : (
                  <Clock className="w-5 h-5 text-gray-400 mt-0.5" />
                )}
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{log.step_label}</span>
                    <Badge variant={log.status === 'success' ? 'default' : log.status === 'failed' ? 'destructive' : 'secondary'} className="text-xs">{log.status_label}</Badge>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">{log.executed_by_name || log.executed_by} · {new Date(log.executed_at).toLocaleString('zh-CN')}</p>
                  <p className="text-xs text-gray-400">{log.step_id}</p>
                  {log.error_message && <p className="text-xs text-red-500 mt-1">{log.error_message}</p>}
                </div>
              </div>
            ))}
            {audit.length === 0 && <p className="text-center text-gray-400 py-4">暂无审计日志</p>}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AuditTrace;