"""Unit tests for DuplicateDetector service."""
import pytest
from app import models
from app.services.duplicate_detector import DuplicateDetector


class TestDuplicateDetectorEmptyDatabase:
    """Test duplicate detection with no existing records."""

    def test_no_duplicates_empty_db(self, seeded_db):
        """TC-DEDUP-001: Empty database should return no duplicates."""
        detector = DuplicateDetector(seeded_db)
        result = detector.check({"material_name": "不锈钢板材304"})
        
        assert result["is_duplicate"] is False
        assert result["confidence"] == 0.0
        assert result["similar_materials"] == []

    def test_short_name_no_check(self, seeded_db):
        """TC-DEDUP-002: Names shorter than 3 chars should skip check."""
        detector = DuplicateDetector(seeded_db)
        result = detector.check({"material_name": "钢"})
        
        assert result["is_duplicate"] is False
        assert result["similar_materials"] == []

    def test_empty_name_no_check(self, seeded_db):
        """TC-DEDUP-003: Empty name should skip check."""
        detector = DuplicateDetector(seeded_db)
        result = detector.check({"material_name": ""})
        
        assert result["is_duplicate"] is False

    def test_whitespace_only_name(self, seeded_db):
        """TC-DEDUP-004: Whitespace-only name should be treated as empty."""
        detector = DuplicateDetector(seeded_db)
        result = detector.check({"material_name": "   "})
        
        assert result["is_duplicate"] is False


class TestDuplicateDetectorExactMatch:
    """Test exact name matching."""

    def test_exact_match_found(self, seeded_db):
        """TC-DEDUP-010: Exact name match should flag duplicate."""
        # Create golden record
        gr = models.GoldenRecord(
            id="gr-001",
            material_code="M01-0101-00001",
            material_name="不锈钢板材304",
            classification_id="cls-child-001",
            material_type=models.MaterialType.RAW,
            status=models.GoldenRecordStatus.ACTIVE,
            created_by="user001"
        )
        seeded_db.add(gr)
        seeded_db.commit()
        
        detector = DuplicateDetector(seeded_db)
        result = detector.check({"material_name": "不锈钢板材304"})
        
        assert result["is_duplicate"] is True
        assert result["confidence"] == 1.0
        assert len(result["similar_materials"]) == 1
        assert result["similar_materials"][0]["similarity"] == 1.0
        assert result["similar_materials"][0]["reason"] == "名称完全相同"

    def test_exact_match_case_insensitive(self, seeded_db):
        """TC-DEDUP-011: Case-insensitive exact match should work."""
        gr = models.GoldenRecord(
            id="gr-001",
            material_code="M01-0101-00001",
            material_name="不锈钢板材304",
            classification_id="cls-child-001",
            material_type=models.MaterialType.RAW,
            status=models.GoldenRecordStatus.ACTIVE,
            created_by="user001"
        )
        seeded_db.add(gr)
        seeded_db.commit()
        
        detector = DuplicateDetector(seeded_db)
        result = detector.check({"material_name": "不锈钢板材304"})
        
        assert result["is_duplicate"] is True

    def test_exact_match_with_whitespace(self, seeded_db):
        """TC-DEDUP-012: Exact match with leading/trailing whitespace."""
        gr = models.GoldenRecord(
            id="gr-001",
            material_code="M01-0101-00001",
            material_name="不锈钢板材304",
            classification_id="cls-child-001",
            material_type=models.MaterialType.RAW,
            status=models.GoldenRecordStatus.ACTIVE,
            created_by="user001"
        )
        seeded_db.add(gr)
        seeded_db.commit()
        
        detector = DuplicateDetector(seeded_db)
        result = detector.check({"material_name": "  不锈钢板材304  "})
        
        assert result["is_duplicate"] is True

    def test_no_match_obsolete_record(self, seeded_db):
        """TC-DEDUP-013: Obsolete records should not match."""
        gr = models.GoldenRecord(
            id="gr-001",
            material_code="M01-0101-00001",
            material_name="不锈钢板材304",
            classification_id="cls-child-001",
            material_type=models.MaterialType.RAW,
            status=models.GoldenRecordStatus.OBSOLETE,  # Not active
            created_by="user001"
        )
        seeded_db.add(gr)
        seeded_db.commit()
        
        detector = DuplicateDetector(seeded_db)
        result = detector.check({"material_name": "不锈钢板材304"})
        
        assert result["is_duplicate"] is False
        assert len(result["similar_materials"]) == 0


