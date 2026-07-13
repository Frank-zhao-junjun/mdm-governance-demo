# MDM Governance 构建修复与工程基线实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐前端缺失的基础库文件（`src/lib/api.ts`、`src/lib/utils.ts`），修复项目构建阻塞；同步完善后端默认配置与项目文档，使整个应用能在本地和 Coze 预览/部署环境中可构建、可运行、可测试。

**Architecture:** 保持现有前后端分离架构不变，仅补充前端公共库与工程化配置；后端调整环境变量默认值以符合开发和预览场景；通过 `pnpm build` 和 `pytest` 作为最终验收闸门。

**Tech Stack:** React 19 + TypeScript + Vite 7 + Tailwind CSS 3.4 + shadcn/ui (new-york), FastAPI + SQLAlchemy 2.0 + Pydantic v2 + uv/pnpm.

## Global Constraints

- 前端包管理器必须使用 pnpm；禁止生成/修改 `package-lock.json`。
- 后端 Python 环境使用 uv 管理依赖。
- 预览端口固定为 5000，禁止使用 9000 端口。
- 开发环境默认使用 SQLite：`SQLALCHEMY_DATABASE_URL=sqlite:///./mdm_governance.db`。
- OpenMetadata 和 BTP Mock 默认关闭：`OM_ENABLED=false`、`BTP_ENABLED=false`。
- 所有代码变更必须遵循现有代码风格；后端 API 路由前缀保持 `/api`。
- 每个任务提交一次 commit；最终必须通过 `pnpm build` 和 `pytest`。

---

### Task 1: 创建 `src/lib/utils.ts`（shadcn/ui 基础工具）

**Files:**
- Create: `src/lib/utils.ts`
- Test: 通过 `pnpm build` 间接验证

**Interfaces:**
- Produces: `cn(...inputs: ClassValue[]): string` —— 合并 Tailwind 类名，供所有 shadcn/ui 组件使用。

- [ ] **Step 1: 写入 `cn` 工具函数**

```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 2: 验证 shadcn/ui 组件可解析**

Run: `pnpm exec tsc -b --noEmit`
Expected: 不再出现 `Cannot find module '@/lib/utils'` 相关错误（仍可能有 `api.ts` 缺失错误，下一任务修复）。

- [ ] **Step 3: Commit**

```bash
git add src/lib/utils.ts
git commit -m "feat: add shadcn/ui cn() utility in src/lib/utils.ts"
```

---

### Task 2: 创建 `src/lib/api.ts`（前端 API 客户端）

**Files:**
- Create: `src/lib/api.ts`
- Modify: `src/types/api.ts`（如有缺失字段）
- Test: 通过 `pnpm build` 和浏览器登录流程间接验证

**Interfaces:**
- Consumes: `User` interface from `@/types/api`; `toast` from `sonner`.
- Produces:
  - `api<T>(path: string, options?: RequestInit): Promise<T>`
  - `login(userId: string, password: string): Promise<User>`
  - `logout(): void`
  - `getUser(): User | null`
  - `upload<T>(path: string, body: FormData): Promise<T>`
  - `downloadFile(path: string, filename: string): Promise<void>`

- [ ] **Step 1: 写入 API 客户端**

```typescript
import { toast } from 'sonner';
import type { User } from '@/types/api';

const API_BASE = '';

const TOKEN_KEY = 'mdm_token';
const USER_KEY = 'mdm_user';

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

function setAuth(token: string, user: User) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.location.href = '/login';
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };

  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    logout();
    throw new Error('登录已过期，请重新登录');
  }

  let data: any;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const message = data?.detail || data?.message || data || `请求失败: ${response.status}`;
    toast.error(String(message));
    throw new Error(String(message));
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
    const message = data?.detail || data?.message || `上传失败: ${response.status}`;
    toast.error(String(message));
    throw new Error(String(message));
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
    throw new Error(`下载失败: ${response.status}`);
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
```

- [ ] **Step 2: 运行 TypeScript 编译检查**

Run: `pnpm exec tsc -b --noEmit`
Expected: 无 `Cannot find module '@/lib/api'` 或 `@/lib/utils` 错误。

- [ ] **Step 3: 运行前端构建**

Run: `pnpm build`
Expected: 构建成功，生成 `dist/` 目录。

- [ ] **Step 4: Commit**

```bash
git add src/lib/api.ts
git commit -m "feat: add frontend API client with JWT, login, upload and download"
```

---

### Task 3: 修复后端默认环境变量

**Files:**
- Modify: `backend/app/core/config.py`
- Test: `pytest backend/tests/test_api.py -v`

**Interfaces:**
- Produces: `settings.DATABASE_URL` 默认 SQLite；`settings.OM_ENABLED` 和 `settings.BTP_ENABLED` 默认 `false`。

- [ ] **Step 1: 修改默认值**

将 `backend/app/core/config.py` 中相关行改为：

```python
# Database
DATABASE_URL: str = os.getenv("SQLALCHEMY_DATABASE_URL", "sqlite:///./mdm_governance.db")

# OpenMetadata
OM_ENABLED: bool = os.getenv("OM_ENABLED", "false").lower() == "true"

# BTP Mock
BTP_ENABLED: bool = os.getenv("BTP_ENABLED", "false").lower() == "true"
```

- [ ] **Step 2: 验证后端测试仍通过**

Run: `cd backend && pytest tests/test_api.py -v`
Expected: 全部通过。

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/config.py
git commit -m "fix: default OM/BTP to false and SQLite as default dev database"
```

