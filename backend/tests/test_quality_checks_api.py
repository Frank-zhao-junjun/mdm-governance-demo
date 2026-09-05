"""质量检测 API 测试（SPEC §3.2 + Phase 2 验收）。"""
import pytest
from fastapi.testclient import TestClient

from app import models
from app.main import app
from app.services import quality_runner
from app.services.rule_derivation import derive_rule_rows


@pytest.fixture(scope="function")
def quality_db(seeded_db):
    """seeded_db（2 标准 + 2 记录）+ 追加标准/派生规则/脏记录。"""
    db = seeded_db
    db.add(models.DataStandard(
        entity_type="material", sap_table="MARA", field_name="MEINS",
        field_label="基本计量单位", data_type="enum", required=True,
        enum_values=["KG", "G", "PC"], owner="钱数据", standard_source="sap",
    ))
    db.add(models.DataStandard(
        entity_type="material", sap_table="MARC", field_name="WERKS",
        field_label="工厂", data_type="string", required=True,
        owner="钱数据", standard_source="sap",
    ))
    db.add(models.DataStandard(
        entity_type="supplier", sap_table="LFA1", field_name="LAND1",
        field_label="国家", data_type="enum", required=True,
        enum_values=["CN", "US"], owner="钱数据", standard_source="sap",
    ))
    db.flush()
    db.add_all(derive_rule_rows(db.query(models.DataStandard).all()))

    # material：M1234 编码格式错 + 缺 MEINS；M10002 干净
    db.add(models.MaterialRecord(
        material_code="M1234", material_name="六角螺栓 M8x30 热镀锌",
        attributes={"MTART": "ROH"},
    ))
    db.add(models.MaterialRecord(
        material_code="M10002", material_name="六角螺栓 M10×40 镀锌",
        attributes={"MEINS": "PC"},
    ))
    # supplier：12345 编码短 + 缺 LAND1；1000000002 干净；给 seeded 供应商补 LAND1
    db.add(models.PartnerRecord(
        entity_type="supplier", partner_code="12345", partner_name="杭州轴承试验中心",
        attributes={"ZTERM": "0010"},
    ))
    db.add(models.PartnerRecord(
        entity_type="supplier", partner_code="1000000002", partner_name="远东液压设备股份有限公司",
        attributes={"LAND1": "CN"},
    ))
    seeded_supplier = (
        db.query(models.PartnerRecord)
        .filter(models.PartnerRecord.partner_code == "1000000001")
        .first()
    )
    seeded_supplier.attributes["LAND1"] = "CN"
    db.commit()
    return db


def _run(data_client, entity_type="material", **body_overrides):
    body = {"entity_type": entity_type, **body_overrides}
    return data_client.post("/api/quality-checks/run", json=body)


def _material_id(db, code):
    return (
        db.query(models.MaterialRecord)
        .filter(models.MaterialRecord.material_code == code)
        .first()
        .id
    )


# ========== POST /run ==========

def test_run_creates_batch_and_stores_only_failures(quality_db, data_client):
    db = quality_db
    resp = _run(data_client)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"batch_id", "total_checked", "passed", "failed", "skipped"}
    assert body["passed"] + body["failed"] == body["total_checked"]
    assert body["failed"] > 0

    batch = db.query(models.QualityCheckBatch).filter(
        models.QualityCheckBatch.id == body["batch_id"]
    ).first()
    assert batch is not None
    assert batch.entity_type == "material"
    assert batch.total_entities == 3  # M10001 + M1234 + M10002
    assert batch.total_checks == body["total_checked"]
    assert batch.passed == body["passed"]
    assert batch.failed == body["failed"]
    assert batch.triggered_by == "data001"

    # 只存失败项（硬性验收）：结果行数 == failed
    result_count = db.query(models.QualityCheckResult).filter(
        models.QualityCheckResult.batch_id == batch.id
    ).count()
    assert result_count == body["failed"]
    assert result_count == 2  # M1234 编码格式错 + 缺 MEINS


def test_run_entity_ids_subset(quality_db, data_client):
    db = quality_db
    m1234_id = _material_id(db, "M1234")
    resp = _run(data_client, entity_ids=[m1234_id])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_checked"] > 0

    batch = db.query(models.QualityCheckBatch).filter(
        models.QualityCheckBatch.id == body["batch_id"]
    ).first()
    assert batch.total_entities == 1
    entity_ids = {
        r.entity_id
        for r in db.query(models.QualityCheckResult).filter(
            models.QualityCheckResult.batch_id == batch.id
        )
    }
    assert entity_ids == {m1234_id}


def test_run_rule_ids_subset(quality_db, data_client):
    db = quality_db
    null_rule = (
        db.query(models.QualityCheckRule)
        .filter(
            models.QualityCheckRule.entity_type == "material",
            models.QualityCheckRule.rule_type == models.RuleType.NULL_CHECK,
        )
        .first()
    )
    resp = _run(data_client, rule_ids=[null_rule.id])
    assert resp.status_code == 200, resp.text

    batch = db.query(models.QualityCheckBatch).filter(
        models.QualityCheckBatch.id == resp.json()["batch_id"]
    ).first()
    assert batch.rule_ids == [null_rule.id]
    # 失败仅来自该规则
    rule_ids = {
        r.rule_id
        for r in db.query(models.QualityCheckResult).filter(
            models.QualityCheckResult.batch_id == batch.id
        )
    }
    assert rule_ids <= {null_rule.id}


