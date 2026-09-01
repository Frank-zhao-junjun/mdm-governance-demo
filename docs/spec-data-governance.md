# 主数据字段治理 SPEC（规格说明）

> **版本**：v1.0  
> **日期**：2026-08-23  
> **状态**：设计中

---

## 1. 概述

### 1.1 目标

基于 SAP 系统的物料主数据（MARA/MARC/MARD/MAKT）和供应商/客户主数据（BP/LFA1/KNA1），建立完整的数据治理体系，包括：

1. **数据标准管理**：定义各字段的数据标准（命名规范、值域范围、必填规则）
2. **数据质量检测**：基于标准进行自动化质量检测
3. **疑似错误检测**：智能识别重复、不规范、异常数据

### 1.2 范围

| 主数据类型 | SAP 表/对象 | 治理范围 |
|-----------|------------|----------|
| 物料主数据 | MARA（基本视图）、MARC（采购视图）、MARD（库存视图）、MAKT（多语言描述） | 字段标准、质量检测、疑似错误 |
| 供应商主数据 | BUT000（BP 通用）、LFA1（供应商视图）、BUT020（地址）、BUT0BANK（银行） | 字段标准、质量检测、疑似错误 |
| 客户主数据 | BUT000（BP 通用）、KNA1（客户视图）、BUT020（地址）、BUT0BANK（银行） | 字段标准、质量检测、疑似错误 |

### 1.3 不在范围内

- SAP 系统对接（当前为 Mock 实现）
- 数据修复/清洗（只检测和报告，不自动修复）
- 审批流程（数据标准变更审批）

---

## 2. 数据模型设计

### 2.1 数据标准（DataStandard）

定义各实体（物料/供应商/客户）各字段的数据标准。

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
    max_length = Column(Integer, nullable=True)  # 最大长度（字符串）
    min_value = Column(Float, nullable=True)  # 最小值（数字）
    max_value = Column(Float, nullable=True)  # 最大值（数字）
    enum_values = Column(JSON, nullable=True)  # 枚举值列表 ["A", "B", "C"]
    
    # 校验规则
    required = Column(Boolean, default=False)  # 是否必填
    pattern = Column(String(200), nullable=True)  # 正则表达式（格式校验）
    unique = Column(Boolean, default=False)  # 是否唯一
    
    # 元数据
    description = Column(Text, nullable=True)  # 字段说明
    sap_field_desc = Column(Text, nullable=True)  # SAP 字段说明
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)
    
    # 唯一约束
    __table_args__ = (
        UniqueConstraint("entity_type", "field_name", name="uq_entity_field"),
    )
```

**示例数据**：

| entity_type | sap_table | field_name | field_label | data_type | required | pattern |
|-------------|-----------|------------|-------------|-----------|----------|---------|
| material | MARA | MATNR | 物料编码 | string | true | ^[A-Z0-9]{18}$ |
| material | MARA | MAKTX | 物料描述 | string | true | null |
| material | MARA | MEINS | 基本计量单位 | string | true | null |
| material | MARA | MATKL | 物料组 | string | true | null |
| supplier | BUT000 | BU_TYPE | BP 类型 | enum | true | null |
| supplier | LFA1 | LIFNR | 供应商编号 | string | true | ^[0-9]{10}$ |
| supplier | LFA1 | NAME1 | 供应商名称 | string | true | null |
| customer | KNA1 | KUNNR | 客户编号 | string | true | ^[0-9]{10}$ |
| customer | KNA1 | NAME1 | 客户名称 | string | true | null |

### 2.2 质量检测规则（QualityCheckRule）

定义质量检测规则，基于数据标准生成或自定义。

```python
class QualityCheckRule(Base):
    """质量检测规则"""
    __tablename__ = "quality_check_rules"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 规则信息
    name = Column(String(200), nullable=False)  # 规则名称
    description = Column(Text, nullable=True)  # 规则说明
    entity_type = Column(String(50), nullable=False, index=True)  # material / supplier / customer
    
    # 规则类型
    rule_type = Column(String(50), nullable=False)  # 见下方规则类型枚举
    field_name = Column(String(100), nullable=True)  # 关联字段（可选）
    standard_id = Column(String(36), ForeignKey("data_standards.id"), nullable=True)  # 关联数据标准（可选）
    
    # 规则配置
    rule_config = Column(JSON, nullable=False)  # 规则配置（JSON）
    severity = Column(String(20), nullable=False, default="error")  # error / warning / info
    
    # 状态
    is_active = Column(Boolean, default=True)  # 是否启用
    
    created_at = Column(DateTime, default=_now_utc)
    updated_at = Column(DateTime, default=_now_utc, onupdate=_now_utc)


