"""数据标准 API 验收：权限矩阵 + 审计 + 删除引用保护（SPEC §3.0 / §3.1）。"""
import pytest
from fastapi.testclient import TestClient

from app import models
from app.main import app

BASE = "/api/data-standards"

NEW_STANDARD = {
    "entity_type": "material",
    "sap_table": "MARA",
    "field_name": "MEINS",
    "field_label": "基本计量单位",
    "data_type": "enum",
    "enum_values": ["PC", "KG", "M"],
    "required": True,
    "standard_source": "sap",
    "owner": "钱数据",
}


@pytest.fixture(scope="function")
def anonymous_client(seeded_db):
    return TestClient(app)


def _standard_id(db, field_name: str) -> str:
    return (
        db.query(models.DataStandard)
        .filter(models.DataStandard.field_name == field_name)
        .first()
        .id
    )


class TestReadAccess:
    def test_anonymous_request_is_rejected(self, anonymous_client):
        assert anonymous_client.get(BASE).status_code == 401

    def test_invalid_token_is_rejected(self, seeded_db):
        client = TestClient(app)
        client.headers.update({"Authorization": "Bearer not-a-real-token"})
        assert client.get(BASE).status_code == 401

    @pytest.mark.parametrize("fixture_name", ["client", "dept_client", "data_client"])
    def test_every_role_can_read(self, request, fixture_name):
        client = request.getfixturevalue(fixture_name)
        body = client.get(BASE).json()
        assert client.get(BASE).status_code == 200
        assert body["total"] == 2

    def test_filters_are_applied(self, client):
        body = client.get(BASE, params={"entity_type": "supplier"}).json()
        assert [i["field_name"] for i in body["items"]] == ["LIFNR"]
        assert client.get(BASE, params={"sap_table": "MARM"}).json()["total"] == 0


class TestWritePermissions:
    @pytest.mark.parametrize("fixture_name", ["client", "dept_client"])
    def test_non_admin_writes_are_forbidden(self, request, fixture_name):
        client = request.getfixturevalue(fixture_name)
        assert client.post(BASE, json=NEW_STANDARD).status_code == 403
        assert client.put(f"{BASE}/any-id", json={"field_label": "x"}).status_code == 403
        assert client.delete(f"{BASE}/any-id").status_code == 403

    def test_admin_role_can_write(self, seeded_db, db):
        from app.core.auth import create_access_token

        client = TestClient(app)
        client.headers.update(
            {"Authorization": f"Bearer {create_access_token({'sub': 'admin001', 'role': 'admin'})}"}
        )
        assert client.post(BASE, json=NEW_STANDARD).status_code == 201


class TestCreate:
    def test_create_persists_management_attributes(self, data_client, seeded_db):
        body = data_client.post(BASE, json=NEW_STANDARD).json()
        assert body["id"]
        assert body["enum_values"] == ["PC", "KG", "M"]
        assert body["owner"] == "钱数据"
        assert body["standard_source"] == "sap"

    def test_create_conflict_returns_409(self, data_client, seeded_db):
        payload = dict(NEW_STANDARD, field_name="MATNR")
        assert data_client.post(BASE, json=payload).status_code == 409

    def test_create_rejects_unknown_entity_type(self, data_client, seeded_db):
        payload = dict(NEW_STANDARD, entity_type="equipment")
        assert data_client.post(BASE, json=payload).status_code == 422

    def test_create_is_audited(self, data_client, seeded_db):
        standard_id = data_client.post(BASE, json=NEW_STANDARD).json()["id"]
        log = (
            seeded_db.query(models.AuditLog)
            .filter(models.AuditLog.step_name == models.StepName.STANDARD_CREATE.value)
            .one()
        )
        assert log.details["standard_id"] == standard_id
        assert log.executed_by == "data001"
        assert log.executed_by_name == "钱数据"
        assert log.status == "success"


class TestUpdate:
    def test_update_persists_and_audits(self, data_client, seeded_db):
        standard_id = _standard_id(seeded_db, "MATNR")
        resp = data_client.put(f"{BASE}/{standard_id}", json={"max_length": 40, "description": "18 位物料号"})
        assert resp.status_code == 200
        assert resp.json()["max_length"] == 40

        standard = seeded_db.get(models.DataStandard, standard_id)
        assert standard.description == "18 位物料号"
        log = (
            seeded_db.query(models.AuditLog)
            .filter(models.AuditLog.step_name == models.StepName.STANDARD_UPDATE.value)
            .one()
        )
        assert log.details["fields"] == ["description", "max_length"]

    def test_update_empty_body_returns_400(self, data_client, seeded_db):
        standard_id = _standard_id(seeded_db, "MATNR")
        assert data_client.put(f"{BASE}/{standard_id}", json={}).status_code == 400

    def test_update_unknown_id_returns_404(self, data_client, seeded_db):
        assert data_client.put(f"{BASE}/missing", json={"field_label": "x"}).status_code == 404

    def test_identity_keys_are_not_updatable(self, data_client, seeded_db):
        standard_id = _standard_id(seeded_db, "MATNR")
        resp = data_client.put(
            f"{BASE}/{standard_id}",
            json={"field_label": "物料号", "field_name": "MATNR2", "entity_type": "supplier"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["field_label"] == "物料号"
        assert body["field_name"] == "MATNR"
        assert body["entity_type"] == "material"


class TestDelete:
    def test_delete_unreferenced_standard(self, data_client, seeded_db):
        standard_id = _standard_id(seeded_db, "LIFNR")
        assert data_client.delete(f"{BASE}/{standard_id}").status_code == 204
        assert seeded_db.get(models.DataStandard, standard_id) is None
        log = (
            seeded_db.query(models.AuditLog)
            .filter(models.AuditLog.step_name == models.StepName.STANDARD_DELETE.value)
            .one()
        )
        assert log.details["standard_id"] == standard_id

    def test_delete_referenced_by_rule_returns_409(self, data_client, seeded_db):
        standard_id = _standard_id(seeded_db, "MATNR")
        seeded_db.add(models.QualityCheckRule(
            name="物料编码非空",
            entity_type="material",
            rule_type=models.RuleType.NULL_CHECK.value,
            field_name="MATNR",
            rule_config={},
            standard_id=standard_id,
        ))
        seeded_db.commit()

        assert data_client.delete(f"{BASE}/{standard_id}").status_code == 409
        assert seeded_db.get(models.DataStandard, standard_id) is not None

    def test_delete_unknown_id_returns_404(self, data_client, seeded_db):
        assert data_client.delete(f"{BASE}/missing").status_code == 404
