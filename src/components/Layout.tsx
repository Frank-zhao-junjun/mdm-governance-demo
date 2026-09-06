import React, { useState } from 'react';
import { Link, useLocation, Outlet, Navigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Database,
  ListChecks,
  ShieldCheck,
  AlertTriangle,
  Bot,
  Scale,
  BookMarked,
  LogOut,
  Menu,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getUser, logout } from '@/lib/api';
import { ROLE_LABELS } from '@/lib/governance';

interface NavItem {
  path: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

// SPEC §6.1 页面结构：/quality/standards · /quality/checks · /quality/checks/report · /quality/suspected
const NAV_ITEMS: NavItem[] = [
  { path: '/dashboard', label: '仪表盘', icon: LayoutDashboard },
  { path: '/quality/standards', label: '数据标准管理', icon: ListChecks },
  { path: '/metadata', label: '元数据管理', icon: BookMarked },
  { path: '/governance', label: '治理驾驶舱', icon: LayoutDashboard },
  { path: '/copilot', label: 'Copilot 裁决', icon: Scale },
  { path: '/disputes', label: '权责冲突', icon: AlertTriangle },
  { path: '/quality/checks', label: '质量检测', icon: ShieldCheck },
  { path: '/quality/suspected', label: '疑似错误', icon: AlertTriangle },
  { path: '/agents', label: 'Agent 活动流', icon: Bot },
];

function resolveTitle(pathname: string): string {
  const matched = NAV_ITEMS.filter((item) => pathname.startsWith(item.path)).sort(
    (a, b) => b.path.length - a.path.length,
  )[0];
  return matched?.label ?? '仪表盘';
}

const Layout: React.FC = () => {
  const location = useLocation();
  const user = getUser();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* 移动端遮罩 */}
      {mobileNavOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      {/* Sidebar：移动端抽屉式，桌面端固定 */}
      <aside
        className={`w-64 bg-slate-900 text-white flex flex-col fixed inset-y-0 left-0 z-40 transform transition-transform duration-200 md:static md:translate-x-0 ${
          mobileNavOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="p-6">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center">
              <Database className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-lg font-bold">MDM</h1>
              <p className="text-xs text-gray-400">AI数据治理</p>
            </div>
          </div>

          <nav className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname.startsWith(item.path);

              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileNavOpen(false)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="mt-auto p-4 border-t border-slate-800">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 bg-gray-600 rounded-full flex items-center justify-center text-sm">
              {user.name?.[0] || '?'}
            </div>
            <div>
              <p className="text-sm font-medium">{user.name}</p>
              <p className="text-xs text-gray-400">
                {user.department} · {ROLE_LABELS[user.role] ?? user.role}
              </p>
            </div>
          </div>
          <Button variant="ghost" size="sm" className="w-full text-gray-400 hover:text-white" onClick={logout}>
            <LogOut className="w-4 h-4 mr-2" />
            退出登录
          </Button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <header className="bg-white border-b border-gray-200 px-4 py-4 md:px-6 flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden shrink-0"
              aria-label="打开导航菜单"
              onClick={() => setMobileNavOpen(true)}
            >
              <Menu className="w-5 h-5" />
            </Button>
            <h2 className="text-lg md:text-xl font-semibold text-gray-800 truncate">
              {resolveTitle(location.pathname)}
            </h2>
          </div>
          <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm shrink-0">
            系统正常
          </span>
        </header>
        <main className="p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};


export default Layout;
