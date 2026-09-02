# 主数据字段治理 SPEC（规格说明）

> **版本**：v1.4
> **日期**：2026-09-02
> **状态**：已定稿，作为实施基线

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
| 物料 material | `material_records`（本 SPEC 新增） | SAP MARA 风格存量存储，字段存 attributes JSON |
| 供应商 supplier | `partner_records`（本 SPEC 新增） | SAP BP 风格存储，字段存 attributes JSON |
| 客户 customer | `partner_records`（本 SPEC 新增） | 与供应商共用表，entity_type 区分 |

SAP 表（MARA/BUT000/LFA1/KNA1 等）在数据标准中作为字段归属元数据使用；数据本体不直接来自 SAP（当前为 Mock，见 1.3）。

### 1.3 不在范围内

- SAP 系统对接（存量数据通过导入/Mock 进入本系统）
- 数据自动修复（只检测、报告、人工处理）
- 数据标准变更审批流
- **业务系统编码映射**（外部系统存量编码与金标编码的对应关系管理，对应浪潮 MDM"数据映射"能力）——后续迭代
- **申请/审批/金标/分发流程**：不属于本系统职能（v1.3 起从代码库移除）

### 1.4 与现有系统的关系

**系统定位**：本系统只提供存量数据治理与数据质量管理服务。 数据的新增申请、审批、金标数据（GoldenData）、外部分发（BTP/OpenMetadata 发布）**不属于本系统职能**，相关代码移除列入 Phase 0（代码库当前处于迁移中间态，见第 7 章）。

本 SPEC 是存量数据治理的**唯一一套规则体系**：

| | 存量数据治理（本 SPEC，本系统全部） |
|--|------------------------------|
| 规则定义 | `data_standards` + `quality_check_rules` 表，完全配置化 |
| 数据对象 | 存量记录 `material_records` / `partner_records` |
| 执行时机 | 人工触发批量检测 |
| 结果 | 检测批次 + 失败明细持久化 |

上游业务系统（SAP/PLM/采购平台等）负责数据创建与分发；本系统通过导入接收存量数据，只做检测、报告、人工处理建议。

### 1.4.1 AI 辅助治理层（v1.4 新增）

v1.4 起，系统在存量治理四件事之上增加 AI 辅助治理层（`app/agents/` + `app/skills/` + `app/core/llm_gateway.py` 及 Copilot/治理 API 与前端页面）。该层遵守以下定位，不与上述服务边界冲突：

1. **Agent 只出建议**：StandardAgent / QualityAgent / DedupAgent 的输出一律是建议与工单（`quality_ticket` / `merge_ticket`），不直接改写存量记录；全程留 `agent_trace` 可审计。
2. **Skill 确定性、无副作用**：`app/skills/` 各 Skill 只做规则化判定与建议生成，不写库；与 LLM 输出冲突时以确定性 Skill 结果为准（L1 覆盖 L3）。
3. **归并仅返回 ready**：`POST /api/governance/merge-execute` 只在做完批准校验与执行预检后返回 `ready`，实际归并由外部执行器完成，本系统不修改 `material_records` / `partner_records`。
4. **"审批"指治理裁决，不是业务审批**：Copilot 的 approve / reject / overturn 是对**治理工单**（质量问题、归并建议）的处置意见，属治理闭环动作；§1.3 与 §1.4 所排除的"申请/审批/金标/分发"指**业务流程**（新增数据申请、业务审批流、金标数据创建发布、下游分发），两者不构成同一职能。高风险归并批准必须填写 opinion 且 confirmed=true，并留存 `approval_evidence` 快照。
5. **LLM 可降级**：LLM 网关默认 mock 模式，DeepSeek 模式失败自动熔断降级为确定性结果，治理能力不依赖外部 LLM 可用性。

### 1.5 治理能力框架（业务属性 / 数据属性 / 管理属性）

本版规范进一步明确：数据治理不是单一的“字段校验”功能，而是由三类属性共同驱动的治理能力闭环。

#### 1.5.1 业务属性（Business Attribute）

