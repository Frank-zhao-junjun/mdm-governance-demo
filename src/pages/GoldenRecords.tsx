import React, { useEffect, useState } from 'react';
import { Database, Search, CheckCircle, XCircle } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api';
import type { GoldenRecord } from '@/types/api';

const GoldenRecords: React.FC = () => {
  const [records, setRecords] = useState<GoldenRecord[]>([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<GoldenRecord[]>('/api/golden-records/')
      .then((data) => { setRecords(data || []); setLoading(false); });
  }, []);

  const filtered = records.filter((r) =>
    r.material_name?.toLowerCase().includes(filter.toLowerCase()) ||
    r.material_code?.toLowerCase().includes(filter.toLowerCase())
  );

  if (loading) return <div className="flex justify-center py-20"><div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"/></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input placeholder="搜索物料编码或名称..." className="pl-10 w-80" value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <Badge className="bg-green-100 text-green-700">共 {filtered.length} 条 Golden Record</Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((r) => (
          <Card key={r.id} className="hover:shadow-md transition-shadow">
            <CardContent className="p-5">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="text-lg font-bold text-blue-700">{r.material_code}</p>
                  <p className="text-sm text-gray-600">{r.material_name}</p>
                </div>
                <Database className="w-5 h-5 text-gray-400" />
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-gray-500">版本:</span> <span>v{r.version}.{r.revision}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">类型:</span> <span>{r.material_type}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">状态:</span><Badge className={r.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100'}>{r.status === 'active' ? '有效' : '废弃'}</Badge></div>
                <div className="flex justify-between"><span className="text-gray-500">BTP:</span>{r.btp_published ? <CheckCircle className="w-4 h-4 text-green-500" /> : <XCircle className="w-4 h-4 text-gray-400" />}</div>
                <div className="flex justify-between"><span className="text-gray-500">OM:</span>{r.om_synced ? <CheckCircle className="w-4 h-4 text-green-500" /> : <XCircle className="w-4 h-4 text-gray-400" />}</div>
              </div>
            </CardContent>
          </Card>
        ))}
        {filtered.length === 0 && <p className="text-center text-gray-400 col-span-3 py-8">暂无 Golden Record</p>}
      </div>
    </div>
  );
};

export default GoldenRecords;