class RuleType(str, PyEnum):
    """规则类型"""
    NULL_CHECK = "null_check"  # 空值检测
    FORMAT_CHECK = "format_check"  # 格式校验（正则）
    RANGE_CHECK = "range_check"  # 值域检查（min/max/enum）
    LENGTH_CHECK = "length_check"  # 长度检查
    UNIQUE_CHECK = "unique_check"  # 唯一性检查
    DUPLICATE_CHECK = "duplicate_check"  # 重复检测（模糊匹配）
    CUSTOM_CHECK = "custom_check"  # 自定义规则（SQL 表达式）
```

**规则配置示例**：

```json
// null_check
{
  "field": "MAKTX",
  "condition": "is_null"
}

// format_check
{
  "field": "MATNR",
  "pattern": "^[A-Z0-9]{18}$",
  "message": "物料编码必须为 18 位大写字母或数字"
}

// range_check
{
  "field": "MATKL",
  "enum": ["001", "002", "003"],
  "message": "物料组必须在枚举值范围内"
}

// duplicate_check
{
  "field": "MAKTX",
  "similarity_threshold": 0.8,
  "algorithm": "jaccard",
  "message": "检测到相似物料描述"
}
```

### 2.3 质量检测结果（QualityCheckResult）

记录每次质量检测的结果。

```python
class QualityCheckResult(Base):
    """质量检测结果"""
    __tablename__ = "quality_check_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 关联
    rule_id = Column(String(36), ForeignKey("quality_check_rules.id"), nullable=False)
    entity_id = Column(String(36), nullable=False)  # 物料/供应商/客户 ID
    entity_type = Column(String(50), nullable=False, index=True)
    
    # 检测信息
    field_name = Column(String(100), nullable=True)
    field_value = Column(String(500), nullable=True)  # 当前值
    passed = Column(Boolean, nullable=False)  # 是否通过
    severity = Column(String(20), nullable=False)  # error / warning / info
    message = Column(Text, nullable=True)  # 错误/警告信息
    
    # 元数据
    checked_at = Column(DateTime, default=_now_utc, index=True)
    batch_id = Column(String(36), nullable=True, index=True)  # 批次 ID（批量检测）
```

### 2.4 疑似错误（SuspectedError）

记录智能检测到的疑似错误，需要人工确认。

```python
class SuspectedError(Base):
    """疑似错误"""
    __tablename__ = "suspected_errors"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 实体信息
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False)
    entity_label = Column(String(200), nullable=True)  # 实体标签（物料描述/供应商名称）
    
    # 错误信息
    error_type = Column(String(50), nullable=False)  # duplicate / naming / classification / unit
    severity = Column(String(20), nullable=False, default="warning")  # error / warning / info
    title = Column(String(200), nullable=False)  # 错误标题
    description = Column(Text, nullable=True)  # 错误描述
    details = Column(JSON, nullable=True)  # 详细信息（如相似物料列表）
    
    # 状态
    status = Column(String(20), nullable=False, default="pending")  # pending / confirmed / resolved / false_positive
    resolved_by = Column(String(50), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)
    
    # 元数据
    detected_at = Column(DateTime, default=_now_utc, index=True)
    detected_by = Column(String(50), nullable=True)  # 检测规则 ID 或 "system"
