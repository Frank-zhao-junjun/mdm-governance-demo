import React, { useEffect, useState } from 'react';
import { FolderTree } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api';
import type { Classification } from '@/types/api';

const Classifications: React.FC = () => {
  const [classifications, setClassifications] = useState<Classification[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<Classification[]>('/api/classifications/')
      .then((data) => { setClassifications(data || []); setLoading(false); });
  }, []);

  if (loading) return <div className="flex justify-center py-20"><div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"/></div>;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <FolderTree className="w-5 h-5" />
            物料分类体系（三级分类）
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {classifications.map((c) => (
              <div key={c.id} className="border rounded-lg p-4">
                <div className="flex items-center gap-3 mb-3">
                  <Badge variant="outline" className="bg-blue-50">{c.code}</Badge>
                  <span className="font-semibold">{c.name}</span>
                  <Badge className="bg-gray-100 text-gray-700">{c.level === 1 ? '大类' : c.level === 2 ? '中类' : '小类'}</Badge>
                  <span className="text-sm text-gray-500">{c.description}</span>
                </div>
                {c.children && c.children.length > 0 && (
                  <div className="ml-8 space-y-2">
                    {c.children.map((child) => (
                      <div key={child.id} className="rounded-lg bg-gray-50 p-2">
                        <div className="flex items-center gap-3">
                          <Badge variant="outline">{child.code}</Badge>
                          <span className="font-medium">{child.name}</span>
                          <Badge className="bg-gray-100 text-gray-700">中类</Badge>
                          <span className="text-sm text-gray-500">{child.description}</span>
                        </div>
                        {child.children && child.children.length > 0 && (
                          <div className="ml-8 mt-2 space-y-1">
                            {child.children.map((minor) => (
                              <div key={minor.id} className="flex items-center gap-3 rounded-md bg-white px-2 py-1">
                                <Badge variant="outline">{minor.code}</Badge>
                                <span className="text-sm font-medium">{minor.name}</span>
                                <Badge className="bg-gray-100 text-gray-700">小类</Badge>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Classifications;