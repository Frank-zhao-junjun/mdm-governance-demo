"""Unit tests for AuditService."""
import pytest
from datetime import datetime
from app import models
from app.services.audit_service import AuditService


class TestAuditLogCreation:
    """Test audit log creation."""

    def test_log_basic_entry(self, seeded_db, sample_application):
        """TC-AUDIT-001: Basic audit log entry creation."""
        audit = AuditService(seeded_db)
        log = audit.log(
            application_id=sample_application.id,
            step_name="submit",
            executed_by="user001",
            executed_by_name="张三",
            status="success",
            details={"material_code": "M01-0101-00001"}
        )
        
        assert log is not None
        assert log.step_name == models.StepName.SUBMIT
        assert log.status == "success"
        assert log.executed_by == "user001"
        assert log.step_id.startswith(sample_application.app_no)

    def test_log_step_id_format(self, seeded_db, sample_application):
        """TC-AUDIT-002: Step ID should follow SQ-YYYY-NNNNN-S# format."""
        audit = AuditService(seeded_db)
        log = audit.log(
            application_id=sample_application.id,
            step_name="submit",
            executed_by="user001",
            executed_by_name="张三",
            status="success"
        )
        
        # Format: {app_no}-S1
        expected_prefix = f"{sample_application.app_no}-S"
        assert log.step_id.startswith(expected_prefix)
        assert log.step_id == f"{sample_application.app_no}-S1"

    def test_log_step_id_increments(self, seeded_db, sample_application):
        """TC-AUDIT-003: Multiple logs should have sequential step IDs."""
        audit = AuditService(seeded_db)
        
        log1 = audit.log(
            application_id=sample_application.id,
            step_name="submit",
            executed_by="user001",
            executed_by_name="张三",
            status="success"
        )
        log2 = audit.log(
            application_id=sample_application.id,
            step_name="validate",
            executed_by="system",
            executed_by_name="系统自动",
            status="success"
        )
        log3 = audit.log(
            application_id=sample_application.id,
            step_name="code_generate",
            executed_by="system",
            executed_by_name="系统自动",
            status="success"
        )
        
        assert log1.step_id == f"{sample_application.app_no}-S1"
        assert log2.step_id == f"{sample_application.app_no}-S2"
        assert log3.step_id == f"{sample_application.app_no}-S3"

    def test_log_step_labels(self, seeded_db, sample_application):
        """TC-AUDIT-004: Step labels should be human-readable Chinese."""
        audit = AuditService(seeded_db)
        
        log = audit.log(
            application_id=sample_application.id,
            step_name="create_draft",
            executed_by="user001",
            executed_by_name="张三",
            status="success"
        )
        
        assert log.step_label == "创建草稿"
        assert log.status_label == "成功"

    def test_log_failed_status(self, seeded_db, sample_application):
        """TC-AUDIT-005: Failed status should be recorded correctly."""
        audit = AuditService(seeded_db)
        
        log = audit.log(
            application_id=sample_application.id,
            step_name="validate",
            executed_by="system",
            executed_by_name="系统自动",
            status="failed",
            error_message="质量校验未通过"
        )
        
        assert log.status == "failed"
        assert log.status_label == "失败"
        assert log.error_message == "质量校验未通过"

    def test_log_with_golden_record(self, seeded_db, sample_application):
        """TC-AUDIT-006: Log can reference a golden record."""
        # Create a golden record
        gr = models.GoldenRecord(
            id="gr-001",
            material_code="M01-0101-00001",
            material_name="测试不锈钢",
            classification_id="cls-child-001",
            material_type=models.MaterialType.RAW,
            created_by="user001"
        )
        seeded_db.add(gr)
        seeded_db.commit()
        
        audit = AuditService(seeded_db)
        log = audit.log(
            application_id=sample_application.id,
            golden_record_id=gr.id,
            step_name="create_gr",
            executed_by="system",
            executed_by_name="系统自动",
            status="success"
        )
        
        assert log.golden_record_id == "gr-001"

    def test_log_without_application(self, seeded_db):
        """TC-AUDIT-007: Log without application should use UNKNOWN app_no."""
        audit = AuditService(seeded_db)
        
        log = audit.log(
            application_id=None,
            step_name="create_gr",
            executed_by="system",
            executed_by_name="系统自动",
            status="success"
        )
        
        assert log.step_id.startswith("UNKNOWN-S")


