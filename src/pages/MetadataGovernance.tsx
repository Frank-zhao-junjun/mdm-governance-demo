import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, CheckCircle, ClipboardList, Database, GitBranch, Network, Search, ShieldCheck, XCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { api } from '@/lib/api';
import type { MetadataGovernanceOverview } from '@/types/api';

const statusLabels: Record<string, string> = {
  draft: '草稿', pending_admin: '待管理员审批', pending_dept: '待部门审批',
  approved: '已通过', rejected: '已驳回', published: '已发布', active: '有效', obsolete: '废弃',
};

const MetadataGovernance: React.FC = () => {
  const [overview, setOverview] = useState<MetadataGovernanceOverview | null>(null);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<MetadataGovernanceOverview>('/api/metadata-governance/overview')
      .then((data) => { setOverview(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const catalog = useMemo(() => {
    const query = filter.toLowerCase();
    return (overview?.catalog || []).filter((item) =>
      item.material_name.toLowerCase().includes(query) ||
      item.material_code.toLowerCase().includes(query) ||
      item.om_entity_fqn.toLowerCase().includes(query)
    );
  }, [overview, filter]);

  const traces = useMemo(() => {
    const query = filter.toLowerCase();
    return (overview?.traces || []).filter((item) =>
      item.app_no.toLowerCase().includes(query) ||
      item.material_name.toLowerCase().includes(query) ||
      (item.material_code || '').toLowerCase().includes(query)
    );
  }, [overview, filter]);

  if (loading) return <div className="flex justify-center py-20"><div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"/></div>;

  const omStatus = overview?.openmetadata.status || 'disabled';
  const summary = overview?.summary;
  const nodeById = new Map((overview?.lineage.nodes || []).map((node) => [node.id, node]));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input placeholder="搜索物料编码、名称或FQN..." className="pl-10 w-96" value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <Badge className={omStatus === 'connected' ? 'bg-green-100 text-green-700' : omStatus === 'disabled' ? 'bg-gray-100 text-gray-700' : 'bg-yellow-100 text-yellow-700'}>
          OpenMetadata {omStatus === 'connected' ? '已连接' : omStatus === 'disabled' ? '未启用' : '未连接'}
        </Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card><CardContent className="p-5 flex items-center justify-between"><div><p className="text-sm text-gray-500">元数据资产</p><p className="text-2xl font-bold">{summary?.metadata_assets || 0}</p></div><Database className="w-6 h-6 text-blue-600" /></CardContent></Card>
        <Card><CardContent className="p-5 flex items-center justify-between"><div><p className="text-sm text-gray-500">OM同步</p><p className="text-2xl font-bold">{summary?.om_synced || 0}</p></div><Network className="w-6 h-6 text-green-600" /></CardContent></Card>
        <Card><CardContent className="p-5 flex items-center justify-between"><div><p className="text-sm text-gray-500">质量测试</p><p className="text-2xl font-bold">{summary?.quality_tests || 0}</p></div><ShieldCheck className="w-6 h-6 text-purple-600" /></CardContent></Card>
        <Card><CardContent className="p-5 flex items-center justify-between"><div><p className="text-sm text-gray-500">可追溯申请</p><p className="text-2xl font-bold">{summary?.traceable_applications || 0}</p></div><ClipboardList className="w-6 h-6 text-orange-600" /></CardContent></Card>
      </div>

      <Tabs defaultValue="catalog" className="space-y-4">
        <TabsList>
          <TabsTrigger value="catalog"><Database className="w-4 h-4" />元数据目录</TabsTrigger>
          <TabsTrigger value="lineage"><GitBranch className="w-4 h-4" />血缘关系</TabsTrigger>
          <TabsTrigger value="quality"><ShieldCheck className="w-4 h-4" />质量测试</TabsTrigger>
          <TabsTrigger value="trace"><Activity className="w-4 h-4" />全链路追溯</TabsTrigger>
        </TabsList>

        <TabsContent value="catalog">
          <Card>
            <CardHeader><CardTitle className="text-base">元数据资产目录（{catalog.length}）</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader><TableRow><TableHead>物料编码</TableHead><TableHead>名称</TableHead><TableHead>分类路径</TableHead><TableHead>OpenMetadata FQN</TableHead><TableHead>同步</TableHead></TableRow></TableHeader>
                <TableBody>
                  {catalog.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">{item.material_code}</TableCell>
                      <TableCell>{item.material_name}</TableCell>
                      <TableCell className="max-w-xs whitespace-normal text-gray-600">{item.classification_path || '-'}</TableCell>
                      <TableCell className="font-mono text-xs text-gray-600">{item.om_entity_fqn}</TableCell>
                      <TableCell>{item.om_synced ? <CheckCircle className="w-4 h-4 text-green-500" /> : <XCircle className="w-4 h-4 text-gray-400" />}</TableCell>
                    </TableRow>
                  ))}
                  {catalog.length === 0 && <TableRow><TableCell colSpan={5} className="py-8 text-center text-gray-400">暂无元数据资产</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="lineage">
          <Card>
            <CardHeader><CardTitle className="text-base">物料主数据血缘</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {(overview?.lineage.edges || []).map((edge, index) => {
                const from = nodeById.get(edge.from);
                const to = nodeById.get(edge.to);
                return (
                  <div key={`${edge.from}-${edge.to}-${index}`} className="grid grid-cols-[1fr_160px_1fr] items-center gap-3 rounded-lg bg-gray-50 p-3">
                    <div><p className="font-medium">{from?.label}</p><p className="text-xs text-gray-500">{from?.subtitle || from?.type}</p></div>
                    <div className="text-center"><Badge variant="outline">{edge.label}</Badge><div className="mt-2 h-px bg-gray-300" /></div>
                    <div><p className="font-medium">{to?.label}</p><p className="text-xs text-gray-500">{to?.subtitle || to?.type}</p></div>
                  </div>
                );
              })}
              {(!overview?.lineage.edges.length) && <p className="py-8 text-center text-gray-400">暂无血缘关系</p>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="quality">
          <Card>
            <CardHeader><CardTitle className="text-base">质量测试结果</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {(overview?.quality_tests || []).map((test) => (
                <div key={test.id} className="flex items-center gap-3 rounded-lg bg-gray-50 p-3">
                  {test.status === 'passed' ? <CheckCircle className="w-5 h-5 text-green-500" /> : <XCircle className="w-5 h-5 text-red-500" />}
                  <div className="flex-1"><p className="font-medium">{test.test_name}</p><p className="text-xs text-gray-500">{test.material_code} · {test.source} · {new Date(test.executed_at).toLocaleString('zh-CN')}</p></div>
                  <span className="text-sm text-gray-600">{test.message}</span>
                </div>
              ))}
              {(!overview?.quality_tests.length) && <p className="py-8 text-center text-gray-400">暂无质量测试结果</p>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="trace">
          <Card>
            <CardHeader><CardTitle className="text-base">申请与发布追溯</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader><TableRow><TableHead>申请编号</TableHead><TableHead>物料</TableHead><TableHead>状态</TableHead><TableHead>步骤数</TableHead><TableHead>最后步骤</TableHead><TableHead>操作</TableHead></TableRow></TableHeader>
                <TableBody>
                  {traces.map((trace) => (
                    <TableRow key={trace.application_id}>
                      <TableCell className="font-medium">{trace.app_no}</TableCell>
                      <TableCell>{trace.material_name}</TableCell>
                      <TableCell><Badge className="bg-gray-100 text-gray-700">{statusLabels[trace.status] || trace.status}</Badge></TableCell>
                      <TableCell>{trace.step_count}</TableCell>
                      <TableCell>{trace.last_step || '-'}</TableCell>
                      <TableCell><Link to={`/audit/${trace.application_id}`}><Button variant="ghost" size="sm">追溯</Button></Link></TableCell>
                    </TableRow>
                  ))}
                  {traces.length === 0 && <TableRow><TableCell colSpan={6} className="py-8 text-center text-gray-400">暂无追溯记录</TableCell></TableRow>}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default MetadataGovernance;