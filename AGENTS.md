# AGENTS.md — 项目工作区规则

> 本文件面向 AI 编码代理，描述项目架构、命令、约定与约束。README.md 提供更完整的产品级文档。

## 项目概述

RalphLoop MDM Governance — 物料主数据治理平台。全栈应用，前端为 React SPA，后端为 FastAPI REST API，覆盖物料申请、审批、金标数据、分类管理、治理规则、元数据治理与审计追踪等 MDM 核心流程。

主数据治理流程：新建申请 → 草稿 → 提交（自动执行质量校验 → 重复预检 → 编码生成）→ 部门审批 → 管理员审批 → 发布（创建金标数据 → BTP 发布 + OpenMetadata 同步）。金标数据支持修订、失效、回滚，每次变更在 `golden_record_versions` 保存不可变快照。

## 技术栈

- **前端**：React 19 + TypeScript + Vite 7 + Tailwind CSS 3.4 + shadcn/ui (new-york)
  - 路由：react-router-dom v7；表单：react-hook-form + zod；图表：recharts；图标：lucide-react；通知：sonner
- **后端**：Python 3.12 + FastAPI + SQLAlchemy 2.0 + Pydantic v2
  - 认证：JWT (python-jose + passlib/bcrypt)
  - 数据库：SQLite (开发默认) / PostgreSQL (生产)
  - 外部集成：OpenMetadata (可选)、BTP Mock (可选)
- **包管理**：前端必须使用 pnpm（原 npm 已迁移，`package-lock.json` 为残留，以 `pnpm-lock.yaml` 为准）；后端使用 uv + requirements.txt

## 目录结构

```
├── src/                        # 前端源码
│   ├── main.tsx               # 前端入口
│   ├── App.tsx                # 根组件 + 路由定义（10 条路由）
│   ├── pages/                 # 页面组件（Dashboard, Applications, GoldenRecords,
│   │                          #   Classifications, MetadataGovernance, GovernanceRules,
│   │                          #   AuditTrace, NewApplication, ApplicationDetail, Login；
│   │                          #   Home.tsx 存在但未挂载路由）
│   ├── components/            # Layout + shadcn/ui 组件库
│   │   └── ui/                # shadcn/ui 组件
│   ├── hooks/                 # 自定义 hooks
│   ├── lib/
│   │   ├── api.ts             # API 客户端 (fetch 封装, JWT, login/logout/upload/download)
│   │   └── utils.ts           # shadcn/ui cn() 工具函数
│   └── types/                 # 类型定义
├── backend/                    # Python 后端
│   ├── app/
│   │   ├── main.py            # FastAPI 入口（路由注册、CORS、SPA fallback）
│   │   ├── models.py          # SQLAlchemy 数据模型（10 张表，含 GovernanceRule、
│   │   │                      #   GoldenRecordVersion、PublishSyncTask、AuditLog 等）
│   │   ├── schemas.py         # Pydantic 请求/响应模型
│   │   ├── crud.py            # 数据库 CRUD 操作（含原子编码生成）
│   │   ├── api/               # 6 个 API 路由模块
│   │   │   ├── applications.py
│   │   │   ├── classifications.py
│   │   │   ├── dashboard.py
│   │   │   ├── golden_records.py
│   │   │   ├── governance_rules.py
│   │   │   └── metadata_governance.py
│   │   ├── core/              # 核心配置
│   │   │   ├── config.py      # 环境变量配置
│   │   │   ├── database.py    # 数据库连接
│   │   │   ├── auth.py        # JWT 认证（用户库为 MOCK_USERS 硬编码）
│   │   │   └── schema_compat.py
│   │   └── services/          # 6 个业务服务
│   │       ├── audit_service.py
│   │       ├── btp_mock.py
│   │       ├── code_generator.py
│   │       ├── duplicate_detector.py
│   │       ├── material_validator.py
│   │       └── openmetadata_sync.py
│   ├── init_db.py             # 数据库初始化 + 种子数据（路径基于脚本位置动态解析）
│   ├── requirements.txt       # Python 依赖（含 pytest、httpx）
│   ├── pytest.ini             # pytest 配置（testpaths=tests）
│   ├── .env.example           # 环境变量示例
│   └── tests/                 # 后端 pytest 测试（10 个文件，约 170+ 用例）
├── scripts/                    # Coze 平台脚本
│   ├── coze-preview-build.sh  # 预览构建 (pnpm install + uv pip + init_db)
│   ├── coze-preview-run.sh    # 预览运行 (后端:8000 + Vite:5000)
│   ├── coze-deploy-build.sh   # 部署构建 (pnpm build + uv pip + init_db)
│   └── coze-deploy-run.sh     # 部署运行 (uvicorn:5000 同时服务 API+SPA)
├── e2e_test.py                # E2E 端到端测试脚本（项目根目录，需后端在 :8000 运行）
├── docs/                      # knowledge-graph.md（代码资产图谱）、openmetadata-assessment.md
├── vite.config.ts             # Vite 配置 (dev port 3000, proxy /api -> :8000, @ -> ./src)
├── package.json               # 前端依赖与脚本
├── components.json            # shadcn/ui 配置
├── .github/workflows/ci.yml   # CI（前端 lint+tsc+build / 后端 pytest）
├── .coze                      # Coze 平台配置
└── info.md                    # 项目初始化信息
```