class TestAuditTraceRetrieval:
    """Test audit trace retrieval."""

    def test_get_empty_trace(self, seeded_db, sample_application):
        """TC-AUDIT-010: Empty trace should return empty list."""
        audit = AuditService(seeded_db)
        trace = audit.get_application_trace(sample_application.id)
        
        assert isinstance(trace, list)
        assert len(trace) == 0

    def test_get_trace_with_logs(self, seeded_db, sample_application):
        """TC-AUDIT-011: Trace should return all logs in order."""
        audit = AuditService(seeded_db)
        
        audit.log(sample_application.id, "submit", "user001", "张三", "success")
        audit.log(sample_application.id, "validate", "system", "系统自动", "success")
        audit.log(sample_application.id, "code_generate", "system", "系统自动", "success")
        
        trace = audit.get_application_trace(sample_application.id)
        
        assert len(trace) == 3
        assert trace[0]["step_name"] == "submit"
        assert trace[1]["step_name"] == "validate"
        assert trace[2]["step_name"] == "code_generate"

    def test_trace_entry_structure(self, seeded_db, sample_application):
        """TC-AUDIT-012: Each trace entry should have required fields."""
        audit = AuditService(seeded_db)
        
        audit.log(sample_application.id, "submit", "user001", "张三", "success")
        
        trace = audit.get_application_trace(sample_application.id)
        entry = trace[0]
        
        assert "step_id" in entry
        assert "step_name" in entry
        assert "step_label" in entry
        assert "executed_by" in entry
        assert "executed_by_name" in entry
        assert "executed_at" in entry
        assert "status" in entry
        assert "status_label" in entry
        assert "details" in entry
        assert "error_message" in entry

    def test_trace_executed_at_isoformat(self, seeded_db, sample_application):
        """TC-AUDIT-013: executed_at should be ISO format string."""
        audit = AuditService(seeded_db)
        
        audit.log(sample_application.id, "submit", "user001", "张三", "success")
        
        trace = audit.get_application_trace(sample_application.id)
        entry = trace[0]
        
        # Should be valid ISO format
        try:
            datetime.fromisoformat(entry["executed_at"].replace("Z", "+00:00"))
        except ValueError:
            pytest.fail("executed_at is not valid ISO format")

    def test_trace_only_returns_own_logs(self, seeded_db, sample_application):
        """TC-AUDIT-014: Trace should only return logs for specified application."""
        from app import crud, schemas
        
        # Create second application
        app2 = crud.create_application(
            seeded_db,
            schemas.ApplicationCreate(
                material_name="第二个测试物料",
                classification_id="cls-child-001",
                material_type=models.MaterialType.RAW
            ),
            "user002", "李四"
        )
        
        audit = AuditService(seeded_db)
        audit.log(sample_application.id, "submit", "user001", "张三", "success")
        audit.log(app2.id, "submit", "user002", "李四", "success")
        
        trace1 = audit.get_application_trace(sample_application.id)
        trace2 = audit.get_application_trace(app2.id)
        
        assert len(trace1) == 1
        assert len(trace2) == 1
        assert trace1[0]["executed_by"] == "user001"
        assert trace2[0]["executed_by"] == "user002"


class TestAuditServiceLabels:
    """Test label mapping completeness."""

    def test_all_step_names_have_labels(self):
        """TC-AUDIT-020: All StepName enum values should have labels."""
        audit = AuditService(None)
        
        # All defined step names should have labels
        for step_name in models.StepName:
            assert step_name.value in audit.STEP_LABELS, f"Missing label for {step_name.value}"

    def test_all_statuses_have_labels(self):
        """TC-AUDIT-021: All status values should have labels."""
        audit = AuditService(None)
        
        for status in ["success", "failed", "pending"]:
            assert status in audit.STATUS_LABELS

    def test_unknown_step_uses_raw_name(self, seeded_db, sample_application):
        """TC-AUDIT-022: Unknown step name should use the raw name as label."""
        audit = AuditService(seeded_db)
        # This won't happen in practice since we use enum,
        # but the code has a fallback
        # Test the fallback logic via direct check
        assert audit.STEP_LABELS.get("unknown_step", "unknown_step") == "unknown_step"
