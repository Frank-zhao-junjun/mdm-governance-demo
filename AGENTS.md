# AGENTS.md — 项目工作区规则

> 本文件面向 AI 编码代理，描述项目架构、命令、约定与约束。README.md 提供更完整的产品级文档。

## 项目概述

制造业数据治理平台（Stock Data Governance，v2.0.0）— 存量数据治理与质量管理平台。服务边界明确为：仅提供数据治理与数据质量管理能力，不承接新增数据流程、审批流程、Golden Data（金标数据）管理和下游分发执行。

本项目重点覆盖数据标准、质量检测、疑似错误识别、AI 辅助裁决（Copilot）、Agent 编排、审计追踪与问题闭环管理；归并执行只输出建议与执行预检，实际归并由外部执行器承担，平台不改写业务记录。

## 技术栈

- **前端**：React 19 + TypeScript + Vite 7 + Tailwind CSS 3.4 + shadcn/ui (new-york)
  - 路由：react-router-dom v7；表单：react-hook-form + zod；图表：recharts；图标：lucide-react；通知：sonner
- **后端**：Python 3.12 + FastAPI + SQLAlchemy 2.0 + Pydantic v2
  - 认证：JWT (python-jose + passlib/bcrypt)
  - 数据库：SQLite (开发默认) / PostgreSQL (生产)
  - LLM：`app/core/llm_gateway.py`（mock 默认 / DeepSeek，15s 超时 + 熔断 + 自动降级）
- **包管理**：前端必须使用 pnpm（原 npm 已迁移，`package-lock.json` 为残留，以 `pnpm-lock.yaml` 为准）；后端使用 uv + requirements.txt

## 目录结构