## 关键入口

- **前端入口**：`src/main.tsx` → `src/App.tsx`（路由定义）
- **前端 API 客户端**：`src/lib/api.ts` — 封装 fetch + JWT，导出 `api`/`login`/`getUser`/`logout`/`upload`/`downloadFile`
- **后端入口**：`backend/app/main.py` — FastAPI app，注册 6 个 router，含 SPA fallback（`dist/` 存在时非 API 路由返回 `dist/index.html`）
- **后端配置**：`backend/app/core/config.py` — 环境变量驱动；`OM_ENABLED`/`BTP_ENABLED` **默认 false**，`ENV` 默认 `development`
- **数据库初始化**：`backend/init_db.py` — 建表 + 种子数据

## 构建与运行命令

### 前端（项目根目录）
```bash
pnpm install
pnpm dev          # 开发服务器 http://localhost:3000（/api 代理至 :8000）
pnpm build        # 构建到 dist/
pnpm lint         # eslint
npx tsc --noEmit  # 类型检查
```

### 后端
```bash
cd backend
uv pip install --system -r requirements.txt
python init_db.py                                # 初始化数据库 (SQLite)
python -m uvicorn app.main:app --reload --port 8000   # API 文档: http://localhost:8000/docs
```

### 测试
```bash
cd backend
python -m pytest                    # 全部测试（约 170+ 用例）
python -m pytest tests/test_auth.py # 单文件
# pytest.ini 将 app.* 的 DeprecationWarning 视为 error
```
E2E 测试（需后端已在 :8000 运行）：
```bash
python e2e_test.py   # 在项目根目录执行
```

### CI
`.github/workflows/ci.yml` 两个 job：
- `check`（前端）：`pnpm install --frozen-lockfile` → `pnpm lint` → `tsc --noEmit` → `pnpm build`（Node 20 + pnpm 9）
- `backend-tests`：Python 3.12，`pytest tests/ -q`，环境变量 `ENV=test`、`SQLALCHEMY_DATABASE_URL=sqlite:///:memory:`、`OM_ENABLED=false`、`BTP_ENABLED=false`

## 预览与部署（Coze 平台）

