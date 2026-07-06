## 项目概述

RalphLoop MDM Governance — 物料主数据治理平台。全栈应用，前端为 React SPA，后端为 FastAPI REST API，覆盖物料申请、审批、金标数据、分类管理、元数据治理与审计追踪等 MDM 核心流程。

## 技术栈

- **前端**：React 19 + TypeScript + Vite 7 + Tailwind CSS 3.4 + shadcn/ui (new-york)
  - 路由：react-router-dom v7
  - 表单：react-hook-form + zod
  - 图表：recharts
  - 图标：lucide-react
  - 通知：sonner
- **后端**：Python 3.12 + FastAPI + SQLAlchemy 2.0 + Pydantic v2
  - 认证：JWT (python-jose + passlib/bcrypt)
  - 数据库：PostgreSQL (生产) / SQLite (开发默认)
  - 外部集成：OpenMetadata (可选)、BTP Mock (可选)
- **包管理**：前端使用 pnpm（原项目为 npm，已迁移）；后端使用 uv + requirements.txt

## 目录结构

```
/workspace/projects/           # 工作区根 = 技术项目根
├── src/                        # 前端源码
│   ├── main.tsx               # 前端入口
│   ├── App.tsx                # 根组件 + 路由定义
│   ├── pages/                 # 页面组件 (Dashboard, Applications, Login 等)
│   ├── components/            # Layout + shadcn/ui 组件库
│   │   └── ui/                # shadcn/ui 组件
│   ├── hooks/                 # 自定义 hooks
│   ├── lib/                   # 工具库
│   │   ├── api.ts             # API 客户端 (fetch 封装, JWT, login/logout/upload/download)
│   │   └── utils.ts           # shadcn/ui cn() 工具函数
│   ├── types/                 # 类型定义
│   ├── index.css              # 全局样式 (Tailwind)
│   └── App.css                # 应用级样式
├── backend/                    # Python 后端
│   ├── app/
│   │   ├── main.py            # FastAPI 入口 (含 SPA fallback)
│   │   ├── models.py          # SQLAlchemy 数据模型
│   │   ├── schemas.py         # Pydantic 请求/响应模型
│   │   ├── crud.py            # 数据库 CRUD 操作
│   │   ├── api/               # API 路由
│   │   │   ├── applications.py
│   │   │   ├── classifications.py
│   │   │   ├── dashboard.py
│   │   │   ├── golden_records.py
│   │   │   └── metadata_governance.py
│   │   ├── core/              # 核心配置
│   │   │   ├── config.py      # 环境配置
│   │   │   ├── database.py    # 数据库连接
│   │   │   ├── auth.py        # JWT 认证
│   │   │   └── schema_compat.py
│   │   └── services/          # 业务服务
│   │       ├── audit_service.py
│   │       ├── btp_mock.py
│   │       ├── code_generator.py
│   │       ├── duplicate_detector.py
│   │       ├── material_validator.py
│   │       └── openmetadata_sync.py
│   ├── init_db.py             # 数据库初始化脚本
│   ├── requirements.txt       # Python 依赖
│   ├── .env.example           # 环境变量示例
│   └── tests/                 # 后端测试
├── scripts/                    # Coze 平台脚本
│   ├── coze-preview-build.sh  # 预览构建 (pnpm install + uv pip + init_db)
│   ├── coze-preview-run.sh    # 预览运行 (后端:8000 + Vite:5000)
│   ├── coze-deploy-build.sh   # 部署构建 (pnpm build + uv pip + init_db)
│   └── coze-deploy-run.sh     # 部署运行 (uvicorn:5000 服务 API+SPA)
├── e2e_test.py                # E2E 端到端测试脚本
├── vite.config.ts             # Vite 配置 (dev port 3000, proxy /api -> :8000)
├── index.html                 # HTML 入口
├── package.json               # 前端依赖与脚本
├── tailwind.config.js
├── tsconfig.json
├── components.json            # shadcn/ui 配置
├── .coze                      # Coze 平台配置 (project/dev/deploy/subprojects)
└── info.md                    # 项目初始化信息
```