用于定义“字段为什么存在、属于哪个业务语义域”。

- 标准主题：主数据对象是否属于物料、供应商、客户、工厂、计量、外协等业务主题
- 标准小类：字段归属于编码、名称、分类、状态、等级等小类
- 业务定义：字段的业务含义、约束原因、业务判定标准
- 标准来源：字段来源于 SAP、业务规范、内部制度或行业标准
- 业务规则：字段是否必须满足某些业务状态联动条件

#### 1.5.2 数据属性（Data Attribute）

用于定义“字段在技术上应当如何表达”。

- 数据类型：字符串、数字、日期、枚举、布尔、金额、文本
- 数据长度：最大长度、最小长度、对象长度限制
- 编码规则：MATNR、LIFNR、KUNNR 等业务编码模式
- 取值范围：枚举值、数值区间、固定值集合
- 数据精度：小数位数、单位、转换格式
- 数据格式：日期格式、编码格式、货币格式

#### 1.5.3 管理属性（Management Attribute）

用于定义“字段谁负责、权限如何控制、如何使用”。

- 标准定义人：字段标准的创建/维护人
- 标准使用人：业务使用者、数据录入人、分析人员
- 应用部门：字段使用方（采购、生产、财务、仓储等）
- 权限范围：谁有读权限、谁有维护权限、谁有审批权限
- 使用系统：字段可用于哪个系统或报表
- 使用期限：字段生命周期、失效期、升级替换策略

#### 1.5.4 质量特性维度（Quality Characteristics）

数据质量不再只看“合法性”，要覆盖以下统一维度：

| 维度 | 定义 | 核心问题 |
|------|------|----------|
| 完整性 | 数据是否完整 | 是否存在必填字段缺失、数据缺失 |
| 准确性 | 数据是否真实准确 | 是否与真实业务事实一致 |
| 一致性 | 数据是否跨系统/跨字段一致 | 同一对象不同来源是否冲突 |
| 及时性 | 数据是否及时更新 | 是否滞后、是否过期 |
| 唯一性 | 数据是否唯一 | 是否重复、是否存在同义重复 |
| 有效性 | 数据是否符合业务规则 | 是否属于合法值域/规则定义 |
| 规范性 | 数据是否符合标准格式 | 是否遵循编码、命名、长度等规范 |
| 可追溯性 | 数据是否可解释、可审计 | 变更来源、审批依据、责任归属是否可证 |

#### 1.5.5 核心治理问题与规则映射

| 维度 | 错误表达 | 治理动作 |
|------|----------|----------|
| 完整性 | 缺失值、空值、字段为空 | 强制必填校验、缺失告警 |
| 准确性 | 数据与事实不符 | 标准校验、业务比对、异常识别 |
| 一致性 | 同一对象不同系统有冲突 | 跨表对账、字段联动校验 |
| 及时性 | 数据未更新、过期 | 时效性规则、周期巡检 |
| 唯一性 | 重复、近重复 | 标识去重、疑似重复审核 |
| 有效性 | 非法值、超范围 | 值域/枚举校验、业务状态校验 |
| 规范性 | 命名/长度/编码不标准 | 格式规则、命名模板约束 |
| 可追溯性 | 缺少责任人、审批证据 | 审计记录、审批意见模板、责任归属 |

#### 1.5.6 与数据模型和规则的承接

本节框架必须落到第 2 章模型，否则只是概念摆设。承接关系如下：

**管理属性进表**：DataStandard 新增三列——`owner`（标准定义人）、`standard_source`（标准来源：sap/industry/internal）、`dept_scope`（应用部门，JSON 数组）。业务属性整体进 `business_attrs` JSON 列（标准主题/标准小类等展示型元数据）；业务定义/业务规则由 `description` 与规则引擎承载，不拆独立列。

**质量维度与规则类型映射**：

