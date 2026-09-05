# 元数据管理模块 — 设计文档

> 日期：2026-09-03
> 状态：已与用户对齐（方向 B / 方案一 / 前端形态 A），待实现
> 基线：本设计是对 `docs/spec-data-governance.md` v1.4 范围的一次**有意扩展**（新增元数据管理能力），实现完成后需同步更新 SPEC 与 AGENTS.md 的范围表述。

## 1. 背景与目标

项目当前只做存量数据治理与数据质量管理，缺少对"治理对象本身"的元数据描述。本模块参考 OpenMetadata 的 Schema-first 设计思想（实体契约、字段登记册、术语表），自研精简版元数据管理能力。

**目标**：
- 管理物料主数据、供应商、客户三类实体的元数据
- 必须治理字段覆盖：SAP 物料主数据基本视图（MARA/MAKT）、SAP 业务伙伴基本视图（BUT000 为主）、Ariba SLP 最佳实践字段
- 字段登记册为**单一权威源**，数据标准（data_standards）引用登记册而非各写各的

**MVP 范围**（已与用户确认）：
- ① 实体级：业务定义 + 数据 Owner + 管理部门
- ② 分类标签 + 敏感等级
- ③ 术语表（Glossary）并与字段关联
- ✗ ④ 血缘/关联图：**不进 MVP**
- ✗ ⑤ 数据画像/质量趋势：不做（现有 quality report 已覆盖）
- ✗ 不部署真实 OpenMetadata 平台，仅借鉴其设计

**字段规模**：60-80 个核心字段（must_govern=true），企业特有字段后续通过界面登记扩展（must_govern=false）。

## 2. 数据模型（方案一：登记册独立成表 + data_standards 外键引用）

### 2.1 `metadata_field` 字段登记册（核心表）

| 列 | 类型 | 说明 |
|---|---|---|
| id | String(36) PK | uuid |
| entity_type | String(50) | material / supplier / customer |
| sap_table | String(50) | MARA / MAKT / BUT000 / LFA1 / KNA1 / ARIBA_SLP |
| field_name | String(100) | MATNR / NAME_ORG1 / TaxID 等 |
| field_label | String(200) | 中文标签 |
| data_type | String(50) | 与 data_standards 同一枚举口径：string/number/date/enum/boolean/amount/text |
| max_length | Integer 可空 | |
| view_section | String(100) | 所属视图分组（基本视图/组织视图/地址/税务/银行/采购 等） |
| business_definition | Text 可空 | 业务定义 |
| standard_source | String(20) | sap / ariba_slp / internal |
| must_govern | Boolean | 核心字段 true（约 70 条），扩展字段 false |
| glossary_term_id | String(36) FK→glossary_term.id 可空 | 关联术语 |
| is_active / created_at / updated_at | 常规 | |

唯一约束：`(entity_type, sap_table, field_name)`，冲突返回 409。

### 2.2 `metadata_entity` 实体元数据（3 条种子）

| 列 | 说明 |
|---|---|
| entity_type | material / supplier / customer，唯一 |
| display_name | 显示名（物料主数据 / 供应商 / 客户） |
| business_definition | 业务定义 |
| data_owner | 数据 Owner（与 governance_owner 文本对齐即可，不强外键） |
| dept | 管理部门 |
| tags | JSON 数组 |
| sensitivity_level | public / internal / confidential（公开/内部/机密） |

### 2.3 `glossary_term` 术语表

| 列 | 说明 |
|---|---|
| term | 术语（唯一） |
| definition | 定义 |
| aliases | JSON 数组 |

反向关联：`metadata_field.glossary_term_id`。

### 2.4 `data_standards` 改造

- 新增 `metadata_field_id`（String(36) FK→metadata_field.id，**可空**，兼容存量）
- POST/PUT 接受 `metadata_field_id`；若提供，则 `entity_type`/`sap_table`/`field_name`/`data_type`/`max_length` 以登记册为准自动带入（防漂移）
- 响应模型带出关联字段信息（field_label、view_section、standard_source）
- 迁移：现有 29 条种子标准按 `(entity_type, sap_table, field_name)` 匹配回填 `metadata_field_id`（init_db.py 种子函数内完成，要求 29 条全部匹配）

## 3. 后端 API

新路由模块 `backend/app/api/metadata.py`，前缀 `/api/metadata`，注册进 `main.py`（成为第 9 个 router）。全部需 JWT；写操作（POST/PUT）限 admin/data_admin（沿用 `require_admin` 同款门禁模式，普通用户写操作返回 403）。

