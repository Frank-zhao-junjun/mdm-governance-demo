"""质量检测规则引擎（SPEC §2.4 规则类型、§5 检测执行语义）。

**纯函数、无 Session**：输入是"规则 + 已加载的存量记录"，输出是失败明细，
调用方（API 层）负责把批次统计与失败项写库（SPEC §2.5 / §2.6 —— 通过项不落库，
只计入批次统计）。

v1 支持的五种规则（§1.5.6 质量维度映射，不多假装覆盖）：

| RuleType | SPEC 落库名 | 数据来源（DataStandard 列）        | 覆盖维度 |
|----------|-------------|----------------------------------|----------|
| null     | null_check  | required                         | 完整性   |
| format   | format_check| pattern（数值转换失败也归此类）    | 规范性   |
| range    | range_check | min_value / max_value / enum_values | 有效性 |
| length   | length_check| max_length                       | 规范性   |
| unique   | unique_check| unique                           | 唯一性   |

硬性语义（§5）：
- **无数据源即跳过**：字段在 `entity_accessor` 判定为无数据源时，整条规则不执行，
  记入 `QualityRunResult.skipped`（含原因与跳过行数），**不产生 null 假告警**。
- **数值转换失败 = format 错误**，不是 range 错误（§5.4）。
- **unique 按规范化值分组**，组内成员数 > 1 时组内每一行都出一条失败（一次哈希
  分组，非两两比较）。
- 空值不参与 format / range / length / unique：缺失由 null 规则独占，避免一个
  缺失字段刷出 4 条重复告警。
- 正则只允许来自 `DataStandard.pattern`（`standard.pattern` 列，长度 ≤ 200，由
  data/admin 经审计写入）；**绝不**执行请求体或 rule_config 里带来的正则，
  **没有** custom_check，也**没有任何** SQL 拼接/执行。编译失败降级为
  `QualityRunResult.rule_errors` 记录，不抛异常打断整批。
- 复杂度 O(规则数 × 行数)；unique 另加一次对行数的哈希分组，不存在对记录集合的
  二次遍历。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from enum import Enum as PyEnum
from typing import Any, Iterable, Optional, Sequence

from app.services.entity_accessor import (
    AccessResult,
    FieldSource,
    describe_source,
    display_value,
    is_blank,
    read_value,
    record_id,
    record_label,
)

MAX_PATTERN_LENGTH = 200  # 与 DataStandard.pattern 列宽一致，防止异常输入拖垮匹配
MAX_MESSAGE_VALUE = 120


class RuleType(str, PyEnum):
    """v1 规则类型（短名，用于引擎内部与 finding.rule_type）。"""

    NULL = "null"
    FORMAT = "format"
    RANGE = "range"
    LENGTH = "length"
    UNIQUE = "unique"


#: 短名 → SPEC §2.4 RuleType / 结果表落库名（供 API 层写 quality_check_results）
RULE_TYPE_CODES = {
    RuleType.NULL.value: "null_check",
    RuleType.FORMAT.value: "format_check",
    RuleType.RANGE.value: "range_check",
    RuleType.LENGTH.value: "length_check",
    RuleType.UNIQUE.value: "unique_check",
}

#: 落库名/别名 → 短名，便于把 quality_check_rules.rule_type 直接喂进来
RULE_TYPE_ALIASES = {
    "null": RuleType.NULL.value,
    "null_check": RuleType.NULL.value,
    "format": RuleType.FORMAT.value,
    "format_check": RuleType.FORMAT.value,
    "range": RuleType.RANGE.value,
    "range_check": RuleType.RANGE.value,
    "length": RuleType.LENGTH.value,
    "length_check": RuleType.LENGTH.value,
    "unique": RuleType.UNIQUE.value,
    "unique_check": RuleType.UNIQUE.value,
}

#: 明确不支持的规则类型：duplicate_check 属 Phase 3 疑似错误流程；
#: custom_check 已按 SPEC §2.4 设计约束删除（可配置 SQL = 注入口子）。
UNSUPPORTED_RULE_TYPES = frozenset({"duplicate", "duplicate_check", "custom", "custom_check"})

#: 需要按数值语义处理的 data_type（§5.4）
NUMERIC_DATA_TYPES = frozenset({"number", "amount"})


# ========== 规则描述符 ==========

@dataclass(frozen=True)
class RuleDescriptor:
    """引擎实际执行的一条检查：字段 + 规则类型 + 结构化约束。

    字段值全部来自 DataStandard 的结构化列（或 quality_check_rules 经标准解析后
    的结果）；`pattern` 只允许来自 `DataStandard.pattern`。
    """

    field_name: str
    rule_type: str
    entity_type: Optional[str] = None
    field_label: Optional[str] = None
    severity: str = "error"
    message: Optional[str] = None
    rule_id: Optional[str] = None
    standard_id: Optional[str] = None
    pattern: Optional[str] = None
    enum_values: Optional[tuple[Any, ...]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    max_length: Optional[int] = None
    numeric: bool = False

    @property
    def label(self) -> str:
        return self.field_label or self.field_name

    @property
    def rule_code(self) -> str:
        """结果表落库用的规则类型名（SPEC §2.4）。"""
        return rule_code_for(self.rule_type)


@dataclass(frozen=True)
class QualityFinding:
    """一条失败明细（SPEC §2.6：只有失败项会被持久化）。"""

    entity_id: str
    entity_label: str
    field_name: str
    field_label: str
    rule_type: str
    message: str
    entity_type: Optional[str] = None
    severity: str = "error"
    field_value: str = ""
    rule_id: Optional[str] = None
    standard_id: Optional[str] = None

    @property
    def rule_code(self) -> str:
        return rule_code_for(self.rule_type)


@dataclass(frozen=True)
class SkippedField:
    """因无数据源而整条规则未执行的记录（SPEC §4.1、§5 验收项）。"""

    entity_type: str
    field_name: str
    rule_type: str
    reason: str
    field_label: Optional[str] = None
    rule_id: Optional[str] = None
    standard_id: Optional[str] = None
    entity_count: int = 0

    @property
    def rule_code(self) -> str:
        return rule_code_for(self.rule_type)


@dataclass(frozen=True)
class RuleConfigError:
    """规则自身不可执行（正则编译失败等），降级记录，不影响整批。"""

    rule_type: str
    field_name: str
    reason: str
    rule_id: Optional[str] = None
    standard_id: Optional[str] = None
    field_label: Optional[str] = None

    @property
    def rule_code(self) -> str:
        return rule_code_for(self.rule_type)


@dataclass
class QualityRunResult:
    """一次检测执行的结果容器（调用方据此写 batch + 失败明细）。"""

    entity_type: str
    total_entities: int = 0
    total_checks: int = 0
    findings: list[QualityFinding] = field(default_factory=list)
    skipped: list[SkippedField] = field(default_factory=list)
    rule_errors: list[RuleConfigError] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return len(self.findings)

    @property
    def passed(self) -> int:
        return self.total_checks - self.failed

    @property
    def skipped_checks(self) -> int:
        return sum(s.entity_count for s in self.skipped)

    @property
    def pass_rate(self) -> float:
        return round(self.passed / self.total_checks, 4) if self.total_checks else 1.0

    def summary(self) -> dict[str, Any]:
        """对齐 QualityCheckBatch 列名，可直接进批次表/接口响应。"""
        return {
            "entity_type": self.entity_type,
            "total_entities": self.total_entities,
            "total_checks": self.total_checks,
            "passed": self.passed,
            "failed": self.failed,
            "skipped_fields": [
                {"field_name": s.field_name, "rule_type": s.rule_code, "reason": s.reason,
                 "entity_count": s.entity_count}
                for s in self.skipped
            ],
            "rule_errors": [
                {"field_name": r.field_name, "rule_type": r.rule_code, "reason": r.reason}
                for r in self.rule_errors
            ],
        }


# ========== 标准 / 规则行 → 规则描述符 ==========

def _as_tuple(values: Any) -> Optional[tuple[Any, ...]]:
    if values is None:
        return None
    if isinstance(values, (str, bytes)):
        return (values,)
    if isinstance(values, (list, tuple, set, frozenset)):
        items = tuple(values)
        return items or None
    return None


def _as_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_rule_type(value: Any) -> Optional[str]:
    """把 null / null_check / RuleType.NULL 等写法收敛为引擎短名；未知返回 None。"""
    raw = str(getattr(value, "value", value) or "").strip().lower()
    return RULE_TYPE_ALIASES.get(raw)


def rule_code_for(rule_type: Any) -> str:
    """规则类型 → SPEC §2.4 落库名（null → null_check；未知值原样保底加后缀）。"""
    text = str(getattr(rule_type, "value", rule_type) or "").strip().lower()
    if text in RULE_TYPE_CODES:
        return RULE_TYPE_CODES[text]
    return text if text.endswith("_check") else f"{text}_check"


def checks_from_standards(
    standards: Iterable[Any],
    rule_types: Optional[Iterable[Any]] = None,
) -> list[RuleDescriptor]:
    """把 DataStandard 行展开成规则描述符（SPEC §2.1 结构化列 → §5 五种检查）。

    展开顺序固定为 null → format → range → length → unique，便于结果可预期。
    """
    wanted = _rule_type_filter(rule_types)
    checks: list[RuleDescriptor] = []
    for standard in standards or []:
        field_name = (getattr(standard, "field_name", None) or "").strip()
        if not field_name:
            continue
        base = dict(
            entity_type=getattr(standard, "entity_type", None),
            field_name=field_name,
            field_label=getattr(standard, "field_label", None) or field_name,
            standard_id=getattr(standard, "id", None),
            severity="error",
        )
        data_type = (getattr(standard, "data_type", None) or "").strip().lower()
        enum_values = _as_tuple(getattr(standard, "enum_values", None))
        min_value = _as_float(getattr(standard, "min_value", None))
        max_value = _as_float(getattr(standard, "max_value", None))
        max_length = _as_int(getattr(standard, "max_length", None))
        pattern = getattr(standard, "pattern", None)

        if getattr(standard, "required", False) and _wanted(wanted, RuleType.NULL):
            checks.append(RuleDescriptor(rule_type=RuleType.NULL.value, **base))
        if pattern and _wanted(wanted, RuleType.FORMAT):
            checks.append(RuleDescriptor(rule_type=RuleType.FORMAT.value, pattern=str(pattern), **base))
        if (enum_values or min_value is not None or max_value is not None
                or data_type in NUMERIC_DATA_TYPES) and _wanted(wanted, RuleType.RANGE):
            checks.append(RuleDescriptor(
                rule_type=RuleType.RANGE.value,
                enum_values=enum_values,
                min_value=min_value,
                max_value=max_value,
                numeric=data_type in NUMERIC_DATA_TYPES,
                **base,
            ))
        if max_length is not None and max_length > 0 and _wanted(wanted, RuleType.LENGTH):
            checks.append(RuleDescriptor(rule_type=RuleType.LENGTH.value, max_length=max_length, **base))
        if getattr(standard, "unique", False) and _wanted(wanted, RuleType.UNIQUE):
            checks.append(RuleDescriptor(
                rule_type=RuleType.UNIQUE.value,
                numeric=data_type in NUMERIC_DATA_TYPES,
                **base,
            ))
    return checks


def check_from_rule_row(rule: Any, standard: Any = None) -> Optional[RuleDescriptor]:
    """把 quality_check_rules 行（SPEC §2.4）翻译成描述符。

    本函数**不查库**：调用方需自行按 `rule.standard_id` 取到 DataStandard 传进
    `standard`。结构化约束（pattern / enum / min / max / max_length）与字段中文
    标签一律取自该标准，`rule_config` 只允许提供 `field`（字段名兜底）与
    `message`（人工提示语）——`rule_config.pattern` 这类来自配置的正则会被忽略，
    以保持"正则只来自 DataStandard.pattern"的信任边界。

    返回 None 表示该规则行不可由本引擎执行（未启用、duplicate_check 属 Phase 3、
    custom_check 已删除、或 rule_type 无法识别），调用方应记为不支持而非报错。
    """
    if rule is None:
        return None
    if getattr(rule, "is_active", True) is False:
        return None
    rule_type = normalize_rule_type(getattr(rule, "rule_type", None))
    if rule_type is None:
        return None

    config = getattr(rule, "rule_config", None)
    config = config if isinstance(config, dict) else {}
    field_name = (
        getattr(rule, "field_name", None)
        or config.get("field")
        or getattr(standard, "field_name", None)
        or ""
    ).strip()
    if not field_name:
        return None

    severity = (getattr(rule, "severity", None) or "error").strip() or "error"
    message = config.get("message")
    return RuleDescriptor(
        field_name=field_name,
        rule_type=rule_type,
        entity_type=getattr(rule, "entity_type", None) or getattr(standard, "entity_type", None),
        field_label=getattr(standard, "field_label", None) or field_name,
        severity=severity,
        message=str(message) if message else None,
        rule_id=getattr(rule, "id", None),
        standard_id=getattr(rule, "standard_id", None) or getattr(standard, "id", None),
        pattern=str(getattr(standard, "pattern", None)) if getattr(standard, "pattern", None) else None,
        enum_values=_as_tuple(getattr(standard, "enum_values", None)),
        min_value=_as_float(getattr(standard, "min_value", None)),
        max_value=_as_float(getattr(standard, "max_value", None)),
        max_length=_as_int(getattr(standard, "max_length", None)),
        numeric=(getattr(standard, "data_type", None) or "").strip().lower() in NUMERIC_DATA_TYPES,
    )


def _rule_type_filter(rule_types: Optional[Iterable[Any]]) -> Optional[frozenset[str]]:
    if not rule_types:
        return None
    wanted = {normalize_rule_type(t) for t in rule_types}
    wanted.discard(None)
    return frozenset(wanted)  # type: ignore[arg-type]


def _wanted(wanted: Optional[frozenset[str]], rule_type: RuleType) -> bool:
    return wanted is None or rule_type.value in wanted


# ========== 取值与比较辅助 ==========

class _NotNumeric(Exception):
    """内部信号：值无法转成有限数值。"""


def _to_number(value: Any) -> float:
    if isinstance(value, bool):
        raise _NotNumeric
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        try:
            number = float(str(value).strip())
        except (TypeError, ValueError):
            raise _NotNumeric from None
    if math.isnan(number) or math.isinf(number):
        raise _NotNumeric
    return number


def normalize_value(value: Any) -> str:
    """unique 分组键 / 枚举比较用的规范化值。

    - 字符串只做去空白，**不**按数值解析：前导零有业务含义（物料组 '001' ≠ '1'）；
    - int / float 归一到最简写法，1 与 1.0 同键（数值字段的分组键由
      `_unique_key` 先转数值再走这里）；
    - 大小写保持敏感（SAP 编码区分大小写，误判为重复的代价更高）。
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (OverflowError, ValueError):
            return str(value).strip()
        if math.isfinite(number) and number.is_integer():
            return str(int(number))
        return repr(number)
    return str(value).strip()


