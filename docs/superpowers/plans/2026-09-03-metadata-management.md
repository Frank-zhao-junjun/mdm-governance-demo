# 元数据管理模块实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为存量数据治理平台新增元数据管理模块（字段登记册 + 实体元数据 + 术语表），作为数据标准的单一权威字段来源。

**Architecture:** 方案一——登记册独立成表（metadata_field / metadata_entity / glossary_term 三张新表），data_standards 加 `metadata_field_id` 外键引用登记册；后端新增第 9 个 router `/api/metadata`；前端新增 `/metadata` 页面（三 Tab）。种子 70 个核心字段（SAP MARA/MAKT 基本视图 30 + 供应商 BUT000/LFA1/Ariba SLP 25 + 客户 BUT000/KNA1 15）。

**Tech Stack:** FastAPI 0.115 + SQLAlchemy 2.0 + Pydantic v2（后端）；React 19 + TS + shadcn/ui + Tailwind（前端）

**设计文档:** `docs/superpowers/specs/2026-09-03-metadata-management-design.md`（字段清单全表在 §4.1，实现时必须照抄）

## Global Constraints

- 所有 API 需 JWT；读操作 `Depends(require_any)`，写操作 `Depends(require_admin)`（require_admin 实际放行 admin + data_admin 双角色）
- 409/404 的 detail 用中文；403 不手写（require_admin 内部抛）
- 后端分层 api → services → crud；crud 函数首参 `db: Session`，列表返回 `Tuple[List[Model], int]`，create/update 内部自行 commit+refresh
- 后端注释/日志/docstring 中文为主；测试用类分组 + 中文 docstring
- 前端**不用** react-hook-form/zod——现有表单是 `useState` + 手写校验函数模式（参照 `src/components/standards/DataStandardFormDialog.tsx`）
- 前端领域模块（`src/lib/*.ts`）零网络代码，请求直接 `import { api } from '@/lib/api'`；按钮显隐用 `canWrite()`
- Radix Select 不允许 `value=""`，"不限"用哨兵 `'all'`，可选清空用 `'__none__'`
- 前端必须 pnpm；验证链 = `pnpm lint` 零错误 + `npx tsc --noEmit` + `pnpm build`
- 后端全量测试：`cd backend && ENV=test SQLALCHEMY_DATABASE_URL="sqlite:///:memory:" python -m pytest -q`（现 310 用例必须全绿）
- 写操作落审计：`AuditService(db).log(step_name=..., executed_by=user["id"], executed_by_name=user["name"], details={...})`，StepName 需加枚举值
- models.py 新表惯例：`id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))`，时间戳用 `_now_utc`

---

### Task 1: 后端模型与契约（models + schemas + crud）

**Files:**
- Modify: `backend/app/models.py`（StepName 枚举 + 3 个新表类 + DataStandard 加列）
- Modify: `backend/app/schemas.py`（元数据四件套）
- Modify: `backend/app/crud.py`（metadata 分节）
- Test: `backend/tests/test_metadata.py`（本任务先建文件，写模型层用例）

