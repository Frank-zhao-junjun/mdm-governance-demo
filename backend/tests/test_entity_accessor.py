"""字段访问层测试（SPEC §4、§10 附录字段映射）。

覆盖三类实体的列映射、attributes 取值、"缺键≠无数据源"与"无数据源必须跳过"
三种语义，以及 EntityFieldAccessor 的取实体行为。
"""
import pytest

from app import models
from app.services import entity_accessor as ea


# ========== 列映射 ==========

class TestColumnMapping:
    def test_matnr_and_maktx_come_from_redundant_columns(self, seeded_db):
        record = seeded_db.query(models.MaterialRecord).one()

        matnr = ea.resolve("material", record, "MATNR")
        maktx = ea.resolve("material", record, "MAKTX")

        assert matnr.value == "M10001"
        assert matnr.source_kind == "column"
        assert matnr.source.column == "material_code"
        assert maktx.value == "六角螺栓 M8×30 镀锌"
        assert maktx.source.column == "material_name"
        assert maktx.skipped is False

    def test_supplier_lifnr_and_name1_come_from_partner_columns(self, seeded_db):
        record = seeded_db.query(models.PartnerRecord).one()

        assert ea.resolve("supplier", record, "LIFNR").value == "1000000001"
        assert ea.resolve("supplier", record, "LIFNR").source.column == "partner_code"
        assert ea.resolve("supplier", record, "NAME1").value == "华成精密机械有限公司"
        assert ea.resolve("supplier", record, "NAME1").source.column == "partner_name"

    def test_customer_kunnr_and_bp_partner_number_map_to_partner_code(self, seeded_db):
        seeded_db.add(models.PartnerRecord(
            entity_type="customer",
            partner_code="2000000001",
            partner_name="测试客户",
            attributes={},
        ))
        seeded_db.commit()
        record = seeded_db.query(models.PartnerRecord).filter(
            models.PartnerRecord.entity_type == "customer"
        ).one()

        assert ea.resolve("customer", record, "KUNNR").value == "2000000001"
        assert ea.resolve("customer", record, "PARTNER").value == "2000000001"

    def test_mapped_column_wins_over_attributes_copy(self, db):
        """冗余列是 SPEC 声明的数据源，attributes 里的同名键不参与取值。"""
        record = models.MaterialRecord(
            material_code="M10002",
            material_name="垫片",
            attributes={"MATNR": "DIRTY", "MAKTX": "脏描述"},
        )
        db.add(record)
        db.commit()

        assert ea.resolve("material", record, "MATNR").value == "M10002"
        assert ea.resolve("material", record, "MAKTX").value == "垫片"

    def test_field_name_match_is_case_insensitive(self, seeded_db):
        record = seeded_db.query(models.MaterialRecord).one()
        assert ea.resolve("material", record, "matnr").value == "M10001"
        # 回显仍用调用方传入的字段名，便于与标准对齐
        assert ea.resolve("material", record, "matnr").field_name == "matnr"


# ========== attributes 取值 ==========

class TestAttributesSourced:
    def test_attribute_key_is_read(self, seeded_db):
        record = seeded_db.query(models.MaterialRecord).one()
        meins = ea.resolve("material", record, "MEINS")

        assert meins.value == "PC"
        assert meins.source_kind == "attributes"
        assert meins.key_present is True
        assert meins.skipped is False

    def test_missing_key_is_absent_value_not_skipped(self, seeded_db):
        """attributes 就是数据源；本行没有这个键属于"未填"，可被 null 规则判失败。"""
        record = seeded_db.query(models.MaterialRecord).one()
        matkl = ea.resolve("material", record, "MATKL")

        assert matkl.skipped is False
        assert matkl.key_present is False
        assert matkl.value is None
        assert matkl.is_blank is True

    def test_whitespace_value_is_present_but_blank(self, seeded_db):
        record = seeded_db.query(models.PartnerRecord).one()
        city = ea.resolve("supplier", record, "CITY1")
        assert city.value == "上海"
        assert city.is_blank is False

        record.attributes["CITY1"] = "   "
        blank = ea.resolve("supplier", record, "CITY1")
        assert blank.key_present is True
        assert blank.is_blank is True

    def test_zero_and_false_are_not_blank(self, db):
        record = models.MaterialRecord(
            material_code="M10003", material_name="钢丝", attributes={"BRGEW": 0, "FLAG": False}
        )
        db.add(record)
        db.commit()

        brgew = ea.resolve("material", record, "BRGEW")
        flag = ea.resolve("material", record, "FLAG")
        assert brgew.key_present is True and brgew.is_blank is False
        assert flag.value is False and flag.is_blank is False

    def test_null_attributes_dict_is_tolerated(self, db):
        record = models.MaterialRecord(material_code="M10004", material_name="螺栓")
        record.attributes = None
        db.add(record)
        db.commit()

        result = ea.resolve("material", record, "MEINS")
        assert result.source_kind == "attributes"
        assert result.key_present is False


# ========== 无数据源：必须跳过 ==========