```

**错误类型枚举**：

```python
class ErrorType(str, PyEnum):
    DUPLICATE = "duplicate"  # 重复数据
    NAMING = "naming"  # 命名不规范
    CLASSIFICATION = "classification"  # 分类错误
    UNIT = "unit"  # 计量单位异常
    MISSING = "missing"  # 必填字段缺失
    FORMAT = "format"  # 格式错误
    RANGE = "range"  # 值域超出
    OTHER = "other"  # 其他
```

---

## 3. API 接口设计

### 3.1 数据标准管理

#### GET /api/data-standards

列出数据标准。

**请求参数**：
- `entity_type`（可选）：material / supplier / customer
- `sap_table`（可选）：MARA / MARC / BUT000 等
- `skip`（默认 0）：分页偏移
- `limit`（默认 50，最大 500）：每页数量

**响应**：
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
      "pattern": "^[A-Z0-9]{18}$",
      "description": "物料主编码，18 位大写字母或数字"
    }
  ]
}
```

#### POST /api/data-standards

创建数据标准。

**请求体**：
```json
{
  "entity_type": "material",
  "sap_table": "MARA",
  "field_name": "MATNR",
  "field_label": "物料编码",
  "data_type": "string",
  "max_length": 18,
  "required": true,
  "pattern": "^[A-Z0-9]{18}$",
  "description": "物料主编码，18 位大写字母或数字"
}
```

**响应**：
```json
{
  "id": "uuid",
  "entity_type": "material",
  ...
}
```

#### PUT /api/data-standards/{id}

更新数据标准。

#### DELETE /api/data-standards/{id}

删除数据标准。

### 3.2 质量检测

#### POST /api/quality-checks/run

执行质量检测。

**请求体**：
```json
{
  "entity_type": "material",
  "entity_ids": ["uuid1", "uuid2"],  // 可选，不传则检测全部
  "rule_ids": ["uuid1"],  // 可选，不传则使用所有启用的规则
  "batch": true  // 是否批量检测
}
```

**响应**：
```json
{
  "batch_id": "uuid",
  "total_checked": 100,
  "passed": 85,
  "failed": 15,
  "results": [
    {
      "id": "uuid",
      "entity_id": "uuid1",
      "entity_type": "material",
      "field_name": "MAKTX",
      "field_value": null,
      "passed": false,
      "severity": "error",
      "message": "物料描述不能为空"
    }
  ]
}
```

#### GET /api/quality-checks/results

查询质量检测结果。

**请求参数**：
- `entity_type`（可选）
- `entity_id`（可选）
- `passed`（可选）：true / false
- `severity`（可选）：error / warning / info
- `batch_id`（可选）
- `skip` / `limit`

**响应**：
```json
{
  "total": 50,
  "items": [
    {
      "id": "uuid",
      "rule_id": "uuid",
      "entity_id": "uuid1",
      "entity_type": "material",
      "field_name": "MAKTX",
      "field_value": null,
      "passed": false,
      "severity": "error",
      "message": "物料描述不能为空",
      "checked_at": "2026-08-23T10:00:00Z"
    }
  ]
}
```

#### GET /api/quality-checks/report

生成质量报告。

**请求参数**：
- `entity_type`（可选）
- `batch_id`（可选）

**响应**：
```json
{
  "entity_type": "material",
  "total_entities": 1000,
  "total_checks": 5000,
  "passed": 4500,
  "failed": 500,
  "pass_rate": 0.9,
  "by_severity": {
    "error": 100,
    "warning": 300,
    "info": 100
  },
  "by_rule": [
    {
      "rule_id": "uuid",
      "rule_name": "物料描述非空检查",
      "total": 1000,
      "passed": 900,
      "failed": 100,
      "pass_rate": 0.9
    }
  ],
  "top_issues": [
    {
      "field_name": "MAKTX",
      "issue_count": 100,
      "issue_type": "null_check",
      "message": "物料描述为空"
    }
  ]
}
```

