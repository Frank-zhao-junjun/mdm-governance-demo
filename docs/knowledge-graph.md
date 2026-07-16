# 制造业物料主数据治理平台 · 代码资产知识图谱

> **版本**: v1.0.0 | **更新**: 2026-07-13 | **技术栈**: React 19 + FastAPI + SQLite/PostgreSQL
> **范围**: 全仓库（HEAD 当前快照），React/FastAPI 架构
> **形式**: 代码资产图谱 — 目录树 / 文件职责 / 数据模型 / API 端点 / 端到端映射

---

## 一、结构全景

`
D:\AI\数据治理\
├── src/                         # 前端 SPA (React 19 + TypeScript + Vite 7)
├── backend/                     # 后端 API (Python 3.12 + FastAPI + SQLAlchemy)
├── docs/                        # 系统文档（本文件在此）
├── data/                        # 运行时数据库 + YAML 配置
├── scripts/                     # Coze 平台构建/部署脚本
├── 1.Ref-technical/             # 技术参考资料（PDF/MD/PPT/drawio 导入，部分为空目录）
├── assets/                      # 静态资源
├── .superpowers/                # SDD 任务分片
├── .claude/                     # Claude Code 配置
├── AGENTS.md                    # 工作区规则（技术栈/目录/API 风格）
├── README.md                    # 项目入口（启动/架构/功能概览）
├── info.md                      # 项目初始化信息
├── vite.config.ts               # Vite 构建/代理配置
├── package.json                 # 前端依赖（pnpm）
├── pnpm-lock.yaml               # pnpm 锁文件
├── components.json              # shadcn/ui 配置
├── tailwind.config.js           # Tailwind CSS 配置
├── postcss.config.js            # PostCSS 配置
├── tsconfig.json                # TypeScript 根配置
├── tsconfig.app.json            # TypeScript 应用配置
├── tsconfig.node.json           # TypeScript Node 配置
├── eslint.config.js             # ESLint 配置
├── e2e_test.py                  # E2E 测试脚本
├── .gitignore
├── .coze                        # Coze 平台项目配置
└── project_20260712_224859.tar.gz  # 项目归档备份
`

---

## 二、前端资产 (src/)

### 2.1 入口与路由

| 文件 | 行数 | 职责 |
|------|------|------|
| src/main.tsx | 9 | React 入口，挂载 <App /> 到 #root |
| src/App.tsx | 35 | **路由定义**：登录、仪表盘、物料申请详情/新建、Golden Record、元数据治理、分类管理、审计追踪 |
| src/App.css | 37 | 应用级样式（Vite 默认，未定制） |
| src/index.css | 72 | 全局样式（Tailwind 指令） |

### 2.2 路由表

| 路径 | 组件 | 权限 | 功能 |
|------|------|------|------|
| /login | Login.tsx | 公开 | 用户登录（Mock 认证） |
| / | → 重定向 | - | 自动跳转到 /dashboard |
| /dashboard | Dashboard.tsx | 登录 | 仪表盘首页 - KPI 卡片 + 最近申请 + 审计日志 |
| /applications | Applications.tsx | 登录 | 物料申请列表 - 搜索/状态筛选/分页 |
| /applications/new | NewApplication.tsx | 登录 | 新建申请 - 三级分类选择/动态表单/附件上传/质量校验 |
| /applications/:id | ApplicationDetail.tsx | 登录 | 申请详情 - 状态流转/审批操作/发布/审计追踪 |
| /golden-records | GoldenRecords.tsx | 登录 | Golden Record 卡片视图 - 搜索/状态/版本/BTP/OM |
| /metadata-governance | MetadataGovernance.tsx | 登录 | **元数据治理看板** - 元数据目录/血缘图谱/质量测试/审计轨迹 |
| /classifications | Classifications.tsx | 登录 | 物料分类树 - 三级分类展示 |
| /audit/:id | AuditTrace.tsx | 登录 | 全链路审计追踪 - 申请全生命周期步骤 |

### 2.3 组件与工具

| 文件 | 行数 | 职责 |
|------|------|------|
| src/components/Layout.tsx | 96 | **应用布局** — 侧边栏导航（5 项）+ 顶栏 + 用户信息 + 退出 |
| src/components/ui/ | ~40 组件 | **shadcn/ui 组件库**：button/card/dialog/tabs/table/badge/sidebar 等 |
| src/hooks/use-mobile.ts | 15 | 移动端检测 hook |
| src/types/api.ts | 219 | **TypeScript 类型定义** — User/Classification/Application/GoldenRecord/AuditLog 等接口 |
| src/lib/utils.ts | 5 | shadcn/ui cn() 工具函数（clsx + tailwind-merge） |
| src/lib/api.ts | — | **API 客户端**（文件缺失，待创建：fetch 封装 + JWT 注入） |

