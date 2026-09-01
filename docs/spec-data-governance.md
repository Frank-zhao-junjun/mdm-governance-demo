# 主数据字段治理 SPEC（规格说明）

> **版本**：v1.1
> **日期**：2026-09-01
> **状态**：已评审，待实施

---

## 1. 概述

### 1.1 目标

基于 SAP 字段标准，对三类主数据的**存量数据**建立治理能力：

1. **数据标准管理**：定义各字段的数据标准（命名规范、值域范围、必填规则）
2. **数据质量检测**：基于标准对存量数据执行自动化质量检测
3. **疑似错误检测**：识别重复、不规范、异常数据，人工确认处理

### 1.2 范围与数据源

| 主数据类型 | 存量数据源 | 说明 |
|-----------|-----------|------|
| 物料 material | `golden_records`（现有表） | 已发布金标数据，字段映射见第 4 节 |
| 供应商 supplier | `partner_records`（本 SPEC 新增） | SAP BP 风格存储，字段存 attributes JSON |
| 客户 customer | `partner_records`（本 SPEC 新增） | 与供应商共用表，entity_type 区分 |

SAP 表（MARA/BUT000/LFA1/KNA1 等）在数据标准中作为字段归属元数据使用；数据本体不直接来自 SAP（当前为 Mock，见 1.3）。

### 1.3 不在范围内

- SAP 系统对接（存量数据通过导入/Mock 进入本系统）
- 数据自动修复（只检测、报告、人工处理）
- 数据标准变更审批流
- **申请流程质量校验**：现有 `GovernanceRule` + `MaterialValidator`（提交申请时的同步校验）不属于本 SPEC 范围

### 1.4 与现有系统的关系

本 SPEC 是**存量数据治理的唯一一套规则体系**，与申请流程校验完全独立：

| | 申请流程校验（现有，保持不动） | 存量数据治理（本 SPEC） |
|--|------------------------------|------------------------|
| 规则定义 | `governance_rules` 表，rule_key 固化于代码 | `data_standards` + `quality_check_rules` 表，完全配置化 |
| 数据对象 | 申请单 `material_applications` | 存量记录 `golden_records` / `partner_records` |
| 执行时机 | 提交申请时同步执行 | 人工触发批量检测 |
| 结果 | 校验结果随申请单返回，不持久化明细 | 检测批次 + 失败明细持久化 |

两套规则不迁移、不合并、不共享定义。存量治理功能只读写本 SPEC 定义的表。

---

## 2. 数据模型设计

### 2.1 数据标准（DataStandard）

定义各实体各字段的数据标准。

```python
class DataStandard(Base):
    """数据标准定义"""
    __tablename__ = "data_standards"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 实体信息
    entity_type = Column(String(50), nullable=False, index=True)  # material / supplier / customer
    sap_table = Column(String(50), nullable=True)  # MARA / MARC / BUT000 / LFA1 / KNA1
    field_name = Column(String(100), nullable=False)  # MATNR / MAKTX / NAME1 等
    field_label = Column(String(200), nullable=False)  # 字段中文标签

    # 数据类型
    data_type = Column(String(50), nullable=False)  # string / number / date / enum / boolean
    max_length = Column(Integer, nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    enum_values = Column(JSON, nullable=True)  # ["A", "B", "C"]

    # 校验规则
    required = Column(Boolean, default=False)
    pattern = Column(String(200), nullable=True)  # 正则（格式校验）
    unique = Column(Boolean, default=False)

    # 元数据
    description = Column(Text, nullable=True)
    sap_field_desc = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)

    __table_args__ = (
        UniqueConstraint("entity_type", "sap_table", "field_name", name="uq_entity_table_field"),
    )
```

**v1.1 修订**：

- 唯一约束从 `(entity_type, field_name)` 扩展为 `(entity_type, sap_table, field_name)`——同一字段名可出现在多张 SAP 表（如 MAKTX 同时在 MARA 与 MAKT），两键约束会互相挤掉
- 物料编码 MATNR 预置正则改为 `^M\d{5}$`，与现有 `CodeGenerator`（前缀 M + 5 位序列）一致；SAP 真实接入后按实际编码规则调整

