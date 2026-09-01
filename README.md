# 制造业数据治理平台

> **服务边界**：本项目聚焦于数据治理与数据质量管理，提供标准、规则、观测、治理闭环和质量管理能力；不承接新增数据流程、审批流程、Golden Data 管理和分发执行。
> **技术栈**: React 19 + FastAPI + SQLite/PostgreSQL | **版本**: v1.0.0

---

## 快速导航

| 入口 | 说明 |
|------|------|
| 知识图谱 | [`docs/knowledge-graph.md`](./docs/knowledge-graph.md) — 完整代码资产映射（文件级） |
| 后端 API | `backend/app/` — FastAPI 路由、数据模型、业务服务 |
| 前端 SPA | `src/` — React 页面、组件、类型定义 |
| 测试 | `backend/tests/` — 153 个 pytest 集成 + 单元测试 |
| Coze 部署 | `scripts/` — 预览/部署 Shell 脚本 |
| 项目规范 | [`AGENTS.md`](./AGENTS.md) — 技术栈、目录结构、安全约束、长期记忆 |

---

## 快速启动

### 前置条件

- **Node.js** 20+（前端）
- **pnpm**（前端包管理器）
- **Python** 3.12+（后端）
- **uv**（Python 包管理器）

### 前端
```bash
pnpm install
pnpm dev          # 开发服务器 → http://localhost:3000
pnpm build        # 构建到 dist/
```

### 后端

```bash
cd backend
uv pip install --system -r requirements.txt   # 安装依赖
python init_db.py                              # 初始化数据库+种子数据
uvicorn app.main:app --reload --port 8000      # 启动 API → http://localhost:8000/docs
```

### 访问入口

| 入口 | URL |
|------|-----|
| 前端 SPA | `http://localhost:3000` |
| API 文档 (Swagger) | `http://localhost:8000/docs` |
| API 文档 (ReDoc) | `http://localhost:8000/redoc` |
| 健康检查 | `http://localhost:8000/api/health` |

---

## 登录凭据

| 角色 | 用户名 | 密码 | 部门 |
|------|--------|------|------|
| 管理员 | `admin001` | `adminpass001` | IT部 |
| 申请人 | `user001` | `password001` | 研发部 |
| 申请人 | `user002` | `password002` | 采购部 |
| 部门审批 | `dept001` | `deptpass001` | 生产部 |
| 数据管理员 | `data001` | `datapass001` | 数据治理部 |

---

## 系统架构

