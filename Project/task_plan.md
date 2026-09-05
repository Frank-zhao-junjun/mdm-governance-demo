# MDM 主数据平台重构 —— 完整任务清单

> 从"单域硬编码"到"元数据驱动多域平台"
> 导出时间：2026-05-07
> 总任务数：44 | 预估总工时：约 11.5 周（2.5-3 个月）

---

## 阶段总览

| 阶段 | 任务数 | 预估工时 | 核心目标 |
|------|--------|----------|----------|
| Phase 0 | 6 | 1 周 | 当前巩固 + 生产准备 |
| Phase 1 | 6 | 1.5 周 | 数据库重构（元数据基础） |
| Phase 2 | 4 | 3 周 | 后端四大引擎 |
| Phase 3 | 6 | 1.5 周 | API 层 + 权限升级 |
| Phase 4 | 8 | 2.5 周 | 前端动态化 + 待办中心 |
| Phase 5 | 6 | 1 周 | 多域配置与验证 |
| Phase 6 | 8 | 1 周 | 生产部署 |

---

## 关键里程碑

| 时间点 | 里程碑 | 验收标准 |
|--------|--------|----------|
| 2.5 周 | 元数据基础 + 引擎就绪 | PG 迁移完成，DynamicValidator + CodeGenerator + DuplicateDetector 单元测试通过 |
| 5.5 周 | WorkflowEngine + API 就绪 | 能跑通一个完整的配置化审批流（从提交到发布） |
| 8 周 | 前端动态化完成 | 新增一个域只需要后端配置，前端自动渲染表单/列表/详情 |
| 9 周 | 物料域 100% 还原 | 元数据驱动下的物料功能与现有版本功能对等 |
| 10 周 | 供应商域上线 | 供应商准入流程端到端跑通 |
| 11.5 周 | 生产部署 | 可访问的 HTTPS 站点，数据持久化，文件走 OSS |

---

## Phase 0：当前巩固与生产准备（1 周）

优先级：P0 — 必须先完成，否则后续重构成本更高

### #1 — 0.1 数据库迁移：SQLite → PostgreSQL
- **状态**：in_progress
- **工时**：2 天
- **阻塞**：无（可并行启动）
- **说明**：将现有 SQLite 数据库迁移到 PostgreSQL。必需 PG 的 JSONB + GIN 支持。包括安装配置 PG、数据导出导入、替换 SQLAlchemy 连接、验证 CRUD。

### #2 — 0.2 抽象文件存储层：StorageService 接口
- **状态**：in_progress
- **工时**：1.5 天
- **阻塞**：无（可并行启动）
- **说明**：定义 StorageService 接口（upload/download/delete/get_url），实现 LocalStorageProvider 和 OSSStorageProvider，.env 配置化切换，替换所有直接本地文件读写逻辑。

### #3 — 0.3 环境配置生产化：.env 分离开发/生产
- **状态**：in_progress
- **工时**：1 天
- **阻塞**：无（可并行启动）
- **说明**：.env.development / .env.production / .env.example 分离，SECRET_KEY 独立生成，JWT 过期时间可调，启动时校验必要环境变量。

### #4 — 0.4 CORS 白名单改为配置项，生产禁止 *
- **状态**：in_progress
- **工时**：0.5 天
- **阻塞**：无（可并行启动）
- **说明**：CORS_ORIGINS 改为列表配置，生产环境严格白名单，禁止 *，预检请求缓存配置。

### #5 — 0.5 用户系统从 MOCK_USERS 迁移到真实数据库表
- **状态**：in_progress
- **工时**：1.5 天
- **阻塞**：无（可并行启动）
- **说明**：创建 mdm_user 表，实现密码哈希，初始化管理员脚本，替换所有 MOCK_USERS 引用为数据库查询。

### #6 — 0.6 补充关键接口的异常测试
- **状态**：in_progress
- **工时**：2 天
- **阻塞**：无（可并行启动）
- **说明**：补充并发提交、越权访问、重复审批、文件上传异常、数据库断连等场景的自动化测试。

---

## Phase 1：数据库重构 - 元数据基础（1.5 周）

优先级：P0 — 地基，不改后面全崩