| 端点 | 方法 | 说明 |
|---|---|---|
| /api/metadata/entities | GET | 三类实体总览（含字段数统计：must_govern 数 / 总数） |
| /api/metadata/entities/{entity_type} | PUT | 编辑实体元数据 |
| /api/metadata/fields | GET | 字段登记册查询，筛选：entity_type / view_section / must_govern / keyword（field_name+field_label 模糊），分页 |
| /api/metadata/fields | POST | 登记新字段（唯一冲突 409） |
| /api/metadata/fields/{id} | PUT | 编辑字段元数据 |
| /api/metadata/glossary | GET / POST | 术语表列表 / 新增 |
| /api/metadata/glossary/{id} | PUT | 编辑术语（含关联字段数返回） |

分层沿用：api → `services/metadata_service.py`（查询装配 + 统计）→ crud。schemas.py 增加对应 Pydantic 模型。

## 4. 种子数据（init_db.py 新增种子函数）

### 4.1 字段登记册（约 70 条，全部 must_govern=true）

**material — SAP 物料主数据基本视图（MARA/MAKT，30 条，standard_source=sap）**

| 字段 | 标签 | 类型 | 视图 |
|---|---|---|---|
| MATNR | 物料编码 | string(18) | 基本视图 |
| MAKTX | 物料描述 | string(40) | 基本视图（MAKT） |
| MTART | 物料类型 | string(4) | 基本视图 |
| MBRSH | 行业领域 | string(1) | 基本视图 |
| MATKL | 物料组 | string(9) | 基本视图 |
| MEINS | 基本计量单位 | string(3) | 基本视图 |
| SPART | 产品组 | string(2) | 基本视图 |
| PRDHA | 产品层次 | string(18) | 基本视图 |
| BISMT | 旧物料号 | string(18) | 基本视图 |
| MSTAE | 跨工厂物料状态 | string(2) | 基本视图 |
| LVORM | 删除标记 | boolean | 基本视图 |
| XCHPF | 批次管理标识 | boolean | 基本视图 |
| NORMT | 行业标准 | string(18) | 基本视图 |
| WRKST | 基本物料 | string(48) | 基本视图 |
| MTPOS_MARA | 通用项目类别组 | string(4) | 基本视图 |
| BRGEW | 毛重 | amount | 基本数据 |
| NTGEW | 净重 | amount | 基本数据 |
| GEWEI | 重量单位 | string(3) | 基本数据 |
| VOLUM | 体积 | amount | 基本数据 |
| VOLEH | 体积单位 | string(3) | 基本数据 |
| LAENG | 长度 | amount | 基本数据 |
| BREIT | 宽度 | amount | 基本数据 |
| HOEHE | 高度 | amount | 基本数据 |
| MEABM | 尺寸单位 | string(3) | 基本数据 |
| EAN11 | EAN/UPC 条码 | string(18) | 基本数据 |
| NUMTP | EAN 类别 | string(2) | 基本数据 |
| ERSDA | 创建日期 | date | 管理数据 |
| ERNAM | 创建人 | string(12) | 管理数据 |
| LAEDA | 最后修改日期 | date | 管理数据 |
| AENAM | 修改人 | string(12) | 管理数据 |

**supplier — SAP 业务伙伴基本视图（BUT000）+ LFA1 + Ariba SLP（25 条）**

SAP 部分（standard_source=sap）：

| 字段 | 标签 | sap_table |
|---|---|---|
| PARTNER | 业务伙伴编号 | BUT000 |
| TYPE | 业务伙伴类别 | BUT000 |
| BU_GROUP | 业务伙伴分组 | BUT000 |
| BPEXT | 业务伙伴外部编号 | BUT000 |
| TITLE | 称谓 | BUT000 |
| NAME_ORG1 | 组织名称 1 | BUT000 |
| NAME_ORG2 | 组织名称 2 | BUT000 |
| BU_SORT1 | 搜索项 1 | BUT000 |
| BU_SORT2 | 搜索项 2 | BUT000 |
| MC_NAME1 | 检索名称 | BUT000 |
| LIFNR | 供应商编号 | LFA1 |
| KTOKK | 供应商账户组 | LFA1 |
| LAND1 | 国家代码 | LFA1 |
| REGIO | 地区（省/州） | LFA1 |
| ORT01 | 城市 | LFA1 |
| PSTLZ | 邮政编码 | LFA1 |
| STRAS | 街道地址 | LFA1 |
| STCD1 | 税号 1 | LFA1 |
| TELF1 | 电话 | LFA1 |
| SMTP_ADDR | 电子邮箱 | LFA1 |

Ariba SLP 部分（standard_source=ariba_slp，sap_table=ARIBA_SLP）：