## 关键入口 / 核心模块

- **前端入口**：`src/main.tsx` → `src/App.tsx`（路由定义）
- **前端 API 客户端**：`src/lib/api.ts` — 封装 fetch + JWT 认证，导出 `api`/`login`/`getUser`/`logout`/`upload`/`downloadFile`
- **前端工具函数**：`src/lib/utils.ts` — shadcn/ui `cn()` 函数 (clsx + tailwind-merge)
- **后端入口**：`backend/app/main.py`（FastAPI app，含路由注册、CORS、SPA fallback）
- **Vite 配置**：`vite.config.ts` — dev server port 3000，`/api` 代理至 `localhost:8000`，`@` 别名指向 `./src`
- **后端配置**：`backend/app/core/config.py` — 通过环境变量配置数据库 URL、OpenMetadata、BTP 等
- **数据库初始化**：`backend/init_db.py` — 创建表结构并填充示例数据

## 运行与预览

### 前端
```bash
pnpm install
pnpm dev          # 开发服务器 (port 3000)
pnpm build        # 构建到 dist/
```

### 后端
```bash
cd backend
uv pip install --system -r requirements.txt    # 安装依赖
python3 init_db.py                               # 初始化数据库 (SQLite)
python3 -m uvicorn app.main:app --reload --port 8000
```

### 预览 (Coze 平台)
- 预览服务暴露端口 5000，禁止使用 9000 端口
- 预览架构：Vite dev server (port 5000) + FastAPI 后端 (port 8000，内部)
- Vite 通过 proxy 将 `/api` 请求转发至后端 (port 8000)
- 预览脚本：`scripts/coze-preview-build.sh`（安装依赖+初始化DB）→ `scripts/coze-preview-run.sh`（启动后端+Vite）
- 后端环境变量：`SQLALCHEMY_DATABASE_URL=sqlite:///./mdm_governance.db`、`OM_ENABLED=false`、`BTP_ENABLED=false`

### 部署 (Coze 平台)
- 部署架构：FastAPI (uvicorn port 5000) 同时服务 API 和 SPA 静态文件 (dist/)
- 部署脚本：`scripts/coze-deploy-build.sh`（pnpm build + pip install + init_db）→ `scripts/coze-deploy-run.sh`（uvicorn:5000）
- 后端 `main.py` 内置 SPA fallback：当 `dist/` 存在时，非 API 路由返回 `dist/index.html`

### 登录凭据
- 管理员：`admin001` / `adminpass001`
- 普通用户：`user001` / `password001`

## 用户偏好与长期约束

- 前端包管理器必须使用 pnpm（平台约束）
- 后端 Python 环境必须使用 uv 管理
- 预览端口固定为 5000，禁止使用 9000 端口
- 数据库默认使用 SQLite (开发环境)，生产环境使用 PostgreSQL

## 常见问题和预防

- `package-lock.json` 为 npm 残留，项目已迁移至 pnpm，使用 `pnpm-lock.yaml`
- `src/lib/api.ts` 和 `src/lib/utils.ts` 在项目初始化时缺失，已补建（前者为前端 API 客户端，后者为 shadcn/ui cn 工具函数）
- `backend/init_db.py` 原有硬编码路径 `/mnt/agents/output/app/backend`，已修复为基于脚本位置的动态路径
- 后端 SPA fallback 仅在 `dist/` 目录存在时生效，开发模式下前端独立运行
- CORS 配置在 DEBUG 模式下允许 localhost:3000 和 localhost:8000
- OpenMetadata 和 BTP 集成默认关闭 (`.env.example` 中 `OM_ENABLED=false`)
- 预览环境使用系统 Python 而非 venv（uv venv + pip install 在沙箱中下载超时），生产环境应使用 venv
- 后端 config.py 中 `OM_ENABLED` 和 `BTP_ENABLED` 默认为 `true`，预览/部署脚本中显式设为 `false`