### #7 — 1.1 设计并创建元数据配置表
- **状态**：in_progress
- **工时**：3 天
- **阻塞**：#6（PG 迁移）
- **说明**：创建 mdm_domain、mdm_entity_schema、mdm_validation_rule、mdm_code_rule、mdm_duplicate_rule 五张核心配置表，含索引和审计字段。

### #8 — 1.2 创建统一业务实体表
- **状态**：in_progress
- **工时**：2 天
- **阻塞**：#6（PG 迁移）
- **说明**：创建 mdm_application（申请单）和 mdm_golden_record（金记录），通用字段平铺 + json_data(JSONB)，按 domain/entity_type 建索引。

### #9 — 1.3 重构现有模型
- **状态**：in_progress
- **工时**：2 天
- **阻塞**：#6（PG 迁移）、#5（用户系统）
- **说明**：分类表增加 domain 字段；审计日志改为 entity_type + entity_id 多态关联；旧表标记 deprecated 保留为迁移源。

### #10 — 1.4 数据迁移脚本：洗入 json_data
- **状态**：in_progress
- **工时**：2 天
- **阻塞**：#8（统一业务实体表）、#9（重构现有模型）
- **说明**：将现有物料数据映射为 JSON 结构迁移到新表，支持幂等执行，含回滚脚本，数据校验对比条数完整性。

### #11 — 1.5 为 json_data 高频查询字段建索引
- **状态**：in_progress
- **工时**：1 天
- **阻塞**：#8（统一业务实体表）
- **说明**：创建 GIN 索引（json_data）和 B-tree 函数索引（entity_code, entity_name, created_by 等），EXPLAIN ANALYZE 验证命中。

### #12 — 1.6 启用 pg_trgm 扩展
- **状态**：in_progress
- **工时**：0.5 天
- **阻塞**：#6（PG 迁移）
- **说明**：启用 pg_trgm，为常用文本字段创建 GIN trigram 索引，验证 similarity() 和 % 操作符可用性。

---

## Phase 2：后端四大核心引擎（3 周）

优先级：P0 — 决定能否真正"零代码"扩展

### #13 — 2.1 动态校验引擎
- **状态**：in_progress
- **工时**：3 天
- **阻塞**：#7（元数据配置表）
- **说明**：构建规则注册表（min_length, max_length, regex, range, unique, luhn...），DynamicValidator 核心类加载 schema 执行校验链，唯一性校验利用 PG 函数索引，单元测试全覆盖。

### #14 — 2.2 动态编码引擎
- **状态**：in_progress
- **工时**：2 天
- **阻塞**：#7（元数据配置表）
- **说明**：模板渲染器解析 {YYYY}, {domain_seq:N}, {classification} 等占位符；原子流水号生成（seq_key 隔离，PG advisory lock / Redis INCR 防并发）；编码规则管理 API（含预览）。

### #15 — 2.3 动态查重引擎
- **状态**：in_progress
- **工时**：2 天
- **阻塞**：#7（元数据配置表）、#10（pg_trgm）
- **说明**：查重策略执行器（exact / fuzzy / composite）；PG pg_trgm + similarity() 模糊匹配；结果动作 block / warn / auto_merge；实时查重 API。

### #16 — 2.4 WorkflowEngine（核心）
- **状态**：in_progress
- **工时**：8 天
- **阻塞**：#7（元数据配置表）、#8（统一业务实体表）、#13（校验引擎）、#14（编码引擎）、#15（查重引擎）
- **说明**：
  - 模型：mdm_workflow_template, mdm_workflow_step, mdm_workflow_instance, mdm_workflow_task, mdm_workflow_history
  - 核心方法：start / enter_step / create_task / execute_action / auto_advance / evaluate_gateway / transfer_task / recall / sync_entity_status
  - 自动动作注册表：validation / code_gen / duplicate_check / credit_check / webhook / notify
  - 乐观锁防并发、30 分钟撤回窗口、排他网关条件求值

---

## Phase 3：API 层重构 + 权限升级（1.5 周）

优先级：P1 — 功能完整性

