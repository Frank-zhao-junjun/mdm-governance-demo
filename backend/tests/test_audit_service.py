"""Unit tests for AuditService (SPEC §3.0 governance audit trail)."""
from app import models
from app.services.audit_service import AuditService


class TestAuditServiceLogging:
    def test_log_with_step_enum_member(self, seeded_db):
        log = AuditService(seeded_db).log(
            step_name=models.StepName.STANDARD_CREATE,
            executed_by="data001",
            executed_by_name="钱数据",
            details={"standard_id": "s-1"},
        )
        assert log.step_id == "GOV-STANDARD_CREATE-00001"
        assert log.step_name == models.StepName.STANDARD_CREATE
        assert log.step_label == "创建数据标准"
        assert log.status == "success"
        assert log.status_label == "成功"

    def test_log_with_step_enum_value(self, seeded_db):
        """Callers pass .value strings; the column must accept both forms."""
        log = AuditService(seeded_db).log(
            step_name=models.StepName.STANDARD_CREATE.value,
            executed_by="admin001",
            executed_by_name="王管理员",
        )
        assert log.step_id == "GOV-STANDARD_CREATE-00001"
        assert log.step_name == models.StepName.STANDARD_CREATE

    def test_step_id_increments_per_step_name(self, seeded_db):
        audit = AuditService(seeded_db)
        first = audit.log(
            step_name="standard_create",
            executed_by="data001",
            executed_by_name="钱数据",
        )
        second = audit.log(
            step_name="standard_create",
            executed_by="data001",
            executed_by_name="钱数据",
        )
        other = audit.log(
            step_name="standard_delete",
            executed_by="data001",
            executed_by_name="钱数据",
        )
        assert first.step_id == "GOV-STANDARD_CREATE-00001"
        assert second.step_id == "GOV-STANDARD_CREATE-00002"
        assert other.step_id == "GOV-STANDARD_DELETE-00001"

    def test_failed_log_keeps_error_message(self, seeded_db):
        log = AuditService(seeded_db).log(
            step_name="quality_run",
            executed_by="data001",
            executed_by_name="钱数据",
            status="failed",
            error_message="实体数量超过 5000 上限",
        )
        assert log.status == "failed"
        assert log.status_label == "失败"
        assert log.error_message == "实体数量超过 5000 上限"
        assert log.step_label == "执行质量检测"

    def test_details_roundtrip_from_database(self, seeded_db):
        log = AuditService(seeded_db).log(
            step_name="data_import",
            executed_by="data001",
            executed_by_name="钱数据",
            details={"entity_type": "supplier", "rows": 20, "rejected": 2},
        )
        stored = seeded_db.query(models.AuditLog).filter(
            models.AuditLog.id == log.id
        ).first()
        assert stored.details == {"entity_type": "supplier", "rows": 20, "rejected": 2}
        assert stored.step_name == models.StepName.DATA_IMPORT


class TestAuditServiceLabels:
    def test_every_step_name_has_a_label(self):
        for step in models.StepName:
            assert step.value in AuditService.STEP_LABELS, f"Missing label for {step.value}"

    def test_labels_cover_no_stale_steps(self):
        assert set(AuditService.STEP_LABELS) == {s.value for s in models.StepName}

    def test_status_labels(self):
        assert AuditService.STATUS_LABELS["success"] == "成功"
        assert AuditService.STATUS_LABELS["failed"] == "失败"
