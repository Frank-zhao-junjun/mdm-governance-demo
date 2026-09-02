# 制造业数据治理平台

> **服务边界**：本项目聚焦于存量数据治理与数据质量管理，提供数据标准、质量检测、疑似错误识别、AI 辅助裁决与治理闭环能力；不承接新增数据流程、审批流程、Golden Data（金标数据）管理和下游分发执行。
> **技术栈**: React 19 + FastAPI + SQLite/PostgreSQL | **版本**: v2.0.0

---

## 快速导航

| 入口 | 说明 |
|------|------|
| 演示剧本 | [`docs/demo-script.md`](./docs/demo-script.md) — 15 分钟现场演示与验收映射 |
| 治理 SPEC | [`docs/spec-data-governance.md`](./docs/spec-data-governance.md) — 主数据字段治理规格说明 |
| 知识图谱 | [`docs/knowledge-graph.md`](./docs/knowledge-graph.md) — 代码资产映射（基于旧版 MDM 代码，已滞后） |
| 后端 API | `backend/app/` — FastAPI 路由、数据模型、业务服务、Agent/Skill 层 |
| 前端 SPA | `src/` — React 页面、组件、类型定义 |
| 测试 | `backend/tests/` — 310 个 pytest 集成 + 单元测试 |
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
python scripts/seed_demo_data.py               # 可选：10,000 条演示存量数据（幂等，--reset 可清理）
uvicorn app.main:app --reload --port 8000      # 启动 API → http://localhost:8000/docs
```

### 访问入口

| 入口 | URL |
|------|-----|
| 前端 SPA | `http://localhost:3000` |
| API 文档 (Swagger) | `http://localhost:8000/docs` |
| API 文档 (ReDoc) | `http://localhost:8000/redoc` |

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
│  Frontend (React 19 + Vite 7 + Tailwind + shadcn/ui)               │
│  仪表盘 │ 数据标准管理 │ 质量检测 │ 质量报告 │ 疑似错误              │
│  治理驾驶舱 │ Copilot 裁决 │ Agent 活动流 │ 权责冲突               │
│                        proxy /api → :8000                          │
└────────────────────────────────────────────────────────────────────┘
                              │
┌────────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI + SQLAlchemy 2.0 + JWT)                          │
│  ┌──────────────┐ ┌──────────────────┐ ┌──────────────┐           │
│  │ API 路由     │ │ Agent 编排层     │ │ 数据模型     │           │
│  │ 8 routers    │ │ 4 agents + 编排器│ │ 14 tables    │           │
│  ├──────────────┤ ├──────────────────┤ ├──────────────┤           │
│  │ 业务服务     │ │ Skill 层         │ │ LLM 网关     │           │
│  │ 8 services   │ │ 6 个确定性 Skill │ │ mock/DeepSeek│           │
│  └──────────────┘ └──────────────────┘ └──────────────┘           │
└────────────────────────────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 职责 | 页面 / API |
|------|------|-----------|
| 数据标准管理 | 字段级标准定义（必填/格式/值域/长度/唯一），服务端分页过滤 | `/quality/standards`，`/api/data-standards` |
| 质量检测 | 标准派生规则 → 批次执行 → 失败明细落库 → 统计报告 | `/quality/checks`、`/quality/checks/report`，`/api/quality-checks` |
| 疑似错误 | 重复/命名违例检测，三键去重、误报白名单、三值状态流转 | `/quality/suspected`，`/api/suspected-errors` |
| 数据导入 | CSV 批量导入存量记录（upsert） | `/api/data-import` |
| Copilot 裁决 | 人工待办、证据/风险/替代选项三件套、approve/reject/overturn | `/copilot`，`/api/copilot` |
| 治理驾驶舱 | 质量分、重复率、待办、Agent 活动指标与图表 | `/governance`，`/api/governance` |
| Agent 活动流 | Agent 执行 trace 可视化 | `/agents` |
| 权责冲突 | FA/FB 双 Owner 争议归并会签视图 | `/disputes` |
| 审计追踪 | 全链路审计日志（检测/裁决/归并审批快照） | `audit_logs` 表，`/api/evidence` |