def _value_text(value: Any) -> str:
    return display_value(value, MAX_MESSAGE_VALUE)


def _enum_text(values: Sequence[Any]) -> str:
    shown = "、".join(str(v) for v in list(values)[:12])
    return shown + ("…" if len(values) > 12 else "")


# ========== 执行 ==========

def _normalize_rule(rule: RuleDescriptor) -> Optional[RuleDescriptor]:
    """把 rule_type 收敛为引擎短名；无法识别（含 custom/duplicate）返回 None。"""
    normalized = normalize_rule_type(rule.rule_type)
    if normalized is None:
        return None
    if normalized == rule.rule_type:
        return rule
    return replace(rule, rule_type=normalized)


def evaluate_checks(
    entity_type: str,
    records: Sequence[Any],
    checks: Sequence[RuleDescriptor],
) -> QualityRunResult:
    """对给定记录集合执行规则，返回失败明细 + 跳过记录 + 统计（不做任何 I/O）。"""
    rows = list(records)
    result = QualityRunResult(entity_type=entity_type, total_entities=len(rows))
    for raw_rule in checks:
        rule = _normalize_rule(raw_rule)
        if rule is None:
            result.rule_errors.append(RuleConfigError(
                rule_type=str(raw_rule.rule_type),
                field_name=raw_rule.field_name,
                reason=(
                    "规则类型不支持：v1 仅执行 null/format/range/length/unique；"
                    "duplicate_check 属疑似错误流程（Phase 3），custom_check 已按 SPEC §2.4 删除"
                ),
                rule_id=raw_rule.rule_id,
                standard_id=raw_rule.standard_id,
                field_label=raw_rule.field_label,
            ))
            continue
        source = describe_source(entity_type, rule.field_name)
        if not source.available:
            result.skipped.append(SkippedField(
                entity_type=entity_type,
                field_name=rule.field_name,
                rule_type=rule.rule_type,
                reason=source.reason or "无数据源，已跳过",
                field_label=rule.field_label,
                rule_id=rule.rule_id,
                standard_id=rule.standard_id,
                entity_count=len(rows),
            ))
            continue
        if rule.rule_type == RuleType.UNIQUE.value:
            executed, failures = _eval_unique(entity_type, rows, rule, source)
        else:
            compiled = None
            if rule.rule_type == RuleType.FORMAT.value:
                try:
                    compiled = compile_pattern(rule.pattern)
                except re.error as exc:
                    result.rule_errors.append(RuleConfigError(
                        rule_type=rule.rule_type,
                        field_name=rule.field_name,
                        reason=f"格式正则无法编译：{exc}",
                        rule_id=rule.rule_id,
                        standard_id=rule.standard_id,
                        field_label=rule.field_label,
                    ))
                    continue
            executed, failures = _eval_rowwise(entity_type, rows, rule, source, compiled)
        result.total_checks += executed
        result.findings.extend(failures)
    return result


