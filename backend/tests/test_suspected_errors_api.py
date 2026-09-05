"""疑似错误 API 测试（SPEC §3.3 + Phase 3 验收：权限矩阵 / 审计 / 状态流转）。"""
import pytest
from fastapi.testclient import TestClient

from app import models
from app.main import app


@pytest.fixture(scope="function")
def api_db(seeded_db):
    """seeded_db + 近似重复（M1234↔M10001）+ naming 违例（M10021）+ 重名供应商对。"""
    db = seeded_db
    db.add(models.MaterialRecord(
        material_code="M1234", material_name="六角螺栓 M8x30 热镀锌",
        attributes={"MTART": "ROH"}, status="active",
    ))
    db.add(models.MaterialRecord(
        material_code="M10021", material_name="测试物料 待补充",
        attributes={"MTART": "ROH"}, status="active",
    ))
    db.add(models.PartnerRecord(
        entity_type="supplier", partner_code="1000000008",
        partner_name="广州密封件工业公司", attributes={}, status="active",
    ))
    db.add(models.PartnerRecord(
        entity_type="supplier", partner_code="1000000019",
        partner_name="广州密封件工业公司", attributes={}, status="active",
    ))
    db.commit()
    return db


def _detect(data_client, entity_type="material", **body_overrides):
    body = {"entity_type": entity_type, **body_overrides}
    return data_client.post("/api/suspected-errors/detect", json=body)


def _first_error_id(db, error_type="duplicate"):
    row = (
        db.query(models.SuspectedError)
        .filter(models.SuspectedError.error_type == error_type)
        .first()
    )
    return row.id


# ========== POST /detect ==========

def test_detect_creates_pending_rows(api_db, data_client):
    db = api_db
    resp = _detect(data_client)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"created", "refreshed", "skipped_false_positive", "auto_closed", "total_pending"}
    # material：M1234↔M10001 近重复 1 + M10021 命名违例 1
    assert body["created"] == 2
    assert body["total_pending"] == 2

    rows = db.query(models.SuspectedError).filter(
        models.SuspectedError.entity_type == "material"
    ).all()
    assert {r.error_type for r in rows} == {"duplicate", "naming"}
    assert all(r.status == "pending" for r in rows)
    assert all(r.detected_by == "data001" for r in rows)  # detected_by 取 JWT 用户


def test_detect_entity_ids_scope(api_db, data_client):
    """作用域收窄到重复对两条实体：只检出 duplicate，naming 违例不在作用域。"""
    db = api_db
    ids = [
        r.id
        for r in db.query(models.MaterialRecord).filter(
            models.MaterialRecord.material_code.in_(["M10001", "M1234"])
        )
    ]
    resp = _detect(data_client, entity_ids=ids)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1  # 只命中 M1234↔M10001 近似对，无 naming
    rows = db.query(models.SuspectedError).all()
    assert len(rows) == 1
    assert rows[0].error_type == "duplicate"


def test_detect_permission_denied(api_db, client, dept_client):
    assert client.post("/api/suspected-errors/detect", json={"entity_type": "material"}).status_code == 403
    assert dept_client.post("/api/suspected-errors/detect", json={"entity_type": "material"}).status_code == 403
    assert TestClient(app).post("/api/suspected-errors/detect", json={"entity_type": "material"}).status_code == 401


def test_detect_invalid_entity_type(api_db, data_client):
    assert _detect(data_client, entity_type="foo").status_code == 422


def test_detect_unsupported_error_type(api_db, data_client):
    resp = _detect(data_client, error_types=["classification"])
    assert resp.status_code == 400
    assert "classification" in resp.json()["detail"]
    # 校验前置：未落任何行
    assert db_row_count(api_db) == 0


def test_detect_audit_logged(api_db, data_client):
    resp = _detect(data_client)
    assert resp.status_code == 200
    audit = (
        api_db.query(models.AuditLog)
        .filter(models.AuditLog.step_name == models.StepName.ERROR_DETECT.value)
        .first()
    )
    assert audit is not None
    assert audit.executed_by == "data001"
    assert audit.step_label == "执行疑似错误检测"
    assert audit.details["entity_type"] == "material"
    assert audit.details["scope"] == "all"
    assert audit.details["created"] == resp.json()["created"]


# ========== GET /（列表）==========

def test_list_requires_entity_type(api_db, data_client):
    assert data_client.get("/api/suspected-errors/").status_code == 422


def test_list_filters_and_order(api_db, data_client):
    _detect(data_client)
    resp = data_client.get("/api/suspected-errors/?entity_type=material")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2

    naming = data_client.get(
        "/api/suspected-errors/?entity_type=material&error_type=naming"
    ).json()
    assert naming["total"] == 1
    assert naming["items"][0]["error_type"] == "naming"
    assert naming["items"][0]["matched_entity_id"] is None

    confirmed = data_client.get(
        "/api/suspected-errors/?entity_type=material&status=confirmed"
    ).json()
    assert confirmed["total"] == 0

    # 分页
    page = data_client.get(
        "/api/suspected-errors/?entity_type=material&skip=1&limit=1"
    ).json()
    assert page["total"] == 2 and len(page["items"]) == 1