**示例数据**：

| entity_type | sap_table | field_name | field_label | data_type | required | pattern |
|-------------|-----------|------------|-------------|-----------|----------|---------|
| material | MARA | MATNR | 物料编码 | string | true | ^M\d{5}$ |
| material | MARA | MAKTX | 物料描述 | string | true | null |
| material | MARA | MEINS | 基本计量单位 | string | true | null |
| material | MARA | MATKL | 物料组 | string | true | null |
| supplier | BUT000 | BU_TYPE | BP 类型 | enum | true | null |
| supplier | LFA1 | LIFNR | 供应商编号 | string | true | ^[0-9]{10}$ |
| supplier | LFA1 | NAME1 | 供应商名称 | string | true | null |
| customer | KNA1 | KUNNR | 客户编号 | string | true | ^[0-9]{10}$ |
| customer | KNA1 | NAME1 | 客户名称 | string | true | null |

### 2.2 供应商/客户存量记录（PartnerRecord）【v1.1 新增】

供应商/客户主数据当前在系统中没有任何存储，新增 BP 风格存量表：

```python
class PartnerRecord(Base):
    """供应商/客户主数据存量记录（SAP BP 风格）"""
    __tablename__ = "partner_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50), nullable=False, index=True)  # supplier / customer
    partner_code = Column(String(50), nullable=False, index=True)  # LIFNR / KUNNR
    partner_name = Column(String(200), nullable=False)  # NAME1 冗余存储
    attributes = Column(JSON, nullable=False, default=dict)  # SAP 字段名 → 值
    source_system = Column(String(50), nullable=False, default="mock_sap")
    status = Column(String(20), nullable=False, default="active")  # active / inactive
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)

    __table_args__ = (
        UniqueConstraint("entity_type", "partner_code", name="uq_entity_partner_code"),
    )
```

设计要点：

- 供应商/客户共用一张表，`entity_type` 区分（对齐 SAP BP 统一模型，BUT000 通用 + LFA1/KNA1 视图）
- `attributes` 以 SAP 字段名（NAME_ORG1/STREET/CITY1/POST_CODE1/COUNTRY/ZTERM 等）为键，与数据标准的 `field_name` 一致，检测引擎直接按键取值，无需二次映射
- `partner_name` 冗余 NAME1：列表展示与重复检测高频访问，避免逐行解析 JSON

### 2.3 质量检测规则（QualityCheckRule）

```python
class QualityCheckRule(Base):
    """质量检测规则"""
    __tablename__ = "quality_check_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    entity_type = Column(String(50), nullable=False, index=True)
    rule_type = Column(String(50), nullable=False)
    field_name = Column(String(100), nullable=True)
    standard_id = Column(String(36), ForeignKey("data_standards.id"), nullable=True)
    rule_config = Column(JSON, nullable=False)
    severity = Column(String(20), nullable=False, default="error")  # error / warning / info
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)


class RuleType(str, PyEnum):
    NULL_CHECK = "null_check"        # 空值检测
    FORMAT_CHECK = "format_check"    # 格式校验（正则）
    RANGE_CHECK = "range_check"      # 值域检查（min/max/enum）
    LENGTH_CHECK = "length_check"    # 长度检查
    UNIQUE_CHECK = "unique_check"    # 精确唯一（同值即违规）
    DUPLICATE_CHECK = "duplicate_check"  # 模糊相似（产出进入疑似错误流程）
```

**v1.1 修订**：删除 `custom_check`（自定义 SQL 表达式）——可配置 SQL 等于开放注入口子，违反项目安全约束。后续如需自定义规则，用受限表达式白名单另做设计。

`unique_check` 与 `duplicate_check` 的区别：前者精确相等判重（如编码重复，直接出结果）；后者相似度判重（如名称相似，产出进疑似错误，需人工确认）。

**规则配置示例**：

