import { toast } from 'sonner';
import type { User, UserRole } from '@/types/api';

const API_BASE = '';

const TOKEN_KEY = 'mdm_token';
const USER_KEY = 'mdm_user';

/** 仅数据管理员 / 管理员可写（SPEC §3.0 权限矩阵，后端 require_admin） */
const WRITE_ROLES: UserRole[] = ['admin', 'data_admin'];

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): User | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

/** 当前登录用户是否具备写权限（用于按钮显隐，避免前端发起必然 403 的请求） */
export function canWrite(): boolean {
  const user = getUser();
  return !!user && WRITE_ROLES.includes(user.role);
}

function setAuth(token: string, user: User) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.location.href = '/login';
}

export interface ApiRequestOptions extends RequestInit {
  /** 出错时不弹全局 toast，由调用方在表单内联展示（HTTP 错误信息仍随 Error.message 抛出） */
  silentError?: boolean;
}

interface FastapiValidationItem {
  loc?: (string | number)[];
  msg?: string;
}

/** 从 FastAPI 响应体中取出可展示的中文/文本错误信息（含 422 校验数组） */
export function extractErrorMessage(body: unknown, status: number): string {
  const fallback = `请求失败: ${status}`;
  if (typeof body === 'string' && body.trim()) return body;
  if (body && typeof body === 'object') {
    const obj = body as Record<string, unknown>;
    const detail = obj.detail ?? obj.message;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length) {
      const parts = (detail as FastapiValidationItem[])
        .map((item) => {
          if (typeof item === 'string') return item;
          const field = Array.isArray(item?.loc)
            ? item.loc.filter((seg) => seg !== 'body').join('.')
            : '';
          const msg = typeof item?.msg === 'string' ? item.msg : '';
          return field ? `${field}: ${msg}` : msg;
        })
        .filter(Boolean);
      if (parts.length) return parts.join('；');
    }
    if (detail && typeof detail === 'object') return JSON.stringify(detail);
  }
  return fallback;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function api<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { silentError, ...init } = options;
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init.headers as Record<string, string>) || {}),
  };

  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...init,
    headers,
  });

  if (response.status === 401) {
    logout();
    throw new ApiError('登录已过期，请重新登录', 401);
  }

  let data: unknown;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    data = await response.json().catch(() => null);
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const message = extractErrorMessage(data, response.status);
    if (!silentError) {
      toast.error(message);
    }
    throw new ApiError(message, response.status);
  }

  return data as T;
}

export async function login(userId: string, password: string): Promise<User> {
  const data = await api<{ access_token: string; token_type: string; user: User }>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, password }),
  });
  setAuth(data.access_token, data.user);
  return data.user;
}

export async function upload<T>(path: string, body: FormData): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    body,
    headers,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message = extractErrorMessage(data, response.status);
    toast.error(message);
    throw new ApiError(message, response.status);
  }

  return data as T;
}

export async function downloadFile(path: string, filename: string) {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, { headers });
  if (!response.ok) {
    toast.error('文件下载失败');
    throw new ApiError(`下载失败: ${response.status}`, response.status);
  }

  const blob = await response.blob();
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}
