import React, { useEffect, useMemo, useState } from 'react';
import { ShieldAlert } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { api, getUser } from '@/lib/api';
import type { GovernanceRule } from '@/types/api';

const GovernanceRules: React.FC = () => {
  const [rules, setRules] = useState<GovernanceRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const user = getUser();
  const canEdit = user?.role === 'admin' || user?.role === 'data_admin';

  useEffect(() => {
    api<GovernanceRule[]>('/api/governance-rules/')
      .then((data) => {
        setRules(data || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const groupedStats = useMemo(() => {
    const active = rules.filter((r) => r.is_active).length;
    const blocking = rules.filter((r) => r.severity === 'blocking' && r.is_active).length;
    const warning = rules.filter((r) => r.severity === 'warning' && r.is_active).length;
    return { active, blocking, warning };
  }, [rules]);

  const updateLocal = (ruleKey: string, patch: Partial<GovernanceRule>) => {
    setRules((prev) => prev.map((rule) => (rule.rule_key === ruleKey ? { ...rule, ...patch } : rule)));
  };

  const saveRule = async (rule: GovernanceRule) => {
    if (!canEdit) return;
    setSavingKey(rule.rule_key);
    try {
      const updated = await api<GovernanceRule>(`/api/governance-rules/${rule.rule_key}`, {
        method: 'PUT',
        body: JSON.stringify({
          rule_name: rule.rule_name,
          severity: rule.severity,
          category: rule.category,
          score_penalty: Number(rule.score_penalty),
          is_active: rule.is_active,
          description: rule.description || null,
        }),
      });
      updateLocal(rule.rule_key, updated);
    } finally {
      setSavingKey(null);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-5">
            <p className="text-sm text-gray-500">生效规则</p>
            <p className="text-2xl font-bold">{groupedStats.active}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-sm text-gray-500">阻断规则</p>
            <p className="text-2xl font-bold text-red-600">{groupedStats.blocking}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <p className="text-sm text-gray-500">预警规则</p>
            <p className="text-2xl font-bold text-yellow-600">{groupedStats.warning}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <ShieldAlert className="w-5 h-5" />
            治理规则管理
          </CardTitle>
          {!canEdit && (
            <p className="text-sm text-gray-500">当前账号为只读权限，仅管理员/数据管理员可编辑。</p>
          )}
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>规则键</TableHead>
                <TableHead>规则名称</TableHead>
                <TableHead>严重级别</TableHead>
                <TableHead>分值扣减</TableHead>
                <TableHead>分类</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.map((rule) => (
                <TableRow key={rule.id}>
                  <TableCell className="font-mono text-xs">{rule.rule_key}</TableCell>
                  <TableCell>
                    <Input
                      value={rule.rule_name}
                      disabled={!canEdit}
                      onChange={(e) => updateLocal(rule.rule_key, { rule_name: e.target.value })}
                    />
                  </TableCell>
                  <TableCell>
                    <select
                      className="h-9 rounded-md border border-gray-300 px-2 text-sm"
                      value={rule.severity}
                      disabled={!canEdit}
                      onChange={(e) => updateLocal(rule.rule_key, { severity: e.target.value as GovernanceRule['severity'] })}
                    >
                      <option value="blocking">blocking</option>
                      <option value="warning">warning</option>
                    </select>
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      value={rule.score_penalty}
                      disabled={!canEdit}
                      onChange={(e) => updateLocal(rule.rule_key, { score_penalty: Number(e.target.value || 0) })}
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      value={rule.category}
                      disabled={!canEdit}
                      onChange={(e) => updateLocal(rule.rule_key, { category: e.target.value })}
                    />
                  </TableCell>
                  <TableCell>
                    <label className="inline-flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={rule.is_active}
                        disabled={!canEdit}
                        onChange={(e) => updateLocal(rule.rule_key, { is_active: e.target.checked })}
                      />
                      {rule.is_active ? <Badge className="bg-green-100 text-green-700">生效</Badge> : <Badge className="bg-gray-100 text-gray-700">停用</Badge>}
                    </label>
                  </TableCell>
                  <TableCell>
                    <Button
                      size="sm"
                      onClick={() => saveRule(rule)}
                      disabled={!canEdit || savingKey === rule.rule_key}
                    >
                      {savingKey === rule.rule_key ? '保存中...' : '保存'}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
};

export default GovernanceRules;