def run_quality_checks(
    entity_type: str,
    records: Sequence[Any],
    standards: Optional[Iterable[Any]] = None,
    rules: Optional[Sequence[RuleDescriptor]] = None,
    rule_types: Optional[Iterable[Any]] = None,
) -> QualityRunResult:
    """引擎入口：标准（和/或规则描述符）+ 记录 → 失败明细。

    `standards` 传 DataStandard 行；`rules` 传 `check_from_rule_row()` 产出的
    描述符；两者可混用。`rule_types` 可选，只跑指定类型。跨实体规则会被忽略
    （`entity_type` 为空的描述符视为当前实体）。
    """
    checks: list[RuleDescriptor] = []
    if standards is not None:
        checks.extend(checks_from_standards(standards, rule_types=rule_types))
    if rules is not None:
        checks.extend(r for r in rules if r is not None)
    wanted = _rule_type_filter(rule_types)
    selected: list[RuleDescriptor] = []
    for candidate in checks:
        normalized = _normalize_rule(candidate)
        if normalized is None:
            selected.append(candidate)  # 交给 evaluate_checks 记为不支持规则，不静默丢弃
            continue
        if not _wanted(wanted, RuleType(normalized.rule_type)):
            continue
        if normalized.entity_type and normalized.entity_type != entity_type:
            continue
        selected.append(normalized)
    return evaluate_checks(entity_type, records, selected)