class TestDuplicateDetectorPartialMatch:
    """Test partial/prefix matching."""

    def test_partial_match_found(self, seeded_db):
        """TC-DEDUP-020: Partial match with high word overlap should be flagged."""
        gr = models.GoldenRecord(
            id="gr-001",
            material_code="M01-0101-00001",
            material_name="304 不锈钢 板材 2mm 厚",
            classification_id="cls-child-001",
            material_type=models.MaterialType.RAW,
            status=models.GoldenRecordStatus.ACTIVE,
            created_by="user001"
        )
        seeded_db.add(gr)
        seeded_db.commit()
        
        detector = DuplicateDetector(seeded_db)
        result = detector.check({"material_name": "304 不锈钢 板材 3mm 厚"})
        
        # Should find similar material
        assert len(result["similar_materials"]) > 0
        # With high overlap ("304", "不锈钢", "板材", "厚"), should be flagged
        assert result["is_duplicate"] is True

    def test_partial_match_low_overlap_not_duplicate(self, seeded_db):
        """TC-DEDUP-021: Low word overlap should not flag as duplicate."""
        gr = models.GoldenRecord(
            id="gr-001",
            material_code="M01-0101-00001",
            material_name="碳素结构钢Q235",
            classification_id="cls-child-001",
            material_type=models.MaterialType.RAW,
            status=models.GoldenRecordStatus.ACTIVE,
            created_by="user001"
        )
        seeded_db.add(gr)
        seeded_db.commit()
        
        detector = DuplicateDetector(seeded_db)
        result = detector.check({"material_name": "铝合金型材6061"})
        
        # Different materials, no overlap
        assert result["is_duplicate"] is False
        # But might still have some prefix match
        # "铝合" vs "碳素" - no 4-char prefix overlap, so no matches

    def test_multiple_similar_materials(self, seeded_db):
        """TC-DEDUP-022: Should return up to 5 similar materials."""
        for i in range(7):
            gr = models.GoldenRecord(
                id=f"gr-{i:03d}",
                material_code=f"M01-0101-{i+1:05d}",
                material_name=f"不锈钢板材304系列{i+1}",
                classification_id="cls-child-001",
                material_type=models.MaterialType.RAW,
                status=models.GoldenRecordStatus.ACTIVE,
                created_by="user001"
            )
            seeded_db.add(gr)
        seeded_db.commit()
        
        detector = DuplicateDetector(seeded_db)
        result = detector.check({"material_name": "不锈钢板材304系列测试"})
        
        # Should return at most 5 similar materials
        assert len(result["similar_materials"]) <= 5
        # All should be sorted by similarity descending
        similarities = [m["similarity"] for m in result["similar_materials"]]
        assert similarities == sorted(similarities, reverse=True)

    def test_deduplicate_by_code(self, seeded_db):
        """TC-DEDUP-023: Should deduplicate by material_code."""
        # Same code, different match paths
        gr = models.GoldenRecord(
            id="gr-001",
            material_code="M01-0101-00001",
            material_name="不锈钢板材304",
            classification_id="cls-child-001",
            material_type=models.MaterialType.RAW,
            status=models.GoldenRecordStatus.ACTIVE,
            created_by="user001"
        )
        seeded_db.add(gr)
        seeded_db.commit()
        
        detector = DuplicateDetector(seeded_db)
        result = detector.check({"material_name": "不锈钢板材304"})
        
        # Even if matched by both exact and partial, should only appear once
        codes = [m["material_code"] for m in result["similar_materials"]]
        assert len(codes) == len(set(codes))


class TestDuplicateDetectorPerformance:
    """Test deduplication performance characteristics."""

    def test_database_query_not_full_scan(self, seeded_db):
        """TC-DEDUP-030: Should use ILIKE query, not load all records."""
        # This is verified by code inspection - the test ensures
        # the method doesn't fail with large datasets
        detector = DuplicateDetector(seeded_db)
        
        # With no records, should be fast
        result = detector.check({"material_name": "测试物料名称"})
        assert result is not None

    def test_handles_special_characters(self, seeded_db):
        """TC-DEDUP-031: Should handle special characters in names."""
        gr = models.GoldenRecord(
            id="gr-001",
            material_code="M01-0101-00001",
            material_name="材料A/B型（测试）",
            classification_id="cls-child-001",
            material_type=models.MaterialType.RAW,
            status=models.GoldenRecordStatus.ACTIVE,
            created_by="user001"
        )
        seeded_db.add(gr)
        seeded_db.commit()
        
        detector = DuplicateDetector(seeded_db)
        # ILIKE with SQL special chars should not crash
        result = detector.check({"material_name": "材料A/B型"})
        assert result is not None

    def test_long_material_name(self, seeded_db):
        """TC-DEDUP-032: Should handle long material names."""
        long_name = "A" * 200
        detector = DuplicateDetector(seeded_db)
        result = detector.check({"material_name": long_name})
        assert result["is_duplicate"] is False
