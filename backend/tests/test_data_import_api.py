"""存量数据 CSV 导入 API 测试（SPEC §7 Phase 4.1）。

验收：CSV 导入成功；格式错误行返回明细报告。
另覆盖 AGENTS.md 上传安全不变量（类型白名单 / 10MB 上限）、
(entity_type, partner_code) upsert 合并语义、SPEC §3.0 权限矩阵与审计。
"""
import io

from fastapi.testclient import TestClient

from app import models
from app.main import app
from app.services import csv_importer

URL = "/api/data-import/partners"
HEADER = "partner_code,partner_name,CITY1,ZTERM\n"


def _post(client, csv_text, entity_type="supplier", filename="suppliers.csv",
          content_type="text/csv", raw=None):
    body = raw if raw is not None else csv_text.encode("utf-8")
    return client.post(
        URL,
        data={"entity_type": entity_type},
        files={"file": (filename, io.BytesIO(body), content_type)},
    )


def _supplier(db, code):
    return (
        db.query(models.PartnerRecord)
        .filter(
            models.PartnerRecord.entity_type == "supplier",
            models.PartnerRecord.partner_code == code,
        )
        .one_or_none()
    )


def test_import_creates_new_suppliers(seeded_db, data_client):
    resp = _post(data_client, HEADER + "1000000002,宁波精工轴承厂,宁波,0001\n1000000003,苏州电子材料公司,苏州,0004\n")
    assert resp.status_code == 200
    body = resp.json()
    assert body["entity_type"] == "supplier"
    assert body["filename"] == "suppliers.csv"
    assert (body["total_rows"], body["created"], body["updated"], body["failed"]) == (2, 2, 0, 0)
    assert body["errors"] == []
    assert _supplier(seeded_db, "1000000002").partner_name == "宁波精工轴承厂"
    assert _supplier(seeded_db, "1000000003").attributes == {"CITY1": "苏州", "ZTERM": "0004"}


def test_import_upserts_existing_supplier_and_merges_attributes(seeded_db, data_client):
    """重导同一 partner_code：更新而非新增；CSV 未出现的列保留旧值（SPEC §4.2）。"""
    resp = _post(data_client, "partner_code,partner_name,CITY1\n1000000001,华成精密机械有限公司（更名）,上海\n")
    assert resp.status_code == 200
    body = resp.json()
    assert (body["created"], body["updated"], body["failed"]) == (0, 1, 0)

    record = _supplier(seeded_db, "1000000001")
    assert record.partner_name == "华成精密机械有限公司（更名）"
    assert record.attributes["CITY1"] == "上海"
    assert record.attributes["ZTERM"] == "0010"  # CSV 无此列 → 保留旧值
    assert (
        seeded_db.query(models.PartnerRecord)
        .filter(models.PartnerRecord.partner_code == "1000000001")
        .count()
        == 1
    )


def test_blank_attribute_cell_keeps_old_value(seeded_db, data_client):
    """空单元格不覆盖既有值——导入是补全，不是清空。"""
    _post(data_client, "partner_code,partner_name,CITY1\n1000000001,华成精密机械有限公司,\n")
    assert _supplier(seeded_db, "1000000001").attributes["CITY1"] == "上海"


def test_malformed_rows_return_detail_report_and_valid_rows_still_import(seeded_db, data_client):
    """验收核心：格式错误行返回明细报告，合法行照常入库（部分成功）。"""
    csv_text = (
        HEADER
        + "1000000002,宁波精工轴承厂,宁波,0001\n"   # 合法
        + ",缺编码公司,杭州,0002\n"                 # 编码为空
        + "1000000003,,苏州,0004\n"                 # 名称为空
        + "1000000004,深圳五金制品厂,深圳,0005\n"   # 合法
    )
    resp = _post(data_client, csv_text)
    assert resp.status_code == 200
    body = resp.json()
    assert (body["total_rows"], body["created"], body["updated"], body["failed"]) == (4, 2, 0, 2)
    assert body["created"] + body["updated"] + body["failed"] == body["total_rows"]

    by_row = {e["row"]: e for e in body["errors"]}
    assert by_row[2]["field"] == "partner_code"
    assert by_row[2]["message"] == "编码不能为空"
    assert by_row[3]["field"] == "partner_name"
    assert _supplier(seeded_db, "1000000002") is not None
    assert _supplier(seeded_db, "1000000004") is not None


def test_duplicate_code_within_file_rejected_per_row(seeded_db, data_client):
    resp = _post(data_client, HEADER + "1000000002,宁波精工轴承厂,宁波,0001\n1000000002,重复编码公司,宁波,0001\n")
    assert resp.status_code == 200
    body = resp.json()
    assert (body["created"], body["failed"]) == (1, 1)
    assert body["errors"][0]["row"] == 2
    assert "重复" in body["errors"][0]["message"]