def compile_pattern(pattern: Optional[str]) -> re.Pattern[str]:
    """编译标准正则；非法或超长抛 `re.error`，由调用方降级为 rule_errors。

    只接受来自 `DataStandard.pattern` 的值（信任边界见模块 docstring）。
    """
    text = (pattern or "").strip()
    if not text:
        raise re.error("规则未提供 pattern，无法执行格式校验")
    if len(text) > MAX_PATTERN_LENGTH:
        raise re.error(f"pattern 超过 {MAX_PATTERN_LENGTH} 字符上限，拒绝编译")
    return re.compile(text)


def _eval_rowwise(
    entity_type: str,
    rows: Sequence[Any],
    rule: RuleDescriptor,
    source: FieldSource,
    compiled: Optional[re.Pattern[str]],
) -> tuple[int, list[QualityFinding]]:
    executed = 0
    findings: list[QualityFinding] = []
    for record in rows:
        access = read_value(record, rule.field_name, entity_type, source)
        executed += 1
        violation = _check_value(rule, access, compiled)
        if violation:
            findings.append(_finding(
                entity_type, record, rule, access.value, violation
            ))
    return executed, findings


@dataclass(frozen=True)
class _Violation:
    """内部信号：一次失败（rule_type 可与规则类型不同，如数值转换失败记为 format）。"""

    rule_type: str
    message: str