### 2.4 页面功能矩阵

| 页面 | API 调用 | UI 组件 | 功能亮点 |
|------|----------|---------|----------|
| Login | POST /api/auth/login | Card/Input/Button | 5 角色 Mock 认证 |
| Dashboard | GET /api/dashboard | Card/Badge | KPI 卡片 + 最近申请表 + 审计日志 |
| Applications | GET /api/applications/ | Card/Input/Select/Table/Badge | 搜索/状态筛选/分页 |
| NewApplication | GET /api/classifications/ + POST/PUT 系列 | Tabs/Card/Form/Select/Upload | 三级级联分类 + 动态属性表单 + 附件上传 + 校验结果展示 |
| ApplicationDetail | GET /api/applications/:id + 审批/POST | Card/Badge/Button | 状态机操作（管理员审批/部门审批/发布）、审计追踪 |
| GoldenRecords | GET /api/golden-records/ | Card/Badge | 卡片网格 + BTP/OM 状态标记 |
| MetadataGovernance | GET /api/metadata-governance/overview | Tabs/Table/Card/Badge | 4 Tab：元数据目录/血缘图谱/质量测试/审计轨迹 |
| Classifications | GET /api/classifications/ | Card/Badge | 三级分类树 |
| AuditTrace | GET /api/applications/:id/audit | Card/Badge | 全链路审计时间线 |

---

## 三、后端资产 (backend/)

### 3.1 入口与核心配置

| 文件 | 行数 | 职责 |
|------|------|------|
| ackend/app/main.py | 89 | FastAPI 入口：路由注册、CORS、SPA fallback、健康检查、登录/当前用户端点 |
| ackend/app/core/config.py | 24 | 环境变量配置（数据库、OM、BTP、DEBUG） |
| ackend/app/core/database.py | 30 | SQLAlchemy 引擎、SessionLocal、依赖注入 |
| ackend/app/core/auth.py | 128 | JWT 认证：密码哈希、token 生成/校验、Mock 用户字典（5 账号）、角色依赖 |
| ackend/app/core/schema_compat.py | 63 | 运行时改表结构兼容（应改为正式迁移） |
| ackend/app/models.py | 238 | **7 张 SQLAlchemy 表** + 枚举（MaterialType/ApplicationStatus/GoldenRecordStatus/StepName） |
| ackend/app/schemas.py | 179 | **Pydantic 请求/响应模型** |
| ackend/app/crud.py | 191 | 数据库 CRUD 操作 |
| ackend/init_db.py | 132 | 数据库初始化 + 种子数据 |
| ackend/requirements.txt | - | Python 依赖清单 |

### 3.2 API 路由 (backend/app/api/)

| 文件 | 行数 | 职责 |
|------|------|------|
| pi/applications.py | 566 | 物料申请 CRUD、草稿编辑、提交、管理员/部门审批、发布、附件上传下载、审计 |
| pi/classifications.py | 58 | 分类树读取、分类详情、属性模板读取与创建 |
| pi/dashboard.py | 46 | 仪表盘 KPI、健康检查、BTP Mock 健康检查 |
| pi/golden_records.py | 43 | Golden Record 列表、详情、按编码查询 |
| pi/metadata_governance.py | 137 | 元数据治理概览 |
| pi/__init__.py | 1 | 包初始化 |

### 3.3 业务服务 (backend/app/services/)

| 文件 | 行数 | 职责 |
|------|------|------|
| services/audit_service.py | 96 | 审计日志记录与查询 |
| services/btp_mock.py | 64 | Mock SAP BTP 发布服务 |
| services/code_generator.py | 74 | 物料编码生成（规则 + 原子递增） |
| services/duplicate_detector.py | 88 | 重复预检（ILIKE + 前缀模糊 + 关键词重罚） |
| services/material_validator.py | 74 | 质量校验（必填/长度/分类/属性模板） |
| services/openmetadata_sync.py | 117 | OpenMetadata 同步与质量测试 |

### 3.4 测试 (backend/tests/)

| 文件 | 行数 | 职责 |
|------|------|------|
| 	ests/conftest.py | 148 | pytest fixtures（数据库、客户端、认证） |
| 	ests/test_api.py | 442 | API 集成测试 |
| 	ests/test_auth.py | 157 | 认证测试 |
| 	ests/test_crud.py | 271 | CRUD 测试 |
| 	ests/test_audit_service.py | 240 | 审计服务测试 |
| 	ests/test_code_generator.py | 148 | 编码生成测试 |
| 	ests/test_duplicate_detector.py | 236 | 重复检测测试 |
| 	ests/test_material_validator.py | 263 | 质量校验测试 |
| 	ests/test_configure_openmetadata.py | 24 | OpenMetadata 配置测试 |
| 	ools/configure_openmetadata.py | 147 | OpenMetadata 配置工具脚本 |