```
┌────────────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + Vite 7 + Tailwind)                           │
│  ┌─────────┐ ┌─────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │ 登录    │ │ 仪表盘  │ │ 物料申请    │ │ GR 管理     │          │
│  │ Login   │ │ Dashboard│ │ Applications│ │ Golden      │          │
│  └─────────┘ └─────────┘ └─────────────┘ └─────────────┘          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│  │ 元数据治理  │ │ 分类管理    │ │ 审计追踪    │ │ 新建申请    │  │
│  │ Metadata    │ │ Classify    │ │ AuditTrace  │ │ NewApp      │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
│                        proxy /api → :8000                          │
└────────────────────────────────────────────────────────────────────┘
                              │
┌────────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI + SQLAlchemy + JWT)                              │
│  ┌──────────────┐ ┌──────────────────┐ ┌──────────────┐           │
│  │ API 路由     │ │ 业务服务         │ │ 数据模型     │           │
│  │ 5 routers    │ │ 6 services       │ │ 7 tables     │           │
│  └──────────────┘ └──────────────────┘ └──────────────┘           │
└────────────────────────────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 职责 |
|------|------|
| 物料申请 (Applications) | 申请创建、编辑、提交、审批、发布 |
| 金标数据 (金标数据s) | 权威主数据卡片、版本、BTP/OM 状态 |
| 分类管理 (Classifications) | 三级物料分类树 + 属性模板 |
| 元数据治理 (Metadata Governance) | 元数据目录、血缘、质量测试、审计轨迹 |
| 审计追踪 (Audit Trace) | 全生命周期操作日志与时间线 |

---

## 服务范围与治理边界

本平台仅提供数据治理与数据质量管理服务，不承接以下执行型流程：

- 新增数据申请与数据落库
- 审批流执行
- Golden Data（金标数据）创建与发布
- 下游系统分发与同步执行

我们关注的核心能力是：治理规则、质量校验、重复识别、问题发现、审计追踪，以及治理结果的可视化与闭环管理。

> 业务侧的新增、审批、金标数据、分发等动作，由客户自身系统或专门的执行层负责，不走本平台。

## 主数据治理流程

```
治理规则定义 → 质量校验 → 重复识别 → 问题治理 → 审计追踪
```

### 提交自动执行链

1. **质量校验** (`MaterialValidator`) — 必填字段/名称长度/分类/属性模板
2. **重复预检** (`DuplicateDetector`) — ILIKE + 前缀模糊 + 关键词重罚
3. **编码生成** (`CodeGenerator`) — 编码规则 + 原子序列递增（`UPDATE...RETURNING` 单语句保证并发安全）

### 发布流程

1. **创建 金标数据** — 成为权威主数据
2. **BTP 发布** — Mock SAP BTP 发布
3. **OpenMetadata 同步** — 元数据目录 + 质量测试

### 金标数据 生命周期

每次初始发布、修订、失效和回滚都会在 `golden_record_versions` 保存不可变快照，并记录父版本、变更原因、操作人和时间。

| 流程 | 状态变化 | API |
|------|----------|-----|
| 修订 | 当前生效 → 待审批 → 已批准 → 已发布（新版本） | `POST /api/golden-records/{id}/revisions`，以及版本 `approve`、`publish` |
| 失效 | 当前生效 → 失效审批 → 已失效 | `POST /api/golden-records/{id}/invalidation`，以及 `invalidation-approve` |
| 回滚 | 已发布 → 生成新的回滚版本，恢复上一版本数据 | `POST /api/golden-records/{id}/rollback` |
| 版本历史 | 查询全部快照 | `GET /api/golden-records/{id}/versions` |

申请发布使用 `PUBLISHING` 临时状态和数据库条件更新进行原子占位。BTP 和 OpenMetadata 分别记录在 `publish_sync_tasks` 中，失败任务可以超时扫描并由管理员重新置为 `pending`。

管理员任务接口：

- `GET /api/publish-sync-tasks`
- `POST /api/publish-sync-tasks/recover-timeouts?timeout_minutes=15`
- `POST /api/publish-sync-tasks/{task_id}/retry`

当前已完成任务持久化、超时标记和人工重新入队；后台 worker、指数退避、死信队列以及真实外部系统幂等重试仍属于后续生产化工作。

---

## 安全特性

| 能力 | 说明 |
|------|------|
| JWT 认证 | 所有 API 必须携带有效 JWT，无免认证回退 |
| 密钥管理 | 生产环境强制 `MDM_SECRET_KEY` 环境变量，缺失即 fail-fast |
| 附件上传 | 类型黑名单（HTML/SVG/JS 等可执行类型）+ 10MB 流式大小限制 |
| 附件下载 | 强制 `application/octet-stream` + `Content-Disposition: attachment`，防存储型 XSS |
| 编码并发 | `increment_seq` 使用单语句 `UPDATE...RETURNING`，消除重复编码竞态 |

---

## 测试

```bash
cd backend
pytest                          # 运行全部 153 个测试
pytest -v                       # 详细输出
pytest tests/test_auth.py       # 仅认证测试
pytest tests/test_api.py        # API 集成测试
```

### E2E 测试

```bash
cd backend
python e2e_test.py              # 端到端流程验证（需后端运行中）
```

---

## CI/CD

GitHub Actions 工作流（`.github/workflows/ci.yml`）包含两个 job：

| Job | 内容 |
|-----|------|
| `frontend-check` | `pnpm lint` (eslint) + `tsc --noEmit` + `pnpm build` |
| `backend-tests` | Python 3.12 + `pytest`（`ENV=test`，SQLite in-memory） |

---

## 预览与部署（Coze 平台）

### 预览（开发模式）

```
Vite dev server (:5000)  ──proxy /api──▶  FastAPI (:8000)
```

- 构建：`scripts/coze-preview-build.sh`（pnpm install + uv pip + init_db）
- 运行：`scripts/coze-preview-run.sh`（后端 :8000 + Vite :5000）

### 部署（生产模式）

```
FastAPI/uvicorn (:5000)  ── 同时服务 API + SPA 静态文件 (dist/)
```

- 构建：`scripts/coze-deploy-build.sh`（pnpm build + uv pip + init_db）
- 运行：`scripts/coze-deploy-run.sh`（`ENV=production`，自动生成 JWT 密钥）

> 预览/部署脚本中 `OM_ENABLED` 和 `BTP_ENABLED` 显式设为 `false`。

---

## 项目结构速览

```
├── src/                        # 前端 SPA (React 19 + TypeScript)
│   ├── App.tsx                 #   路由定义（9 页面）
│   ├── main.tsx                #   React 入口
│   ├── pages/                  #   页面组件
│   ├── components/             #   Layout + shadcn/ui 组件库
│   ├── hooks/                  #   自定义 hooks
│   ├── types/api.ts            #   TypeScript 类型定义
│   └── lib/                    #   工具库（api.ts API 客户端 + utils.ts）
├── backend/                    # 后端 API (Python 3.12 + FastAPI)
│   ├── app/
│   │   ├── main.py             #   FastAPI 入口 + 路由注册 + SPA fallback
│   │   ├── models.py           #   SQLAlchemy 数据模型（7 表）
│   │   ├── schemas.py          #   Pydantic 请求/响应模型
│   │   ├── crud.py             #   CRUD 操作（含原子编码生成）
│   │   ├── api/                #   5 个 API 路由模块
│   │   ├── core/               #   配置/数据库/认证
│   │   └── services/           #   6 个业务服务
│   ├── init_db.py              #   数据库初始化 + 种子数据
│   ├── requirements.txt        #   Python 依赖
│   └── tests/                  #   153 个 pytest 测试
├── scripts/                    #   Coze 平台构建/部署脚本
├── docs/
│   └── knowledge-graph.md      #   完整代码资产图谱
├── e2e_test.py                 #   E2E 端到端测试脚本
├── AGENTS.md                   #   项目工作区规则
├── README.md                   #   本文件：项目入口
├── info.md                     #   项目初始化信息
├── .coze                       #   Coze 平台配置
├── vite.config.ts              #   Vite 构建/代理配置
├── package.json                #   前端依赖（pnpm）
├── pnpm-lock.yaml              #   pnpm 锁文件
├── components.json             #   shadcn/ui 配置
├── tailwind.config.js          #   Tailwind CSS 配置
└── tsconfig.json               #   TypeScript 根配置
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SQLALCHEMY_DATABASE_URL` | `sqlite:///./mdm_governance.db` | 数据库连接（生产使用 PostgreSQL） |
| `MDM_SECRET_KEY` | — | **生产环境必填**。JWT 签名密钥，缺失时启动 fail-fast |
| `ENV` | `development` | 运行环境：`development` / `production` / `test` |
| `OPENMETADATA_HOST` | `http://localhost:8585/api` | OpenMetadata API 地址 |
| `OPENMETADATA_TOKEN` | `""` | OM 认证 Token |
| `OM_ENABLED` | `true` | OpenMetadata 开关 |
| `BTP_MOCK_URL` | `http://localhost:8888` | BTP Mock 地址 |
| `BTP_ENABLED` | `true` | BTP 开关 |

> 预览/部署脚本中会将 `OM_ENABLED` 和 `BTP_ENABLED` 显式设为 `false`。

---

## 技术栈一览

| 前端 | 后端 | 工具 |
|------|------|------|
| React 19 + TypeScript | Python 3.12 + FastAPI | Vite 7 |
| shadcn/ui (new-york) | SQLAlchemy 2.0 + Pydantic v2 | pnpm / uv |
| Tailwind CSS 3.4 | JWT (python-jose) + bcrypt | pytest |
| react-router-dom v7 | SQLite / PostgreSQL | GitHub Actions |
| recharts | uvicorn | Coze 平台 |
| sonner (Toast) | requests + httpx | Git |

---

## 待办

- [ ] 用户库 `MOCK_USERS` 迁入数据库（当前硬编码于 `auth.py`）
- [ ] 后台 worker、指数退避和死信队列
- [ ] 统一领域状态机，收敛 API 路由中的状态判断
- [ ] 生产环境 PostgreSQL 迁移脚本
- [ ] OpenMetadata 真实接入验证
- [ ] Docker 部署配置
- [x] ~~前端 17 个预存 eslint 错误~~ 已修复，`pnpm lint` 已加入 CI