| 质量维度 | 对应规则类型 | v1 是否覆盖 |
|---------|-------------|------------|
| 完整性 | null_check | ✓ |
| 唯一性 | unique_check / duplicate_check | ✓ |
| 有效性 | range_check | ✓ |
| 规范性 | format_check / length_check | ✓ |
| 准确性 | 无（需与外部事实源比对） | ✗ 后续迭代 |
| 一致性 | 无（需跨系统对账） | ✗ 后续迭代 |
| 及时性 | 无（需业务时效定义） | ✗ 后续迭代 |
| 可追溯性 | 由 audit_logs + 检测批次承担，不设规则类型 | 部分（审计已有，血缘无） |

不在 v1 覆盖的维度不假装覆盖：检测报告按上述四种维度归类统计，报告里不出现空维度。

### 1.6 疑似重复判定与审核意见标准化

本版新增对“相似重复”数据的治理流程要求：

1. 发现相似项后，系统先生成候选重复列表，并计算相似度分数。
2. 用户或数据管理员在审核页面确认：同意重复、拒绝、待人工补充、误报。
3. 审核意见必须标准化输出，便于后续归档和分析。
4. 对被判定为重复的记录，系统保留证据：候选编码、名称、相似率、对应规则、责任人与判定理由。

标准审核意见模板：

- 同意：该数据与已存在记录重复，按标准合并/去重。
- 拒绝：该数据为合法业务差异，不属于重复。
- 误报：当前规则对该数据判定存在偏差，需关闭该问题。
- 待补充：需进一步核实，补充业务上下文后再判定。

#### 1.6.1 规范化审核意见示例

```
审核结论：共发现以下 17 条疑似重复数据，现进行确认

相似度  规则编码    物料描述                          对应关系          处理建议
95%     11002422585  低压气动阀门 Z642H 1.6MPa C DN50   可能重复       确认并合并
87%     11002422586  低压气动阀门 Z642Y 1.6MPa C DN150  可能重复       确认并合并
83%     11002422587  低压气动阀门 Z642Y 1.6MPa C DN200  可能重复       确认并合并
...
```

#### 1.6.2 审核结论标准流程

- 若用户确认"重复"，则自动进入待合并/待处理工单，记录证据
- 若用户确认"非重复"，则加入误报白名单，避免重复召回
- 若用户最终未确认，则保留为 pending，并要求补充说明

#### 1.6.3 与 2.7 状态机的对接

- "同意/确认重复" → `confirmed`；修复完成 → `resolved`
- "拒绝/误报" → `false_positive`，并进入**误报白名单**：重检时同 `(entity_id, matched_entity_id, error_type)` 已为 false_positive 的不再生成新记录（对应 2.7 重检去重策略的补充条款）
- "待补充" → 保持 `pending`，用 `resolution_note` 记录待补充说明，**不新增状态**（状态机保持 4 态，避免状态膨胀）
- 审核意见模板作为前端处理对话框的**预设文案**（见 6.4），用户可改
- "待合并工单"在 v1 简化为 confirmed 记录 + details 证据链，独立工单系统不在范围

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

    # 业务属性进 JSON（标准主题/标准小类等展示型元数据；业务定义由 description 承载，业务规则由规则引擎承载）
    business_attrs = Column(JSON, nullable=True)  # {"standard_topic": "...", "standard_subcategory": "..."}

    # 元数据
    description = Column(Text, nullable=True)
    sap_field_desc = Column(Text, nullable=True)
    # 管理属性（承接 1.5.6）
    owner = Column(String(50), nullable=True)          # 标准定义人
    standard_source = Column(String(20), nullable=True) # sap / industry / internal
    dept_scope = Column(JSON, nullable=True)            # 应用部门列表
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)

    __table_args__ = (
        UniqueConstraint("entity_type", "sap_table", "field_name", name="uq_entity_table_field"),
    )