```json
// null_check
{"field": "MAKTX"}

// format_check
{"field": "MATNR", "pattern": "^M\\d{5}$", "message": "物料编码必须为 M + 5 位数字"}

// range_check
{"field": "MATKL", "enum": ["001", "002", "003"], "message": "物料组必须在枚举值范围内"}

// duplicate_check
{"field": "MAKTX", "similarity_threshold": 0.8, "message": "检测到相似物料描述"}
```

### 2.4 检测批次（QualityCheckBatch）【v1.1 新增】

v1.0 的 `batch_id` 是散在结果上的字段，没有批次主表，报告统计无从取数。新增批次表：

```python
class QualityCheckBatch(Base):
    """一次质量检测执行的批次记录"""
    __tablename__ = "quality_check_batches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50), nullable=False, index=True)
    total_entities = Column(Integer, nullable=False)  # 检测实体数
    total_checks = Column(Integer, nullable=False)    # 执行检查数
    passed = Column(Integer, nullable=False)          # 通过数
    failed = Column(Integer, nullable=False)          # 未通过数
    rule_ids = Column(JSON, nullable=False)           # 本批使用的规则 ID
    triggered_by = Column(String(50), nullable=False) # 触发人
    started_at = Column(DateTime, default=_now_utc)
    finished_at = Column(DateTime, nullable=True)
```

### 2.5 检测结果（QualityCheckResult）

**v1.1 修订：只持久化未通过项。** v1.0 连通过项都存，1000 实体 × 50 规则全量检测一次写入 5 万行，跑十次就是 50 万行。通过项不写结果表，仅计入批次统计（`passed` 数）。

```python
class QualityCheckResult(Base):
    """质量检测结果（仅未通过项）"""
    __tablename__ = "quality_check_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = Column(String(36), ForeignKey("quality_check_rules.id"), nullable=False)
    batch_id = Column(String(36), ForeignKey("quality_check_batches.id"), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False)
    entity_type = Column(String(50), nullable=False, index=True)
    field_name = Column(String(100), nullable=True)
    field_value = Column(String(500), nullable=True)  # 当前值（截断至 500）
    severity = Column(String(20), nullable=False)     # error / warning / info
    message = Column(Text, nullable=True)
    checked_at = Column(DateTime, default=_now_utc, index=True)
```

### 2.6 疑似错误（SuspectedError）

```python
class SuspectedError(Base):
    """疑似错误"""
    __tablename__ = "suspected_errors"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False)
    entity_label = Column(String(200), nullable=True)

    error_type = Column(String(50), nullable=False)  # duplicate / naming / classification / unit
    severity = Column(String(20), nullable=False, default="warning")
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)  # 如相似物料列表

    status = Column(String(20), nullable=False, default="pending")
    resolved_by = Column(String(50), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)

    detected_at = Column(DateTime, default=_now_utc, index=True)
    detected_by = Column(String(50), nullable=True)
```

**错误类型**：duplicate（重复）、naming（命名不规范）、classification（分类错误）、unit（计量单位异常）。

**重检去重策略【v1.1 新增】**：

- 同 `(entity_id, error_type)` 存在 `status=pending` 记录时，更新该记录（刷新 details/detected_at），不新插
- `confirmed/resolved/false_positive` 的记录不动
- 实体已不存在的 pending 记录，自动关闭：`status=resolved`，`resolution_note="实体已删除/失效，自动关闭"`

**状态机【v1.1 新增】**：

```
pending ──确认是错误──> confirmed ──修复完成──> resolved
   └──────误报────────> false_positive
```

- pending：待人工判断
- confirmed：确认是错误，待修复（本系统不自动修复）
- resolved：已处理完毕
- false_positive：判定为误报

---

## 3. API 接口设计

### 3.0 权限与审计【v1.1 新增】

| 操作 | user001 | dept001 | data001 | admin001 |
|------|---------|---------|---------|----------|
| 查询标准/规则/结果/疑似错误 | ✓ | ✓ | ✓ | ✓ |
| 增删改数据标准、增改规则 | ✗ | ✗ | ✓ | ✓ |
| 执行质量检测/疑似错误检测 | ✗ | ✗ | ✓ | ✓ |
| 处理疑似错误 | ✗ | ✗ | ✓ | ✓ |

