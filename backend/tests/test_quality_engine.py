"""规则引擎测试（SPEC §2.4 五种规则、§5 检测执行语义、§2.6 只存失败项）。

引擎不碰 Session：标准用 `models.DataStandard` 瞬态对象表达（列名与真实表一致），
记录取自 `seeded_db` / `db` fixture。
"""
import re
import time

import pytest

from app import models
from app.services import quality_engine as qe
from app.services.quality_engine import RuleType


def _standard(field_name="MATNR", **overrides):
    """构造一条数据标准（不入库，字段与 §2.1 列一致）。"""
    data = dict(
        entity_type="material",
        sap_table="MARA",
        field_name=field_name,
        field_label=f"字段{field_name}",
        data_type="string",
    )
    data.update(overrides)
    return models.DataStandard(**data)


class _Row:
    """quality_check_rules 行的最小替身（引擎只按属性名读取，不依赖 ORM）。"""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _rule_row(rule_type, **overrides):
    data = dict(
        id=f"rule-{rule_type}",
        name=f"规则-{rule_type}",
        entity_type="material",
        rule_type=rule_type,
        field_name="MATNR",
        rule_config={},
        severity="error",
        is_active=True,
    )
    data.update(overrides)
    return _Row(**data)


def _material(code="M10001", name="六角螺栓", attributes=None, db=None):
    record = models.MaterialRecord(
        material_code=code,
        material_name=name,
        attributes={"MTART": "ROH", "MEINS": "PC"} if attributes is None else attributes,
    )
    if db is not None:
        db.add(record)
        db.commit()
    return record


def _run(records, standards=None, rules=None, rule_types=None, entity_type="material"):
    return qe.run_quality_checks(
        entity_type, records, standards=standards, rules=rules, rule_types=rule_types
    )


# ========== null ==========

class TestNullRule:
    def test_pass_when_required_value_present(self, seeded_db):
        records = seeded_db.query(models.MaterialRecord).all()
        result = _run(records, [_standard(required=True)])

        assert result.total_checks == 1
        assert result.findings == []
        assert result.passed == 1 and result.failed == 0

    def test_fail_when_required_attribute_key_absent(self, seeded_db):
        records = seeded_db.query(models.MaterialRecord).all()
        result = _run(records, [_standard("MATKL", field_label="物料组", required=True)])

        assert result.failed == 1
        finding = result.findings[0]
        assert finding.rule_type == "null"
        assert finding.field_name == "MATKL"
        assert finding.field_label == "物料组"
        assert finding.entity_label == "M10001"
        assert finding.entity_id == records[0].id
        assert "必填" in finding.message

    def test_whitespace_and_none_count_as_missing(self, db):
        blank = _material("M10002", "   ", db=db)
        none_name = _material("M10003", "", db=db)
        result = _run([blank, none_name], [_standard("MAKTX", field_label="物料描述", required=True)])

        assert result.total_checks == 2 and result.failed == 2

    def test_zero_is_not_missing(self, db):
        record = _material(attributes={"BRGEW": 0}, db=db)
        result = _run([record], [_standard("BRGEW", data_type="number", required=True)])
        assert result.findings == []


# ========== format ==========

class TestFormatRule:
    def test_pass_on_seeded_pattern(self, seeded_db):
        records = seeded_db.query(models.MaterialRecord).all()
        standards = seeded_db.query(models.DataStandard).filter(
            models.DataStandard.field_name == "MATNR"
        ).all()
        result = _run(records, standards)

        assert result.total_checks == 3  # required + pattern + unique
        assert result.findings == []

    def test_fail_when_pattern_not_matched(self, db):
        bad = _material("A10001", "错误编码物料", db=db)
        result = _run([bad], [_standard(pattern=r"^M\d{5}$", field_label="物料编码")])

        assert result.failed == 1
        assert result.findings[0].rule_type == "format"
        assert "格式不符合标准" in result.findings[0].message

    def test_empty_value_is_left_to_null_rule(self, db):
        """同一字段同时 required + pattern 时，缺失只报一条 null，不刷 format 假告警。"""
        record = _material(attributes={"MTART": "ROH"}, db=db)
        result = _run(
            [record],
            [_standard("MEINS", field_label="基本计量单位", required=True, pattern=r"^[A-Z]{2,3}$")],
        )

        assert result.failed == 1
        assert [f.rule_type for f in result.findings] == ["null"]

    def test_numeric_value_is_matched_as_string(self, db):
        record = _material(attributes={"POST_CODE1": 200120}, db=db)
        result = _run([record], [_standard("POST_CODE1", data_type="number", pattern=r"^\d{6}$")])
        assert result.findings == []