```
├── src/                        # 前端源码
│   ├── main.tsx               # 前端入口
│   ├── App.tsx                # 根组件 + 路由定义（10 页面：/login /dashboard
│   │                          #   /quality/standards /quality/checks
│   │                          #   /quality/checks/report /quality/suspected
│   │                          #   /copilot /governance /agents /disputes）
│   ├── pages/                 # 页面组件（Dashboard, Login, DataStandards,
│   │                          #   QualityChecks, QualityReport, SuspectedErrors,
│   │                          #   Copilot, GovernanceDashboard, AgentActivity,
│   │                          #   DisputeView）
│   ├── components/            # Layout + standards/（DataStandardFormDialog）+ shadcn/ui
│   │   └── ui/                # shadcn/ui 组件
│   ├── hooks/                 # 自定义 hooks
│   ├── lib/
│   │   ├── api.ts             # API 客户端 (fetch 封装, JWT, login/logout)
│   │   ├── governance.ts      # 数据标准领域 API + 表单模型
│   │   ├── quality.ts         # 质量检测领域 API
│   │   ├── suspected.ts       # 疑似错误领域 API
│   │   └── utils.ts           # shadcn/ui cn() 工具函数
│   └── types/                 # 类型定义
├── backend/                    # Python 后端
│   ├── app/
│   │   ├── main.py            # FastAPI 入口（8 个 router 注册、login/me 认证端点、
│   │   │                      #   CORS、SPA fallback）
│   │   ├── models.py          # SQLAlchemy 数据模型（14 张表：data_standards,
│   │   │                      #   material_records, partner_records, quality_check_rules,
│   │   │                      #   quality_check_batches, quality_check_results,
│   │   │                      #   suspected_errors, audit_logs, quality_ticket,
│   │   │                      #   merge_ticket, key_mapping, agent_trace,
│   │   │                      #   governance_owner, approval_evidence）
│   │   ├── schemas.py         # Pydantic 请求/响应模型
│   │   ├── crud.py            # 数据库 CRUD 操作
│   │   ├── api/               # 8 个 API 路由模块
│   │   │   ├── data_standards.py      # 数据标准 CRUD（409 冲突 / 403 权限）
│   │   │   ├── quality_checks.py      # POST run（admin/data_admin）+ rules/results/batches/report 查询
│   │   │   ├── suspected_errors.py    # POST detect + GET 列表 + POST /{id}/resolve
│   │   │   ├── data_import.py         # CSV 批量导入（upsert）
│   │   │   ├── copilot.py             # 待办、approve/reject/overturn、问责
│   │   │   ├── governance.py          # 报告、簇、归并预检（merge-execute 仅返回 ready）
│   │   │   ├── owners.py              # 治理 Owner CRUD
│   │   │   └── evidence.py            # 证据链
│   │   ├── core/              # 核心配置
│   │   │   ├── config.py      # 环境变量配置（ENV 默认 development）
│   │   │   ├── database.py    # 数据库连接
│   │   │   ├── auth.py        # JWT 认证（用户库为 MOCK_USERS 硬编码，4 种角色）
│   │   │   └── llm_gateway.py # LLM 网关（mock/DeepSeek，熔断降级，trace_id 透传）
│   │   ├── services/          # 8 个业务服务
│   │   │   ├── quality_engine.py      # 检测规则执行引擎
│   │   │   ├── rule_derivation.py     # 标准 → 规则派生（required→null / pattern→format 等）
│   │   │   ├── quality_runner.py      # 限额 → 装配 → 执行 → 单事务落库（上限 5,000 实体）
│   │   │   ├── suspected_error_runner.py  # 疑似错误检测（三键去重/误报白名单/终态拦截）
│   │   │   ├── duplicate_detector.py  # 重复识别
│   │   │   ├── entity_accessor.py     # 实体数据访问
│   │   │   ├── csv_importer.py        # CSV 导入
│   │   │   └── audit_service.py       # 审计日志
│   │   ├── skills/            # 确定性 Skill 层（无副作用，只输出建议）
│   │   │   ├── common.py              # EvidenceItem / SkillSuggestion / SkillResult 契约
│   │   │   ├── naming.py / attribute.py / unit.py / quality_rule.py
│   │   │   ├── duplicate_match.py     # 重复匹配合并建议
│   │   │   └── merge_executor.py      # 归并执行预检（仅 approved 状态可继续）
│   │   └── agents/            # Agent 编排层
│   │       ├── base.py                # BaseAgent：统一 trace、失败可审计返回
│   │       ├── standard_agent.py      # 标准建议（仅输出建议）
│   │       ├── quality_agent.py       # 创建并指派 3 天 SLA 质量工单
│   │       ├── dedup_agent.py         # 归并建议工单（绝不执行归并）
│   │       └── orchestrator.py        # 编排器：request_id 幂等 + 进程内锁串行化
│   ├── scripts/
│   │   └── seed_demo_data.py  # 可复现演示数据（默认 10,000 条 material_records，
│   │                          #   8 个重复簇，幂等；--reset 仅清 demo_seed 数据）
│   ├── init_db.py             # 数据库初始化 + 种子数据（29 标准 → 55 条派生规则）
│   ├── requirements.txt       # Python 依赖（含 pytest、httpx）
│   ├── pytest.ini             # pytest 配置（testpaths=tests）
│   ├── .env.example           # 环境变量示例
│   └── tests/                 # 后端 pytest 测试（21 个文件，310 个用例）
├── scripts/                    # Coze 平台脚本
│   ├── coze-preview-build.sh  # 预览构建 (pnpm install + uv pip + init_db)
│   ├── coze-preview-run.sh    # 预览运行 (后端:8000 + Vite:5000)
│   ├── coze-deploy-build.sh   # 部署构建 (pnpm build + uv pip + init_db)
│   └── coze-deploy-run.sh     # 部署运行 (uvicorn:5000 同时服务 API+SPA)
├── docs/                      # demo-script.md（演示剧本）、spec-data-governance.md（治理 SPEC）、
│                              #   knowledge-graph.md（旧版代码资产图谱，已滞后）
├── vite.config.ts             # Vite 配置 (dev port 3000, proxy /api -> :8000, @ -> ./src)
├── package.json               # 前端依赖与脚本
├── components.json            # shadcn/ui 配置
├── .github/workflows/ci.yml   # CI（前端 lint+tsc+build / 后端 pytest）
├── .coze                      # Coze 平台配置
└── info.md                    # 项目初始化信息
```