```

**设计说明**：

- 唯一约束含 `sap_table`，即 `(entity_type, sap_table, field_name)`——同一字段名可出现在多张 SAP 表（如 MAKTX 同时在 MARA 与 MAKT），缺 sap_table 会互相挤掉
- 物料编码 MATNR 预置正则 `^M\d{5}$`（前缀 M + 5 位序列）；SAP 真实接入后按实际编码规则调整

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

### 2.2 物料存量记录（MaterialRecord）

物料存量数据不再依赖申请流程的 `golden_records`（已随申请链路移除），新建 MARA 风格存量表：

```python
class MaterialRecord(Base):
    """物料主数据存量记录（SAP MARA 风格）"""
    __tablename__ = "material_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    material_code = Column(String(50), nullable=False, index=True)   # MATNR
    material_name = Column(String(200), nullable=False)              # MAKTX 冗余存储
    attributes = Column(JSON, nullable=False, default=dict)          # SAP 字段名 → 值（MTART/MEINS/MATKL/BRGEW/NTGEW/GEWEI 等）
    source_system = Column(String(50), nullable=False, default="mock_sap")
    status = Column(String(20), nullable=False, default="active")    # active / inactive
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)

    __table_args__ = (
        UniqueConstraint("material_code", name="uq_material_code"),
    )
```

设计要点与 `partner_records` 对称：`material_name` 冗余 MAKTX 供列表与重复检测高频访问；`attributes` 键名与数据标准 `field_name` 一致，检测引擎直接按键取值。

### 2.3 供应商/客户存量记录（PartnerRecord）

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

### 2.4 质量检测规则（QualityCheckRule）

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

**设计约束**：不提供 `custom_check`（自定义 SQL 表达式）——可配置 SQL 等于开放注入口子，违反项目安全约束。后续如需自定义规则，用受限表达式白名单另做设计。

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

### 2.5 检测批次（QualityCheckBatch）

每次检测生成一条批次记录，承载报告统计：

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

### 2.6 检测结果（QualityCheckResult）

**只持久化未通过项。** 若连通过项都存，1000 实体 × 50 规则全量检测一次写入 5 万行，跑十次就是 50 万行。通过项不写结果表，仅计入批次统计（`passed` 数）。

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

### 2.7 疑似错误（SuspectedError）

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
    matched_entity_id = Column(String(36), nullable=True, index=True)  # 重复类错误的疑似匹配实体 ID（误报白名单用）

    detected_at = Column(DateTime, default=_now_utc, index=True)
    detected_by = Column(String(50), nullable=True)
```

**错误类型**：duplicate（重复）、naming（命名不规范）、classification（分类错误）、unit（计量单位异常）。

**重检去重策略**：

- 同 `(entity_id, error_type)` 存在 `status=pending` 记录时，更新该记录（刷新 details/detected_at），不新插
- `confirmed/resolved/false_positive` 的记录不动
- **误报白名单**：同 `(entity_id, matched_entity_id, error_type)` 已为 false_positive 的，重检时不再生成新记录（对应 1.6.3）。两键 `(entity_id, error_type)` 会把该实体所有匹配对全拉黑，过宽；matched_entity_id 粒度到单个组合对
- 实体已不存在的 pending 记录，自动关闭：`status=resolved`，`resolution_note="实体已删除/失效，自动关闭"`

**状态机**：

```
pending ──确认是错误──> confirmed ──修复完成──> resolved
   └──────误报────────> false_positive
```

- pending：待人工判断
- confirmed：确认是错误，待修复（本系统不自动修复）
- resolved：已处理完毕
- false_positive：判定为误报

**处置建议（参考浪潮 MDM 停用语义）**：疑似错误 details 给出建议处置动作（如重复数据给出"建议保留 X / 停用 Y"）。处置一律人工执行，系统不自动停用或删除任何存量记录；停用优先于删除。

---

## 3. API 接口设计

### 3.0 权限与审计

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

参数：`entity_type`、`error_type`、`status`、`skip`/`limit`。

#### POST /api/suspected-errors/{id}/resolve（data/admin）

```json
{
  "status": "confirmed",
  "resolution_note": "确认为重复物料，已在源系统合并"
}
```

status 仅允许 confirmed/resolved/false_positive；`resolved_by` 取当前登录用户，不接受请求体传入。

---