def test_run_permission_denied(seeded_db, client, dept_client):
    # 依赖层拦截：即使无规则，权限 403 先于业务 400
    assert client.post("/api/quality-checks/run", json={"entity_type": "material"}).status_code == 403
    assert dept_client.post("/api/quality-checks/run", json={"entity_type": "material"}).status_code == 403
    # 无 token → 401
    assert TestClient(app).post("/api/quality-checks/run", json={"entity_type": "material"}).status_code == 401


def test_run_invalid_entity_type(quality_db, data_client):
    assert _run(data_client, entity_type="foo").status_code == 422


def test_run_limit_5000(quality_db, data_client, monkeypatch):
    monkeypatch.setattr(
        quality_runner, "count_entities", lambda db, entity_type, entity_ids=None: 5001
    )
    resp = _run(data_client)
    assert resp.status_code == 400
    assert "分批" in resp.json()["detail"]

    monkeypatch.setattr(
        quality_runner, "count_entities", lambda db, entity_type, entity_ids=None: 5000
    )
    assert _run(data_client).status_code == 200


def test_run_no_executable_rules(quality_db, data_client):
    resp = _run(data_client, entity_type="customer")
    assert resp.status_code == 400
    assert "没有可执行" in resp.json()["detail"]


def test_run_no_matching_entity_ids(quality_db, data_client):
    resp = _run(data_client, entity_ids=["00000000-0000-0000-0000-000000000000"])
    assert resp.status_code == 400


def test_skipped_recorded(quality_db, data_client):
    db = quality_db
    resp = _run(data_client)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # WERKS 规则整条跳过，3 实体各记 1 次
    assert body["skipped"] == 3

    batch = db.query(models.QualityCheckBatch).filter(
        models.QualityCheckBatch.id == body["batch_id"]
    ).first()
    assert batch.skipped_checks == 3

    audit = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.step_name == "quality_run")
        .order_by(models.AuditLog.id.desc())
        .first()
    )
    assert audit is not None
    assert any(s["field_name"] == "WERKS" for s in audit.details["skipped_fields"])


def test_run_writes_audit(quality_db, data_client):
    db = quality_db
    resp = _run(data_client)
    assert resp.status_code == 200, resp.text

    audit = (
        db.query(models.AuditLog)
        .filter(
            models.AuditLog.step_name == "quality_run",
            models.AuditLog.executed_by == "data001",
        )
        .first()
    )
    assert audit is not None
    assert audit.details["batch_id"] == resp.json()["batch_id"]
    assert audit.details["scope"] == "all"


# ========== GET /rules ==========

def test_rules_list(quality_db, client, dept_client, data_client):
    resp = data_client.get("/api/quality-checks/rules")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 11  # 5 条标准派生：material 6 + supplier 5
    assert len(body["items"]) == 11
    first = body["items"][0]
    assert {"id", "name", "entity_type", "rule_type", "field_name", "standard_id",
            "severity", "is_active"} <= set(first)

    # 全角色可读
    for c in (client, dept_client):
        assert c.get("/api/quality-checks/rules").status_code == 200


