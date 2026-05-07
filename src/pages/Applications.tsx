import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search, Filter } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { api } from '@/lib/api';
import type { Application } from '@/types/api';

const Applications: React.FC = () => {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    const url = statusFilter !== 'all' ? `/api/applications/?status=${statusFilter}` : '/api/applications/';
    api<Application[]>(url)
      .then((data) => { setApplications(data || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [statusFilter]);

  const filtered = applications.filter((a) =>
    a.material_name?.toLowerCase().includes(filter.toLowerCase()) ||
    a.app_no?.toLowerCase().includes(filter.toLowerCase()) ||
    a.material_code?.toLowerCase().includes(filter.toLowerCase())
  );

  const statusColors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-700',
    pending_admin: 'bg-yellow-100 text-yellow-700',
    pending_dept: 'bg-blue-100 text-blue-700',
    approved: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700',
    published: 'bg-emerald-100 text-emerald-700',
  };

  const statusLabels: Record<string, string> = {
    draft: '草稿', pending_admin: '待管理员审批', pending_dept: '待部门审批',
    approved: '已通过', rejected: '已驳回', published: '已发布',
  };

  if (loading) return <div className="flex justify-center py-20"><div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"/></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input placeholder="搜索申请编号、物料名称或编码..." className="pl-10 w-80" value={filter} onChange={(e) => setFilter(e.target.value)} />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-40">
              <Filter className="w-4 h-4 mr-2" />
              <SelectValue placeholder="全部状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              {Object.keys(statusLabels).map((s) => (
                <SelectItem key={s} value={s}>{statusLabels[s]}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Link to="/applications/new">
          <Button className="bg-blue-600 hover:bg-blue-700"><Plus className="w-4 h-4 mr-2" />新增申请</Button>
        </Link>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-lg">物料申请单列表（共 {filtered.length} 条）</CardTitle></CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-3 px-4">申请编号</th>
                  <th className="text-left py-3 px-4">物料名称</th>
                  <th className="text-left py-3 px-4">物料编码</th>
                  <th className="text-left py-3 px-4">类型</th>
                  <th className="text-left py-3 px-4">状态</th>
                  <th className="text-left py-3 px-4">申请人</th>
                  <th className="text-left py-3 px-4">操作</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((app) => (
                  <tr key={app.id} className="border-b hover:bg-gray-50">
                    <td className="py-3 px-4 font-medium">{app.app_no}</td>
                    <td className="py-3 px-4">{app.material_name}</td>
                    <td className="py-3 px-4">{app.material_code || '-'}</td>
                    <td className="py-3 px-4"><Badge variant="outline">{app.material_type}</Badge></td>
                    <td className="py-3 px-4">
                      <Badge className={statusColors[app.status] || 'bg-gray-100'}>{statusLabels[app.status] || app.status}</Badge>
                    </td>
                    <td className="py-3 px-4">{app.created_by_name || app.created_by}</td>
                    <td className="py-3 px-4">
                      <Link to={`/applications/${app.id}`}><Button variant="ghost" size="sm">详情</Button></Link>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && <tr><td colSpan={7} className="py-8 text-center text-gray-400">暂无申请单</td></tr>}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Applications;