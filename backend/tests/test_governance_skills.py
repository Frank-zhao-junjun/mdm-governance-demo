"""Unit tests for deterministic AI-governance Skills (TC-AIG-001/002/003/008/009)."""
from app import models
from app.skills.attribute import check_attributes
from app.skills.duplicate_match import evaluate_duplicate_candidates
from app.skills.merge_executor import prepare_merge_execution
from app.skills.naming import check_naming
from app.skills.quality_rule import check_quality_rules
from app.skills.unit import check_unit


def test_naming_skill_returns_l1_evidence_for_a_naming_rule_violation():
    result = check_naming({"name": "临时螺栓"})

    assert result.status == "block"
    assert result.suggestions[0].evidence.level == "L1"
    assert result.suggestions[0].field == "name"


def test_attribute_skill_identifies_missing_required_attributes_with_l1_evidence():
    result = check_attributes(
        {"attributes": {"MTART": "ROH"}},
        {"required_fields": ["MTART", "MEINS"]},
    )

    assert result.status == "block"
    assert result.suggestions[0].field == "MEINS"
    assert result.suggestions[0].evidence.level == "L1"


def test_unit_skill_normalizes_an_alias_using_a_l1_conversion_mapping():
    result = check_unit(
        {"unit": "公斤"},
        {"canonical_unit": "KG", "aliases": {"公斤": "KG"}},
    )

    assert result.status == "suggest"
    assert result.suggestions[0].suggestion == "KG"
    assert result.suggestions[0].auto_fixable is True
    assert result.suggestions[0].evidence.level == "L1"


def test_unit_skill_marks_an_unmapped_unit_as_l3_human_review():
    result = check_unit(
        {"unit": "piece"},
        {"canonical_unit": "PC", "aliases": {}},
    )

    assert result.status == "warn"
    assert result.suggestions[0].evidence.level == "L3"
    assert result.suggestions[0].auto_fixable is False


def test_quality_rule_skill_wraps_quality_engine_failures_as_l1_suggestions():
    standard = models.DataStandard(
        entity_type="material",
        sap_table="MARA",
        field_name="MEINS",
        field_label="Base unit",
        data_type="string",
        required=True,
    )
    record = models.MaterialRecord(
        material_code="M10001",
        material_name="Bolt",
        attributes={},
    )

    result = check_quality_rules("material", [record], [standard])

    assert result.status == "block"
    assert result.suggestions[0].field == "MEINS"
    assert result.suggestions[0].evidence.level == "L1"


def test_duplicate_skill_blocks_llm_merge_recommendation_for_strength_conflict():
    result = evaluate_duplicate_candidates(
        {
            "left": {"id": "golden-109", "name": "Hex bolt M8x30", "strength": "10.9"},
            "right": {"id": "golden-88", "name": "Hex bolt M8x30", "strength": "8.8"},
            "llm_suggestion": "merge",
        }
    )

    assert result.status == "block"
    assert result.conflicts[0]["level"] == "L1"
    assert result.conflicts[0]["message"] == "不建议合并"


def test_merge_executor_requires_an_approved_ticket_before_execution():
    result = prepare_merge_execution({"status": "pending", "golden_ids": ["golden-001", "golden-002"]})

    assert result.status == "block"
    assert result.conflicts[0]["level"] == "L1"


def test_merge_executor_allows_an_approved_ticket_to_reach_external_executor():
    result = prepare_merge_execution({"status": "approved", "golden_ids": ["golden-001", "golden-002"]})

    assert result.status == "pass"