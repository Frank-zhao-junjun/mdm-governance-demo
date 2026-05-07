"""Unit tests for CodeGenerator service."""
import pytest
from app import models
from app.services.code_generator import CodeGenerator


class TestCodeGeneratorBasics:
    """Test basic code generation scenarios."""

    def test_generate_with_rule(self, seeded_db):
        """TC-CODE-001: Generate code using defined rule pattern."""
        generator = CodeGenerator(seeded_db)
        code = generator.generate("cls-child-001", "raw")
        
        assert code is not None
        assert len(code) > 0
        # Pattern: M{大类}-{小类}-{流水} -> M01-0101-00001
        assert code.startswith("M")
        assert "-" in code

    def test_code_is_unique_per_call(self, seeded_db):
        """TC-CODE-002: Sequential calls should produce different codes."""
        generator = CodeGenerator(seeded_db)
        code1 = generator.generate("cls-child-001", "raw")
        code2 = generator.generate("cls-child-001", "raw")
        
        assert code1 != code2
        # Sequence should increment
        seq1 = int(code1.split("-")[-1])
        seq2 = int(code2.split("-")[-1])
        assert seq2 == seq1 + 1

    def test_code_format_compliance(self, seeded_db):
        """TC-CODE-003: Generated code should match expected format."""
        generator = CodeGenerator(seeded_db)
        code = generator.generate("cls-child-001", "raw")
        
        # Format: M01-0101-NNNNN
        parts = code.replace("M", "").split("-")
        assert len(parts) == 3
        assert parts[0] == "01"  # parent code
        assert parts[1] == "0101"  # child code
        assert len(parts[2]) == 5  # sequence padding
        assert parts[2].isdigit()

    def test_sequence_increment_atomic(self, seeded_db):
        """TC-CODE-004: Sequence should increment correctly with each generation."""
        from app import crud
        
        initial_seq = crud.increment_seq(seeded_db, "rule-001")
        next_seq = crud.increment_seq(seeded_db, "rule-001")
        
        assert next_seq == initial_seq + 1

    def test_different_types_different_prefix(self, seeded_db):
        """TC-CODE-005: Different material types should share same sequence."""
        generator = CodeGenerator(seeded_db)
        
        code1 = generator.generate("cls-child-001", "raw")
        code2 = generator.generate("cls-child-001", "finished")
        
        # Both use same sequence counter
        seq1 = int(code1.split("-")[-1])
        seq2 = int(code2.split("-")[-1])
        assert seq2 == seq1 + 1


class TestCodeGeneratorEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_classification_raises(self, seeded_db):
        """TC-CODE-010: Invalid classification should raise ValueError."""
        generator = CodeGenerator(seeded_db)
        with pytest.raises(ValueError, match="分类不存在"):
            generator.generate("non-existent-id", "raw")

    def test_generate_without_rule_uses_default(self, seeded_db):
        """TC-CODE-011: Classification without rule uses default pattern."""
        # Create classification without rule
        new_cls = models.MaterialClassification(
            id="cls-no-rule",
            code="99",
            name="无规则分类",
            level=2,
            parent_id="cls-parent-001",
            is_active=True
        )
        seeded_db.add(new_cls)
        seeded_db.commit()
        
        generator = CodeGenerator(seeded_db)
        code = generator.generate("cls-no-rule", "raw")
        
        # Default format: {parent_code}-{child_code}-{count+1:05d}
        assert code is not None
        assert len(code) > 0

    def test_empty_material_type(self, seeded_db):
        """TC-CODE-012: Empty material type should still generate code."""
        generator = CodeGenerator(seeded_db)
        code = generator.generate("cls-child-001", "")
        assert code is not None

    def test_sequence_padding(self, seeded_db):
        """TC-CODE-013: Sequence numbers should be zero-padded."""
        from app import crud
        
        # Manually set sequence to test padding
        rule = seeded_db.query(models.CodeRule).filter_by(id="rule-001").first()
        rule.current_seq = 42
        seeded_db.commit()
        
        generator = CodeGenerator(seeded_db)
        code = generator.generate("cls-child-001", "raw")
        
        # Should be padded to 5 digits: 00043
        seq_part = code.split("-")[-1]
        assert len(seq_part) == 5
        assert seq_part == "00043"

    def test_high_sequence_number(self, seeded_db):
        """TC-CODE-014: High sequence numbers should still work."""
        from app import crud
        
        # Reset and set high sequence
        rule = seeded_db.query(models.CodeRule).filter_by(id="rule-001").first()
        rule.current_seq = 99998
        seeded_db.commit()
        
        generator = CodeGenerator(seeded_db)
        code = generator.generate("cls-child-001", "raw")
        
        seq_part = code.split("-")[-1]
        assert seq_part == "99999"

    def test_rule_with_prefix_suffix(self, seeded_db):
        """TC-CODE-015: Rules with prefix/suffix should be applied."""
        rule = seeded_db.query(models.CodeRule).filter_by(id="rule-001").first()
        rule.prefix = "PRE"
        rule.suffix = "SUF"
        seeded_db.commit()
        
        generator = CodeGenerator(seeded_db)
        code = generator.generate("cls-child-001", "raw")
        
        assert code.startswith("PRE")
        assert code.endswith("SUF")


class TestCodeGeneratorYearReplacement:
    """Test year placeholder replacement in code patterns."""

    def test_year_placeholder_replacement(self, seeded_db):
        """TC-CODE-020: {年份} placeholder should be replaced with last 2 digits of current year."""
        from datetime import datetime
        
        rule = seeded_db.query(models.CodeRule).filter_by(id="rule-001").first()
        rule.pattern = "{年份}-{流水}"
        rule.prefix = ""
        seeded_db.commit()
        
        generator = CodeGenerator(seeded_db)
        code = generator.generate("cls-child-001", "raw")
        
        year_suffix = str(datetime.now().year)[-2:]
        assert year_suffix in code