---

## 四、数据模型

### 4.1 实体关系

`
MaterialClassification (1) ───────< (N) MaterialApplication
       (三级分类：大类/中类/小类)
              │
              └──< (N) AttributeTemplate（属性模板，按分类定义字段）

MaterialApplication (1) ───────< (0..1) GoldenRecord
       (发布后生成)                    (权威主数据)

MaterialApplication (1) ───────< (N) AuditLog
       (全生命周期日志)

CodeRule (编码规则，独立表，关联分类)

ExternalSystemLog (外部系统交互日志：OpenMetadata / BTP，独立表)
`

> **注意**：用户认证为 Mock 字典（uth.py 中 MOCK_USERS），无独立 users 表。
> 申请的动态属性（ttribute_values）和附件（ttachments）以 JSON 列存储于 material_applications 表，无独立子表。

### 4.2 表清单（7 张）

| 表名 | 核心字段 | 职责 |
|------|----------|------|
| material_classifications | id, parent_id, code, name, level, is_active | 三级分类树（1=大类, 2=中类, 3=小类） |
| ttribute_templates | id, classification_id, field_name, field_type, is_required, options | 按分类定义的属性字段模板 |
| material_applications | id, app_no, material_name, classification_id, material_type, status, material_code, attribute_values(JSON), attachments(JSON) | 物料申请主表 |
| code_rules | id, name, pattern, prefix, current_seq, seq_length, classification_id | 编码规则 |
| golden_records | id, application_id, material_code, version, btp_published, om_synced | 权威主数据 |
| udit_logs | id, step_id, application_id, step_name, executed_by, status | 全链路审计日志 |
| external_system_logs | id, system_name, operation, entity_id, status, duration_ms | 外部系统交互日志 |

### 4.3 枚举

| 枚举 | 值 |
|------|------|
| MaterialType | raw / semi / finished / auxiliary / spare |
| ApplicationStatus | draft / pending_admin / pending_dept / approved / rejected / published |
| GoldenRecordStatus | active / obsolete |
| StepName | create_draft / save_draft / submit / validate / dedup_check / code_generate / admin_approve / dept_approve / create_gr / publish_btp / sync_om / om_test / revoke / edit / revise |

---

## 五、API 端点清单

### 5.1 认证（定义于 main.py）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/login | 用户登录，返回 JWT |
| GET | /api/auth/me | 当前用户信息 |

### 5.2 物料申请（/api/applications）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/applications/ | 申请列表（状态筛选/分页，申请人仅见自己） |
| POST | /api/applications/ | 创建申请 |
| GET | /api/applications/:id | 申请详情 |
| PUT | /api/applications/:id/draft | 编辑草稿 |
| POST | /api/applications/:id/attachments | 上传附件（仅草稿状态） |
| GET | /api/applications/:id/attachments/:attachment_id | 下载附件 |
| POST | /api/applications/:id/submit | 提交申请（触发校验/去重/编码） |
| POST | /api/applications/:id/admin-approve | 管理员审批 |
| POST | /api/applications/:id/dept-approve | 部门审批 |
| POST | /api/applications/:id/publish | 发布（创建 GR + BTP + OM） |
| GET | /api/applications/:id/audit | 审计轨迹 |

### 5.3 分类（/api/classifications）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/classifications/ | 分类树 |
| GET | /api/classifications/:id | 分类详情 |
| POST | /api/classifications/ | 创建分类 |
| GET | /api/classifications/:id/templates | 属性模板列表 |
| POST | /api/classifications/:id/templates | 创建属性模板 |

### 5.4 仪表盘 / Golden Record / 元数据治理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/dashboard | 仪表盘数据 |
| GET | /api/health | 健康检查 |
| GET | /api/btp-mock/health | BTP Mock 健康检查 |
| GET | /api/golden-records/ | Golden Record 列表 |
| GET | /api/golden-records/:id | Golden Record 详情 |
| GET | /api/golden-records/code/:material_code | 按编码查询 Golden Record |
| GET | /api/metadata-governance/overview | 元数据治理概览 |

---

## 六、端到端映射

### 6.1 页面 → API → 服务

