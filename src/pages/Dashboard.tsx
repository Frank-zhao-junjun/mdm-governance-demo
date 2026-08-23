import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FileText, Database, FolderTree, CheckCircle, Clock } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api';
import type { DashboardStats, Application, AuditLog } from '@/types/api';

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<DashboardStats>('/api/dashboard')
      .then((data) => {
        setStats(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="flex justify-center py-20"><div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"/></div>;
  }

  const statCards = [
    { label: '总申请单', value: stats?.stats?.total_applications || 0, icon: FileText, color: 'bg-blue-500' },
    { label: 'Golden Record', value: stats?.stats?.total_golden_records || 0, icon: Database, color: 'bg-green-500' },
    { label: '分类数', value: stats?.stats?.total_classifications || 0, icon: FolderTree, color: 'bg-purple-500' },
    { label: '待审批', value: (stats?.stats?.pending_admin || 0) + (stats?.stats?.pending_dept || 0), icon: Clock, color: 'bg-orange-500' },
  ];

  const statusColors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-700',
    pending_admin: 'bg-yellow-100 text-yellow-700',
    pending_dept: 'bg-blue-100 text-blue-700',
    approved: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700',
    published: 'bg-emerald-100 text-emerald-700',
  };

  const statusLabels: Record<string, string> = {
    draft: '草稿',
    pending_admin: '待管理员审批',
    pending_dept: '待部门审批',
    approved: '已通过',
    rejected: '已驳回',
    published: '已发布',
  };

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.label}>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-500">{card.label}</p>
                    <p className="text-3xl font-bold mt-1">{card.value}</p>
                  </div>
                  <div className={`${card.color} p-3 rounded-lg`}>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Quick Actions */}
      <div className="flex gap-4">
        <Link to="/applications/new">
          <Button className="bg-blue-600 hover:bg-blue-700">
            <FileText className="w-4 h-4 mr-2" />
            新增物料申请
          </Button>
        </Link>
      </div>

      {/* Recent Applications */}
      <Card>
        <CardHeader><CardTitle className="text-lg">最近申请单</CardTitle></CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-3 px-4">申请编号</th>
                  <th className="text-left py-3 px-4">物料名称</th>
                  <th className="text-left py-3 px-4">物料编码</th>
                  <th className="text-left py-3 px-4">状态</th>
                  <th className="text-left py-3 px-4">申请人</th>
                </tr>
              </thead>
              <tbody>
                {(stats?.recent_applications || []).map((app: Application) => (
                  <tr key={app.id} className="border-b hover:bg-gray-50">
                    <td className="py-3 px-4 font-medium">{app.app_no}</td>
                    <td className="py-3 px-4">{app.material_name}</td>
                    <td className="py-3 px-4">{app.material_code || '-'}</td>
                    <td className="py-3 px-4">
                      <Badge className={statusColors[app.status] || 'bg-gray-100'}>
                        {statusLabels[app.status] || app.status}
                      </Badge>
                    </td>
                    <td className="py-3 px-4">{app.created_by_name || app.created_by}</td>
                  </tr>
                ))}
                {(!stats?.recent_applications?.length) && (
                  <tr><td colSpan={5} className="py-8 text-center text-gray-400">暂无申请单</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Audit Summary */}
      <Card>
        <CardHeader><CardTitle className="text-lg">最近审计日志</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-3">
            {(stats?.recent_audit_logs || []).slice(0, 5).map((log: AuditLog) => (
              <div key={log.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                {log.status === 'success' ? (
                  <CheckCircle className="w-5 h-5 text-green-500" />
                ) : (
                  <div className="w-5 h-5 rounded-full bg-red-500" />
                )}
                <div className="flex-1">
                  <p className="font-medium">{log.step_label}</p>
                  <p className="text-xs text-gray-500">
                    {log.executed_by_name || log.executed_by} · {new Date(log.executed_at).toLocaleString('zh-CN')}
                  </p>
                </div>
                <Badge variant={log.status === 'success' ? 'default' : 'destructive'}>
                  {log.status === 'success' ? '成功' : '失败'}
                </Badge>
              </div>
            ))}
            {(!stats?.recent_audit_logs?.length) && <p className="text-center text-gray-400 py-4">暂无审计日志</p>}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Dashboard;