- 所有写操作（标准 CRUD、检测执行、疑似错误处理）写 `audit_logs`（复用现有 audit_service）
- 所有接口要求有效 JWT，无免认证回退

### 3.1 数据标准管理

#### GET /api/data-standards

参数：`entity_type`、`sap_table`（可选）、`skip`（默认 0）、`limit`（默认 50，最大 500）。

```json
{
  "total": 150,
  "items": [
    {
      "id": "uuid",
      "entity_type": "material",
      "sap_table": "MARA",
      "field_name": "MATNR",
      "field_label": "物料编码",
      "data_type": "string",
      "max_length": 18,
      "required": true,
      "pattern": "^M\\d{5}$",
      "description": "物料主编码，M + 5 位数字"
    }
  ]
}
```

#### POST /api/data-standards（data/admin）

请求体含 entity_type/sap_table/field_name/field_label/data_type 及校验属性。`(entity_type, sap_table, field_name)` 冲突返回 409。

#### PUT /api/data-standards/{id}（data/admin）

#### DELETE /api/data-standards/{id}（data/admin）

删除前检查是否被 `quality_check_rules.standard_id` 引用，被引用返回 409。

### 3.2 质量检测

#### POST /api/quality-checks/run（data/admin）

```json
{
  "entity_type": "material",
  "entity_ids": ["uuid1"],
  "rule_ids": ["uuid1"]
}
```

entity_ids 不传检测全部；rule_ids 不传使用所有启用规则。响应：

```json
{
  "batch_id": "uuid",
  "total_checked": 100,
  "passed": 85,
  "failed": 15
}
```

#### GET /api/quality-checks/results

查失败明细。参数：`entity_type`、`entity_id`、`severity`、`batch_id`（可选）、`skip`/`limit`。

#### GET /api/quality-checks/report

参数：`entity_type`、`batch_id`（不传取该实体最新批次）。统计从批次表取，失败分布从结果表聚合：

```json
{
  "batch_id": "uuid",
  "entity_type": "material",
  "total_entities": 1000,
  "total_checks": 5000,
  "passed": 4500,
  "failed": 500,
  "pass_rate": 0.9,
  "by_severity": {"error": 100, "warning": 300, "info": 100},
  "by_rule": [{"rule_id": "uuid", "rule_name": "物料描述非空检查", "total": 1000, "failed": 100, "pass_rate": 0.9}],
  "top_issues": [{"field_name": "MAKTX", "issue_count": 100, "issue_type": "null_check", "message": "物料描述为空"}]
}
```

### 3.3 疑似错误

#### POST /api/suspected-errors/detect（data/admin）

```json
{
  "entity_type": "material",
  "error_types": ["duplicate", "naming"],
  "entity_ids": ["uuid1"]
}
```

#### GET /api/suspected-errors

（v1.0 为 `/list`，按 REST 修正为资源本身。）参数：`entity_type`、`error_type`、`status`、`skip`/`limit`。

#### POST /api/suspected-errors/{id}/resolve（data/admin）

```json
{
  "status": "confirmed",
  "resolution_note": "确认为重复物料，已在源系统合并"
}
```

status 仅允许 confirmed/resolved/false_positive；`resolved_by` 取当前登录用户，不接受请求体传入。

---

## 4. 字段访问层与数据源映射【v1.1 新增】

检测引擎不直接查各实体表，统一走字段访问层，屏蔽三实体存储差异：

```python
class EntityFieldAccessor:
    def get_field(self, entity_type: str, entity_id: str, field_name: str) -> Any | None
    def list_entities(self, entity_type: str, entity_ids: list[str] | None = None) -> list
```

### 4.1 物料字段映射（golden_records）

