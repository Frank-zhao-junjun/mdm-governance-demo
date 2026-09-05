"""存量记录字段修正 API 测试（字段治理闭环·修复环节）。

护栏矩阵：权限 403 / 记录 404（含实体隔离）/ 未治理字段 400（含无数据源
字段）/ 必填清空 400 / 身份列清空 400 / pattern 400 / 唯一冲突 409 /
attributes 整体赋值 + 审计 / 列镜像 / 大小写不敏感 / 数值类型保留 /
修复→重跑→最新批次失败归零（e2e 核心，旧批次留档）。
"""
import pytest
from fastapi.testclient import TestClient

from app import models
from app.main import app
from app.services import record_fixer
from app.services.rule_derivation import derive_rule_rows

FIX = "/api/records"


@pytest.fixture(scope="function")
def fix_db(seeded_db):
    """seeded（MATNR/LIFNR 标准 + 干净记录）+ 修正护栏用标准与脏记录。"""
    db = seeded_db
    db.add_all([
        models.DataStandard(
            entity_type="material", sap_table="MARA", field_name="MEINS",
            field_label="基本计量单位", data_type="enum", required=True,
            enum_values=["KG", "G", "PC"], owner="钱数据", standard_source="sap",
        ),
        models.DataStandard(
            entity_type="material", sap_table="MARA", field_name="MTART",
            field_label="物料类型", data_type="enum",
            enum_values=["ROH", "FERT", "VERP"], owner="钱数据", standard_source="sap",
        ),
        models.DataStandard(
            entity_type="material", sap_table="MARA", field_name="GEWEI",
            field_label="重量单位", data_type="number", required=False,
            owner="钱数据", standard_source="sap",
        ),
        models.DataStandard(
            entity_type="material", sap_table="MAKT", field_name="MAKTX",
            field_label="物料描述", data_type="string", owner="钱数据", standard_source="sap",
        ),
        models.DataStandard(
            entity_type="material", sap_table="MARC", field_name="WERKS",
            field_label="工厂", data_type="string", required=True,
            owner="钱数据", standard_source="sap",
        ),
        models.DataStandard(
            entity_type="customer", sap_table="KNA1", field_name="KUNNR",
            field_label="客户编码", data_type="string", required=True,
            pattern=r"^[0-9]{10}$", unique=True, owner="钱数据", standard_source="sap",
        ),
    ])
    # 脏记录：M1234（编码格式错 + 缺 MEINS）；12345（编码短）；customer 干净
    db.add(models.MaterialRecord(
        material_code="M1234", material_name="六角螺栓 M8x30 热镀锌",
        attributes={"MTART": "ROH", "GEWEI": 0.5},
    ))
    db.add(models.PartnerRecord(
        entity_type="supplier", partner_code="12345", partner_name="杭州轴承试验中心",
        attributes={"CITY1": "杭州"},
    ))
    db.add(models.PartnerRecord(
        entity_type="customer", partner_code="2000000017", partner_name="示范客户股份公司",
        attributes={"CITY1": "上海"},
    ))
    db.commit()
    yield db


def _material_id(db, code):
    return (
        db.query(models.MaterialRecord)
        .filter(models.MaterialRecord.material_code == code)
        .first()
        .id
    )


def _partner_id(db, entity_type, code):
    return (
        db.query(models.PartnerRecord)
        .filter(
            models.PartnerRecord.entity_type == entity_type,
            models.PartnerRecord.partner_code == code,
        )
        .first()
        .id
    )


def _fix(client, entity_type, record_id, field_name, value=None):
    return client.post(
        f"{FIX}/{entity_type}/{record_id}/fix",
        json={"field_name": field_name, "value": value},
    )


# ========== 权限与定位 ==========

class TestPermissions:
    @pytest.mark.parametrize("fixture_name", ["client", "dept_client"])
    def test_non_admin_fix_is_forbidden(self, request, fixture_name, fix_db):
        client = request.getfixturevalue(fixture_name)
        m = _material_id(fix_db, "M1234")
        assert _fix(client, "material", m, "MATNR", "M10234").status_code == 403

    def test_data_admin_can_fix(self, data_client, fix_db):
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "MATNR", "M10234")
        assert resp.status_code == 200, resp.text