### AI 治理分层

```
LLM 网关 (llm_gateway)      mock（默认）/ DeepSeek，15s 超时 + 熔断 + 降级
        │
Agent 编排层 (app/agents)    StandardAgent / QualityAgent / DedupAgent + 编排器
        │                    按 request_id 幂等，SLA 3 天升级 dept_head、7 天升级 committee
        │
Skill 层 (app/skills)        naming / attribute / unit / quality_rule /
        │                    duplicate_match / merge_executor —— 全部确定性、无副作用
        │
工单闭环                    quality_ticket / merge_ticket（归并仅记录建议，
                             批准后才返回 ready，绝不直接改写业务数据）
```

### 质量检测执行链

1. **规则派生** (`rule_derivation.py`) — 数据标准自动派生检测规则（required→null / pattern→format / 值域→range / max_length→length / unique→unique）
2. **批次执行** (`quality_runner.py`) — 限额（≤5,000 实体，超限拒绝并要求分批）→ 规则装配 → 执行 → 批次 + 失败明细单事务落库
3. **疑似错误** (`suspected_error_runner.py`) — `(entity_id, matched_entity_id, error_type)` 三键粒度去重，误报白名单，终态拦截，实体消失自动关闭

---

## 服务范围与治理边界

本平台仅提供数据治理与数据质量管理服务，不承接以下执行型流程：

- 新增数据申请与数据落库
- 审批流执行
- Golden Data（金标数据）创建与发布
- 下游系统分发与同步执行

归并执行（merge-execute）同样遵循此边界：批准后平台只返回 `ready` 状态与执行预检结果，实际数据归并由外部执行器完成，平台不修改 `material_records`。

> 业务侧的新增、审批、金标数据、分发等动作，由客户自身系统或专门的执行层负责，不走本平台。

## 治理闭环流程

```
数据标准定义 → 规则派生 → 质量检测 → 疑似错误识别 → Agent 建议 → 人工裁决 → 审计追踪
```

---

## 安全特性

| 能力 | 说明 |
|------|------|
| JWT 认证 | 所有 API 必须携带有效 JWT，无免认证回退 |
| 密钥管理 | 生产环境（`ENV=production`）强制 `MDM_SECRET_KEY` 环境变量，缺失即 fail-fast |
| LLM 密钥 | `DEEPSEEK_API_KEY` 仅由环境变量提供，日志不记录 prompt 或密钥 |
| 高风险操作门禁 | merge 批准必须填写 opinion 且 confirmed=true，审批前保存 status/evidence/trace 快照到 `approval_evidence` |
| 无副作用 Skill | Skill 层只输出建议，不写库；归并执行预检仅允许 approved 状态继续 |
| 编排幂等 | 编排器按 request_id 检查工单保证幂等，进程内锁串行化增量执行 |

---

## 测试

```bash
cd backend
pytest                          # 运行全部 310 个测试
pytest -v                       # 详细输出
pytest tests/test_auth.py       # 仅认证测试
pytest tests/test_demo_e2e.py   # 端到端验收（seed → 增量检核 → 裁决 → 问责）
```

测试分层：模型层 / LLM 网关 / Skill 层 / Agent 编排 / API 集成 / E2E 验收。

---

## CI/CD

GitHub Actions 工作流（`.github/workflows/ci.yml`）包含两个 job：

| Job | 内容 |
|-----|------|
| `check`（前端） | `pnpm lint` (eslint) + `tsc --noEmit` + `pnpm build`（Node 20 + pnpm 9） |
| `backend-tests` | Python 3.12 + `pytest tests/ -q`（`ENV=test`，SQLite in-memory） |

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
- 运行：`scripts/coze-deploy-run.sh`（`ENV=production`，自动生成 JWT 密钥并持久化到 `backend/.mdm_secret_key`）

> 预览/部署脚本中 `OM_ENABLED` 和 `BTP_ENABLED` 显式设为 `false`（历史遗留变量，当前代码已不再读取）。

---

## 项目结构速览