**Interfaces（后续任务依赖的确切名字）:**
- `models.MetadataField`：列 = id, entity_type, sap_table, field_name, field_label, data_type, max_length, view_section, business_definition, standard_source, must_govern, glossary_term_id(FK→glossary_term.id, nullable), is_active, created_at, updated_at；`__table_args__ = (UniqueConstraint("entity_type", "sap_table", "field_name", name="uq_metadata_entity_table_field"),)`
- `models.MetadataEntity`：列 = id, entity_type(unique, index), display_name, business_definition, data_owner, dept, tags(JSON), sensitivity_level, created_at, updated_at
- `models.GlossaryTerm`：列 = id, term(unique), definition, aliases(JSON), created_at, updated_at
- `models.DataStandard.metadata_field_id = Column(String(36), ForeignKey("metadata_field.id"), nullable=True)`
- StepName 新增枚举值：`METADATA_ENTITY_UPDATE = "metadata_entity_update"`、`METADATA_FIELD_CREATE = "metadata_field_create"`、`METADATA_FIELD_UPDATE = "metadata_field_update"`、`GLOSSARY_CREATE = "glossary_create"`、`GLOSSARY_UPDATE = "glossary_update"`
- schemas 四件套命名：`MetadataFieldBase/Create/Update/Response/ListResponse`、`MetadataEntityBase/Update/Response`、`GlossaryTermBase/Create/Update/Response`；`MetadataEntityResponse` 额外带 `governed_field_count: int` 与 `total_field_count: int`（由 service 装配）
- crud 函数：`get_metadata_fields(db, entity_type=None, view_section=None, must_govern=None, keyword=None, skip=0, limit=50) -> Tuple[List[MetadataField], int]`、`get_metadata_field(db, field_id)`、`find_metadata_field_conflict(db, entity_type, sap_table, field_name)`、`create_metadata_field(db, data)`、`update_metadata_field(db, field, data)`、`get_metadata_entities(db) -> List[MetadataEntity]`、`get_metadata_entity(db, entity_type)`、`update_metadata_entity(db, entity, data)`、`get_glossary_terms(db) -> List[GlossaryTerm]`、`create_glossary_term(db, data)`、`update_glossary_term(db, term, data)`、`count_standards_referencing_field(db, metadata_field_id) -> int`（按 DataStandard.metadata_field_id 计数）

- [ ] **Step 1: 写失败测试** `backend/tests/test_metadata.py` 模型层用例：直接 `db.add(models.MetadataField(...))` 可落库；唯一约束冲突抛 IntegrityError；`DataStandard(metadata_field_id=...)` 可写入。conftest 已有 `db` fixture（裸库）可用。
- [ ] **Step 2: 跑测试确认失败** `cd backend && ENV=test SQLALCHEMY_DATABASE_URL="sqlite:///:memory:" python -m pytest tests/test_metadata.py -q` → 预期 ImportError/AttributeError
- [ ] **Step 3: 实现** models.py 加 3 个类 + StepName 5 个枚举值 + DataStandard 加列（ForeignKey 需在文件头确认已 import ForeignKey）；schemas.py 加四件套（字段约束仿 DataStandardBase：entity_type pattern `^(material|supplier|customer)$`，standard_source pattern 改为 `^(sap|ariba_slp|internal)$`，data_type 同现有枚举，sensitivity_level pattern `^(public|internal|confidential)$`）；crud.py 加 `# ========== Metadata ==========` 分节函数
- [ ] **Step 4: 跑测试确认通过**，再跑全量 `python -m pytest -q` 确认 310 旧用例无回归

### Task 2: init_db.py 种子（70 字段 + 3 实体 + 15 术语 + 29 标准回填）

**Files:**
- Modify: `backend/init_db.py`
- Test: `backend/tests/test_metadata.py`（加种子验证用例：直接调 `init_db()` 后断言数量）

**Interfaces:**
- 新增函数 `seed_metadata(db) -> dict`（返回 `{"fields": {三键: MetadataField}, "terms": {...}}` 供回填使用）；在 `init_db()` 中顺序：`standards = _standard_rows()` → `db.add_all(standards)` → `db.flush()` → `metadata = seed_metadata(db)` → 回填循环：对每条 standard 用 `(entity_type, sap_table, field_name)` 查 `metadata["fields"]`，命中则 `standard.metadata_field_id = field.id`，未命中则在 seed_metadata 的字段表中补一条（must_govern=True，standard_source 沿用标准的）再回填——保证 29/29。
- 字段种子数据结构：`METADATA_FIELDS = [(entity_type, sap_table, field_name, field_label, data_type, max_length, view_section, standard_source, business_definition), ...]`，70 条**严格照抄** spec §4.1 三张表（material 30 / supplier 25 / customer 15，全部 must_govern=True）
- `GLOSSARY_TERMS = [(term, definition, [aliases]), ...]` 15 条（spec §4.3 列名，definition 一句话中文），术语→字段关联：物料编码→MATNR、物料描述→MAKTX、基本计量单位→MEINS、物料组→MATKL、物料类型→MTART、业务伙伴→PARTNER(supplier)、供应商编号→LIFNR、客户编号→KUNNR、税号→STCD1(supplier)、邓白氏编码→DUNSNumber 等
- `METADATA_ENTITIES` 3 条照抄 spec §4.2