def _check_value(
    rule: RuleDescriptor,
    access: AccessResult,
    compiled: Optional[re.Pattern[str]],
) -> Optional["_Violation"]:
    """单值校验，失败返回 `_Violation`，通过返回 None。"""
    rule_type = rule.rule_type
    if rule_type == RuleType.NULL.value:
        if access.is_blank:
            return _Violation(rule_type, rule.message or (
                f"{rule.label}（{rule.field_name}）为必填字段，当前值为空"
            ))
        return None

    # 其余四类只校验"有数据源且本行已填"的值；空值归 null 规则独占
    if access.skipped or not access.key_present or is_blank(access.value):
        return None
    value = access.value

    if rule_type == RuleType.FORMAT.value:
        if compiled is None:  # 防御：编译失败的规则已在 rule_errors 中记录，不猜测语义
            return None
        if not compiled.search(str(value)):
            return _Violation(rule_type, rule.message or (
                f"{rule.label}（{rule.field_name}）格式不符合标准，当前值「{_value_text(value)}」"
                f"不匹配规则 {rule.pattern}"
            ))
        return None

    if rule_type == RuleType.RANGE.value:
        if rule.enum_values:
            allowed = [normalize_value(v) for v in rule.enum_values]
            if normalize_value(value) not in allowed:
                return _Violation(rule_type, rule.message or (
                    f"{rule.label}（{rule.field_name}）取值非法，当前值「{_value_text(value)}」"
                    f"不在值域 {_enum_text(list(rule.enum_values))} 内"
                ))
            return None
        if rule.min_value is None and rule.max_value is None and not rule.numeric:
            return None
        try:
            number = _to_number(value)
        except _NotNumeric:
            # §5.4：该当数值的值转换失败按 format 错误处理（不是 range）
            return _Violation(RuleType.FORMAT.value, rule.message or (
                f"{rule.label}（{rule.field_name}）应为数值，当前值「{_value_text(value)}」无法转换为数值"
            ))
        if rule.min_value is not None and number < rule.min_value:
            return _Violation(rule_type, rule.message or (
                f"{rule.label}（{rule.field_name}）低于最小值 {rule.min_value}，当前值「{_value_text(value)}」"
            ))
        if rule.max_value is not None and number > rule.max_value:
            return _Violation(rule_type, rule.message or (
                f"{rule.label}（{rule.field_name}）超过最大值 {rule.max_value}，当前值「{_value_text(value)}」"
            ))
        return None

    if rule_type == RuleType.LENGTH.value:
        length = len(str(value).strip())
        if rule.max_length is not None and length > rule.max_length:
            return _Violation(rule_type, rule.message or (
                f"{rule.label}（{rule.field_name}）长度超限：当前 {length} 字符 > 最大 {rule.max_length}"
            ))
        return None

    return None