```
├── src/                        # 前端 SPA (React 19 + TypeScript)
│   ├── App.tsx                 #   路由定义（10 页面）
│   ├── main.tsx                #   React 入口
│   ├── pages/                  #   Dashboard / Login / DataStandards / QualityChecks /
│   │                           #   QualityReport / SuspectedErrors / Copilot /
│   │                           #   GovernanceDashboard / AgentActivity / DisputeView
│   ├── components/             #   Layout + standards/ + shadcn/ui 组件库
│   ├── hooks/                  #   自定义 hooks
│   ├── types/api.ts            #   TypeScript 类型定义
│   └── lib/                    #   api.ts（API 客户端）+ governance.ts / quality.ts /
│                               #   suspected.ts（领域 API 封装）+ utils.ts
├── backend/                    # 后端 API (Python 3.12 + FastAPI)
│   ├── app/
│   │   ├── main.py             #   FastAPI 入口 + 8 个路由注册 + 认证端点 + SPA fallback
│   │   ├── models.py           #   SQLAlchemy 数据模型（14 表）
│   │   ├── schemas.py          #   Pydantic 请求/响应模型
│   │   ├── crud.py             #   CRUD 操作
│   │   ├── api/                #   data_standards / quality_checks / suspected_errors /
│   │   │                       #   data_import / copilot / governance / owners / evidence
│   │   ├── core/               #   config / database / auth / llm_gateway
│   │   ├── services/           #   quality_engine / rule_derivation / quality_runner /
│   │   │                       #   suspected_error_runner / duplicate_detector /
│   │   │                       #   entity_accessor / csv_importer / audit_service
│   │   ├── skills/             #   6 个确定性 Skill（naming/attribute/unit/
│   │   │                       #   quality_rule/duplicate_match/merge_executor）
│   │   └── agents/             #   base / standard / quality / dedup Agent + 编排器
│   ├── scripts/
│   │   └── seed_demo_data.py   #   可复现演示数据（默认 10,000 条，幂等，--reset 清理）
│   ├── init_db.py              #   数据库初始化 + 种子数据（29 标准 → 55 条派生规则）
│   ├── requirements.txt        #   Python 依赖
│   └── tests/                  #   310 个 pytest 测试
├── scripts/                    #   Coze 平台构建/部署脚本
├── docs/                       #   demo-script / spec-data-governance / knowledge-graph 等
├── AGENTS.md                   #   项目工作区规则
├── README.md                   #   本文件：项目入口
├── vite.config.ts              #   Vite 构建/代理配置（dev :3000，proxy /api → :8000）
├── package.json                #   前端依赖（pnpm）
├── pnpm-lock.yaml              #   pnpm 锁文件
└── components.json             #   shadcn/ui 配置
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SQLALCHEMY_DATABASE_URL` | `sqlite:///./mdm_governance.db` | 数据库连接（生产使用 PostgreSQL） |
| `MDM_SECRET_KEY` | — | **生产环境必填**。JWT 签名密钥，缺失时启动 fail-fast |
| `ENV` | `development` | 运行环境：`development` / `production` / `test` |
| `DEEPSEEK_API_KEY` | — | LLM 网关 DeepSeek 模式密钥（默认 mock 模式无需配置） |

---

## 技术栈一览

| 前端 | 后端 | 工具 |
|------|------|------|
| React 19 + TypeScript | Python 3.12 + FastAPI | Vite 7 |
| shadcn/ui (new-york) | SQLAlchemy 2.0 + Pydantic v2 | pnpm / uv |
| Tailwind CSS 3.4 | JWT (python-jose) + bcrypt | pytest |
| react-router-dom v7 | uvicorn | GitHub Actions |
| recharts | httpx | Coze 平台 |
| sonner (Toast) | | Git |

---

## 待办

- [ ] 用户库 `MOCK_USERS` 迁入数据库（当前硬编码于 `auth.py`）
- [ ] 生产环境 PostgreSQL 迁移脚本
- [ ] Docker 部署配置
- [ ] LLM 网关 DeepSeek 模式真实接入验证（当前默认 mock）
- [ ] 后台 worker：SLA 升级扫描目前按需触发，尚无独立调度器