class TestRecordLookup:
    def test_unknown_record_returns_404(self, data_client, fix_db):
        resp = _fix(data_client, "material", "no-such-id", "MATNR", "M10234")
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]

    def test_unknown_entity_type_returns_404(self, data_client, fix_db):
        resp = _fix(data_client, "machine", "any-id", "ZZ", "x")
        assert resp.status_code == 404

    def test_entity_isolation_between_supplier_and_customer(self, data_client, fix_db):
        """supplier 记录 id 走 customer 路径 → 404（entity_type 参与定位）。"""
        sid = _partner_id(fix_db, "supplier", "12345")
        resp = _fix(data_client, "customer", sid, "KUNNR", "2000000018")
        assert resp.status_code == 404


# ========== 护栏 ==========

class TestGuardrails:
    def test_unregistered_field_returns_400(self, data_client, fix_db):
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "ZZFIELD", "x")
        assert resp.status_code == 400
        assert "未纳入" in resp.json()["detail"]

    def test_no_source_field_returns_400(self, data_client, fix_db):
        """WERKS 已登记标准但本系统无数据源（NO_SOURCE_FIELDS）→ 拒绝修正。"""
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "WERKS", "1000")
        assert resp.status_code == 400
        assert "无数据源" in resp.json()["detail"]

    def test_clearing_required_column_field_returns_400(self, data_client, fix_db):
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "MATNR", None)
        assert resp.status_code == 400
        assert "必填字段" in resp.json()["detail"]

    def test_clearing_required_attributes_field_returns_400(self, data_client, fix_db):
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "MEINS", "")
        assert resp.status_code == 400
        assert "必填字段" in resp.json()["detail"]

    def test_clearing_identity_column_returns_400(self, data_client, fix_db):
        """MAKTX 非必填但落 material_name NOT NULL 列 → 禁清空，只许改填。"""
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "MAKTX", None)
        assert resp.status_code == 400
        assert "身份列" in resp.json()["detail"]

    def test_pattern_violation_returns_400(self, data_client, fix_db):
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "MATNR", "M-123")
        assert resp.status_code == 400
        assert "格式" in resp.json()["detail"]

    def test_code_conflict_returns_409_and_keeps_db(self, data_client, fix_db):
        """新编码撞 M10001 → 409；库中记录不被污染（仍 M1234）。"""
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "MATNR", "M10001")
        assert resp.status_code == 409
        assert "唯一" in resp.json()["detail"]
        assert fix_db.get(models.MaterialRecord, m).material_code == "M1234"

    def test_partner_code_conflict_isolated_by_entity_type(self, data_client, fix_db):
        """partner_code 唯一域是 (entity_type, code)：customer 可复用 supplier 的码。"""
        c = _partner_id(fix_db, "customer", "2000000017")
        resp = _fix(data_client, "customer", c, "KUNNR", "1000000001")
        assert resp.status_code == 200, resp.text
        assert fix_db.get(models.PartnerRecord, c).partner_code == "1000000001"


# ========== 成功修正 ==========

class TestFixSuccess:
    def test_fix_attributes_field_writes_whole_dict(self, data_client, fix_db):
        """MEINS 补值 → attributes 键存在；其余键不受影响（整体赋值语义）。"""
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "MEINS", "KG")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["record_id"] == m
        assert body["field_name"] == "MEINS"
        assert body["old_value"] is None
        assert body["new_value"] == "KG"

        record = fix_db.get(models.MaterialRecord, m)
        assert record.attributes["MEINS"] == "KG"
        assert record.attributes["MTART"] == "ROH"  # 无关键不被清掉

    def test_fix_column_field_mirrors_material_code(self, data_client, fix_db):
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "MATNR", "M10234")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["field_name"] == "MATNR"
        assert body["old_value"] == "M1234"
        assert body["new_value"] == "M10234"
        assert fix_db.get(models.MaterialRecord, m).material_code == "M10234"

    def test_fix_field_name_case_insensitive(self, data_client, fix_db):
        """请求 matnr 小写 → 以标准登记名规范化返回 MATNR。"""
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "matnr", "M10234")
        assert resp.status_code == 200, resp.text
        assert resp.json()["field_name"] == "MATNR"

    def test_fix_strips_surrounding_whitespace(self, data_client, fix_db):
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "MATNR", "  M10234  ")
        assert resp.status_code == 200, resp.text
        assert fix_db.get(models.MaterialRecord, m).material_code == "M10234"

    def test_fix_partner_column_mirrors_partner_code(self, data_client, fix_db):
        s = _partner_id(fix_db, "supplier", "12345")
        resp = _fix(data_client, "supplier", s, "LIFNR", "1000000012")
        assert resp.status_code == 200, resp.text
        assert fix_db.get(models.PartnerRecord, s).partner_code == "1000000012"

    def test_fix_customer_column(self, data_client, fix_db):
        c = _partner_id(fix_db, "customer", "2000000017")
        resp = _fix(data_client, "customer", c, "KUNNR", "2000000018")
        assert resp.status_code == 200, resp.text
        assert fix_db.get(models.PartnerRecord, c).partner_code == "2000000018"

    def test_numeric_value_keeps_type(self, data_client, fix_db):
        """GEWEI（number）修 12.5 → JSON 中仍为 float，不被字符串化。"""
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "GEWEI", 12.5)
        assert resp.status_code == 200, resp.text
        value = fix_db.get(models.MaterialRecord, m).attributes["GEWEI"]
        assert value == 12.5
        assert isinstance(value, float)

    def test_clearing_optional_attribute_deletes_key(self, data_client, fix_db):
        """MTART 非必填 attributes 字段清空 → 键被移除，new_value 回显 None。"""
        m = _material_id(fix_db, "M1234")
        resp = _fix(data_client, "material", m, "MTART", None)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["old_value"] == "ROH"
        assert body["new_value"] is None
        assert "MTART" not in fix_db.get(models.MaterialRecord, m).attributes

    def test_fix_writes_audit_log(self, data_client, fix_db):
        m = _material_id(fix_db, "M1234")
        _fix(data_client, "material", m, "MEINS", "KG")
        log = fix_db.query(models.AuditLog).filter(
            models.AuditLog.step_name == models.StepName.RECORD_FIELD_UPDATE
        ).one()
        assert log.executed_by == "data001"
        assert log.details["record_id"] == m
        assert log.details["field_name"] == "MEINS"
        assert log.details["old_value"] is None
        assert log.details["new_value"] == "KG"