- **预览**：Vite dev server (port 5000) + FastAPI (port 8000 内部)，Vite proxy 转发 `/api`。预览端口固定 5000，**禁止使用 9000 端口**。脚本：`coze-preview-build.sh` → `coze-preview-run.sh`
- **部署**：uvicorn (port 5000) 同时服务 API 和 SPA 静态文件 (dist/)。脚本：`coze-deploy-build.sh` → `coze-deploy-run.sh`（`ENV=production`）
- 预览/部署脚本中 `OM_ENABLED` 和 `BTP_ENABLED` 显式设为 `false`
- JWT 密钥：生产模式必须提供 `MDM_SECRET_KEY`（未设置时启动 fail-fast）；deploy-run.sh 会优先生成并持久化到 `backend/.mdm_secret_key`（600 权限，已 gitignore）

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SQLALCHEMY_DATABASE_URL` | `sqlite:///./mdm_governance.db` | 数据库连接（生产用 PostgreSQL） |
| `MDM_SECRET_KEY` | — | **生产必填**，JWT 签名密钥，缺失 fail-fast |
| `ENV` | `development` | `development` / `production` / `test` |
| `OM_ENABLED` / `BTP_ENABLED` | `false` | OpenMetadata / BTP Mock 开关（config.py 默认即为 false） |
| `OPENMETADATA_HOST` / `OPENMETADATA_TOKEN` | — | OM API 地址与 Token |
| `BTP_MOCK_URL` | — | BTP Mock 地址 |

## 登录凭据

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | `admin001` | `adminpass001` |
| 普通用户 | `user001` | `password001` |
| 部门审批 | `dept001` | `deptpass001` |
| 数据管理员 | `data001` | `datapass001` |

## 代码风格与约定

- 前端：TypeScript + eslint 9（`pnpm lint` 已加入 CI，必须零错误）；shadcn/ui 目录关闭了 `react-refresh/only-export-components`（variants 同文件导出是 shadcn 既定模式），carousel/sidebar 两处上游写法使用行内豁免
- 前端导入别名：`@` 指向 `./src`
- 后端：SQLAlchemy 2.0 + Pydantic v2；业务逻辑分层为 api（路由）→ services（业务服务）→ crud（数据访问）
- 提交申请时自动执行链：`MaterialValidator`（质量校验）→ `DuplicateDetector`（重复预检）→ `CodeGenerator`（编码生成）

## 安全约束（不可违反）

- **认证**：所有 API 必须携带有效 JWT（无免认证回退）；`get_current_user` 不允许任何无 token 放行
- **附件**：上传拒绝 HTML/SVG/JS 等可执行类型，单文件 ≤ 10MB；下载一律 `application/octet-stream` + `Content-Disposition: attachment`（防存储型 XSS）
- **编码生成**：`crud.increment_seq` 使用单语句 `UPDATE...RETURNING` 保证原子性，**禁止**拆成 UPDATE + 独立 SELECT（会产生重复编码）
- **密钥**：生产环境 `MDM_SECRET_KEY` 独立环境变量，禁止硬编码

## 长期约束

- 前端包管理器必须使用 pnpm；后端 Python 环境必须使用 uv 管理
- 预览端口固定 5000，禁止 9000
- 数据库默认 SQLite（开发），生产 PostgreSQL
- 预览环境使用系统 Python 而非 venv（沙箱中 uv venv 下载超时），生产环境应使用 venv
- CORS 在 DEBUG 模式下允许 localhost:3000 和 localhost:8000

## 已知问题与历史教训

- `package-lock.json` 为 npm 残留，勿使用 npm
- 后端 SPA fallback 仅在 `dist/` 存在时生效，开发模式下前端独立运行
- **2026-07 安全修复**：生产部署曾用 `ENV=development` 导致免认证回退生效 + JWT 密钥硬编码可伪造，已修复（ENV=production、删除回退、MDM_SECRET_KEY 独立环境变量）
- `auth.py` 用户库仍是 MOCK_USERS 硬编码，中期应迁入数据库
- 发布同步任务（`publish_sync_tasks`）已实现持久化、超时标记和人工重新入队；后台 worker、指数退避、死信队列仍属后续工作