# ========== range（值域 / 枚举 / 数值区间） ==========

class TestRangeRule:
    def test_enum_pass_and_fail(self, db):
        good = _material("M10001", attributes={"MTART": "ROH"}, db=db)
        bad = _material("M10002", attributes={"MTART": "BOGUS"}, db=db)
        result = _run(
            [good, bad],
            [_standard("MTART", field_label="物料类型", enum_values=["ROH", "HALB", "VERP"])],
        )

        assert result.total_checks == 2
        assert result.failed == 1
        finding = result.findings[0]
        assert finding.rule_type == "range"
        assert finding.entity_label == "M10002"
        assert "ROH" in finding.message and "BOGUS" in finding.message

    def test_numeric_bounds_pass_and_fail(self, db):
        ok = _material("M10001", attributes={"BRGEW": 12.5}, db=db)
        too_big = _material("M10002", attributes={"BRGEW": 150}, db=db)
        too_small = _material("M10003", attributes={"BRGEW": -3}, db=db)
        result = _run(
            [ok, too_big, too_small],
            [_standard("BRGEW", field_label="毛重", data_type="number", min_value=0, max_value=100)],
        )

        assert result.total_checks == 3
        assert [f.rule_type for f in result.findings] == ["range", "range"]
        assert "超过最大值" in result.findings[0].message
        assert "低于最小值" in result.findings[1].message

    def test_string_number_is_converted_before_comparison(self, db):
        """§5.4：number 字段的字符串值先转数值再比较。"""
        record = _material(attributes={"BRGEW": "20"}, db=db)
        result = _run([record], [_standard("BRGEW", data_type="number", min_value=0, max_value=100)])
        assert result.findings == []

    @pytest.mark.parametrize("value", ["abc", "12.34.56", "N/A", True, "nan", "1e", "—", ["3"]])
    def test_unconvertible_number_is_a_format_error_not_range(self, db, value):
        """§5.4 硬要求：该当数值的值转换失败按 format 错误处理。"""
        record = _material(attributes={"BRGEW": value}, db=db)
        result = _run(
            [record],
            [_standard("BRGEW", field_label="毛重", data_type="number", min_value=0, max_value=100)],
        )

        assert result.failed == 1
        assert result.findings[0].rule_type == "format"
        assert result.findings[0].rule_code == "format_check"
        assert "无法转换为数值" in result.findings[0].message

    def test_number_typed_field_without_bounds_still_checks_convertibility(self, db):
        record = _material(attributes={"NTGEW": "十二"}, db=db)
        result = _run([record], [_standard("NTGEW", data_type="number")])
        assert [f.rule_type for f in result.findings] == ["format"]

    def test_min_only_bound(self, db):
        record = _material(attributes={"BRGEW": -1}, db=db)
        result = _run([record], [_standard("BRGEW", data_type="number", min_value=0)])
        assert result.failed == 1 and result.findings[0].rule_type == "range"


# ========== length ==========

class TestLengthRule:
    def test_pass_within_max_length(self, db):
        record = _material(attributes={"MEINS": "PC"}, db=db)
        result = _run([record], [_standard("MEINS", field_label="基本计量单位", max_length=3)])
        assert result.findings == []

    def test_fail_over_max_length(self, db):
        long_name = "料" * 30
        record = _material("M10002", long_name, db=db)
        result = _run([record], [_standard("MAKTX", field_label="物料描述", max_length=20)])

        assert result.failed == 1
        finding = result.findings[0]
        assert finding.rule_type == "length"
        assert "30" in finding.message and "20" in finding.message
        assert len(finding.field_value) <= 500  # §2.6 结果列宽

    def test_length_of_numeric_value_uses_stored_representation(self, db):
        record = _material(attributes={"BRGEW": 400.0}, db=db)
        ok = _run([record], [_standard("BRGEW", data_type="number", max_length=10)])
        bad = _run([record], [_standard("BRGEW", data_type="number", max_length=3)])
        assert ok.findings == []
        assert bad.failed == 1 and bad.findings[0].rule_type == "length"


# ========== unique ==========

