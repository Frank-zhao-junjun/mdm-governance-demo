# RalphLoop MDM Governance — 制造业物料主数据治理平台

> **物料主数据全生命周期管理平台**：从申请、校验、去重、编码、审批到发布的端到端治理闭环。
> **技术栈**: React 19 + FastAPI + SQLite/PostgreSQL | **版本**: v1.0.0

---

## 快速导航

| 入口 | 说明 |
|------|------|
| 知识图谱 | [`docs/knowledge-graph.md`](./docs/knowledge-graph.md) — 完整代码资产映射（文件级） |
| 后端 API | `backend/app/` — FastAPI 路由、数据模型、业务服务 |
| 前端 SPA | `src/` — React 页面、组件、类型定义 |
| 测试 | `backend/tests/` — pytest 集成 + 单元测试 |
| Coze 部署 | `scripts/` — 预览/部署 Shell 脚本 |
| 任务追踪 | `.superpowers/sdd/` — SDD 任务分片 |

---

## 快速启动

### 前置条件

- **Node.js** 20+（前端）
- **pnpm**（前端包管理器）
- **Python** 3.12+（后端）
- **uv**（Python 包管理器）

### 前端

`ash
pnpm install
pnpm dev          # 开发服务器 → http://localhost:3000
pnpm build        # 构建到 dist/
`

### 后端

`ash
cd backend
uv pip install --system -r requirements.txt   # 安装依赖
python init_db.py                              # 初始化数据库+种子数据
uvicorn app.main:app --reload --port 8000      # 启动 API → http://localhost:8000/docs
`

### 访问入口

| 入口 | URL |
|------|-----|
| 前端 SPA | `http://localhost:3000` |
| API 文档 (Swagger) | `http://localhost:8000/docs` |
| API 文档 (ReDoc) | `http://localhost:8000/redoc` |
| 健康检查 | `http://localhost:8000/api/health` |

---

## 系统架构

`
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
`

### 核心模块

| 模块 | 职责 |
|------|------|
| 物料申请 (Applications) | 申请创建、编辑、提交、审批、发布 |
| 金标数据 (Golden Records) | 权威主数据卡片、版本、BTP/OM 状态 |
| 分类管理 (Classifications) | 三级物料分类树 + 属性模板 |
| 元数据治理 (Metadata Governance) | 元数据目录、血缘、质量测试、审计轨迹 |
| 审计追踪 (Audit Trace) | 全生命周期操作日志与时间线 |

---

## 主数据治理流程

`
新建申请 → 保存草稿 → 提交 → 质量校验 → 重复预检 → 编码生成
                                              ↓
              管理员审批 ← 部门审批 ← 待审批 ←┘
                 ↓
              已批准 → 发布 → 创建 Golden Record → BTP 发布 + OpenMetadata 同步
`

### 提交自动执行链

1. **质量校验** (`MaterialValidator`) — 必填字段/名称长度/分类/属性模板
2. **重复预检** (`DuplicateDetector`) — ILIKE + 前缀模糊 + 关键词重罚
3. **编码生成** (`CodeGenerator`) — 编码规则 + 原子序列递增

### 发布流程

1. **创建 Golden Record** — 成为权威主数据
2. **BTP 发布** — Mock SAP BTP 发布
3. **OpenMetadata 同步** — 元数据目录 + 质量测试

---

## 测试

`ash
cd backend
pytest                          # 运行全部测试
pytest -v                       # 详细输出
pytest tests/test_auth.py       # 仅认证测试
pytest tests/test_api.py        # API 集成测试
`

---

## 项目结构速览

`
D:\AI\数据治理\
├── src/                        # 前端 SPA (React 19 + TypeScript)
│   ├── App.tsx                 #   路由定义（9 页面）
│   ├── main.tsx                #   React 入口
│   ├── pages/                  #   页面组件
│   ├── components/             #   Layout + shadcn/ui 组件库
│   ├── hooks/                  #   自定义 hooks
│   ├── types/api.ts            #   TypeScript 类型定义
│   └── lib/                    #   工具库（utils.ts；api.ts 待创建）
├── backend/                    # 后端 API (Python 3.12 + FastAPI)
│   ├── app/
│   │   ├── main.py             #   FastAPI 入口 + 路由注册
│   │   ├── models.py           #   SQLAlchemy 数据模型（7 表）
│   │   ├── schemas.py          #   Pydantic 请求/响应模型
│   │   ├── crud.py             #   CRUD 操作
│   │   ├── api/                #   5 个 API 路由模块
│   │   ├── core/               #   配置/数据库/认证/兼容
│   │   └── services/           #   6 个业务服务
│   ├── init_db.py              #   数据库初始化 + 种子数据
│   ├── requirements.txt        #   Python 依赖
│   └── tests/                  #   pytest 测试
├── docs/
│   └── knowledge-graph.md      #   完整代码资产图谱
├── scripts/                    #   Coze 平台构建/部署脚本
├── data/                       #   运行时数据库 + YAML 配置
├── assets/                     #   静态资源
├── AGENTS.md                   #   项目工作区规则
├── README.md                   #   本文件：项目入口
├── info.md                     #   项目初始化信息
├── vite.config.ts              #   Vite 构建/代理配置
├── package.json                #   前端依赖（pnpm）
├── pnpm-lock.yaml              #   pnpm 锁文件
├── components.json             #   shadcn/ui 配置
├── tailwind.config.js          #   Tailwind CSS 配置
└── tsconfig.json               #   TypeScript 根配置
`

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SQLALCHEMY_DATABASE_URL` | `postgresql://mdg_user:mdg_password@localhost:5432/mdm_governance` | 数据库连接（开发自动降级 SQLite） |
| `OPENMETADATA_HOST` | `http://localhost:8585/api` | OpenMetadata API 地址 |
| `OPENMETADATA_TOKEN` | `""` | OM 认证 Token |
| `OM_ENABLED` | `true` | OpenMetadata 开关 |
| `BTP_MOCK_URL` | `http://localhost:8888` | BTP Mock 地址 |
| `BTP_ENABLED` | `true` | BTP 开关 |
| `ENV` | `development` | 环境（development → DEBUG） |

> 注意：预览/部署脚本中会将 `OM_ENABLED` 和 `BTP_ENABLED` 显式设为 `false`。

---

## 技术栈一览

| 前端 | 后端 | 工具 |
|------|------|------|
| React 19 + TypeScript | Python 3.12 + FastAPI | Vite 7 |
| shadcn/ui (new-york) | SQLAlchemy 2.0 + Pydantic v2 | pnpm / uv |
| Tailwind CSS 3.4 | JWT (python-jose) + bcrypt | pytest |
| react-router-dom v7 | SQLite / PostgreSQL | node:test |
| recharts | uvicorn | Coze 平台 |
| sonner (Toast) | requests + httpx | Git |

---

## 登录凭据

用户认证为 Mock 字典（`backend/app/core/auth.py` 中 `MOCK_USERS`），共 5 个账号：

| 角色 | 用户名 | 密码 | 部门 |
|------|--------|------|------|
| 申请人 | `user001` | `password001` | 研发部 |
| 申请人 | `user002` | `password002` | 采购部 |
| 管理员 | `admin001` | `adminpass001` | IT部 |
| 部门审批 | `dept001` | `deptpass001` | 生产部 |
| 数据管理员 | `data001` | `datapass001` | 数据治理部 |

---

## 待办

- [ ] 创建 `src/lib/api.ts`（前端 API 客户端，当前文件缺失）
- [ ] 生产环境 PostgreSQL 迁移脚本
- [ ] OpenMetadata 真实接入验证
- [ ] Docker 部署配置