### 3.3 疑似错误检测

#### POST /api/suspected-errors/detect

执行疑似错误检测。

**请求体**：
```json
{
  "entity_type": "material",
  "error_types": ["duplicate", "naming"],  // 可选，不传则检测全部
  "entity_ids": ["uuid1", "uuid2"]  // 可选，不传则检测全部
}
```

**响应**：
```json
{
  "total_detected": 25,
  "errors": [
    {
      "id": "uuid",
      "entity_type": "material",
      "entity_id": "uuid1",
      "entity_label": "不锈钢螺丝 M8x20",
      "error_type": "duplicate",
      "severity": "warning",
      "title": "疑似重复物料",
      "description": "检测到 2 个相似物料",
      "details": {
        "similar_entities": [
          {
            "entity_id": "uuid2",
            "entity_label": "不锈钢螺钉 M8x20",
            "similarity": 0.95
          }
        ]
      },
      "status": "pending",
      "detected_at": "2026-08-23T10:00:00Z"
    }
  ]
}
```

#### GET /api/suspected-errors/list

列出疑似错误。

**请求参数**：
- `entity_type`（可选）
- `error_type`（可选）
- `status`（可选）：pending / confirmed / resolved / false_positive
- `skip` / `limit`

**响应**：
```json
{
  "total": 50,
  "items": [
    {
      "id": "uuid",
      "entity_type": "material",
      "entity_id": "uuid1",
      "entity_label": "不锈钢螺丝 M8x20",
      "error_type": "duplicate",
      "severity": "warning",
      "title": "疑似重复物料",
      "description": "检测到 2 个相似物料",
      "status": "pending",
      "detected_at": "2026-08-23T10:00:00Z"
    }
  ]
}
```

#### POST /api/suspected-errors/{id}/resolve

标记疑似错误为已处理。

**请求体**：
```json
{
  "status": "confirmed",  // confirmed / resolved / false_positive
  "resolution_note": "确认为重复物料，已合并"
}
```

**响应**：
```json
{
  "id": "uuid",
  "status": "confirmed",
  "resolved_by": "admin001",
  "resolved_at": "2026-08-23T11:00:00Z",
  "resolution_note": "确认为重复物料，已合并"
}
```

---

## 4. 前端 UI 设计

### 4.1 页面结构

```
/quality
├── /quality/standards          # 数据标准管理
├── /quality/checks             # 质量检测
│   ├── /quality/checks/run     # 执行检测
│   ├── /quality/checks/results # 检测结果
│   └── /quality/checks/report  # 质量报告
└── /quality/suspected          # 疑似错误
```

### 4.2 数据标准管理页面

**功能**：
- 列表展示所有数据标准
- 按实体类型（物料/供应商/客户）筛选
- 按 SAP 表筛选
- 创建/编辑/删除数据标准

**UI 组件**：
- 筛选栏：实体类型下拉、SAP 表下拉、搜索框
- 数据表格：字段名、字段标签、数据类型、是否必填、校验规则
- 操作按钮：新建、编辑、删除

### 4.3 质量检测页面

**功能**：
- 执行质量检测（选择实体类型、实体、规则）
- 查看检测结果列表
- 查看质量报告（图表、统计）

**UI 组件**：
- 执行检测表单：实体类型、实体选择（多选）、规则选择（多选）
- 检测结果表格：实体、字段、当前值、是否通过、严重程度、错误信息
- 质量报告：通过率饼图、按规则统计表、Top 问题列表

### 4.4 疑似错误页面

**功能**：
- 执行疑似错误检测
- 查看疑似错误列表
- 处理疑似错误（确认/解决/误报）

**UI 组件**：
- 检测按钮：执行检测
- 疑似错误表格：实体、错误类型、严重程度、标题、状态、检测时间
- 处理对话框：状态选择、处理说明

---

## 5. 实施计划