def _eval_unique(
    entity_type: str,
    rows: Sequence[Any],
    rule: RuleDescriptor,
    source: FieldSource,
) -> tuple[int, list[QualityFinding]]:
    """精确唯一：一次哈希分组，组内 >1 行则组内每行各出一条失败。"""
    groups: dict[str, list[tuple[Any, Any]]] = {}
    findings: list[QualityFinding] = []
    executed = 0
    for record in rows:
        access = read_value(record, rule.field_name, entity_type, source)
        executed += 1
        if access.skipped or not access.key_present or is_blank(access.value):
            continue  # 空值不参与判重，缺失由 null 规则负责
        if rule.numeric:
            try:
                key = normalize_value(_to_number(access.value))
            except _NotNumeric:
                # §5.4：该当数值的值转换失败按 format 错误处理
                findings.append(_finding(entity_type, record, rule, access.value, _Violation(
                    RuleType.FORMAT.value,
                    f"{rule.label}（{rule.field_name}）应为数值，"
                    f"当前值「{_value_text(access.value)}」无法转换为数值",
                )))
                continue
        else:
            key = normalize_value(access.value)
        groups.setdefault(key, []).append((record, access.value))

    for members in groups.values():
        if len(members) < 2:
            continue
        for record, value in members:
            others = "、".join(
                record_label(other, entity_type) for other, _ in members if other is not record
            )
            findings.append(_finding(
                entity_type, record, rule, value,
                _Violation(rule.rule_type, rule.message or (
                    f"{rule.label}（{rule.field_name}）值「{_value_text(value)}」与 "
                    f"{len(members) - 1} 条记录重复：{others}"
                )),
            ))
    return executed, findings


def _finding(
    entity_type: str,
    record: Any,
    rule: RuleDescriptor,
    value: Any,
    violation: "_Violation",
) -> QualityFinding:
    return QualityFinding(
        entity_id=record_id(record),
        entity_label=record_label(record, entity_type),
        field_name=rule.field_name,
        field_label=rule.field_label or rule.field_name,
        rule_type=violation.rule_type,
        message=violation.message,
        entity_type=entity_type,
        severity=rule.severity,
        field_value=display_value(value),
        rule_id=rule.rule_id,
        standard_id=rule.standard_id,
    )


__all__ = [
    "RuleType",
    "RULE_TYPE_CODES",
    "RULE_TYPE_ALIASES",
    "UNSUPPORTED_RULE_TYPES",
    "RuleDescriptor",
    "QualityFinding",
    "SkippedField",
    "RuleConfigError",
    "QualityRunResult",
    "checks_from_standards",
    "check_from_rule_row",
    "normalize_rule_type",
    "rule_code_for",
    "normalize_value",
    "compile_pattern",
    "evaluate_checks",
    "run_quality_checks",
]