### #17 — 3.1 权限模型升级
- **状态**：in_progress
- **工时**：2 天
- **阻塞**：#5（用户系统）
- **说明**：mdm_user_role 表（user_id + domain + role + scope_type + scope_value）；require_role_in_domain 中间件；行级权限过滤函数（global/department/self）；权限初始化脚本。

### #18 — 3.2 通用业务 API
- **状态**：in_progress
- **工时**：2 天
- **阻塞**：#8（统一业务实体表）、#16（WorkflowEngine）
- **说明**：POST /api/:domain/applications（创建草稿）；PUT /api/:domain/applications/:id/draft；POST /api/:domain/applications/:id/submit；GET /api/:domain/applications（列表+筛选+排序+分页）；GET /api/:domain/golden-records。

### #19 — 3.3 Schema 配置 API
- **状态**：in_progress
- **工时**：1 天
- **阻塞**：#7（元数据配置表）
- **说明**：GET /api/domains（可用域列表）；GET /api/schema/:domain（字段+校验+编码+查重+工作流模板）；Redis 缓存 5 分钟，变更主动失效。

### #20 — 3.4 工作流 API
- **状态**：in_progress
- **工时**：1.5 天
- **阻塞**：#16（WorkflowEngine）
- **说明**：POST /api/workflow/tasks/:task_id/execute；POST /api/workflow/tasks/:task_id/transfer；POST /api/workflow/instances/:id/recall；GET /api/workflow/instances/:id/timeline。

### #21 — 3.5 待办中心 API
- **状态**：in_progress
- **工时**：2 天
- **阻塞**：#16（WorkflowEngine）
- **说明**：GET /api/workflow/tasks/pending；GET /api/workflow/tasks/completed；GET /api/workflow/tasks/initiated；GET /api/workflow/tasks/counts；GET /api/workflow/tasks/:task_id；POST /api/workflow/tasks/batch-execute。

### #22 — 3.6 Dashboard API 重构
- **状态**：in_progress
- **工时**：1 天
- **阻塞**：#18（通用业务 API）
- **说明**：GET /api/dashboard/stats（按 domain 聚合：申请单状态数、金记录数、待办数、7 天趋势、分类占比）；GET /api/dashboard/activities；Redis 缓存 1 分钟。

---

## Phase 4：前端动态化 + 待办中心（2.5 周）

优先级：P1 — 用户体验

### #23 — 4.1 路由改造
- **状态**：in_progress
- **工时**：1 天
- **阻塞**：#18（通用业务 API）、#19（Schema 配置 API）
- **说明**：新路由结构 /:domain/applications/new, /:domain/applications/:id, /:domain/golden-records, /todo-center, /admin/schema；路由守卫校验 domain；面包屑动态生成；旧路由兼容重定向。

### #24 — 4.2 前端类型重构
- **状态**：in_progress
- **工时**：1 天
- **阻塞**：#19（Schema 配置 API）
- **说明**：定义 BaseEntity / Application / GoldenRecord 通用类型（json_data）；删除旧 MaterialApplication / MaterialGoldenRecord；类型工具 JsonDataGetter；Schema 相关类型定义。

### #25 — 4.3 DynamicForm 组件
- **状态**：in_progress
- **工时**：4 天
- **阻塞**：#19（Schema 配置 API）、#24（前端类型重构）
- **说明**：支持 text/number/date/select/boolean/textarea/file/ref 字段类型；字段级校验；联动逻辑（A 控制 B 显示/隐藏/必填）；文件上传进度；关联选择弹窗；分组展示；自动保存草稿（debounce 5s）。

### #26 — 4.4 DynamicTable 组件
- **状态**：in_progress
- **工时**：3 天
- **阻塞**：#18（通用业务 API）、#19（Schema 配置 API）、#24（前端类型重构）
- **说明**：按 schema 的 is_filterable 生成筛选栏；按 is_searchable 加入全局搜索；列可配置（显隐/拖拽/本地缓存）；分页/排序/批量操作；空状态/加载状态/错误状态。

### #27 — 4.5 DynamicDetail 组件
- **状态**：in_progress
- **工时**：1.5 天
- **阻塞**：#18（通用业务 API）、#19（Schema 配置 API）、#24（前端类型重构）
- **说明**：只读渲染实体详情；分组展示；操作栏（编辑/提交/撤回/审批）；流程状态卡片；审计日志快捷查看。