## 4. 字段访问层与数据源映射

检测引擎不直接查各实体表，统一走字段访问层，屏蔽三实体存储差异：

```python
class EntityFieldAccessor:
    def get_field(self, entity_type: str, entity_id: str, field_name: str) -> Any | None
    def list_entities(self, entity_type: str, entity_ids: list[str] | None = None) -> list
```

### 4.1 物料字段映射（material_records）

| SAP 字段 | 数据源 | 说明 |
|---------|--------|------|
| MATNR | material_records.material_code | 冗余列 |
| MAKTX | material_records.material_name | 冗余列 |
| MTART/MEINS/MATKL/BRGEW/NTGEW/GEWEI | material_records.attributes JSON | 键名与数据标准 field_name 一致 |
| WERKS/EKGRP/LGORT | 无数据源 | 工厂/采购/库存视图字段：标准可定义；检测时记"数据源缺失"并跳过 |

### 4.2 供应商/客户字段

`partner_records.attributes` 以 SAP 字段名为键，直接按 `field_name` 取值；`partner_code` 对应 LIFNR/KUNNR，`partner_name` 对应 NAME1。

---

## 5. 检测执行语义

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
- 处理对话框：状态选择、处理说明（预填 1.6 审核意见模板，用户可改）；details 展开显示相似实体列表与处置建议（保留/停用）

---

## 7. 实施计划

### Phase 0：申请链路移除收尾（1-2 天）

代码库当前处于迁移中间态：模型已收缩为 4 张表（data_standards / material_records / partner_records / audit_logs），但 api 路由、部分服务与前端仍残留申请链路引用。收尾内容：

1. 移除 applications / golden_records / governance_rules / classifications / metadata_governance 等申请链路 API 路由与前端页面路由
2. 移除 code_generator / material_validator / btp_mock / openmetadata_sync 服务与发布同步任务
3. 保留并改造 duplicate_detector（去除对已删 crud 的依赖）供 Phase 3 复用；audit_service 保留
4. 更新 init_db、e2e 脚本与前端导航

**验收**：后端启动无 ImportError；pytest 全绿；前端 lint/tsc/build 零错误；代码库无**业务**申请/审批/金标/分发链路残留引用（AI 辅助治理层的治理裁决与归并建议能力见 §1.4.1，属治理闭环，不在本判据限制内）。

### Phase 1：存量存储 + 数据标准管理（3 天）

1. MaterialRecord + PartnerRecord 模型 + init_db 建表 + Mock 种子（物料/供应商/客户各 ≥ 20 条，含故意脏数据供检测演示）
2. DataStandard 模型 + 种子数据（附录字段）
3. CRUD API + 权限矩阵 + 审计
4. 前端数据标准管理页

**验收**：三实体标准可增删改查；物料/供应商/客户 Mock 数据入库；user/dept 角色写操作返回 403；写操作有审计记录。

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

**总工期：10-14 天**（含 Phase 0 申请链路移除收尾）。

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

## 9. 与浪潮 MDM V2.0 产品白皮书的对照

评审参照《浪潮主数据管理 V2.0 产品白皮书》（27 页）校验本 SPEC 的功能设计取向：

| 白皮书能力 | 本 SPEC 对应 | 结论 |
|-----------|-------------|------|
| 基础字典全生命周期（申请→审批→维护→变更→日志） | 本系统只承接"维护 + 日志"（数据标准 CRUD + audit_logs）；申请/审批属上游系统，变更审批不做（1.3） | 定位差异：治理面收窄，明确接受 |
| 清洗规则 = 临界相似度 + 清洗依据字段 | duplicate_check 的 similarity_threshold + field | 一致 |
| 清洗规则中的合并规则 | 不做自动合并；疑似错误人工处理 + details 处置建议 | 定位差异：只检测不修复 |
| 数据清洗对重复数据做停用处理 | 处置建议采用"停用优先于删除"语义，人工执行 | 借鉴 |
| 数据映射（业务系统编码 ↔ 标准编码） | 无 | 明确列入 1.3 后续迭代，避免缺位 |
| 物资编码申请保存时自动查重 | 申请流程已移除；存量重复检测由 duplicate_check 规则承接 | 已覆盖 |
| 按岗位权限查询字典 | 3.0 权限矩阵 | 印证 |
| 主数据同步 / 适配器 / 字段映射下发 | 无——分发（BTP/OM 发布）已随申请链路移出系统职能（1.3） | 不做；如需分发再立 SPEC |
| 私有/公有主数据分级管理 | 无 | 不做（单一企业演示场景） |