## 关键入口

- **前端入口**：`src/main.tsx` → `src/App.tsx`（路由定义）
- **前端 API 客户端**：`src/lib/api.ts` — 封装 fetch + JWT；领域封装在 `governance.ts` / `quality.ts` / `suspected.ts`
- **后端入口**：`backend/app/main.py` — FastAPI app，注册 8 个 router，含 SPA fallback（`dist/` 存在时非 API 路由返回 `dist/index.html`）
- **后端配置**：`backend/app/core/config.py` — 环境变量驱动，`ENV` 默认 `development`
- **数据库初始化**：`backend/init_db.py` — 建表 + 种子数据
- **演示数据**：`backend/scripts/seed_demo_data.py` — 固定种子，默认幂等，`--reset` 只删演示对象

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
python scripts/seed_demo_data.py                 # 可选：演示数据
python -m uvicorn app.main:app --reload --port 8000   # API 文档: http://localhost:8000/docs
```

### 测试
```bash
cd backend
python -m pytest                    # 全部测试（310 个用例）
python -m pytest tests/test_auth.py # 单文件
# pytest.ini 将 app.* 的 DeprecationWarning 视为 error
```

### CI
`.github/workflows/ci.yml` 两个 job：
- `check`（前端）：`pnpm install --frozen-lockfile` → `pnpm lint` → `tsc --noEmit` → `pnpm build`（Node 20 + pnpm 9）
- `backend-tests`：Python 3.12，`pytest tests/ -q`，环境变量 `ENV=test`、`SQLALCHEMY_DATABASE_URL=sqlite:///:memory:`

## 预览与部署（Coze 平台）

- **预览**：Vite dev server (port 5000) + FastAPI (port 8000 内部)，Vite proxy 转发 `/api`。预览端口固定 5000，**禁止使用 9000 端口**。脚本：`coze-preview-build.sh` → `coze-preview-run.sh`
- **部署**：uvicorn (port 5000) 同时服务 API 和 SPA 静态文件 (dist/)。脚本：`coze-deploy-build.sh` → `coze-deploy-run.sh`（`ENV=production`）
- 预览/部署脚本中 `OM_ENABLED` 和 `BTP_ENABLED` 显式设为 `false`（历史遗留变量，当前代码不再读取）
- JWT 密钥：生产模式必须提供 `MDM_SECRET_KEY`（未设置时启动 fail-fast）；deploy-run.sh 会优先生成并持久化到 `backend/.mdm_secret_key`（600 权限，已 gitignore）

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SQLALCHEMY_DATABASE_URL` | `sqlite:///./mdm_governance.db` | 数据库连接（生产用 PostgreSQL） |
| `MDM_SECRET_KEY` | — | **生产必填**，JWT 签名密钥，缺失 fail-fast |
| `ENV` | `development` | `development` / `production` / `test` |
| `DEEPSEEK_API_KEY` | — | LLM 网关 DeepSeek 模式密钥（默认 mock 无需配置） |

## 登录凭据

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | `admin001` | `adminpass001` |
| 普通用户 | `user001` / `user002` | `password001` / `password002` |
| 部门审批 | `dept001` | `deptpass001` |
| 数据管理员 | `data001` | `datapass001` |

## 代码风格与约定

- 前端：TypeScript + eslint 9（`pnpm lint` 已加入 CI，必须零错误）；shadcn/ui 目录关闭了 `react-refresh/only-export-components`（variants 同文件导出是 shadcn 既定模式），carousel/sidebar 两处上游写法使用行内豁免
- 前端导入别名：`@` 指向 `./src`
- 后端：SQLAlchemy 2.0 + Pydantic v2；分层为 api（路由）→ agents/skills（AI 治理）→ services（业务服务）→ crud（数据访问）
- 质量检测执行链：`rule_derivation`（标准→规则派生）→ `quality_runner`（限额+装配+执行+单事务落库）→ `suspected_error_runner`（疑似错误，三键去重）
- AI 治理链：LLM 网关 → Agent（trace 可审计）→ Skill（确定性、无副作用）→ 工单（quality_ticket / merge_ticket）→ 人工裁决（approval_evidence 快照）