# ========== 闭环 e2e：修复 → 重跑 → 最新批次失败归零 ==========

class TestGovernanceLoop:
    def _derive_and_run(self, db, data_client):
        """派生全部规则并跑一次 material 检测，返回 batch_id。"""
        standards = db.query(models.DataStandard).all()
        db.add_all(derive_rule_rows(standards))
        db.commit()
        resp = data_client.post(
            "/api/quality-checks/run", json={"entity_type": "material"}
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["batch_id"]

    def _failed_field_names(self, db, batch_id):
        return {
            r.field_name
            for r in db.query(models.QualityCheckResult).filter(
                models.QualityCheckResult.batch_id == batch_id
            ).all()
        }

    def test_fix_then_rerun_zeroes_latest_batch_keeps_history(self, data_client, fix_db):
        db = fix_db
        # run#1：M1234 的 MATNR 格式错 + MEINS 缺失 → 两字段失败（基线）
        batch1 = self._derive_and_run(db, data_client)
        assert {"MATNR", "MEINS"} <= self._failed_field_names(db, batch1)
        assert db.query(models.QualityCheckBatch).count() == 1

        # 修复两条问题（编码改合法 + 补必填计量单位）
        m = _material_id(db, "M1234")
        assert _fix(data_client, "material", m, "MATNR", "M10234").status_code == 200
        assert _fix(data_client, "material", m, "MEINS", "KG").status_code == 200

        # run#2：最新批次 MATNR/MEINS 失败归零，且旧批次仍留档（证据链保留）
        resp = data_client.post(
            "/api/quality-checks/run", json={"entity_type": "material"}
        )
        batch2 = resp.json()["batch_id"]
        assert batch2 != batch1
        assert db.query(models.QualityCheckBatch).count() == 2
        assert "MATNR" not in self._failed_field_names(db, batch2)
        assert "MEINS" not in self._failed_field_names(db, batch2)
        # 旧批次失败行不因重跑被清理（历史留档）
        assert "MATNR" in self._failed_field_names(db, batch1)

    def test_field_results_filter_by_field_name(self, data_client, fix_db):
        """GET /results 的 field_name 过滤：新 API 透传生效（供检测页单字段视图）。"""
        batch1 = self._derive_and_run(db=fix_db, data_client=data_client)
        matnr = data_client.get(
            "/api/quality-checks/results",
            params={"entity_type": "material", "batch_id": batch1, "field_name": "MATNR"},
        ).json()
        assert matnr["total"] > 0
        assert {i["field_name"] for i in matnr["items"]} == {"MATNR"}
        meins = data_client.get(
            "/api/quality-checks/results",
            params={"entity_type": "material", "batch_id": batch1, "field_name": "MEINS"},
        ).json()
        assert {i["field_name"] for i in meins["items"]} == {"MEINS"}