### #28 — 4.6 分类选择器改造
- **状态**：in_progress
- **工时**：1 天
- **阻塞**：#18（通用业务 API）
- **说明**：支持按 domain 加载分类树；GET /api/:domain/classifications?tree=true；缓存分类树（5 分钟）；级联/树形选择器组件。

### #29 — 4.7 待办中心页面
- **状态**：in_progress
- **工时**：3 天
- **阻塞**：#20（工作流 API）、#21（待办中心 API）、#25（DynamicForm）、#27（DynamicDetail）
- **说明**：Tab 切换（待办/已办/我发起）；列表卡片（含快速操作）；审批弹窗（意见+附件+确认）；流程时间轴 Timeline；批量操作；Pinia 状态管理。

### #30 — 4.8 管理后台（Schema & 工作流配置）
- **状态**：in_progress
- **工时**：3 天
- **阻塞**：#19（Schema 配置 API）、#20（工作流 API）
- **说明**：域管理、字段配置（表单+拖拽排序）、校验规则配置、编码规则配置（含预览）、查重规则配置、工作流模板/步骤/网关配置（表单版）、版本管理。

---

## Phase 5：多域配置与验证（1 周）

优先级：P0 — 验证架构是否真正可用

### #31 — 5.1 物料域 Schema 配置
- **状态**：in_progress
- **工时**：2 天
- **阻塞**：#26（管理后台）、#13（校验引擎）、#14（编码引擎）、#15（查重引擎）
- **说明**：所有现有物料字段录入 mdm_entity_schema；录入校验规则、编码规则、查重规则；录入现有审批流配置。目标：物料功能在元数据驱动下 100% 还原现有能力。

### #32 — 5.2 供应商域 Schema 配置
- **状态**：in_progress
- **工时**：1.5 天
- **阻塞**：#26（管理后台）、#13（校验引擎）、#14（编码引擎）、#15（查重引擎）
- **说明**：字段：供应商名称、统一社会信用代码、银行账号、营业执照、资质等级、联系人、年交易额等；校验：统一社会信用代码正则、银行卡号 Luhn 校验；编码：VN-{YYYY}-{domain_seq:5}；查重：代码 exact block，名称 fuzzy warn。

### #33 — 5.3 供应商准入工作流配置
- **状态**：in_progress
- **工时**：1.5 天
- **阻塞**：#16（WorkflowEngine）、#31（供应商域 Schema）
- **说明**：提交 → 自动校验 → 征信查询 → 采购初审 → 财务审核 → 法务审核 → [网关：年交易额>500万？总经理审批：直接入库] → 已入库。

### #34 — 5.4 客户域 Schema 配置（可选）
- **状态**：in_progress
- **工时**：1 天
- **阻塞**：#26（管理后台）、#13（校验引擎）、#14（编码引擎）、#15（查重引擎）
- **说明**：字段：客户名称、统一社会信用代码、客户类型、信用等级、授信额度、销售区域；校验：授信额度范围、手机号格式；编码：CU-{YYYY}-{domain_seq:5}。

### #35 — 5.5 客户主数据工作流配置（可选）
- **状态**：in_progress
- **工时**：1 天
- **阻塞**：#16（WorkflowEngine）、#34（客户域 Schema）
- **说明**：客户准入/变更审批流程配置。

### #36 — 5.6 跨域回归测试
- **状态**：in_progress
- **工时**：2 天
- **阻塞**：#31（物料域）、#32（供应商域）、#33（供应商工作流）、#29（待办中心页面）
- **说明**：物料域全流程回归；供应商域全流程回归；客户域全流程（如配置）；交叉测试（数据隔离、权限边界）；性能测试（并发 50 申请单、1000 条列表 <500ms）。产出：测试报告 + 缺陷清单。

---

## Phase 6：生产部署（1 周）

优先级：P1 — 真实可用

### #37 — 6.1 Docker 化：后端 + 前端
- **状态**：in_progress
- **工时**：1 天
- **阻塞**：#36（跨域回归测试）
- **说明**：后端 Dockerfile（python:3.11-slim，多阶段构建，非 root 运行）；前端 Dockerfile（node:20-alpine 构建 + nginx:alpine 运行）；.dockerignore；健康检查。

