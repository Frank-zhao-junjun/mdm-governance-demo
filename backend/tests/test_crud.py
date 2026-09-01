"""Unit tests for governance CRUD operations (SPEC §2.1, §3.1)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app import crud, models


def _standard(**overrides):
    data = dict(
        entity_type="material",
        sap_table="MARA",
        field_name="MATNR",
        field_label="物料编码",
        data_type="string",
        required=True,
        pattern=r"^M\d{5}$",
        unique=True,
    )
    data.update(overrides)
    return data


class TestDataStandardCRUD:
    def test_list_returns_total_and_page(self, seeded_db):
        items, total = crud.get_data_standards(seeded_db, skip=0, limit=50)
        assert total == 2
        assert len(items) == 2

    def test_list_pagination_does_not_overlap(self, seeded_db):
        for i in range(5):
            crud.create_data_standard(
                seeded_db,
                _standard(field_name=f"F{i:02d}", field_label=f"字段{i}"),
            )
        # seeded_db carries MATNR + LIFNR, so MARA now has 6 rows
        page1, total = crud.get_data_standards(seeded_db, sap_table="MARA", skip=0, limit=4)
        page2, _ = crud.get_data_standards(seeded_db, sap_table="MARA", skip=4, limit=4)

        assert total == 6
        assert len(page1) == 4
        assert len(page2) == 2
        assert {p.id for p in page1}.isdisjoint({p.id for p in page2})

    def test_filter_by_entity_type(self, seeded_db):
        items, total = crud.get_data_standards(seeded_db, entity_type="supplier")
        assert total == 1
        assert all(i.entity_type == "supplier" for i in items)

    def test_create_persists_management_attributes(self, seeded_db):
        created = crud.create_data_standard(
            seeded_db,
            _standard(
                field_name="MEINS",
                field_label="基本计量单位",
                data_type="enum",
                enum_values=["PC", "KG"],
                owner="钱数据",
                standard_source="sap",
                dept_scope=["采购部"],
                business_attrs={"standard_topic": "物料主数据"},
            ),
        )
        found = crud.get_data_standard(seeded_db, created.id)
        assert found.owner == "钱数据"
        assert found.standard_source == "sap"
        assert found.dept_scope == ["采购部"]
        assert found.enum_values == ["PC", "KG"]
        assert found.business_attrs == {"standard_topic": "物料主数据"}

    def test_update_changes_only_given_fields(self, seeded_db):
        standard = crud.create_data_standard(seeded_db, _standard(field_name="MEINS"))
        updated = crud.update_data_standard(
            seeded_db, standard, {"field_label": "计量单位", "required": False}
        )
        assert updated.field_label == "计量单位"
        assert updated.required is False
        assert updated.field_name == "MEINS"
        assert updated.sap_table == "MARA"

    def test_delete_removes_row(self, seeded_db):
        standard = crud.create_data_standard(seeded_db, _standard(field_name="MEINS"))
        crud.delete_data_standard(seeded_db, standard)
        assert crud.get_data_standard(seeded_db, standard.id) is None

    def test_unique_identity_key_is_enforced(self, seeded_db):
        crud.create_data_standard(seeded_db, _standard(sap_table="MARM", field_name="MEINH"))
        with pytest.raises(IntegrityError):
            crud.create_data_standard(
                seeded_db, _standard(sap_table="MARM", field_name="MEINH", field_label="重复")
            )
        seeded_db.rollback()


class TestFindDataStandardConflict:
    def test_conflict_on_entity_table_field(self, seeded_db):
        crud.create_data_standard(seeded_db, _standard(sap_table="MARM", field_name="MEINH"))
        conflict = crud.find_data_standard_conflict(seeded_db, "material", "MARM", "MEINH")
        assert conflict is not None

    def test_no_conflict_across_sap_tables(self, seeded_db):
        crud.create_data_standard(seeded_db, _standard(sap_table="MARM", field_name="MEINH"))
        assert crud.find_data_standard_conflict(seeded_db, "material", "MARA", "MEINH") is None

    def test_null_sap_table_matches_only_null(self, seeded_db):
        crud.create_data_standard(seeded_db, _standard(sap_table=None, field_name="ZEXT"))
        assert crud.find_data_standard_conflict(seeded_db, "material", None, "ZEXT") is not None
        assert crud.find_data_standard_conflict(seeded_db, "material", "MARA", "ZEXT") is None


class TestStockRecordCRUD:
    def test_get_material_records(self, seeded_db):
        records = crud.get_material_records(seeded_db)
        assert [r.material_code for r in records] == ["M10001"]

    def test_material_records_respects_entity_ids(self, seeded_db):
        existing = crud.get_material_records(seeded_db)
        seeded_db.add(models.MaterialRecord(
            material_code="M10002", material_name="垫片", attributes={}
        ))
        seeded_db.commit()
        records = crud.get_material_records(seeded_db, entity_ids=[existing[0].id])
        assert len(records) == 1
        assert records[0].material_code == "M10001"

    def test_material_records_respects_limit(self, seeded_db):
        for i in range(2, 12):
            seeded_db.add(models.MaterialRecord(
                material_code=f"M100{i:02d}", material_name=f"物料{i}", attributes={}
            ))
        seeded_db.commit()
        assert len(crud.get_material_records(seeded_db, limit=7)) == 7

    def test_partner_records_filter_by_entity_type(self, seeded_db):
        seeded_db.add(models.PartnerRecord(
            entity_type="customer", partner_code="2000000001",
            partner_name="测试客户", attributes={},
        ))
        seeded_db.commit()
        suppliers = crud.get_partner_records(seeded_db, entity_type="supplier")
        customers = crud.get_partner_records(seeded_db, entity_type="customer")
        assert [r.partner_code for r in suppliers] == ["1000000001"]
        assert [r.partner_code for r in customers] == ["2000000001"]


class TestAuditLogCRUD:
    def test_step_name_accepts_enum_value_string(self, seeded_db):
        """Regression: Enum column must persist values, not member names."""
        log = crud.create_audit_log(
            seeded_db,
            step_id="GOV-STANDARD-CREATE-00001",
            step_name=models.StepName.STANDARD_CREATE,
            step_label="创建数据标准",
            executed_by="data001",
            executed_by_name="钱数据",
            status="success",
            status_label="成功",
        )
        assert log.step_name == models.StepName.STANDARD_CREATE

    def test_get_audit_logs_orders_desc_with_paging(self, seeded_db):
        base = datetime.now(timezone.utc)
        for i in range(5):
            crud.create_audit_log(
                seeded_db,
                step_id=f"GOV-STANDARD-UPDATE-{i + 1:05d}",
                step_name=models.StepName.STANDARD_UPDATE,
                step_label="更新数据标准",
                executed_by="data001",
                executed_by_name="钱数据",
                status="success",
                executed_at=base + timedelta(minutes=i),
            )
        logs = crud.get_audit_logs(seeded_db, skip=0, limit=3)
        assert [log.step_id for log in logs] == [
            "GOV-STANDARD-UPDATE-00005",
            "GOV-STANDARD-UPDATE-00004",
            "GOV-STANDARD-UPDATE-00003",
        ]
        assert len(crud.get_audit_logs(seeded_db, skip=3, limit=3)) == 2

    def test_audit_log_details_json_roundtrip(self, seeded_db):
        log = crud.create_audit_log(
            seeded_db,
            step_id="GOV-QUALITY-RUN-00001",
            step_name=models.StepName.QUALITY_RUN,
            step_label="执行质量检测",
            executed_by="admin001",
            executed_by_name="王管理员",
            status="success",
            details={"batch_id": "b-1", "checked": 20, "failed": 4},
        )
        stored = seeded_db.query(models.AuditLog).filter(models.AuditLog.id == log.id).first()
        assert stored.details["failed"] == 4