class TestUniqueRule:
    def test_pass_when_values_are_distinct(self, db):
        records = [
            _material("M10001", attributes={"MATKL": "001"}, db=db),
            _material("M10002", attributes={"MATKL": "002"}, db=db),
        ]
        result = _run(records, [_standard("MATKL", field_label="物料组", unique=True)])
        assert result.total_checks == 2 and result.findings == []

    def test_flags_every_member_of_a_duplicate_group(self, db):
        records = [
            _material("M10001", attributes={"MATKL": "001"}, db=db),
            _material("M10002", attributes={"MATKL": "001"}, db=db),
            _material("M10003", attributes={"MATKL": "003"}, db=db),
        ]
        result = _run(records, [_standard("MATKL", field_label="物料组", unique=True)])

        assert result.total_checks == 3
        assert result.failed == 2  # 组内每一行都出一条
        assert {f.entity_label for f in result.findings} == {"M10001", "M10002"}
        assert result.findings[0].rule_type == "unique"
        assert "1 条记录重复" in result.findings[0].message
        assert "M10002" in result.findings[0].message  # 证据：对端编码

    def test_grouping_uses_normalized_values(self, db):
        records = [
            _material("M10001", attributes={"MATKL": "001"}, db=db),
            _material("M10002", attributes={"MATKL": " 001 "}, db=db),
            _material("M10003", attributes={"BRGEW": 1}, db=db),
            _material("M10004", attributes={"BRGEW": "1.0"}, db=db),
        ]
        by_code = _run(records, [_standard("MATKL", unique=True)])
        numeric = _run(records, [_standard("BRGEW", data_type="number", unique=True)])

        assert by_code.failed == 2  # '001' 与 ' 001 ' 同组
        assert numeric.failed == 2  # 数值字段：1 与 '1.0' 同组
        assert qe.normalize_value(" 001 ") == "001"
        assert qe.normalize_value(1) == qe.normalize_value(1.0) == "1"

    def test_text_uniqueness_keeps_leading_zeros_meaningful(self, db):
        """文本字段不做数值解析：'001' 与 '1' 是两个不同的合法编码。"""
        records = [
            _material("M10001", attributes={"MATKL": "001"}, db=db),
            _material("M10002", attributes={"MATKL": "1"}, db=db),
        ]
        result = _run(records, [_standard("MATKL", unique=True)])
        assert result.failed == 0

    def test_numeric_field_reports_unconvertible_value_as_format_error(self, db):
        records = [
            _material("M10001", attributes={"BRGEW": "约 3"}, db=db),
            _material("M10002", attributes={"BRGEW": "abc"}, db=db),
        ]
        result = _run(
            records,
            [_standard("BRGEW", field_label="毛重", data_type="number", unique=True)],
            rule_types=["unique"],
        )

        assert result.total_checks == 2
        assert [f.rule_type for f in result.findings] == ["format", "format"]

    def test_blank_values_are_excluded_from_grouping(self, db):
        records = [
            _material("M10001", attributes={}, db=db),
            _material("M10002", attributes={"MATKL": None}, db=db),
            _material("M10003", attributes={"MATKL": "  "}, db=db),
        ]
        result = _run(records, [_standard("MATKL", unique=True)])
        assert result.total_checks == 3 and result.findings == []

    def test_identity_column_duplicates_are_detected(self, db):
        """MAKTX 冗余列上的精确重复同样可判（编码列有 DB 唯一约束，不会走到这里）。"""
        records = [
            _material("M10001", "同名物料", db=db),
            _material("M10002", "同名物料", db=db),
        ]
        result = _run(records, [_standard("MAKTX", field_label="物料描述", unique=True)])
        assert result.failed == 2


# ========== 无数据源：跳过并留痕 ==========

class TestSkippedFields:
    def test_no_source_field_never_produces_findings(self, db):
        records = [_material("M10001", db=db), _material("M10002", db=db)]
        result = _run(records, [_standard("WERKS", field_label="工厂", required=True)])

        assert result.findings == []
        assert result.total_checks == 0
        assert len(result.skipped) == 1
        skipped = result.skipped[0]
        assert skipped.field_name == "WERKS"
        assert skipped.rule_type == "null"
        assert skipped.rule_code == "null_check"
        assert skipped.entity_count == 2
        assert result.skipped_checks == 2
        assert "无数据源" in skipped.reason

    def test_skip_is_recorded_per_rule_not_per_row(self, db):
        records = [_material(code=f"M100{i:02d}", db=db) for i in range(1, 6)]
        plant = _standard("LGORT", field_label="存储位置", required=True, pattern=r"^\d{4}$",
                          max_length=4, unique=True)
        result = _run(records, [plant])

        assert result.findings == []
        assert len(result.skipped) == 4  # null / format / length / unique
        assert {s.rule_type for s in result.skipped} == {"null", "format", "length", "unique"}
        assert all(s.entity_count == 5 for s in result.skipped)
        assert result.skipped_checks == 20

    def test_skipped_and_executed_rules_coexist(self, seeded_db):
        records = seeded_db.query(models.MaterialRecord).all()
        standards = [
            _standard("MATKL", field_label="物料组", required=True),   # 有数据源、值缺失 → 失败
            _standard("WERKS", field_label="工厂", required=True),      # 无数据源 → 跳过
        ]
        result = _run(records, standards)

        assert [f.field_name for f in result.findings] == ["MATKL"]
        assert [s.field_name for s in result.skipped] == ["WERKS"]
        assert result.total_checks == 1 and result.skipped_checks == 1

    def test_unknown_entity_type_skips_everything(self, seeded_db):
        records = seeded_db.query(models.MaterialRecord).all()
        checks = qe.checks_from_standards([_standard(required=True)])
        result = qe.evaluate_checks("plant", records, checks)

        assert result.findings == []
        assert result.total_checks == 0
        assert result.skipped_checks == 1