- [ ] **Step 1: 写失败测试** `test_seed_metadata`：调用 `init_db()`（注意它会 drop_all 重建——测试内用独立内存库 engine，参照 conftest 模式临时替换，或直接在测试里 import init_db 模块函数作用于 TestingSessionLocal；若耦合过深，改为在测试里手动调 `seed_metadata(db)` + `_standard_rows()` 回填逻辑断言）。断言：metadata_field 70 条、metadata_entity 3 条、glossary_term 15 条、29 条 DataStandard 的 metadata_field_id 全部非空。
- [ ] **Step 2: 跑确认失败**
- [ ] **Step 3: 实现种子**（70 字段从 spec §4.1 逐行转元组）
- [ ] **Step 4: 跑测试通过 + 真实跑一次 `python init_db.py` 看输出无异常**

### Task 3: metadata API 路由

**Files:**
- Create: `backend/app/api/metadata.py`
- Modify: `backend/app/main.py`（import + include_router 两行）
- Create: `backend/app/services/metadata_service.py`（实体总览统计装配：每个实体的 must_govern 字段数/总字段数）
- Test: `backend/tests/test_metadata.py`（追加 API 用例）

**Interfaces:**
- `metadata_service.get_entity_overview(db) -> List[dict]`：每项 = MetadataEntity 字段 + `governed_field_count` + `total_field_count`
- 端点（全部仿 owners.py 风格，写操作落审计）：
  - `GET /api/metadata/entities`（require_any）→ 返回 overview 列表
  - `PUT /api/metadata/entities/{entity_type}`（require_admin，404「实体元数据不存在」）→ 审计 step METADATA_ENTITY_UPDATE
  - `GET /api/metadata/fields`（require_any；参数 entity_type / view_section / must_govern: Optional[bool] / keyword / skip / limit）→ `{total, items}`；keyword 对 field_name+field_label 做 `ilike` 模糊
  - `POST /api/metadata/fields`（require_admin，201；冲突 409「同（实体, SAP表, 字段）的元数据字段已存在」）→ 审计 METADATA_FIELD_CREATE
  - `PUT /api/metadata/fields/{field_id}`（require_admin，404「元数据字段不存在」；空 payload 400「未提供可更新字段」）→ 审计 METADATA_FIELD_UPDATE
  - `GET /api/metadata/glossary`（require_any）→ 列表，每项带 `field_count`（关联字段数）
  - `POST /api/metadata/glossary`（require_admin，201；term 重复 409「术语已存在」）→ 审计 GLOSSARY_CREATE
  - `PUT /api/metadata/glossary/{term_id}`（require_admin，404「术语不存在」）→ 审计 GLOSSARY_UPDATE

- [ ] **Step 1: 写失败测试**（类分组仿 test_data_standards_api.py）：`TestReadAccess`（匿名 401、三角色可读）、`TestWritePermissions`（client/dept_client 写 403，data_client 写 200/201——注意 conftest 无 admin fixture，data_admin 即写角色）、`TestFieldCRUD`（创建→列表可见→keyword 过滤→must_govern 过滤→重复创建 409→更新→空更新 400）、`TestEntityOverview`（3 实体 + 计数字段正确）、`TestEntityUpdate`（404 + 正常更新）、`TestGlossary`（CRUD + 409 + field_count）
- [ ] **Step 2: 跑确认失败**（404/405）
- [ ] **Step 3: 实现** metadata.py + metadata_service.py + main.py 注册（import 行按字母序插入 `metadata`，include_router 加在 owners 后）
- [ ] **Step 4: 测试通过 + 全量无回归**

### Task 4: data_standards 外键带入

**Files:**
- Modify: `backend/app/api/data_standards.py`（create/update 接受 metadata_field_id 并带入）
- Modify: `backend/app/schemas.py`（DataStandardCreate/Update/Response 加 metadata_field_id；Response 加只读带出 `metadata_field_label` / `metadata_view_section` 可空）
- Test: `backend/tests/test_metadata.py` 追加 `TestStandardFieldLink`