### Phase 1：数据标准管理（2-3 天）

**任务**：
1. 创建 DataStandard 数据模型
2. 实现 CRUD API
3. 实现前端数据标准管理页面
4. 导入 SAP 标准字段数据（物料/供应商/客户）

**验收标准**：
- ✅ 可以创建/编辑/删除数据标准
- ✅ 可以按实体类型和 SAP 表筛选
- ✅ 预置 SAP 标准字段数据

### Phase 2：数据质量检测（3-5 天）

**任务**：
1. 创建 QualityCheckRule 和 QualityCheckResult 数据模型
2. 实现规则引擎（null_check / format_check / range_check / length_check / unique_check）
3. 实现质量检测 API
4. 实现前端质量检测页面（执行检测、查看结果、质量报告）

**验收标准**：
- ✅ 可以执行质量检测
- ✅ 可以查看检测结果
- ✅ 可以生成质量报告（图表）
- ✅ 支持 5 种基础规则类型

### Phase 3：疑似错误检测（2-3 天）

**任务**：
1. 创建 SuspectedError 数据模型
2. 实现疑似错误检测算法（重复检测、命名不规范检测）
3. 实现疑似错误 API
4. 实现前端疑似错误页面（列表、处理）

**验收标准**：
- ✅ 可以执行疑似错误检测
- ✅ 可以查看疑似错误列表
- ✅ 可以处理疑似错误（确认/解决/误报）
- ✅ 支持重复检测和命名不规范检测

---

## 6. 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 重复检测算法性能 | 高 | 使用索引、分批检测、异步任务 |
| 数据标准导入工作量 | 中 | 预置 SAP 标准字段模板 |
| 前端图表库选择 | 低 | 使用 recharts（已集成） |
| 批量检测性能 | 中 | 使用后台任务、分页处理 |

---

## 7. 附录

### 7.1 SAP 物料主数据核心字段

| SAP 表 | 字段 | 描述 |
|--------|------|------|
| MARA | MATNR | 物料编码 |
| MARA | MAKTX | 物料描述 |
| MARA | MEINS | 基本计量单位 |
| MARA | MATKL | 物料组 |
| MARA | MTART | 物料类型 |
| MARA | BRGEW | 毛重 |
| MARA | NTGEW | 净重 |
| MARA | GEWEI | 重量单位 |
| MARC | WERKS | 工厂 |
| MARC | EKGRP | 采购组 |
| MARC | DISMM | MRB 参数文件 |
| MARD | LGORT | 存储位置 |
| MARD | CHARG | 批次号 |
| MAKT | SPRAS | 语言代码 |
| MAKT | MAKTX | 物料描述（多语言） |

### 7.2 SAP BP 核心字段

| SAP 表 | 字段 | 描述 |
|--------|------|------|
| BUT000 | PARTNER | BP 编号 |
| BUT000 | BU_TYPE | BP 类型 |
| BUT000 | NAME_ORG1 | 组织名称 1 |
| BUT000 | NAME_ORG2 | 组织名称 2 |
| BUT000 | NAME_LAST | 姓氏 |
| BUT000 | NAME_FIRST | 名字 |
| BUT020 | STREET | 街道 |
| BUT020 | CITY1 | 城市 |
| BUT020 | POST_CODE1 | 邮编 |
| BUT020 | COUNTRY | 国家 |
| BUT0BANK | BANKS | 银行代码 |
| BUT0BANK | BANKL | 银行账号 |
| LFA1 | LIFNR | 供应商编号 |
| LFA1 | NAME1 | 供应商名称 |
| LFA1 | LAND1 | 国家 |
| LFA1 | ZTERM | 付款条件 |
| KNA1 | KUNNR | 客户编号 |
| KNA1 | NAME1 | 客户名称 |
| KNA1 | LAND1 | 国家 |
| KNA1 | ZTERM | 付款条件 |

---

## 8. 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | 2026-08-23 | 初始版本，完成数据模型、API、UI 设计 |
