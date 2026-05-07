import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, CheckCircle, XCircle, Clock, RefreshCw, FileText } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { api, downloadFile } from '@/lib/api';
import type { Application, AuditLog } from '@/types/api';

const ApplicationDetail: React.FC = () => {
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

  const handleAction = async (endpoint: string, successMsg: string) => {
    try {
      const data = await api<{ success: boolean; message: string }>(endpoint, { method: 'POST', body: { approved: true, comment: successMsg } });
      toast.success(data.message);
      window.location.reload();
    } catch {
      // Error handled by api client
    }
  };

  const handlePublish = async () => {
    if (!id) return;
    try {
      const data = await api<{ success: boolean; message: string }>(`/api/applications/${id}/publish`, { method: 'POST' });
      toast.success(data.message);
      window.location.reload();
    } catch {
      // Error handled by api client
    }
  };

  const handleDownload = async (path: string, filename: string) => {
    try {
      await downloadFile(path, filename);
    } catch {
      toast.error('附件下载失败');
    }
  };

  const statusColors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-700', pending_admin: 'bg-yellow-100 text-yellow-700',
    pending_dept: 'bg-blue-100 text-blue-700', approved: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700', published: 'bg-emerald-100 text-emerald-700',
  };
  const statusLabels: Record<string, string> = {
    draft: '草稿', pending_admin: '待管理员审批', pending_dept: '待部门审批',
    approved: '已通过', rejected: '已驳回', published: '已发布',
  };

  if (loading) return <div className="flex justify-center py-20"><div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"/></div>;
  if (!app) return <div>申请单不存在</div>;

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center gap-4">
        <Link to="/applications"><Button variant="ghost"><ArrowLeft className="w-4 h-4 mr-2" />返回</Button></Link>
        <h2 className="text-xl font-semibold">申请单详情</h2>
        <Badge className={statusColors[app.status] || 'bg-gray-100'}>{statusLabels[app.status] || app.status}</Badge>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">基本信息</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-3 gap-4 text-sm">
          <div><span className="text-gray-500">申请编号:</span> <span className="font-medium">{app.app_no}</span></div>
          <div><span className="text-gray-500">物料名称:</span> <span className="font-medium">{app.material_name}</span></div>
          <div><span className="text-gray-500">物料编码:</span> <span className="font-medium">{app.material_code || '-'}</span></div>
          <div><span className="text-gray-500">物料类型:</span> <span>{app.material_type}</span></div>
          <div><span className="text-gray-500">申请人:</span> <span>{app.created_by_name || app.created_by}</span></div>
          <div><span className="text-gray-500">申请时间:</span> <span>{new Date(app.created_at).toLocaleString('zh-CN')}</span></div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">审批状态</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-3">
            {app.admin_approved ? <CheckCircle className="w-5 h-5 text-green-500" /> : <Clock className="w-5 h-5 text-gray-400" />}
            <span>管理员审批</span>
            {app.admin_approved_by && <span className="text-sm text-gray-500">by {app.admin_approved_by}</span>}
          </div>
          <div className="flex items-center gap-3">
            {app.dept_approved ? <CheckCircle className="w-5 h-5 text-green-500" /> : <Clock className="w-5 h-5 text-gray-400" />}
            <span>部门审批</span>
            {app.dept_approved_by && <span className="text-sm text-gray-500">by {app.dept_approved_by}</span>}
          </div>
        </CardContent>
      </Card>

      {app.attachments && app.attachments.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">图纸与附件</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {app.attachments.map((file) => (
              <button
                key={file.id}
                type="button"
                onClick={() => handleDownload(file.download_url, file.original_name)}
                className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-sm hover:bg-gray-100"
              >
                <span className="flex items-center gap-2 text-gray-700">
                  <FileText className="w-4 h-4" />
                  {file.original_name}
                </span>
                <span className="text-xs text-gray-500">{Math.ceil(file.size / 1024)} KB</span>
              </button>
            ))}
          </CardContent>
        </Card>
      )}

      {app.validation_result && (
        <Card>
          <CardHeader><CardTitle className="text-base">质量校验结果</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {app.validation_result.checks?.map((c, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  {c.passed ? <CheckCircle className="w-4 h-4 text-green-500" /> : <XCircle className="w-4 h-4 text-red-500" />}
                  <span>{c.message}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle className="text-base">全链路审计追踪</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-3">
            {audit.map((log, i) => (
              <div key={i} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                {log.status === 'success' ? <CheckCircle className="w-5 h-5 text-green-500 mt-0.5" /> : <XCircle className="w-5 h-5 text-red-500 mt-0.5" />}
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{log.step_label}</span>
                    <Badge variant={log.status === 'success' ? 'default' : 'destructive'} className="text-xs">{log.status_label}</Badge>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">{log.executed_by_name || log.executed_by} · {new Date(log.executed_at).toLocaleString('zh-CN')}</p>
                  <p className="text-xs text-gray-400">{log.step_id}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-3">
        {app.status === 'pending_admin' && (
          <>
            <Button className="bg-green-600 hover:bg-green-700" onClick={() => handleAction(`/api/applications/${id}/admin-approve`, '管理员审批通过')}><CheckCircle className="w-4 h-4 mr-2" />通过</Button>
            <Button variant="destructive" onClick={() => handleAction(`/api/applications/${id}/admin-approve`, '驳回')}><XCircle className="w-4 h-4 mr-2" />驳回</Button>
          </>
        )}
        {app.status === 'pending_dept' && (
          <>
            <Button className="bg-green-600 hover:bg-green-700" onClick={() => handleAction(`/api/applications/${id}/dept-approve`, '部门审批通过')}><CheckCircle className="w-4 h-4 mr-2" />通过</Button>
            <Button variant="destructive" onClick={() => handleAction(`/api/applications/${id}/dept-approve`, '驳回')}><XCircle className="w-4 h-4 mr-2" />驳回</Button>
          </>
        )}
        {app.status === 'approved' && (
          <Button className="bg-blue-600 hover:bg-blue-700" onClick={handlePublish}><RefreshCw className="w-4 h-4 mr-2" />发布到 Golden Record</Button>
        )}
      </div>
    </div>
  );
};

export default ApplicationDetail;