---

### Task 4: 重写 `README.md`

**Files:**
- Modify: `README.md`
- Test: 无代码测试，人工检查即可

**Interfaces:**
- Produces: 项目级说明文档，包含简介、技术栈、目录、运行、测试、登录凭据、注意事项。

- [ ] **Step 1: 写入新 README**

```markdown
# RalphLoop MDM Governance — 物料主数据治理平台

制造业物料主数据治理平台，覆盖物料申请、审批、Golden Record 生成、分类管理、元数据治理与审计追踪。

## 技术栈

- **前端**: React 19 + TypeScript + Vite 7 + Tailwind CSS 3.4 + shadcn/ui
- **后端**: Python 3.12 + FastAPI + SQLAlchemy 2.0 + Pydantic v2
- **认证**: JWT (python-jose + passlib/bcrypt)
- **数据库**: PostgreSQL（生产）/ SQLite（开发默认）

## 目录结构

```
src/                  # 前端源码
backend/app/          # FastAPI 后端
backend/tests/        # 后端测试
scripts/              # Coze 预览/部署脚本
```

## 本地运行

### 前端

```bash
pnpm install
pnpm dev          # http://localhost:3000
```

### 后端

```bash
cd backend
uv pip install --system -r requirements.txt
python3 init_db.py
python3 -m uvicorn app.main:app --reload --port 8000
```

## 测试

```bash
# 后端单元/集成测试
cd backend
pytest

# 端到端测试（需前后端均已启动）
python3 e2e_test.py
```

## 登录凭据

- 管理员: `admin001` / `adminpass001`
- 普通用户: `user001` / `password001`
- 部门审批: `dept001` / `deptpass001`
- 数据管理员: `data001` / `datapass001`

## Coze 预览/部署

- 预览: `bash scripts/coze-preview-build.sh && bash scripts/coze-preview-run.sh`
- 部署: `bash scripts/coze-deploy-build.sh && bash scripts/coze-deploy-run.sh`

## 注意事项

- 前端包管理使用 pnpm，已迁移至 `pnpm-lock.yaml`，`package-lock.json` 为残留文件。
- 预览环境使用端口 5000，禁止使用 9000。
- OpenMetadata 与 BTP Mock 默认关闭。
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README with project overview and run instructions"
```

---

### Task 5: 验证前后端构建与测试

**Files:**
- 间接验证所有已修改/新增文件
- 可能需要修复：构建或测试过程中暴露出的路径/类型问题

**Interfaces:**
- Consumes: Task 1-4 的所有产物。
- Produces: `dist/` 构建产物；测试通过报告。

- [ ] **Step 1: 安装前端依赖**

Run: `pnpm install`
Expected: 成功生成 `node_modules/` 并更新 `pnpm-lock.yaml`（如无变化则不变）。

- [ ] **Step 2: 前端构建**

Run: `pnpm build`
Expected: 输出 `dist/index.html`、`dist/assets/` 等，无 TypeScript/构建错误。

- [ ] **Step 3: 后端依赖安装**

Run: `cd backend && uv pip install --system -r requirements.txt`
Expected: 成功安装依赖。

- [ ] **Step 4: 初始化数据库**

Run: `cd backend && python3 init_db.py`
Expected: 输出 `✅ Database initialized with seed data`。

- [ ] **Step 5: 运行后端测试**

Run: `cd backend && pytest -v`
Expected: 全部通过（当前已有 60+ 测试）。

- [ ] **Step 6: Commit（如仅有验证无修复则跳过）**

若验证过程中有修复，单独提交：

```bash
git add <fixed-files>
git commit -m "fix: resolve build/test issues from baseline verification"
```

---

### Task 6: 清理未跟踪的 tar.gz 并更新 `.gitignore`

**Files:**
- Modify: `.gitignore`
- 删除（可选）: `project_20260712_224859.tar.gz`
- Test: `git status --short`

**Interfaces:**
- Produces: 干净的 git 状态；忽略规则覆盖常见的构建产物和备份文件。

- [ ] **Step 1: 检查未跟踪文件**

Run: `git status --short`
Expected: 看到 `?? project_20260712_224859.tar.gz`。

- [ ] **Step 2: 更新 `.gitignore`**

在 `.gitignore` 末尾追加：

```gitignore
# Project backups
*.tar.gz
*.zip

# Local data
data/
backend/mdm_governance.db
backend/uploads/
```

- [ ] **Step 3: 删除临时 tar.gz（用户已授权清理工作区）**

Run: `rm project_20260712_224859.tar.gz`
Expected: 文件被移除。

- [ ] **Step 4: 验证 git 状态**

Run: `git status --short`
Expected: 仅显示已跟踪的修改，无多余的 `??` 文件。

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore local backups, data files and uploads"
```

---

## Self-Review

**Spec coverage:**
- 方案 1（补齐基础依赖）→ Task 1、Task 2、Task 5
- 方案 3（工程化与文档）→ Task 3、Task 4、Task 6

**Placeholder scan:**
- 无 "TBD"、"TODO"、"implement later"。
- 每个代码步骤都包含完整代码。
- 每个命令都包含预期输出。

**Type consistency:**
- `api<T>`、`upload<T>`、`downloadFile` 签名与 `src/pages/*` 中的调用一致。
- `cn` 签名与 shadcn/ui 组件一致。

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-13-mdm-build-and-engineering-baseline.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