def test_rules_filter_entity_type(quality_db, data_client):
    resp = data_client.get("/api/quality-checks/rules", params={"entity_type": "material"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 6
    assert all(item["entity_type"] == "material" for item in body["items"])


# ========== GET /results ==========

def test_results_requires_entity_type(quality_db, client):
    assert client.get("/api/quality-checks/results").status_code == 422


def test_results_filters_and_pagination(quality_db, data_client):
    db = quality_db
    _run(data_client)
    batch = (
        db.query(models.QualityCheckBatch)
        .order_by(models.QualityCheckBatch.id.desc())
        .first()
    )

    # severity 过滤
    resp = data_client.get(
        "/api/quality-checks/results",
        params={"entity_type": "material", "severity": "error", "limit": 100},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == batch.failed
    assert all(item["severity"] == "error" for item in body["items"])

    # batch_id 过滤
    resp = data_client.get(
        "/api/quality-checks/results",
        params={"entity_type": "material", "batch_id": batch.id, "limit": 100},
    )
    assert resp.json()["total"] == batch.failed

    # entity_id 过滤
    m1234_id = _material_id(db, "M1234")
    resp = data_client.get(
        "/api/quality-checks/results",
        params={"entity_type": "material", "entity_id": m1234_id, "limit": 100},
    )
    body = resp.json()
    assert body["total"] == 2  # M1234 两条失败（格式 + 缺 MEINS）
    assert all(item["entity_id"] == m1234_id for item in body["items"])

    # field_name 过滤（字段治理单字段视图数据源）
    for field in ("MATNR", "MEINS"):
        resp = data_client.get(
            "/api/quality-checks/results",
            params={"entity_type": "material", "batch_id": batch.id, "field_name": field, "limit": 100},
        )
        items = resp.json()["items"]
        assert items and all(item["field_name"] == field for item in items)

    # 分页：limit=1 切片正确、total 恒定
    page1 = data_client.get(
        "/api/quality-checks/results",
        params={"entity_type": "material", "batch_id": batch.id, "limit": 1},
    ).json()
    page2 = data_client.get(
        "/api/quality-checks/results",
        params={"entity_type": "material", "batch_id": batch.id, "skip": 1, "limit": 1},
    ).json()
    assert page1["total"] == page2["total"] == batch.failed
    assert len(page1["items"]) == 1
    assert page1["items"][0]["id"] != page2["items"][0]["id"]


def test_results_all_roles(quality_db, client, dept_client, data_client):
    _run(data_client)
    for c in (client, dept_client):
        resp = c.get("/api/quality-checks/results", params={"entity_type": "material"})
        assert resp.status_code == 200


# ========== GET /batches ==========

def test_batches_newest_first(quality_db, data_client):
    first = _run(data_client).json()["batch_id"]
    second = _run(data_client).json()["batch_id"]
    resp = data_client.get("/api/quality-checks/batches", params={"entity_type": "material"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["id"] == second
    assert items[1]["id"] == first


# ========== GET /report ==========

def test_report_consistency(quality_db, data_client):
    db = quality_db
    resp = _run(data_client)
    body = resp.json()

    report = data_client.get(
        "/api/quality-checks/report", params={"entity_type": "material"}
    ).json()
    batch = db.query(models.QualityCheckBatch).filter(
        models.QualityCheckBatch.id == report["batch_id"]
    ).first()

    # 报告统计与批次表一致（硬性验收）
    assert report["batch_id"] == body["batch_id"]
    assert report["total_entities"] == batch.total_entities
    assert report["total_checks"] == batch.total_checks
    assert report["passed"] == batch.passed
    assert report["failed"] == batch.failed
    assert report["pass_rate"] == round(batch.passed / batch.total_checks, 4)

    # 失败分布与结果表一致
    assert sum(report["by_severity"].values()) == batch.failed
    assert report["by_severity"].keys() == {"error", "warning", "info"}

    # by_rule 覆盖批次全部规则（含 failed=0），failed 求和 == 批次 failed
    assert len(report["by_rule"]) == len(batch.rule_ids)
    assert {stat["rule_id"] for stat in report["by_rule"]} == set(batch.rule_ids)
    assert sum(stat["failed"] for stat in report["by_rule"]) == batch.failed

    # 决策 4 口径：total = 批次实体数；failed=0 的规则 pass_rate=1.0
    zero_failed = [stat for stat in report["by_rule"] if stat["failed"] == 0]
    assert zero_failed
    for stat in report["by_rule"]:
        assert stat["total"] == batch.total_entities
    for stat in zero_failed:
        assert stat["pass_rate"] == 1.0

    # 决策 1 派生规则名可读
    assert all(stat["rule_name"] for stat in report["by_rule"])


def test_report_defaults_to_latest(quality_db, data_client):
    _run(data_client)
    second = _run(data_client).json()["batch_id"]
    report = data_client.get(
        "/api/quality-checks/report", params={"entity_type": "material"}
    ).json()
    assert report["batch_id"] == second


def test_report_top_issues(quality_db, data_client):
    _run(data_client)
    report = data_client.get(
        "/api/quality-checks/report", params={"entity_type": "material"}
    ).json()
    assert report["top_issues"]
    counts = [issue["issue_count"] for issue in report["top_issues"]]
    assert counts == sorted(counts, reverse=True)
    # issue_type 来自规则表（派生规则 rule_type）
    assert all(issue["issue_type"] in {"null_check", "format_check", "range_check",
                                       "length_check", "unique_check"}
               for issue in report["top_issues"])


def test_report_batch_not_found(quality_db, data_client):
    db = quality_db
    resp = data_client.get(
        "/api/quality-checks/report",
        params={"entity_type": "material", "batch_id": "nonexistent"},
    )
    assert resp.status_code == 404

    # batch 存在但实体类型不匹配
    _run(data_client)
    batch = (
        db.query(models.QualityCheckBatch)
        .order_by(models.QualityCheckBatch.id.desc())
        .first()
    )
    resp = data_client.get(
        "/api/quality-checks/report",
        params={"entity_type": "supplier", "batch_id": batch.id},
    )
    assert resp.status_code == 404

    # 无任何批次
    resp = data_client.get(
        "/api/quality-checks/report", params={"entity_type": "customer"}
    )
    assert resp.status_code == 404


def test_report_all_roles(quality_db, client, dept_client, data_client):
    _run(data_client)
    for c in (client, dept_client):
        resp = c.get("/api/quality-checks/report", params={"entity_type": "material"})
        assert resp.status_code == 200