**Interfaces:**
- 行为契约：POST/PUT data-standards 传 `metadata_field_id` 时——① 登记册字段必须存在（404「关联的元数据字段不存在」）；② 以登记册为准覆盖 entity_type/sap_table/field_name/data_type/max_length（field_label 若 payload 未显式给出则也用登记册的）；③ 409 唯一键检查在带入之后执行
- Response 组装：api 层查出关联字段后填 `metadata_field_label`、`metadata_view_section`

- [ ] **Step 1: 写失败测试**：带 metadata_field_id 创建标准 → 响应中 field_name/data_type 与登记册一致；不存在的 metadata_field_id → 404；带入后与既有标准撞唯一键 → 409；不传 metadata_field_id 的旧行为不变（回归）
- [ ] **Step 2-4:** 失败确认 → 实现 → 通过 + 全量回归

### Task 5: 前端类型与领域库

**Files:**
- Modify: `src/types/api.ts`
- Create: `src/lib/metadata.ts`

**Interfaces:**
- types 新增（注释注明对应后端 schema）：
  - `export type MetadataSource = 'sap' | 'ariba_slp' | 'internal'`
  - `export type SensitivityLevel = 'public' | 'internal' | 'confidential'`
  - `export interface MetadataField { id, entity_type: EntityType, sap_table: string | null, field_name, field_label, data_type: StandardDataType, max_length: number | null, view_section: string | null, business_definition: string | null, standard_source: MetadataSource, must_govern: boolean, glossary_term_id: string | null, is_active: boolean, created_at: string, updated_at: string }`
  - `MetadataFieldListResponse { total, items }`、`MetadataFieldCreatePayload`、`MetadataFieldUpdatePayload`（全可选，不含身份键）
  - `MetadataEntity { id, entity_type, display_name, business_definition, data_owner, dept, tags: string[], sensitivity_level: SensitivityLevel, governed_field_count: number, total_field_count: number, created_at, updated_at }`
  - `MetadataEntityUpdatePayload { display_name?, business_definition?, data_owner?, dept?, tags?, sensitivity_level? }`
  - `GlossaryTerm { id, term, definition, aliases: string[], field_count: number, created_at, updated_at }`、`GlossaryTermCreatePayload { term, definition, aliases? }`、`GlossaryTermUpdatePayload`
  - `DataStandard` 接口加 `metadata_field_id?: string | null; metadata_field_label?: string | null; metadata_view_section?: string | null`
- lib/metadata.ts（零网络代码，仿 governance.ts）：
  - `METADATA_SOURCE_OPTIONS/LABELS`（sap=SAP 标准 / ariba_slp=Ariba SLP / internal=内部自定义）
  - `SENSITIVITY_OPTIONS/LABELS`（public=公开 / internal=内部 / confidential=机密）
  - 表单模型：`FieldFormValues/emptyFieldForm/fieldFormFromField/validateFieldForm/hasFieldFormErrors/toFieldCreatePayload/toFieldUpdatePayload`；`EntityFormValues/...`；`GlossaryFormValues/...`（tags、aliases 用 `splitList` 复用 governance.ts 的导出）

- [ ] **Step 1: 实现两个文件**
- [ ] **Step 2: `npx tsc --noEmit` 通过**

### Task 6: 前端 Metadata 页面（三 Tab）

**Files:**
- Create: `src/pages/Metadata.tsx`
- Modify: `src/App.tsx`（import + Route `/metadata`）
- Modify: `src/components/Layout.tsx`（NAV_ITEMS 加 `{ path: '/metadata', label: '元数据管理', icon: BookMarked }`，lucide import 加 BookMarked，位置放「数据标准管理」之后）

