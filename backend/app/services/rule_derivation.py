"""quality_check_rules 种子派生（SPEC §2.4 + Phase 2 设计决策 1）。

DataStandard 结构化列 → v1 五种规则行。派生条件与
`quality_engine.checks_from_standards` 的展开逻辑一一对应，
保证「标准直接展开」与「规则行执行」两条路径产生相同的检查。

无 Session：纯函数，供 init_db 与测试共用。
"""
from typing import Iterable, List

from app import models
from app.services.quality_engine import NUMERIC_DATA_TYPES

RULE_TYPE_LABELS = {
    models.RuleType.NULL_CHECK: "必填检查",
    models.RuleType.FORMAT_CHECK: "格式检查",
    models.RuleType.RANGE_CHECK: "值域检查",
    models.RuleType.LENGTH_CHECK: "长度检查",
    models.RuleType.UNIQUE_CHECK: "唯一性检查",
}


def _enum_values(standard: models.DataStandard) -> list:
    values = getattr(standard, "enum_values", None)
    if values is None:
        return []
    if isinstance(values, (list, tuple, set, frozenset)):
        return list(values)
    return [values]


def derive_rules(standard: models.DataStandard) -> List[models.QualityCheckRule]:
    """把一条 DataStandard 展开成规则行（最多 5 条）。

    派生条件与 `quality_engine.checks_from_standards` 同源：
    - required → null_check
    - pattern → format_check
    - enum / min / max / 数值类型 → range_check
    - max_length > 0 → length_check
    - unique → unique_check

    无任何约束的标准派生 0 条；无 field_name 的标准同样跳过。
    """
    if not getattr(standard, "field_name", None):
        return []

    data_type = (getattr(standard, "data_type", None) or "").strip().lower()
    enum_values = _enum_values(standard)
    min_value = getattr(standard, "min_value", None)
    max_value = getattr(standard, "max_value", None)
    max_length = getattr(standard, "max_length", None)

    rule_types: List[models.RuleType] = []
    if getattr(standard, "required", False):
        rule_types.append(models.RuleType.NULL_CHECK)
    if getattr(standard, "pattern", None):
        rule_types.append(models.RuleType.FORMAT_CHECK)
    if (
        enum_values
        or min_value is not None
        or max_value is not None
        or data_type in NUMERIC_DATA_TYPES
    ):
        rule_types.append(models.RuleType.RANGE_CHECK)
    if max_length is not None and int(max_length) > 0:
        rule_types.append(models.RuleType.LENGTH_CHECK)
    if getattr(standard, "unique", False):
        rule_types.append(models.RuleType.UNIQUE_CHECK)

    label = getattr(standard, "field_label", None) or standard.field_name
    return [
        models.QualityCheckRule(
            name=f"{label}·{RULE_TYPE_LABELS[rule_type]}",
            description=f"由数据标准 {standard.field_name} 派生（{standard.id}）",
            entity_type=standard.entity_type,
            rule_type=rule_type,
            field_name=standard.field_name,
            standard_id=standard.id,
            rule_config={},
            severity="error",
            is_active=True,
        )
        for rule_type in rule_types
    ]


def derive_rule_rows(
    standards: Iterable[models.DataStandard],
) -> List[models.QualityCheckRule]:
    """多条标准 → 规则行（扁平化）。"""
    rows: List[models.QualityCheckRule] = []
    for standard in standards or []:
        rows.extend(derive_rules(standard))
    return rows