| 页面 | 核心 API | 后端服务 |
|------|----------|----------|
| Login | POST /api/auth/login | uth.py |
| Dashboard | GET /api/dashboard | crud.py |
| Applications | GET /api/applications/ | crud.py |
| NewApplication | POST /api/applications/, GET /api/classifications/ | MaterialValidator, DuplicateDetector, CodeGenerator |
| ApplicationDetail | GET/POST /api/applications/:id/* | AuditService, crud.py |
| GoldenRecords | GET /api/golden-records/ | crud.py |
| MetadataGovernance | GET /api/metadata-governance/* | OpenMetadataSync |
| Classifications | GET /api/classifications/ | crud.py |
| AuditTrace | GET /api/applications/:id/audit | AuditService |

### 6.2 状态机（ApplicationStatus）

`
draft → submit → pending_admin/pending_dept → approved → published
                                    ↓
                              rejected（可驳回）
`

提交后由系统自动决定流转至 pending_admin 或 pending_dept，审批通过后进入 pproved，发布后变为 published。任何审批环节可驳回至 ejected。

### 6.3 提交事务（原子操作）

`
submit_application()
  ├── Step 1: MaterialValidator.validate()  → 质量校验
  ├── Step 2: DuplicateDetector.check()     → 重复预检
  ├── Step 3: CodeGenerator.generate()      → 编码生成（原子递增）
  ├── 写入: status + material_code + validation + dedup
  └── AuditService.log() × 4（validate/dedup/code_generate/submit）
`

### 6.4 发布流程

`
publish_application()
  ├── Step 1: create_golden_record()        → Golden Record 表
  ├── Step 2: BTPMockService.publish()      → 模拟 BTP 发布
  ├── Step 3: OpenMetadataSync.sync_material() → OM 同步
  └── Step 4: OpenMetadataSync.run_quality_tests() → 质量测试
`

---

## 七、架构决策

| 决策 | 选型 | 理由 |
|------|------|------|
| 前端框架 | React 19 + TypeScript | 类型安全、组件生态强 |
| 构建工具 | Vite 7 | 极速 HMR、ESM 原生 |
| UI 组件 | shadcn/ui (new-york) | 可定制、无运行时依赖 |
| 样式 | Tailwind CSS 3.4 | 原子化 CSS、主题可接 |
| 图表 | recharts | React 原生、可组合 |
| 路由 | react-router-dom v7 | SPA 标准路由方案 |
| 后端框架 | FastAPI + Pydantic v2 | 现代 Python API、自动文档（/docs /redoc） |
| ORM | SQLAlchemy 2.0 | 成熟可靠、支持多数据库 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） | 低成本启动、按需切换 |
| 认证 | JWT (python-jose) + bcrypt + Mock 用户字典 | 无状态、开发期免建用户表 |
| 包管理 | pnpm（前端） / uv（后端） | 平台约束 |

---

## 八、运行指南

### 前端开发

`ash
pnpm install        # 安装依赖
pnpm dev            # 开发服务器 (localhost:3000)
pnpm build          # 构建到 dist/
`

### 后端开发

`ash
cd backend
uv pip install --system -r requirements.txt    # 安装依赖
python init_db.py                              # 初始化数据库
uvicorn app.main:app --reload --port 8000      # 启动 API
`

### 开发环境

- 前端 port 3000，/api 代理到 localhost:8000
- 数据库默认 SQLite（开发）/ PostgreSQL（生产）
- OpenMetadata 和 BTP Mock 默认关闭（环境变量控制）

### 登录凭据

用户认证为 Mock 字典（ackend/app/core/auth.py 中 MOCK_USERS），共 5 个账号：

| 角色 | 用户名 | 密码 | 部门 |
|------|--------|------|------|
| 申请人 | user001 | password001 | 研发部 |
| 申请人 | user002 | password002 | 采购部 |
| 管理员 | dmin001 | dminpass001 | IT部 |
| 部门审批 | dept001 | deptpass001 | 生产部 |
| 数据管理员 | data001 | datapass001 | 数据治理部 |

---

## 九、待办事项与技术债务

| 项目 | 说明 | 优先级 |
|------|------|--------|
| src/lib/api.ts 缺失 | 前端 API 客户端文件不存在，需创建 fetch 封装 + JWT 注入 | 高 |
| 1.Ref-technical/ 空目录 | 参考资料目录无内容 | 低 |
| ackend/app/services/__init__.py 缺失 | 服务模块无包初始化 | 低 |
| docs/ 仅含本文件 | 缺 SPEC/TC/规划文档 | 中 |
| ackend/app/core/schema_compat.py | 运行时改表结构，应改为正式迁移 | 中 |
| Mock 用户密码硬编码 | 生产应替换为数据库认证 | 高 |
| 缺 Docker/Podman 部署配置 | 仅 Coze 平台脚本可用 | 中 |

---

## 十、文档分层

`
README.md                    → 项目入口（启动/架构/功能概览）
docs/knowledge-graph.md      → 本文档：完整代码资产图谱（当前 codebase）
    ├── AGENTS.md            → 工作区规则（技术栈/目录/约束）
    ├── info.md              → 项目初始化信息
    └── .superpowers/        → SDD 任务分片
`

> **提示**: 当前 codebase 中 docs/ 目录内容较少。完整的知识工程体系（SPEC/TC/ROADMAP）如有需要可另行补充。