# ========== 正则信任边界 ==========

class TestPatternSafety:
    def test_invalid_pattern_degrades_to_recorded_error(self, db):
        records = [_material("M10001", db=db), _material("M10002", db=db)]
        standards = [
            _standard("MAKTX", field_label="物料描述", pattern=r"^(M[\d+"),        # 编译失败
            _standard("MATNR", field_label="物料编码", required=True),             # 正常规则
        ]
        result = _run(records, standards)

        assert len(result.rule_errors) == 1
        error = result.rule_errors[0]
        assert error.rule_type == "format" and error.field_name == "MAKTX"
        assert "无法编译" in error.reason
        # 整批没有被打断：其余规则照常执行并产出
        assert result.total_checks == 2
        assert result.failed == 0

    def test_broken_pattern_on_failing_standard_does_not_kill_batch(self, db):
        records = [_material("A10001", "", db=db)]  # 编码格式规则坏掉，描述必填规则应仍报错
        standards = [
            _standard("MATNR", field_label="物料编码", pattern=r"^(a"),
            _standard("MAKTX", field_label="物料描述", required=True),
        ]
        result = _run(records, standards)

        assert len(result.rule_errors) == 1
        assert [f.field_name for f in result.findings] == ["MAKTX"]

    def test_overlong_pattern_is_refused(self):
        with pytest.raises(re.error):
            qe.compile_pattern("(" + "a" * 300)

    def test_missing_pattern_raises_instead_of_silently_passing(self):
        with pytest.raises(re.error):
            qe.compile_pattern(None)

    def test_rule_type_names_map_to_persisted_codes(self):
        assert qe.RULE_TYPE_CODES == {
            "null": "null_check", "format": "format_check", "range": "range_check",
            "length": "length_check", "unique": "unique_check",
        }
        assert qe.normalize_rule_type("null_check") == "null"
        assert qe.normalize_rule_type(RuleType.UNIQUE) == "unique"
        assert qe.normalize_rule_type("FORMAT") == "format"
        assert qe.normalize_rule_type("custom_check") is None


# ========== 规则行适配（quality_check_rules） ==========

class TestRuleRowAdapter:
    @pytest.mark.parametrize("row_type,expected", [
        ("null_check", "null"),
        ("format_check", "format"),
        ("range_check", "range"),
        ("length_check", "length"),
        ("unique_check", "unique"),
    ])
    def test_five_rule_types_map_to_descriptors(self, row_type, expected):
        standard = _standard(
            "MATNR", field_label="物料编码", pattern=r"^M\d{5}$", data_type="string",
            enum_values=["M1"], max_length=18, min_value=1, max_value=99,
        )
        descriptor = qe.check_from_rule_row(_rule_row(row_type), standard)

        assert descriptor is not None
        assert descriptor.rule_type == expected
        assert descriptor.rule_id == f"rule-{row_type}"
        assert descriptor.field_label == "物料编码"

    @pytest.mark.parametrize("row_type", ["custom_check", "custom", "duplicate_check", "timeliness_check"])
    def test_unsupported_and_unknown_types_are_not_executed(self, row_type):
        assert qe.check_from_rule_row(_rule_row(row_type), _standard()) is None

    def test_inactive_rule_row_is_skipped(self):
        assert qe.check_from_rule_row(_rule_row("null_check", is_active=False), _standard()) is None

    def test_pattern_never_comes_from_rule_config(self, db):
        """rule_config 里的 pattern 被忽略：正则只允许来自 DataStandard.pattern。"""
        hostile = _rule_row(
            "format_check",
            rule_config={"field": "MATNR", "pattern": r"(?|(?:(?:x)|x)|){88}"},
        )
        descriptor = qe.check_from_rule_row(hostile, _standard("MATNR"))  # 标准没有 pattern

        assert descriptor is not None
        assert descriptor.pattern is None

        records = [_material("A10001", db=db)]
        result = _run(records, rules=[descriptor])
        assert result.findings == []
        # 无正则可编译 → 规则降级为 rule_errors，不执行、不猜测语义、更不执行配置里的正则
        assert result.total_checks == 0
        assert len(result.rule_errors) == 1

    def test_field_name_falls_back_to_rule_config_field(self):
        rule = _rule_row("null_check", field_name=None, rule_config={"field": "MEINS"})
        descriptor = qe.check_from_rule_row(rule, _standard("MEINS", field_label="基本计量单位"))
        assert descriptor.field_name == "MEINS"

    def test_custom_message_and_severity_are_respected(self, db):
        rule = _rule_row(
            "null_check",
            rule_config={"field": "MATNR", "message": "编码不能为空，请回源系统补录"},
            severity="warning",
        )
        record = _material("", "空编码物料", db=db)
        result = _run([record], rules=[qe.check_from_rule_row(rule, _standard("MATNR"))])

        assert result.failed == 1
        assert result.findings[0].message == "编码不能为空，请回源系统补录"
        assert result.findings[0].severity == "warning"

    def test_unknown_rule_type_descriptor_is_recorded_not_executed(self, db):
        bogus = qe.RuleDescriptor(field_name="MATNR", rule_type="custom_check")
        result = _run([_material(db=db)], rules=[bogus])

        assert result.findings == [] and result.total_checks == 0
        assert len(result.rule_errors) == 1 and "不支持" in result.rule_errors[0].reason