def test_overlong_fields_reported_per_row(seeded_db, data_client):
    csv_text = HEADER + f"{'9' * 51},超长编码公司,宁波,0001\n1000000002,{'名' * 201},宁波,0001\n"
    body = _post(data_client, csv_text).json()
    assert body["failed"] == 2
    assert body["errors"][0]["field"] == "partner_code"
    assert body["errors"][1]["field"] == "partner_name"
    assert body["created"] == 0


def test_rejects_non_csv_extension(seeded_db, data_client):
    resp = _post(data_client, HEADER + "1000000002,宁波精工轴承厂,宁波,0001\n", filename="suppliers.txt")
    assert resp.status_code == 400
    assert "文件类型" in resp.json()["detail"]
    assert _supplier(seeded_db, "1000000002") is None


def test_rejects_executable_content_type(seeded_db, data_client):
    """AGENTS.md 上传不变量：HTML/SVG/JS 一律拒收，即使扩展名伪装成 .csv。"""
    for content_type in ("text/html", "image/svg+xml", "application/javascript"):
        resp = _post(data_client, "<script>alert(1)</script>", content_type=content_type)
        assert resp.status_code == 400
        assert "Content-Type" in resp.json()["detail"]


def test_rejects_oversize_file(seeded_db, data_client):
    resp = _post(data_client, "", raw=b"a" * (csv_importer.MAX_FILE_BYTES + 1))
    assert resp.status_code == 400
    assert "10MB" in resp.json()["detail"]


def test_rejects_empty_file(seeded_db, data_client):
    assert _post(data_client, "").status_code == 400


def test_rejects_missing_header(seeded_db, data_client):
    resp = _post(data_client, "\n\n")
    assert resp.status_code == 400
    assert "表头" in resp.json()["detail"]


def test_rejects_missing_required_column(seeded_db, data_client):
    resp = _post(data_client, "code,name\n1000000002,宁波精工轴承厂\n")
    assert resp.status_code == 400
    assert "partner_code" in resp.json()["detail"]
    assert _supplier(seeded_db, "1000000002") is None


def test_rejects_row_count_over_limit(seeded_db, data_client):
    rows = "".join(f"10000{i:05d},供应商{i},宁波,0001\n" for i in range(csv_importer.MAX_ROWS + 1))
    resp = _post(data_client, HEADER + rows)
    assert resp.status_code == 400
    assert "分批" in resp.json()["detail"]


def test_tolerates_utf8_bom_and_blank_lines(seeded_db, data_client):
    csv_text = "\ufeff" + HEADER + "1000000002,宁波精工轴承厂,宁波,0001\n\n"
    body = _post(data_client, csv_text).json()
    assert (body["total_rows"], body["created"]) == (1, 1)


def test_rejects_invalid_entity_type(seeded_db, data_client):
    assert _post(data_client, HEADER + "M10001,物料,宁波,0001\n", entity_type="material").status_code == 422
    assert _post(data_client, HEADER, entity_type="vendor").status_code == 422


def test_customer_import_is_isolated_from_supplier(seeded_db, data_client):
    """同一编码在不同 entity_type 下是不同实体（uq_entity_partner_code）。"""
    assert _post(data_client, HEADER + "1000000001,客户甲,广州,0001\n", entity_type="customer").json()["created"] == 1
    assert _supplier(seeded_db, "1000000001").partner_name == "华成精密机械有限公司"
    customer = (
        seeded_db.query(models.PartnerRecord)
        .filter(models.PartnerRecord.entity_type == "customer")
        .one()
    )
    assert customer.partner_code == "1000000001"


def test_import_permission_denied(seeded_db, client, dept_client, data_client):
    payload = HEADER + "1000000002,宁波精工轴承厂,宁波,0001\n"
    assert _post(client, payload).status_code == 403
    assert _post(dept_client, payload).status_code == 403
    anon = TestClient(app).post(
        URL, data={"entity_type": "supplier"},
        files={"file": ("s.csv", io.BytesIO(payload.encode("utf-8")), "text/csv")},
    )
    assert anon.status_code == 401
    assert _supplier(seeded_db, "1000000002") is None


def test_import_is_audited(seeded_db, data_client):
    _post(data_client, HEADER + "1000000002,宁波精工轴承厂,宁波,0001\n")
    log = (
        seeded_db.query(models.AuditLog)
        .filter(models.AuditLog.step_name == models.StepName.DATA_IMPORT.value)
        .one()
    )
    assert log.step_label == "导入存量数据"
    assert log.status == "success"
    assert log.executed_by == "data001"
    assert log.details["created"] == 1
    assert log.details["total_rows"] == 1


def test_file_level_failure_is_audited_as_failed(seeded_db, data_client):
    _post(data_client, HEADER, filename="suppliers.txt")
    log = (
        seeded_db.query(models.AuditLog)
        .filter(models.AuditLog.step_name == models.StepName.DATA_IMPORT.value)
        .one()
    )
    assert log.status == "failed"
    assert log.error_message
