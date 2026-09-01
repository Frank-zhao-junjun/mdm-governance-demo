import React from 'react';
import { Link } from 'react-router-dom';
import { Database, ShieldCheck } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const Dashboard: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Database className="w-5 h-5 text-blue-600" />
              数据标准管理
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-600">
              物料 / 供应商 / 客户主数据的字段级取值标准管理，支持按实体类型与 SAP 表检索。
            </p>
            <Link to="/quality/standards" className="inline-block mt-3 text-sm text-blue-600 hover:underline">
              进入管理 →
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-green-600" />
              服务边界
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-600">
              本平台仅提供数据治理与数据质量管理能力；新增数据申请、审批、金标数据与发布分发由业务系统承接。
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;