## 安全约束（不可违反）

- **认证**：所有 API 必须携带有效 JWT（无免认证回退）；`get_current_user` 不允许任何无 token 放行
- **密钥**：生产环境 `MDM_SECRET_KEY` 独立环境变量，禁止硬编码；`DEEPSEEK_API_KEY` 仅由环境变量提供，日志不记录 prompt 或密钥
- **归并门禁**：merge-execute 仅 admin/data_admin 可调用；未批准返回 409；批准后只返回 `ready` 交外部执行器，**禁止**平台直接改写 `material_records`
- **审批快照**：高风险 merge 批准必须填写 opinion 且 confirmed=true，保存审批前 status/evidence/trace 快照到 `approval_evidence`
- **Skill 无副作用**：Skill 层只输出建议，禁止在 Skill 内写库
- **编排幂等**：编排器必须按 request_id 检查已有工单，重复提交不得产生重复工单

## 长期约束

- 前端包管理器必须使用 pnpm；后端 Python 环境必须使用 uv 管理
- 预览端口固定 5000，禁止 9000
- 数据库默认 SQLite（开发），生产 PostgreSQL
- 预览环境使用系统 Python 而非 venv（沙箱中 uv venv 下载超时），生产环境应使用 venv
- CORS 在 DEBUG 模式下允许 localhost:3000 和 localhost:8000
- 实体批量操作上限 **5,000**（`entity_accessor.MAX_ENTITIES` / `duplicate_detector.MAX_ENTITIES_PER_RUN` / `csv_importer.MAX_ROWS` 三处口径一致，SPEC §7 Phase 2「5000 上限生效」；超限拒绝并要求分批，不自动切批）
- ⚠️ `scripts/seed_demo_data.py` 默认播 **10,000** 条 `material_records`，**超过上面的 5,000 上限**——用默认参数播种后整表质量检测会直接被拒。演示时用 `--records 5000` 以内，或按 `entity_ids` 分批检测
- ⚠️ `crud.get_material_records` / `crud.get_partner_records` 的默认 `limit` 是 **10,000**，与 5,000 上限口径不一致。当前无害，因为唯一调用方 `entity_accessor` 总是传自己封顶过的 limit（`entity_accessor.py:288`）；**新代码若直接调这两个 crud 函数会绕过上限**，必须显式传 ≤5,000 的 limit

## 已知问题与历史教训

- `package-lock.json` 为 npm 残留，勿使用 npm
- 后端 SPA fallback 仅在 `dist/` 存在时生效，开发模式下前端独立运行
- **2026-07 安全修复**：生产部署曾用 `ENV=development` 导致免认证回退生效 + JWT 密钥硬编码可伪造，已修复（ENV=production、删除回退、MDM_SECRET_KEY 独立环境变量）
- **2026-09 架构演进**：旧版 MDM 申请/审批/金标数据/发布链路已按 SPEC §1.4 移除（applications/classifications/golden_records 等模块与页面），OpenMetadata/BTP 集成代码已删除；`docs/knowledge-graph.md` 与 `graphify-out/` 图谱基于旧版代码，仅供参考
- `auth.py` 用户库仍是 MOCK_USERS 硬编码，中期应迁入数据库
- SLA 升级扫描（3 天 dept_head / 7 天 committee）目前按需触发，尚无独立后台调度器
- 前端 `pnpm build` 不做类型检查，验证必须单独跑 `tsc`；`tsc -b` 增量缓存可能掩盖错误，验证用 `--force`
- Git Bash 下 `curl -d` 中文 body 会编码损坏致 JSON 400，冒烟脚本用 Python urllib 代替