| SAP 字段 | 数据源 | 说明 |
|---------|--------|------|
| MATNR | golden_records.material_code | 现有编码（M + 5 位） |
| MAKTX | golden_records.material_name | |
| 长描述 | golden_records.material_desc | |
| MATKL | golden_records.classification_path | 分类路径 |
| MTART | golden_records.material_type | 枚举 |
| 扩展属性 | golden_records.attribute_values JSON | 键名需与数据标准 field_name 一致 |
| WERKS/EKGRP/LGORT | 无数据源 | 工厂/采购/库存视图字段：标准可定义；检测时记"数据源缺失"并跳过 |

### 4.2 供应商/客户字段

`partner_records.attributes` 以 SAP 字段名为键，直接按 `field_name` 取值；`partner_code` 对应 LIFNR/KUNNR，`partner_name` 对应 NAME1。

---

## 5. 检测执行语义【v1.1 新增】

1. **run 流程**：按 entity_type 取实体清单（可按 entity_ids 过滤）→ 逐规则逐实体执行 → 批次表写统计 → 失败项写结果表，同一事务提交
2. **同步上限**：v1 同步执行，单次限 5000 实体；超出返回 400 提示分批，后台任务化留后续迭代（复用 publish_sync_tasks 模式）
3. **重复检测**：复用现有 `DuplicateDetector` 的数据库 ILIKE 预筛 + 词重叠打分，禁止全量两两比较（jaccard O(n²) 不可接受）；相似度阈值在 rule_config 配置
4. **类型语义**：data_type=number 的值以字符串存储时先转数值再比较；转换失败按 format 错误处理

---

## 6. 前端 UI 设计

### 6.1 页面结构

```
/quality
├── /quality/standards          # 数据标准管理
├── /quality/checks             # 质量检测（执行 + 结果）
│   └── /quality/checks/report  # 质量报告
└── /quality/suspected          # 疑似错误
```

### 6.2 数据标准管理页面

- 筛选栏：实体类型下拉、SAP 表下拉、搜索框
- 数据表格：字段名、字段标签、数据类型、是否必填、校验规则
- 写操作按钮（新建/编辑/删除）按角色显隐，仅 data/admin 可见

### 6.3 质量检测页面

- 执行检测表单：实体类型、规则多选、实体范围（全部/指定）
- 检测结果表格：实体、字段、当前值、严重程度、错误信息
- 质量报告：批次选择器（默认最新批次）、通过率图表（recharts）、按规则统计、Top 问题列表

### 6.4 疑似错误页面

- 状态筛选（pending/confirmed/resolved/false_positive）+ 实体类型/错误类型筛选
- 疑似错误表格：实体、错误类型、严重程度、标题、状态、检测时间
- 处理对话框：状态选择、处理说明；details 展开显示相似实体列表

---

## 7. 实施计划

### Phase 1：存量存储 + 数据标准管理（3 天）

1. PartnerRecord 模型 + init_db 建表 + Mock 种子（供应商/客户各 ≥ 20 条，含故意脏数据供检测演示）
2. DataStandard 模型 + 种子数据（附录字段，正则与现有 CodeGenerator 对齐）
3. CRUD API + 权限矩阵 + 审计
4. 前端数据标准管理页

**验收**：三实体标准可增删改查；供应商/客户 Mock 数据入库；user/dept 角色写操作返回 403；写操作有审计记录。

### Phase 2：数据质量检测（3-4 天）

1. QualityCheckBatch / Rule / Result 三表 + 迁移
2. 字段访问层（三实体统一取值）
3. 规则引擎（null/format/range/length/unique 五种）
4. run/results/report API
5. 前端检测页 + 报告图表

**验收**：五种规则可执行且各有正反用例测试；结果表只存失败项；报告统计与批次表一致；无数据源字段跳过且有记录；5000 上限生效。

### Phase 3：疑似错误检测（2-3 天）

1. SuspectedError 模型
2. 检测服务（重复检测复用 DuplicateDetector；命名不规范检测）
3. detect/list/resolve API + 重检去重
4. 前端疑似错误页 + 处理对话框