| 字段 | 标签 |
|---|---|
| SMVendorID | SLP 供应商 ID |
| ERPVendorID | ERP 供应商编号映射 |
| TaxID | 税务登记号 |
| DUNSNumber | 邓白氏编码（DUNS） |
| RiskLevel | 风险等级 |

**customer — BUT000 + KNA1（15 条，standard_source=sap）**

| 字段 | 标签 | sap_table |
|---|---|---|
| PARTNER | 业务伙伴编号 | BUT000 |
| TYPE | 业务伙伴类别 | BUT000 |
| BU_GROUP | 业务伙伴分组 | BUT000 |
| NAME_ORG1 | 组织名称 1 | BUT000 |
| NAME_ORG2 | 组织名称 2 | BUT000 |
| BU_SORT1 | 搜索项 1 | BUT000 |
| MC_NAME1 | 检索名称 | BUT000 |
| KUNNR | 客户编号 | KNA1 |
| KTOKD | 客户账户组 | KNA1 |
| LAND1 | 国家代码 | KNA1 |
| REGIO | 地区（省/州） | KNA1 |
| ORT01 | 城市 | KNA1 |
| BRAN1 | 行业代码 | KNA1 |
| STCD1 | 税号 1 | KNA1 |
| SMTP_ADDR | 电子邮箱 | KNA1 |

合计：30 + 25 + 15 = **70 条**。

### 4.2 实体元数据（3 条）

- material：物料主数据，Owner=张三（数据管理部），tags=["核心主数据","SAP"], sensitivity=internal
- supplier：供应商主数据，Owner=张三，tags=["核心主数据","SAP","Ariba SLP"], sensitivity=internal
- customer：客户主数据，Owner=张三，tags=["核心主数据","SAP"], sensitivity=internal

### 4.3 术语表（约 15 条）

物料编码、物料描述、物料类型、物料组、基本计量单位、业务伙伴、业务伙伴分组、供应商编号、客户编号、账户组、税号、邓白氏编码（DUNS）、搜索项、删除标记、批次管理——并预关联到对应 metadata_field。

### 4.4 data_standards 回填

29 条种子标准全部按 `(entity_type, sap_table, field_name)` 匹配登记册回填 `metadata_field_id`；若有种标准字段不在登记册，先补登记册条目再回填（测试断言 29/29 匹配）。

## 5. 前端

- 新页面 `src/pages/Metadata.tsx`，路由 `/metadata`，菜单第 8 项「元数据管理」（lucide `BookMarked` 图标）
- **Tab 1 实体总览**：三卡片（定义/Owner/部门/敏感等级徽标/标签/字段统计），admin/data_admin 可见编辑按钮，Dialog + react-hook-form + zod
- **Tab 2 字段登记册**：筛选条（实体类型/视图分组/只看必须治理/关键词）+ 表格（SAP表·字段名、标签、类型、视图、来源徽标、must_govern、关联术语、已建标准数）+「登记新字段」「编辑」Dialog；默认 must_govern=true 过滤
- **Tab 3 术语表**：表格（术语/定义/别名/关联字段数）+ 新增/编辑 Dialog
- 新增 `src/lib/metadata.ts` API 封装；类型进 `src/types/api.ts`
- `DataStandardFormDialog` 改造：字段名手填 → 登记册下拉（按 entity_type 过滤），选中后 data_type/max_length 自动带入只读

## 6. 测试策略

- 新增 `backend/tests/test_metadata.py`：实体/字段/术语 CRUD、user 角色写操作 403、唯一约束 409、data_standards 外键带入逻辑、种子回填 29/29 匹配、筛选与分页
- 全量：`cd backend && ENV=test SQLALCHEMY_DATABASE_URL="sqlite:///:memory:" python -m pytest -q`（310 → 约 330 用例）
- 前端：`pnpm lint` 零错误 + `npx tsc --noEmit` + `pnpm build`
- 实测：init_db 后 `/metadata` 三 Tab 可用，标准表单下拉联动正常

## 7. 约束遵守清单（AGENTS.md）

- 所有 API 需 JWT，无免认证回退；写操作 admin/data_admin 门禁
- 前端 pnpm、后端 uv；注释与日志中文为主
- 分层：api → services → crud；新代码风格与现有一致
- 不触碰 5,000 上限口径、归并门禁、审批快照等既有安全约束
- 完成后更新 AGENTS.md（新增第 9 个 router、3 张新表、新页面路由）与 SPEC 范围表述

## 8. 遗留事项

- 血缘/关联图（④）待后续版本评估
- 企业 Z 字段通过界面登记，不做批量导入（MVP）
- OpenMetadata 真实平台集成不在本次范围