---

## 10. 附录：SAP 核心字段

### 10.1 SAP 物料主数据核心字段

| SAP 表 | 字段 | 描述 | 本系统数据源 |
|--------|------|------|-------------|
| MARA | MATNR | 物料编码 | material_records.material_code |
| MARA | MAKTX | 物料描述 | material_records.material_name |
| MARA | MEINS | 基本计量单位 | attributes |
| MARA | MATKL | 物料组 | attributes |
| MARA | MTART | 物料类型 | attributes |
| MARA | BRGEW | 毛重 | attributes |
| MARA | NTGEW | 净重 | attributes |
| MARA | GEWEI | 重量单位 | attributes |
| MARC | WERKS | 工厂 | 无数据源（检测跳过） |
| MARC | EKGRP | 采购组 | 无数据源（检测跳过） |
| MARC | DISMM | MRP 参数文件 | 无数据源（检测跳过） |
| MARD | LGORT | 存储位置 | 无数据源（检测跳过） |
| MAKT | SPRAS | 语言代码 | 无数据源（检测跳过） |

### 10.2 SAP BP 核心字段

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

## 11. 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | 2026-08-23 | 初始版本 |
| v1.1 | 2026-09-01 | 评审修订：保留供应商/客户并新增 PartnerRecord 存量存储；明确本 SPEC 为存量治理唯一规则体系（与申请流程 GovernanceRule 独立）；删除 custom_check；新增检测批次表、结果只存失败项；新增字段访问层与映射表；补权限矩阵、审计、重检去重、状态机；修唯一约束与 MATNR 正则；API 命名修正 |
| v1.2 | 2026-09-01 | 参照浪潮 MDM V2.0 白皮书与治理框架补充：1.5 治理能力框架收敛为模型承接（DataStandard 增加 owner/standard_source/dept_scope 管理属性列 + 质量维度与规则类型映射，v1 覆盖完整性/唯一性/有效性/规范性四维度）；1.6 疑似重复审核标准化对接状态机（误报白名单防重复召回、审核意见模板进前端、不加新状态）；业务系统编码映射明确列入后续迭代；疑似错误处置建议采用停用语义（人工执行）；新增第 9 节白皮书对照 |
| v1.3 | 2026-09-01 | 定稿基线：正文清理过程性修订标注（版本痕迹归入本表），状态改为已定稿，进入实施 |
| v1.3 | 2026-09-01 | 系统定位收敛：本系统只做存量数据治理与数据质量管理服务，申请/审批/金标/分发（BTP/OpenMetadata 发布）移出代码库；物料存量数据源由 golden_records 改为新建 material_records（MARA 风格，与 partner_records 对称）；DataStandard 属性方案合并：管理属性 owner/standard_source/dept_scope 三结构化列 + 业务属性 business_attrs JSON；**定稿基线**：正文清理过程性修订标注，新增 Phase 0 申请链路移除收尾任务，对照表同步定位变更 |
| v1.4 | 2026-09-02 | 承认 AI 辅助治理层为正式范围：新增 §1.4.1（Agent 只出建议、Skill 确定性无副作用、归并仅返回 ready、Copilot 审批=治理裁决而非业务审批、LLM 可降级）；Phase 0 验收判据改写为"无**业务**申请/审批/金标/分发链路残留"；据此保留 T1-T8 构建的 agents/skills/llm_gateway 与 copilot/governance/owners/evidence 路由及对应前端页面，取消分支隔离动议 |