**验收**：检测出真重复与命名问题；重跑不产生重复 pending；状态流转符合状态机；处理写审计。

### Phase 4：数据导入（1-2 天）

1. 供应商/客户 CSV 导入接口（复用现有 upload 安全约束：类型白名单、大小限制）

**验收**：CSV 导入成功；格式错误行返回明细报告。

**总工期：9-12 天**（供应商/客户存量存储与导入为 v1.1 新增工作量）。

---

## 8. 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 重复检测性能 | 高 | 复用数据库 ILIKE 预筛，禁止全量两两比较 |
| 批量检测超时 | 中 | v1 限 5000 实体同步执行，超出提示分批；后台任务留后续 |
| 标准与 Mock 数据不一致 | 中 | 种子数据按附录字段同源生成 |
| SQLite JSON 查询性能 | 中 | 高频字段（名称/编码）冗余为列，JSON 仅存低频属性 |
| 前端图表 | 低 | recharts 已集成 |

---

## 9. 附录：SAP 核心字段

### 9.1 SAP 物料主数据核心字段

| SAP 表 | 字段 | 描述 | 本系统数据源 |
|--------|------|------|-------------|
| MARA | MATNR | 物料编码 | golden_records.material_code |
| MARA | MAKTX | 物料描述 | golden_records.material_name |
| MARA | MEINS | 基本计量单位 | attribute_values |
| MARA | MATKL | 物料组 | classification_path |
| MARA | MTART | 物料类型 | material_type |
| MARA | BRGEW | 毛重 | attribute_values |
| MARA | NTGEW | 净重 | attribute_values |
| MARA | GEWEI | 重量单位 | attribute_values |
| MARC | WERKS | 工厂 | 无数据源（检测跳过） |
| MARC | EKGRP | 采购组 | 无数据源（检测跳过） |
| MARC | DISMM | MRP 参数文件 | 无数据源（检测跳过） |
| MARD | LGORT | 存储位置 | 无数据源（检测跳过） |
| MAKT | SPRAS | 语言代码 | 无数据源（检测跳过） |

### 9.2 SAP BP 核心字段

| SAP 表 | 字段 | 描述 | 本系统数据源 |
|--------|------|------|-------------|
| BUT000 | PARTNER | BP 编号 | partner_code |
| BUT000 | BU_TYPE | BP 类型 | attributes |
| BUT000 | NAME_ORG1 | 组织名称 1 | attributes |
| BUT000 | NAME_ORG2 | 组织名称 2 | attributes |
| BUT000 | NAME_LAST | 姓氏 | attributes |
| BUT000 | NAME_FIRST | 名字 | attributes |
| BUT020 | STREET | 街道 | attributes |
| BUT020 | CITY1 | 城市 | attributes |
| BUT020 | POST_CODE1 | 邮编 | attributes |
| BUT020 | COUNTRY | 国家 | attributes |
| BUT0BANK | BANKS | 银行代码 | attributes |
| BUT0BANK | BANKL | 银行账号 | attributes |
| LFA1 | LIFNR | 供应商编号 | partner_code（supplier） |
| LFA1 | NAME1 | 供应商名称 | partner_name |
| LFA1 | LAND1 | 国家 | attributes |
| LFA1 | ZTERM | 付款条件 | attributes |
| KNA1 | KUNNR | 客户编号 | partner_code（customer） |
| KNA1 | NAME1 | 客户名称 | partner_name |
| KNA1 | LAND1 | 国家 | attributes |
| KNA1 | ZTERM | 付款条件 | attributes |

---

## 10. 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | 2026-08-23 | 初始版本 |
| v1.1 | 2026-09-01 | 评审修订：保留供应商/客户并新增 PartnerRecord 存量存储；明确本 SPEC 为存量治理唯一规则体系（与申请流程 GovernanceRule 独立）；删除 custom_check；新增检测批次表、结果只存失败项；新增字段访问层与映射表；补权限矩阵、审计、重检去重、状态机；修唯一约束与 MATNR 正则；API 命名修正 |