### #38 — 6.2 docker-compose.yml 编排
- **状态**：in_progress
- **工时**：0.5 天
- **阻塞**：#37（Docker 化）
- **说明**：编排 postgres:15-alpine + redis:7-alpine + backend + frontend-nginx；数据卷持久化；内部网络隔离。

### #39 — 6.3 对象存储接入
- **状态**：in_progress
- **工时**：1 天
- **阻塞**：#2（StorageService）、#37（Docker 化）
- **说明**：接入阿里云 OSS / AWS S3 / Cloudflare R2 / MinIO；预签名 URL；文件上传安全（后缀/MIME/大小限制）；私有 bucket；存量文件迁移脚本。

### #40 — 6.4 PostgreSQL 生产配置
- **状态**：in_progress
- **工时**：1 天
- **阻塞**：#38（docker-compose）
- **说明**：连接池优化（max_connections, shared_buffers, work_mem）；pg_dump 每日全量备份 + WAL 归档；只读副本（可选）；慢查询日志；SSL 强制；网络隔离。

### #41 — 6.5 Nginx 反向代理 + SSL
- **状态**：in_progress
- **工时**：0.5 天
- **阻塞**：#37（Docker 化）
- **说明**：反向代理（前端静态 + API + 文件）；Let's Encrypt / 云厂商 SSL；HTTP/2；80→443 跳转；限流 50 req/s；安全头部；gzip；静态文件缓存 30 天。

### #42 — 6.6 日志聚合
- **状态**：in_progress
- **工时**：0.5 天
- **阻塞**：#37（Docker 化）
- **说明**：结构化 JSON 日志（timestamp, level, request_id, user_id, domain, duration_ms）；access.log / app.log / error.log / audit.log 分离；logrotate 按天切割保留 30 天。

### #43 — 6.7 监控与健康检查
- **状态**：in_progress
- **工时**：0.5 天
- **阻塞**：#37（Docker 化）
- **说明**：/health / /health/ready / /health/live 端点；Prometheus 指标（请求数/响应时间/错误率/业务指标）；systemd/supervisor 守护进程；告警阈值（错误率>1%，P99>2s，磁盘<20%）。

### #44 — 6.8 CI/CD 流水线
- **状态**：in_progress
- **工时**：1 天
- **阻塞**：#37（Docker 化）
- **说明**：GitHub Actions：lint → 单元测试 → 构建镜像 → trivy 安全扫描 → push 镜像 → SSH 部署；工作流：ci.yml / deploy-staging.yml / deploy-prod.yml（需 manual approve）；构建结果通知。

---

## 进阶优化（P2 - 后续迭代）

| 模块 | 说明 | 建议时机 |
|------|------|----------|
| Elasticsearch 集成 | 百万级全文搜索 + 聚合分析 | 数据量超 10 万 |
| 并行网关 + 会签 | 复杂审批（多部门同时审批） | 有真实业务需求 |
| 消息推送（WebSocket/SSE） | 实时待办通知、审批结果推送 | Phase 4 后可做 |
| 数据血缘可视化 | OpenMetadata 深度集成 | 有数据治理团队 |
| 移动端适配 | H5 或小程序审批中心 | 管理层高频需求 |
| SaaS 多租户 | tenant_id 隔离 | 商业化阶段 |

---

## 任务依赖图（简版）

```
Phase 0:  #1 #2 #3 #4 #5 #6 (并行)
            ↓   ↓
Phase 1:  #7 #8 #9 #10 #11 #12
            ↓
Phase 2:  #13 #14 #15 #16
            ↓
Phase 3:  #17 #18 #19 #20 #21 #22
            ↓
Phase 4:  #23 #24 #25 #26 #27 #28 #29 #30
            ↓
Phase 5:  #31 #32 #33 #34 #35 #36
            ↓
Phase 6:  #37 #38 #39 #40 #41 #42 #43 #44
```

> 完整依赖关系见各任务的【阻塞】字段。

---

*本文件由自动化工具生成，后续任务状态更新需手动同步或使用 Task 工具管理。*
