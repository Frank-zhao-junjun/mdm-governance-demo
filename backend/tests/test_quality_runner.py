"""质量检测编排层与规则派生的单元测试（Phase 2）。"""
import pytest

from app import models
from app.services import quality_runner
from app.services.rule_derivation import derive_rule_rows, derive_rules


def _standard(field_name="MATNR", entity_type="material", **overrides):
    """构造瞬态 DataStandard（不入库），只读属性即可派生规则。"""
    defaults = dict(
        id=f"std-{field_name}",
        entity_type=entity_type,
        sap_table="MARA",
        field_name=field_name,
        field_label=field_name,
        data_type="string",
    )
    defaults.update(overrides)
    return models.DataStandard(**defaults)


# ========== rule_derivation ==========

def test_derive_rules_all_five_types():
    standard = _standard(
        required=True,
        pattern=r"^M\d{5}$",
        enum_values=["KG", "G"],
        max_length=40,
        unique=True,
    )
    rules = derive_rules(standard)
    assert {r.rule_type.value for r in rules} == {
        "null_check",
        "format_check",
        "range_check",
        "length_check",
        "unique_check",
    }
    assert len(rules) == 5
    for rule in rules:
        assert rule.standard_id == standard.id
        assert rule.entity_type == "material"
        assert rule.field_name == "MATNR"
        assert rule.rule_config == {}
        assert rule.is_active is True
        assert rule.severity == "error"


def test_derive_rules_numeric_data_type_yields_range():
    standard = _standard(data_type="number", min_value=0)
    rules = derive_rules(standard)
    assert {r.rule_type.value for r in rules} == {"range_check"}


def test_derive_rules_no_constraints_yields_nothing():
    assert derive_rules(_standard()) == []
    assert derive_rules(_standard(field_name="")) == []


def test_derive_rule_rows_flattens():
    rows = derive_rule_rows([_standard(required=True), _standard("MAKTX", max_length=40)])
    assert len(rows) == 2
    assert rows[0].rule_type == models.RuleType.NULL_CHECK
    assert rows[1].rule_type == models.RuleType.LENGTH_CHECK


# ========== quality_runner ==========

def test_load_rule_rows_default_is_active_only(db):
    db.add(models.QualityCheckRule(
        id="rule-active", name="A", entity_type="material",
        rule_type=models.RuleType.NULL_CHECK, rule_config={}, is_active=True,
    ))
    db.add(models.QualityCheckRule(
        id="rule-inactive", name="B", entity_type="material",
        rule_type=models.RuleType.NULL_CHECK, rule_config={}, is_active=False,
    ))
    db.commit()

    rows = quality_runner.load_rule_rows(db, "material")
    assert [r.id for r in rows] == ["rule-active"]

    rows = quality_runner.load_rule_rows(db, "material", rule_ids=["rule-active", "rule-inactive"])
    assert {r.id for r in rows} == {"rule-active", "rule-inactive"}


def test_run_batch_entity_limit(db, monkeypatch):
    monkeypatch.setattr(
        quality_runner, "count_entities", lambda db, entity_type, entity_ids=None: 10001
    )
    with pytest.raises(quality_runner.EntityLimitExceeded) as exc_info:
        quality_runner.run_batch(db, "material")
    assert "分批" in str(exc_info.value)
    assert exc_info.value.count == 10001


def test_run_batch_no_executable_rules(db):
    # customer 无任何标准/规则 → 无规则可执行
    with pytest.raises(quality_runner.NoExecutableRules):
        quality_runner.run_batch(db, "customer")


def test_run_batch_no_matching_entity_ids(db, seeded_db):
    with pytest.raises(quality_runner.NoMatchingEntities):
        quality_runner.run_batch(
            db, "material", entity_ids=["00000000-0000-0000-0000-000000000000"]
        )
