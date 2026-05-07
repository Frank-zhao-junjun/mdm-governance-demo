"""Unit tests for MaterialValidator service."""
import pytest
from app import models
from app.services.material_validator import MaterialValidator


class TestMaterialValidatorRequiredFields:
    """Test validation of required fields."""

    def test_all_required_fields_present(self, seeded_db):
        """TC-VAL-001: All required fields should pass."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "cls-child-001",
            "material_type": "raw",
            "attribute_values": {"material_grade": "304不锈钢", "thickness": "2.0"}
        })
        assert result["passed"] is True
        assert len(result["errors"]) == 0

    def test_missing_material_name(self, seeded_db):
        """TC-VAL-002: Missing material_name should fail."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "",
            "classification_id": "cls-child-001",
            "material_type": "raw"
        })
        assert result["passed"] is False
        assert any("必填字段缺失" in e for e in result["errors"])

    def test_missing_classification(self, seeded_db):
        """TC-VAL-003: Missing classification_id should fail."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "",
            "material_type": "raw"
        })
        assert result["passed"] is False
        assert any("必填字段缺失" in e for e in result["errors"])

    def test_missing_material_type(self, seeded_db):
        """TC-VAL-004: Missing material_type should fail."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "cls-child-001",
            "material_type": ""
        })
        assert result["passed"] is False
        assert any("必填字段缺失" in e for e in result["errors"])

    def test_all_fields_missing(self, seeded_db):
        """TC-VAL-005: All missing fields should produce multiple errors."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({})
        assert result["passed"] is False
        assert len(result["errors"]) >= 3


class TestMaterialValidatorNameLength:
    """Test material name length validation."""

    def test_name_too_short(self, seeded_db):
        """TC-VAL-010: Name shorter than 5 chars should fail."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "钢板",
            "classification_id": "cls-child-001",
            "material_type": "raw"
        })
        assert result["passed"] is False
        assert any("太短" in e for e in result["errors"])

    def test_name_exactly_5_chars(self, seeded_db):
        """TC-VAL-011: Name of exactly 5 chars should pass."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "不锈钢板材",  # 5 characters
            "classification_id": "cls-child-001",
            "material_type": "raw",
            "attribute_values": {"material_grade": "Q235", "thickness": "1.0"}
        })
        assert result["passed"] is True

    def test_name_too_long(self, seeded_db):
        """TC-VAL-012: Name longer than 200 chars should fail."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "A" * 201,
            "classification_id": "cls-child-001",
            "material_type": "raw",
            "attribute_values": {"material_grade": "Q235", "thickness": "1.0"}
        })
        assert result["passed"] is False
        assert any("太长" in e for e in result["errors"])

    def test_name_at_200_chars(self, seeded_db):
        """TC-VAL-013: Name of exactly 200 chars should pass."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "A" * 200,
            "classification_id": "cls-child-001",
            "material_type": "raw",
            "attribute_values": {"material_grade": "Q235", "thickness": "1.0"}
        })
        assert result["passed"] is True


class TestMaterialValidatorClassification:
    """Test classification existence validation."""

    def test_valid_classification(self, seeded_db):
        """TC-VAL-020: Existing classification should pass."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "cls-child-001",
            "material_type": "raw",
            "attribute_values": {"material_grade": "Q235", "thickness": "1.0"}
        })
        assert result["passed"] is True
        # Check that classification_exists check passed
        checks = result["checks"]
        cls_check = next((c for c in checks if c["check"] == "classification_exists"), None)
        assert cls_check is not None
        assert cls_check["passed"] is True
        assert "金属材料" in cls_check["message"]

    def test_invalid_classification(self, seeded_db):
        """TC-VAL-021: Non-existent classification should fail."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "non-existent-id",
            "material_type": "raw"
        })
        assert result["passed"] is False
        assert any("分类不存在" in e for e in result["errors"])


class TestMaterialValidatorType:
    """Test material type validation."""

    def test_valid_type_raw(self, seeded_db):
        """TC-VAL-030: Valid type 'raw' should pass."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "cls-child-001",
            "material_type": "raw",
            "attribute_values": {"material_grade": "Q235", "thickness": "1.0"}
        })
        assert result["passed"] is True

    def test_valid_types_all(self, seeded_db):
        """TC-VAL-031: All valid types should pass."""
        validator = MaterialValidator(seeded_db)
        valid_types = ["raw", "semi", "finished", "auxiliary", "spare"]
        
        for mtype in valid_types:
            result = validator.validate({
                "material_name": "测试物料名称",  # at least 5 chars
                "classification_id": "cls-child-001",
                "material_type": mtype,
                "attribute_values": {"material_grade": "Q235", "thickness": "1.0"}
            })
            assert result["passed"] is True, f"Type {mtype} should be valid"

    def test_invalid_type(self, seeded_db):
        """TC-VAL-032: Invalid type should fail."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "cls-child-001",
            "material_type": "invalid_type"
        })
        assert result["passed"] is False
        assert any("无效的物料类型" in e for e in result["errors"])


class TestMaterialValidatorAttributes:
    """Test attribute template validation."""

    def test_required_attribute_missing(self, seeded_db):
        """TC-VAL-040: Missing required attribute should fail."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "cls-child-001",
            "material_type": "raw",
            "attribute_values": {}  # Empty, but material_grade and thickness are required
        })
        assert result["passed"] is False
        assert any("必填属性缺失" in e for e in result["errors"])

    def test_required_attribute_present(self, seeded_db):
        """TC-VAL-041: All required attributes present should pass."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "cls-child-001",
            "material_type": "raw",
            "attribute_values": {
                "material_grade": "304不锈钢",
                "thickness": "2.0"
            }
        })
        assert result["passed"] is True

    def test_optional_attribute_missing_ok(self, seeded_db):
        """TC-VAL-042: Missing optional attribute should not fail."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "cls-child-001",
            "material_type": "raw",
            "attribute_values": {
                "material_grade": "304不锈钢",
                "thickness": "2.0"
                # width is optional, not provided
            }
        })
        assert result["passed"] is True

    def test_partial_required_attribute(self, seeded_db):
        """TC-VAL-043: One required attribute missing should fail."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "cls-child-001",
            "material_type": "raw",
            "attribute_values": {
                "material_grade": "304不锈钢"
                # thickness is required but missing
            }
        })
        assert result["passed"] is False
        assert any("厚度" in e for e in result["errors"])


class TestMaterialValidatorCheckStructure:
    """Test validation result structure."""

    def test_result_has_all_keys(self, seeded_db):
        """TC-VAL-050: Result should have passed, checks, errors keys."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "cls-child-001",
            "material_type": "raw"
        })
        assert "passed" in result
        assert "checks" in result
        assert "errors" in result
        assert isinstance(result["checks"], list)
        assert isinstance(result["errors"], list)

    def test_checks_have_required_structure(self, seeded_db):
        """TC-VAL-051: Each check should have check, passed, message keys."""
        validator = MaterialValidator(seeded_db)
        result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "cls-child-001",
            "material_type": "raw"
        })
        for check in result["checks"]:
            assert "check" in check
            assert "passed" in check
            assert "message" in check
            assert isinstance(check["passed"], bool)

    def test_passed_true_when_no_errors(self, seeded_db):
        """TC-VAL-052: passed should be True iff errors is empty."""
        validator = MaterialValidator(seeded_db)
        
        valid_result = validator.validate({
            "material_name": "测试不锈钢板材",
            "classification_id": "cls-child-001",
            "material_type": "raw",
            "attribute_values": {"material_grade": "Q235", "thickness": "1.0"}
        })
        assert valid_result["passed"] == (len(valid_result["errors"]) == 0)

    def test_passed_false_when_errors(self, seeded_db):
        """TC-VAL-053: passed should be False when errors exist."""
        validator = MaterialValidator(seeded_db)
        
        invalid_result = validator.validate({
            "material_name": "",
            "classification_id": "",
            "material_type": ""
        })
        assert invalid_result["passed"] is False
        assert len(invalid_result["errors"]) > 0