**Interfaces:**
- 页面结构：顶部 `Tabs` 做三面板切换（项目无 TabsContent 先例，用 `value` state + 条件渲染三个区块：`'entities' | 'fields' | 'glossary'`）
- **实体总览**：`GET /api/metadata/entities` → 三卡片（grid md:grid-cols-3），卡片显示 display_name、business_definition、data_owner、dept、敏感等级 Badge（confidential 红 / internal 黄 / public 灰）、tags Badge 组、`必须治理 X / 共 Y 字段`；`canWrite()` 显示编辑按钮 → Dialog（useState 表单模式，字段：display_name/business_definition(Textarea)/data_owner/dept/tags(逗号分隔 Input)/sensitivity_level(Select)），保存 `PUT /api/metadata/entities/{entity_type}`，成功 toast.success + reload
- **字段登记册**：筛选条 = Select(实体类型，含'全部'哨兵) + Select(视图分组，选项由当前已加载数据 `view_section` 去重生成) + Switch 或 Select(只看必须治理，默认开=must_govern:true) + Input(关键词) + 刷新 + 「登记新字段」按钮(canWrite)；请求 `GET /api/metadata/fields?...`（参数映射同名 query）；表格列：字段名(font-mono)、中文标签、实体 Badge、SAP表、视图、类型 Badge、来源 Badge、必须治理(是/—)、业务定义(truncate)；操作列（canWrite）：编辑 Dialog。分页沿用上一页/下一页按钮模式
- **术语表**：`GET /api/metadata/glossary` → 表格（术语/定义/别名/关联字段数），canWrite 显示「新增术语」+ 行内编辑，Dialog 表单（term/definition(Textarea)/aliases）
- 渲染三分支（loadError / loading Spinner / Empty）与 DataStandards.tsx 完全一致；请求全部 `api<T>(..., { silentError: true })`

- [ ] **Step 1: 实现页面与接线**
- [ ] **Step 2: `pnpm lint` 零错误 + `npx tsc --noEmit` + `pnpm build` 全通过**

### Task 7: 标准表单字段下拉改造

**Files:**
- Modify: `src/components/standards/DataStandardFormDialog.tsx`
- Modify: `src/lib/governance.ts`（StandardFormValues 加 `metadata_field_id: string`；emptyForm/formFromStandard/toCreatePayload 同步）

**Interfaces:**
- 行为：标识信息区「SAP 表 + 字段名」手填改为单个「元数据字段」Select——选项来自 `GET /api/metadata/fields?entity_type=<当前实体>&limit=200`，label 显示 `{sap_table}·{field_name} — {field_label}`；选中后 setField 联动带入 sap_table/field_name/field_label/data_type/max_length 且这些 Input 变只读（disabled）；「清除关联」后恢复手填（metadata_field_id 置空）。编辑态若有 metadata_field_id 同样展示关联字段名（只读）
- payload：toCreatePayload/toUpdatePayload 在有 metadata_field_id 时带上它

- [ ] **Step 1: 实现**
- [ ] **Step 2: `pnpm lint` + `npx tsc --noEmit` + `pnpm build` 通过**

### Task 8: 文档同步与最终验证

**Files:**
- Modify: `AGENTS.md`（目录结构补 api/metadata.py、services/metadata_service.py、3 张新表（14→17）、新页面 /metadata、测试数更新；项目概述补元数据管理能力）
- Modify: `docs/spec-data-governance.md`（范围段补一句元数据管理扩展说明 + 指向设计文档）

- [ ] **Step 1: 改文档**
- [ ] **Step 2: 最终验证链全跑**：后端全量 pytest（310 → ~335 全绿）、`pnpm lint`、`npx tsc --noEmit`、`pnpm build`
- [ ] **Step 3: 冒烟（可选）**：`python init_db.py` 重建库 + 起 uvicorn，GET /api/metadata/fields?must_govern=true 返回 70 条

---

## Self-Review 记录

- Spec 覆盖：§2 数据模型→T1；§4 种子→T2；§3 API→T3；§2.4 标准带入→T4；§5 前端→T5/T6/T7；§6 测试→各任务内嵌 + T8；§7 约束→Global Constraints ✓
- 占位符扫描：无 TBD/TODO；种子清单以 spec §4.1 全表为准（实现时逐行转元组，不允许自由发挥字段）
- 类型一致性：crud 函数名、schemas 四件套名、前端 payload 名在 T1-T7 间已交叉核对 ✓
- 风险点：① conftest 无 admin fixture，测试用 data_client（data_admin）做写角色；② init_db 会 drop_all，测试种子里避免直接调 init_db() 污染共享 engine，改为调 seed_metadata(db) + 回填函数；③ StepName 加枚举值后，检查现有审计测试是否对枚举做全量断言（若断言集合需同步更新）