@pytest.mark.parametrize("field_name", ["WERKS", "EKGRP", "DISMM", "LGORT", "SPRAS"])
def test_sap_view_fields_have_no_data_source_and_are_skipped(field_name, seeded_db):
    record = seeded_db.query(models.MaterialRecord).one()
    result = ea.resolve("material", record, field_name)

    assert result.skipped is True
    assert result.source_kind == "none"
    assert result.value is None
    assert "无数据源" in result.reason
    # 跳过态不得被误读成"值为空"
    assert result.key_present is False


def test_no_source_registry_wins_over_attributes_content(seeded_db):
    """登记为无数据源的字段即使 attributes 里出现同名键也仍跳过（要改就改登记表）。"""
    record = seeded_db.query(models.MaterialRecord).one()
    record.attributes = {"WERKS": "1000"}
    assert ea.resolve("material", record, "WERKS").skipped is True
    assert ea.supports_field("material", "WERKS") is False


def test_unknown_entity_type_has_no_data_source():
    source = ea.describe_source("plant", "WERKS")
    assert source.available is False
    assert "未定义该实体类型" in source.reason


def test_empty_field_name_is_skipped():
    assert ea.describe_source("material", "  ").available is False
    assert ea.describe_source("material", None).available is False


# ========== 实体类型推断与标签 ==========

class TestRecordHelpers:
    def test_entity_type_inference(self, seeded_db):
        material = seeded_db.query(models.MaterialRecord).one()
        partner = seeded_db.query(models.PartnerRecord).one()
        assert ea.entity_type_of(material) == "material"
        assert ea.entity_type_of(partner) == "supplier"

    def test_read_value_infers_entity_type(self, seeded_db):
        record = seeded_db.query(models.MaterialRecord).one()
        assert ea.read_value(record, "MATNR").value == "M10001"

    def test_record_label_uses_code_then_id(self, seeded_db):
        material = seeded_db.query(models.MaterialRecord).one()
        partner = seeded_db.query(models.PartnerRecord).one()
        assert ea.record_label(material) == "M10001"
        assert ea.record_label(partner) == "1000000001"
        assert ea.record_id(material) == material.id

    def test_display_value_truncates_to_column_width(self):
        assert ea.display_value("x" * 600) == "x" * 500
        assert ea.display_value(None) == ""
        assert ea.display_value(12.5) == "12.5"


# ========== Accessor 取实体 ==========

class TestEntityFieldAccessor:
    def test_list_entities_per_entity_type(self, seeded_db):
        accessor = ea.EntityFieldAccessor(seeded_db)
        assert [r.material_code for r in accessor.list_entities("material")] == ["M10001"]
        assert [r.partner_code for r in accessor.list_entities("supplier")] == ["1000000001"]
        assert accessor.list_entities("customer") == []

    def test_list_entities_respects_ids_and_limit(self, seeded_db):
        for i in range(2, 10):
            seeded_db.add(models.MaterialRecord(
                material_code=f"M100{i:02d}", material_name=f"物料{i}", attributes={}
            ))
        seeded_db.commit()
        accessor = ea.EntityFieldAccessor(seeded_db)

        first = accessor.list_entities("material")[0]
        picked = accessor.list_entities("material", entity_ids=[first.id])
        assert [r.id for r in picked] == [first.id]
        assert len(accessor.list_entities("material", limit=3)) == 3
        # §5.2 同步上限：limit 不得越过 MAX_ENTITIES
        assert len(accessor.list_entities("material", limit=999999)) == 9

    def test_list_entities_rejects_unknown_entity_type(self, seeded_db):
        with pytest.raises(ValueError):
            ea.EntityFieldAccessor(seeded_db).list_entities("plant")

    def test_get_field_returns_plain_value(self, seeded_db):
        accessor = ea.EntityFieldAccessor(seeded_db)
        material_id = accessor.list_entities("material")[0].id
        partner_id = accessor.list_entities("supplier")[0].id

        assert accessor.get_field("material", material_id, "MATNR") == "M10001"
        assert accessor.get_field("supplier", partner_id, "ZTERM") == "0010"
        # 无数据源 / 未填 / 记录不存在都回 None（需要区分时用 get_value）
        assert accessor.get_field("material", material_id, "WERKS") is None
        assert accessor.get_field("material", material_id, "MATKL") is None
        assert accessor.get_field("material", "no-such-id", "MATNR") is None

    def test_get_value_keeps_skip_distinction(self, seeded_db):
        accessor = ea.EntityFieldAccessor(seeded_db)
        record = accessor.list_entities("material")[0]

        assert accessor.get_value("material", record, "MATNR").skipped is False
        assert accessor.get_value("material", record, "LGORT").skipped is True
        assert accessor.supports_field("material", "MEINS") is True

    def test_list_standards_reads_seeded_standards(self, seeded_db):
        standards = ea.EntityFieldAccessor(seeded_db).list_standards(entity_type="material")
        assert [s.field_name for s in standards] == ["MATNR"]

    def test_accessor_does_not_write_to_session(self, seeded_db):
        accessor = ea.EntityFieldAccessor(seeded_db)
        record = accessor.list_entities("material")[0]
        accessor.get_value("material", record, "MEINS")
        accessor.get_field("supplier", accessor.list_entities("supplier")[0].id, "CITY1")

        assert len(seeded_db.new) == 0
        assert len(seeded_db.dirty) == 0