def test_list_accessible_to_all_roles(api_db, client, dept_client, data_client):
    _detect(data_client)
    for c in (client, dept_client, data_client):
        resp = c.get("/api/suspected-errors/?entity_type=material")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2


# ========== POST /{id}/resolve ==========

def test_resolve_confirmed(api_db, data_client):
    db = api_db
    _detect(data_client)
    error_id = _first_error_id(db)

    resp = data_client.post(
        f"/api/suspected-errors/{error_id}/resolve",
        json={"status": "confirmed", "resolution_note": "确认为重复，合并处理"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "confirmed"
    assert body["resolved_by"] == "data001"  # resolved_by 取 JWT，不接受请求体传入
    assert body["resolved_at"] is not None
    assert body["resolution_note"] == "确认为重复，合并处理"

    row = db.query(models.SuspectedError).filter(
        models.SuspectedError.id == error_id
    ).first()
    assert row.status == "confirmed"
    assert row.resolved_by == "data001"


@pytest.mark.parametrize("status", ["resolved", "false_positive"])
def test_resolve_other_statuses(api_db, data_client, status):
    db = api_db
    _detect(data_client)
    error_id = _first_error_id(db)
    resp = data_client.post(
        f"/api/suspected-errors/{error_id}/resolve",
        json={"status": status},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == status
    row = db.query(models.SuspectedError).filter(
        models.SuspectedError.id == error_id
    ).first()
    assert row.status == status
    assert row.resolved_at is not None


def test_resolve_404(api_db, data_client):
    resp = data_client.post(
        "/api/suspected-errors/no-such-id/resolve",
        json={"status": "confirmed"},
    )
    assert resp.status_code == 404


def test_resolve_invalid_status(api_db, data_client):
    _detect(data_client)
    error_id = _first_error_id(api_db)
    # pending 不在三值集合内 → 422
    resp = data_client.post(
        f"/api/suspected-errors/{error_id}/resolve",
        json={"status": "pending"},
    )
    assert resp.status_code == 422


def test_resolve_permission_denied(api_db, client, dept_client, data_client):
    _detect(data_client)
    error_id = _first_error_id(api_db)
    assert client.post(f"/api/suspected-errors/{error_id}/resolve", json={"status": "confirmed"}).status_code == 403
    assert dept_client.post(f"/api/suspected-errors/{error_id}/resolve", json={"status": "confirmed"}).status_code == 403
    assert TestClient(app).post(f"/api/suspected-errors/{error_id}/resolve", json={"status": "confirmed"}).status_code == 401


def test_resolve_audit_logged(api_db, data_client):
    db = api_db
    _detect(data_client)
    error_id = _first_error_id(db)
    resp = data_client.post(
        f"/api/suspected-errors/{error_id}/resolve",
        json={"status": "confirmed", "resolution_note": "核实无误"},
    )
    assert resp.status_code == 200

    audit = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.step_name == models.StepName.ERROR_RESOLVE.value)
        .first()
    )
    assert audit is not None
    assert audit.executed_by == "data001"
    assert audit.step_label == "处理疑似错误"
    assert audit.details["from_status"] == "pending"
    assert audit.details["to_status"] == "confirmed"
    assert audit.details["suspected_error_id"] == error_id
    assert audit.details["note"] == "核实无误"


# ========== 端到端闭环（§2.7 重检去重 + 状态流转）==========

def test_rerun_no_duplicate_pending(api_db, data_client):
    """硬性验收：重跑不产生重复 pending。"""
    db = api_db
    first = _detect(data_client).json()
    second = _detect(data_client).json()
    assert second["created"] == 0
    assert second["refreshed"] == first["created"]
    assert second["total_pending"] == first["total_pending"]
    assert db_row_count(db) == first["created"]


def test_false_positive_whitelist_on_rerun(api_db, data_client):
    """误报白名单：resolve false_positive 后重跑，该键跳过并计数。"""
    db = api_db
    _detect(data_client)
    error_id = _first_error_id(db, "duplicate")
    assert data_client.post(
        f"/api/suspected-errors/{error_id}/resolve",
        json={"status": "false_positive", "resolution_note": "人工判定为误报"},
    ).status_code == 200

    rerun = _detect(data_client).json()
    assert rerun["skipped_false_positive"] == 1
    assert rerun["created"] == 0
    assert rerun["refreshed"] == 1  # 仅 naming 行刷新
    row = db.query(models.SuspectedError).filter(
        models.SuspectedError.id == error_id
    ).first()
    assert row.status == "false_positive"
    assert row.resolution_note == "人工判定为误报"


def db_row_count(db, entity_type=None):
    query = db.query(models.SuspectedError)
    if entity_type:
        query = query.filter(models.SuspectedError.entity_type == entity_type)
    return query.count()