# ========== 批次统计与执行边界 ==========

class TestRunSemantics:
    def test_only_failures_are_returned_and_stats_add_up(self, seeded_db):
        records = seeded_db.query(models.MaterialRecord).all()
        standards = seeded_db.query(models.DataStandard).all()
        standards += [_standard("MATKL", field_label="物料组", required=True, max_length=2)]
        result = _run(records, standards)

        assert result.total_entities == 1
        assert result.failed == len(result.findings)
        assert result.passed + result.failed == result.total_checks
        assert all(f.message for f in result.findings)
        summary = result.summary()
        assert summary["total_checks"] == result.total_checks
        assert summary["failed"] == result.failed
        assert summary["passed"] == result.passed

    def test_rules_are_filtered_by_entity_type(self, seeded_db):
        records = seeded_db.query(models.MaterialRecord).all()
        supplier_standard = _standard("LIFNR", entity_type="supplier", required=True)
        result = _run(records, [supplier_standard], entity_type="material")

        assert result.total_checks == 0 and result.findings == []

    def test_rule_types_selection(self, db):
        records = [_material("A10001", attributes={"MATKL": "001"}, db=db)]
        standards = [
            _standard("MAKTX", required=True),
            _standard("MATNR", pattern=r"^M\d{5}$"),
            _standard("MATKL", unique=True),
        ]
        only_format = _run(records, standards, rule_types=["format"])
        assert only_format.total_checks == 1 and only_format.failed == 1

        spec_names = _run(records, standards, rule_types=["null_check", "unique_check"])
        assert spec_names.total_checks == 2 and spec_names.failed == 0

    def test_standard_without_field_name_is_ignored(self, db):
        result = _run([_material(db=db)], [_standard(field_name="   ", required=True)])
        assert result.total_checks == 0 and result.skipped == []

    def test_linear_in_rows_times_rules(self, db):
        """2000 行 × 7 条规则保持线性：不做全量两两比较，也不被单条坏规则打断。"""
        records = [
            models.MaterialRecord(
                material_code=f"M{i:05d}",
                material_name=f"物料{i}",
                attributes={"MATKL": f"{i % 50:03d}"},
            )
            for i in range(1, 2001)
        ]
        db.add_all(records)
        db.commit()
        standards = [
            _standard("MATNR", required=True, pattern=r"^M\d{5}$", unique=True, max_length=18),
            _standard("MAKTX", required=True),
            _standard("MATKL", required=True, enum_values=[f"{i:03d}" for i in range(50)]),
        ]
        started = time.perf_counter()
        result = _run(records, standards)
        elapsed = time.perf_counter() - started

        assert result.total_entities == 2000
        assert result.total_checks == 2000 * 7
        assert result.failed == 0
        assert elapsed < 5, f"疑似出现超线性复杂度：{elapsed:.2f}s"

    def test_empty_record_set(self, seeded_db):
        standards = seeded_db.query(models.DataStandard).all()
        result = _run([], standards)
        assert result.total_checks == 0 and result.pass_rate == 1.0
        assert result.skipped_checks == 0
