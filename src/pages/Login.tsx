import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogIn, Database } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { login } from '@/lib/api';

const Login: React.FC = () => {
  const navigate = useNavigate();
  const [userId, setUserId] = useState('user001');
  const [password, setPassword] = useState('password001');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setLoading(true);
    try {
      await login(userId, password);
      toast.success('登录成功');
      navigate('/dashboard');
    } catch (err: any) {
      toast.error('登录失败: ' + (err.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <Card className="w-96">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center">
              <Database className="w-7 h-7 text-white" />
            </div>
          </div>
          <CardTitle className="text-xl">制造业数据治理平台</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>用户ID</Label>
            <Input
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="user001"
            />
          </div>
          <div className="space-y-2">
            <Label>密码</Label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="password001"
            />
          </div>
          <Button 
            className="w-full bg-blue-600 hover:bg-blue-700" 
            onClick={handleLogin}
            disabled={loading}
          >
            <LogIn className="w-4 h-4 mr-2" />
            {loading ? '登录中...' : '登录'}
          </Button>
          <div className="text-xs text-gray-400 text-center space-y-1">
            <p>测试账号: user001 / password001 (申请人)</p>
            <p>admin001 / adminpass001 (管理员)</p>
            <p>dept001 / deptpass001 (部门审批)</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Login;