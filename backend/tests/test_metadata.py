"""元数据管理模块模型层用例（Task 1）：落库 / 唯一约束 / DataStandard 关联列。
另含 Task 2 种子验证用例（seed_metadata + 回填 29/29）。
Task 3 追加 /api/metadata 路由验收用例（权限矩阵 + CRUD + 审计）。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

import init_db
from app import models
from app.main import app
from sqlalchemy import func

BASE = "/api/metadata"


def _make_field(**overrides):
    """构造一个最小可落库的 MetadataField。"""
    data = {
        "entity_type": "material",
        "sap_table": "MARA",
        "field_name": "MATNR",
        "field_label": "物料编码",
        "data_type": "string",
        "standard_source": "sap",
    }
    data.update(overrides)
    return models.MetadataField(**data)


class TestMetadataFieldModel:
    def test_field_can_be_persisted(self, db):
        """MetadataField 直接 db.add 可落库并回读全部列。"""
        field = _make_field(
            max_length=18,
            view_section="基本数据",
            business_definition="物料主记录的唯一标识",
            must_govern=True,
            is_active=True,
        )
        db.add(field)
        db.commit()

        loaded = db.query(models.MetadataField).one()
        assert loaded.id
        assert loaded.entity_type == "material"
        assert loaded.sap_table == "MARA"
        assert loaded.field_name == "MATNR"
        assert loaded.field_label == "物料编码"
        assert loaded.max_length == 18
        assert loaded.view_section == "基本数据"
        assert loaded.must_govern is True
        assert loaded.is_active is True
        assert loaded.glossary_term_id is None
        assert loaded.created_at is not None
        assert loaded.updated_at is not None

    def test_unique_constraint_conflict_raises_integrity_error(self, db):
        """(entity_type, sap_table, field_name) 三元组重复时抛 IntegrityError。"""
        db.add(_make_field())
        db.commit()
        db.add(_make_field(field_label="物料编码（重复）"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_field_links_to_glossary_term(self, db):
        """glossary_term_id 外键可指向 glossary_term 记录。"""
        term = models.GlossaryTerm(term="物料编码", definition="标识物料的编码", aliases=["料号"])
        db.add(term)
        db.commit()

        db.add(_make_field(glossary_term_id=term.id))
        db.commit()
        loaded = db.query(models.MetadataField).one()
        assert loaded.glossary_term_id == term.id


class TestMetadataEntityModel:
    def test_entity_can_be_persisted(self, db):
        """MetadataEntity 可落库，tags 为 JSON 列表。"""
        entity = models.MetadataEntity(
            entity_type="material",
            display_name="物料主数据",
            business_definition="企业物料主记录",
            data_owner="钱数据",
            dept="采购部",
            tags=["核心主数据", "SAP-MARA"],
            sensitivity_level="internal",
        )
        db.add(entity)
        db.commit()

        loaded = db.query(models.MetadataEntity).one()
        assert loaded.display_name == "物料主数据"
        assert loaded.tags == ["核心主数据", "SAP-MARA"]
        assert loaded.sensitivity_level == "internal"
        assert loaded.created_at is not None
        assert loaded.updated_at is not None

    def test_entity_type_is_unique(self, db):
        """entity_type 重复时抛 IntegrityError。"""
        db.add(models.MetadataEntity(entity_type="material", display_name="物料主数据"))
        db.commit()
        db.add(models.MetadataEntity(entity_type="material", display_name="物料主数据副本"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestGlossaryTermModel:
    def test_term_can_be_persisted(self, db):
        """GlossaryTerm 可落库，aliases 为 JSON 列表。"""
        term = models.GlossaryTerm(
            term="物料编码",
            definition="标识物料的编码",
            aliases=["料号", "物料号"],
        )
        db.add(term)
        db.commit()

        loaded = db.query(models.GlossaryTerm).one()
        assert loaded.term == "物料编码"
        assert loaded.aliases == ["料号", "物料号"]
        assert loaded.created_at is not None
        assert loaded.updated_at is not None

    def test_term_is_unique(self, db):
        """term 重复时抛 IntegrityError。"""
        db.add(models.GlossaryTerm(term="物料编码", definition="标识物料的编码"))
        db.commit()
        db.add(models.GlossaryTerm(term="物料编码", definition="重复词条"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestDataStandardMetadataLink:
    def test_data_standard_accepts_metadata_field_id(self, db):
        """DataStandard 新增 metadata_field_id 列可写入并可回读。"""
        field = _make_field()
        db.add(field)
        db.commit()

        standard = models.DataStandard(
            entity_type="material",
            sap_table="MARA",
            field_name="MATNR",
            field_label="物料编码",
            data_type="string",
            required=True,
            metadata_field_id=field.id,
        )
        db.add(standard)
        db.commit()

        loaded = db.query(models.DataStandard).one()
        assert loaded.metadata_field_id == field.id

    def test_step_name_has_metadata_values(self, db):
        """StepName 枚举新增元数据管理与术语管理步骤名。"""
        assert models.StepName.METADATA_ENTITY_UPDATE.value == "metadata_entity_update"
        assert models.StepName.METADATA_FIELD_CREATE.value == "metadata_field_create"
        assert models.StepName.METADATA_FIELD_UPDATE.value == "metadata_field_update"
        assert models.StepName.GLOSSARY_CREATE.value == "glossary_create"
        assert models.StepName.GLOSSARY_UPDATE.value == "glossary_update"


class TestMetadataSeed:
    """init_db.py 元数据种子验证（Task 2）。

    不直接调 init_db()（会 drop_all 污染共享 engine），改为对裸 db fixture
    调 seed_metadata(db) + backfill_standard_metadata_links 断言数量。
    """

    def test_seed_metadata_counts(self, db):
        """种子落库数量：字段 70 / 实体 3 / 术语 15（设计文档 §4.1-4.3）。"""
        metadata = init_db.seed_metadata(db)
        db.commit()

        assert len(init_db.METADATA_FIELDS) == 70
        assert len(init_db.METADATA_ENTITIES) == 3
        assert len(init_db.GLOSSARY_TERMS) == 15
        assert db.query(models.MetadataField).count() == 70
        assert db.query(models.MetadataEntity).count() == 3
        assert db.query(models.GlossaryTerm).count() == 15
        assert len(metadata["fields"]) == 70
        assert len(metadata["terms"]) == 15

    def test_seed_fields_split_by_entity(self, db):
        """字段登记册三实体分布：material 30 / supplier 25 / customer 15，全部 must_govern。"""
        init_db.seed_metadata(db)
        db.commit()

        counts = dict(
            db.query(models.MetadataField.entity_type, func.count())
            .group_by(models.MetadataField.entity_type)
            .all()
        )
        assert counts == {"material": 30, "supplier": 25, "customer": 15}
        assert db.query(models.MetadataField).filter(
            models.MetadataField.must_govern.is_(True)
        ).count() == 70

    def test_seed_terms_linked_to_fields(self, db):
        """15 条术语全部预关联到对应登记册字段。"""
        metadata = init_db.seed_metadata(db)
        db.commit()

        linked = db.query(models.MetadataField).filter(
            models.MetadataField.glossary_term_id.isnot(None)
        ).count()
        assert linked == 15

        # 抽查：物料编码 → MARA-MATNR；邓白氏编码（DUNS）→ ARIBA_SLP-DUNSNumber
        matnr = metadata["fields"][("material", "MARA", "MATNR")]
        assert matnr.glossary_term_id == metadata["terms"]["物料编码"].id
        duns = metadata["fields"][("supplier", "ARIBA_SLP", "DUNSNumber")]
        assert duns.glossary_term_id == metadata["terms"]["邓白氏编码（DUNS）"].id

    def test_backfill_links_all_standards(self, db):
        """29 条种子标准全部回填 metadata_field_id；未命中登记册的先补条目再回填。"""
        metadata = init_db.seed_metadata(db)
        seed_keys = set(metadata["fields"].keys())

        standards = init_db._standard_rows()
        db.add_all(standards)
        db.flush()
        linked = init_db.backfill_standard_metadata_links(db, standards, metadata["fields"])
        db.commit()

        assert len(standards) == 29
        assert linked == 29
        assert all(s.metadata_field_id for s in standards)

        # 不在 §4.1 清单的标准字段（BUT020/BUT0BANK/WERKS 等）走补登记册路径，
        # 补完后登记册总数 = 70 + 缺失键数
        standard_keys = {(s.entity_type, s.sap_table, s.field_name) for s in standards}
        missing = standard_keys - seed_keys
        assert len(missing) == 16  # 现有 29 条标准中 16 个键不在 §4.1 清单
        assert db.query(models.MetadataField).count() == 70 + len(missing)

        # 回填的关联指向真实存在的登记册记录
        field_ids = {f.id for f in db.query(models.MetadataField).all()}
        assert {s.metadata_field_id for s in standards} <= field_ids


# ========== Task 3: /api/metadata 路由验收 ==========

NEW_FIELD = {
    "entity_type": "material",
    "sap_table": "MARA",
    "field_name": "MTART",
    "field_label": "物料类型",
    "data_type": "enum",
    "view_section": "基本数据",
    "must_govern": True,
    "standard_source": "sap",
}


@pytest.fixture(scope="function")
def metadata_db(seeded_db):
    """种入元数据基础数据：3 实体 + 4 字段 + 2 术语（1 条已关联字段）。

    分布（供实体总览计数断言）：
    - material：MATNR(must_govern) + MAKTX(must_govern) + MEINS(非) → 2/3
    - supplier：LIFNR(must_govern) → 1/1
    - customer：无字段 → 0/0
    术语：物料编码 → 关联 MATNR（field_count=1）；供应商编号 → 无关联（field_count=0）。
    """
    db = seeded_db
    db.add_all([
        models.MetadataEntity(entity_type="material", display_name="物料主数据", data_owner="钱数据", dept="采购部"),
        models.MetadataEntity(entity_type="supplier", display_name="供应商主数据", data_owner="钱数据", dept="采购部"),
        models.MetadataEntity(entity_type="customer", display_name="客户主数据", data_owner="孙销售", dept="销售部"),
    ])
    term_linked = models.GlossaryTerm(term="物料编码", definition="标识物料的编码", aliases=["料号"])
    term_free = models.GlossaryTerm(term="供应商编号", definition="标识供应商的编码")
    db.add_all([term_linked, term_free])
    db.flush()
    db.add_all([
        models.MetadataField(
            entity_type="material", sap_table="MARA", field_name="MATNR",
            field_label="物料编码", data_type="string", view_section="基本数据",
            must_govern=True, glossary_term_id=term_linked.id,
        ),
        models.MetadataField(
            entity_type="material", sap_table="MAKT", field_name="MAKTX",
            field_label="物料描述", data_type="string", view_section="基本数据",
            must_govern=True,
        ),
        models.MetadataField(
            entity_type="material", sap_table="MARA", field_name="MEINS",
            field_label="基本计量单位", data_type="enum", view_section="采购视图",
            must_govern=False,
        ),
        models.MetadataField(
            entity_type="supplier", sap_table="LFA1", field_name="LIFNR",
            field_label="供应商编号", data_type="string", view_section="基本数据",
            must_govern=True,
        ),
    ])
    db.commit()
    yield db


def _field_id(db, field_name: str) -> str:
    return (
        db.query(models.MetadataField)
        .filter(models.MetadataField.field_name == field_name)
        .first()
        .id
    )


def _term_id(db, term: str) -> str:
    return db.query(models.GlossaryTerm).filter(models.GlossaryTerm.term == term).first().id


class TestApiReadAccess:
    """读权限矩阵：匿名 401，三角色均可读三类资源。"""

    def test_anonymous_request_is_rejected(self, metadata_db):
        anonymous = TestClient(app)
        assert anonymous.get(f"{BASE}/entities").status_code == 401
        assert anonymous.get(f"{BASE}/fields").status_code == 401
        assert anonymous.get(f"{BASE}/glossary").status_code == 401

    @pytest.mark.parametrize("fixture_name", ["client", "dept_client", "data_client"])
    def test_every_role_can_read(self, request, fixture_name, metadata_db):
        client = request.getfixturevalue(fixture_name)
        assert client.get(f"{BASE}/entities").status_code == 200
        assert client.get(f"{BASE}/fields").status_code == 200
        assert client.get(f"{BASE}/glossary").status_code == 200


class TestApiWritePermissions:
    """写权限矩阵：applicant/dept_approver 写 403；data_admin 可写。"""

    @pytest.mark.parametrize("fixture_name", ["client", "dept_client"])
    def test_non_admin_writes_are_forbidden(self, request, fixture_name, metadata_db):
        client = request.getfixturevalue(fixture_name)
        assert client.post(f"{BASE}/fields", json=NEW_FIELD).status_code == 403
        assert client.put(f"{BASE}/fields/any-id", json={"field_label": "x"}).status_code == 403
        assert client.put(f"{BASE}/entities/material", json={"data_owner": "x"}).status_code == 403
        assert client.post(f"{BASE}/glossary", json={"term": "x", "definition": "y"}).status_code == 403
        assert client.put(f"{BASE}/glossary/any-id", json={"definition": "z"}).status_code == 403

    def test_data_admin_can_write(self, data_client, metadata_db):
        assert data_client.post(f"{BASE}/fields", json=NEW_FIELD).status_code == 201
        assert data_client.put(
            f"{BASE}/entities/material", json={"data_owner": "李四"}
        ).status_code == 200
        assert data_client.post(
            f"{BASE}/glossary", json={"term": "物料类型", "definition": "物料的分类标识"}
        ).status_code == 201


class TestFieldCRUD:
    def test_create_then_list_and_audit(self, data_client, metadata_db):
        """创建 201 → 列表可见 → 审计落 metadata_field_create。"""
        body = data_client.post(f"{BASE}/fields", json=NEW_FIELD).json()
        assert body["id"]
        assert body["field_name"] == "MTART"
        assert body["must_govern"] is True

        listing = data_client.get(f"{BASE}/fields").json()
        assert listing["total"] == 5
        assert any(i["id"] == body["id"] for i in listing["items"])

        log = metadata_db.query(models.AuditLog).filter(
            models.AuditLog.step_name == models.StepName.METADATA_FIELD_CREATE
        ).one()
        assert log.details["field_name"] == "MTART"
        assert log.executed_by == "data001"

    def test_keyword_filter_matches_name_and_label(self, client, metadata_db):
        by_name = client.get(f"{BASE}/fields", params={"keyword": "matnr"}).json()
        assert [i["field_name"] for i in by_name["items"]] == ["MATNR"]
        by_label = client.get(f"{BASE}/fields", params={"keyword": "物料"}).json()
        assert {i["field_name"] for i in by_label["items"]} == {"MATNR", "MAKTX"}

    def test_must_govern_and_section_filters(self, client, metadata_db):
        governed = client.get(f"{BASE}/fields", params={"must_govern": True}).json()
        assert governed["total"] == 3
        section = client.get(f"{BASE}/fields", params={"view_section": "采购视图"}).json()
        assert [i["field_name"] for i in section["items"]] == ["MEINS"]
        supplier = client.get(f"{BASE}/fields", params={"entity_type": "supplier"}).json()
        assert [i["field_name"] for i in supplier["items"]] == ["LIFNR"]

    def test_create_unknown_glossary_term_returns_404(self, data_client, metadata_db):
        """POST 带不存在的 glossary_term_id → 404「关联的术语不存在」。"""
        payload = dict(NEW_FIELD, glossary_term_id="no-such-term")
        resp = data_client.post(f"{BASE}/fields", json=payload)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "关联的术语不存在"

    def test_duplicate_create_returns_409(self, data_client, metadata_db):
        payload = dict(NEW_FIELD, field_name="MATNR", field_label="物料编码（重复）")
        resp = data_client.post(f"{BASE}/fields", json=payload)
        assert resp.status_code == 409
        assert "已存在" in resp.json()["detail"]

    def test_update_null_glossary_term_id_unlinks(self, data_client, metadata_db):
        """PUT 显式传 glossary_term_id=null → 解除术语关联且不被存在性校验误伤。"""
        field_id = _field_id(metadata_db, "MATNR")  # 种子中已关联「物料编码」术语
        resp = data_client.put(f"{BASE}/fields/{field_id}", json={"glossary_term_id": None})
        assert resp.status_code == 200
        assert resp.json()["glossary_term_id"] is None
        assert metadata_db.get(models.MetadataField, field_id).glossary_term_id is None

    def test_update_field(self, data_client, metadata_db):
        field_id = _field_id(metadata_db, "MEINS")
        resp = data_client.put(
            f"{BASE}/fields/{field_id}",
            json={"must_govern": True, "field_label": "基本计量单位（治理）"},
        )
        assert resp.status_code == 200
        assert resp.json()["must_govern"] is True
        assert resp.json()["field_label"] == "基本计量单位（治理）"

        log = metadata_db.query(models.AuditLog).filter(
            models.AuditLog.step_name == models.StepName.METADATA_FIELD_UPDATE
        ).one()
        assert log.details["field_id"] == field_id

    def test_update_field_not_found(self, data_client, metadata_db):
        resp = data_client.put(f"{BASE}/fields/no-such-id", json={"field_label": "x"})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "元数据字段不存在"

    def test_update_field_empty_payload_returns_400(self, data_client, metadata_db):
        field_id = _field_id(metadata_db, "MEINS")
        resp = data_client.put(f"{BASE}/fields/{field_id}", json={})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "未提供可更新字段"


class TestEntityOverview:
    def test_overview_lists_three_entities_with_counts(self, client, metadata_db):
        body = client.get(f"{BASE}/entities").json()
        assert len(body) == 3
        by_type = {e["entity_type"]: e for e in body}
        assert by_type["material"]["governed_field_count"] == 2
        assert by_type["material"]["total_field_count"] == 3
        assert by_type["supplier"]["governed_field_count"] == 1
        assert by_type["supplier"]["total_field_count"] == 1
        assert by_type["customer"]["governed_field_count"] == 0
        assert by_type["customer"]["total_field_count"] == 0
        assert by_type["material"]["display_name"] == "物料主数据"


class TestEntityUpdate:
    def test_update_entity(self, data_client, metadata_db):
        resp = data_client.put(
            f"{BASE}/entities/material",
            json={"data_owner": "李四", "sensitivity_level": "confidential"},
        )
        assert resp.status_code == 200
        assert resp.json()["data_owner"] == "李四"
        assert resp.json()["sensitivity_level"] == "confidential"

        log = metadata_db.query(models.AuditLog).filter(
            models.AuditLog.step_name == models.StepName.METADATA_ENTITY_UPDATE
        ).one()
        assert log.details["entity_type"] == "material"

    def test_update_entity_not_found(self, data_client, metadata_db):
        resp = data_client.put(f"{BASE}/entities/no-such-entity", json={"data_owner": "x"})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "实体元数据不存在"


class TestGlossary:
    def test_list_terms_with_field_count(self, client, metadata_db):
        body = client.get(f"{BASE}/glossary").json()
        by_term = {t["term"]: t for t in body}
        assert by_term["物料编码"]["field_count"] == 1
        assert by_term["供应商编号"]["field_count"] == 0

    def test_create_term_and_audit(self, data_client, metadata_db):
        resp = data_client.post(
            f"{BASE}/glossary",
            json={"term": "物料类型", "definition": "物料的分类标识", "aliases": ["MTART"]},
        )
        assert resp.status_code == 201
        assert resp.json()["aliases"] == ["MTART"]

        log = metadata_db.query(models.AuditLog).filter(
            models.AuditLog.step_name == models.StepName.GLOSSARY_CREATE
        ).one()
        assert log.details["term"] == "物料类型"

    def test_duplicate_term_returns_409(self, data_client, metadata_db):
        resp = data_client.post(
            f"{BASE}/glossary", json={"term": "物料编码", "definition": "重复词条"}
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "术语已存在"

    def test_update_term(self, data_client, metadata_db):
        term_id = _term_id(metadata_db, "供应商编号")
        resp = data_client.put(
            f"{BASE}/glossary/{term_id}",
            json={"definition": "标识供应商的唯一编码", "aliases": ["LIFNR"]},
        )
        assert resp.status_code == 200
        assert resp.json()["definition"] == "标识供应商的唯一编码"

        log = metadata_db.query(models.AuditLog).filter(
            models.AuditLog.step_name == models.StepName.GLOSSARY_UPDATE
        ).one()
        assert log.details["term_id"] == term_id

    def test_update_term_not_found(self, data_client, metadata_db):
        resp = data_client.put(f"{BASE}/glossary/no-such-id", json={"definition": "x"})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "术语不存在"


# ========== Task 4: data_standards 外键带入 ==========

STANDARDS_BASE = "/api/data-standards"


def _standard_id(db, field_name: str) -> str:
    return (
        db.query(models.DataStandard)
        .filter(models.DataStandard.field_name == field_name)
        .first()
        .id
    )


class TestStandardFieldLink:
    """POST/PUT data-standards 传 metadata_field_id 时以登记册为准带入核心字段。

    登记册（metadata_db fixture）分布：MATNR(material/MARA) / MAKTX(material/MAKT) /
    MEINS(material/MARA) / LIFNR(supplier/LFA1)；种子标准：material/MARA/MATNR +
    supplier/LFA1/LIFNR（均未关联元数据字段）。
    """

    def test_create_carries_registry_fields(self, data_client, metadata_db):
        """带 metadata_field_id 创建：payload 中不一致的核心字段全部被登记册覆盖。"""
        field_id = _field_id(metadata_db, "MAKTX")  # material/MAKT/物料描述/string/基本数据
        resp = data_client.post(STANDARDS_BASE, json={
            "entity_type": "supplier",   # 与登记册不一致，应被覆盖
            "sap_table": "LFA1",
            "field_name": "WRONG",
            "data_type": "number",
            "max_length": 99,
            "metadata_field_id": field_id,
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["entity_type"] == "material"
        assert body["sap_table"] == "MAKT"
        assert body["field_name"] == "MAKTX"
        assert body["data_type"] == "string"
        assert body["max_length"] is None  # 登记册未填，覆盖为 None
        assert body["field_label"] == "物料描述"  # 未显式给出 → 用登记册标签
        assert body["metadata_field_id"] == field_id
        assert body["metadata_field_label"] == "物料描述"
        assert body["metadata_view_section"] == "基本数据"

    def test_create_explicit_field_label_wins(self, data_client, metadata_db):
        """payload 显式给出 field_label 时保留，不被登记册覆盖。"""
        field_id = _field_id(metadata_db, "MEINS")
        resp = data_client.post(STANDARDS_BASE, json={
            "entity_type": "material",
            "sap_table": "MARA",
            "field_name": "IGNORED",
            "field_label": "自定义单位标签",
            "data_type": "string",
            "metadata_field_id": field_id,
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["field_name"] == "MEINS"
        assert body["field_label"] == "自定义单位标签"
        assert body["metadata_field_label"] == "基本计量单位"
        assert body["metadata_view_section"] == "采购视图"

    def test_create_unknown_metadata_field_returns_404(self, data_client, metadata_db):
        resp = data_client.post(STANDARDS_BASE, json={
            "entity_type": "material",
            "sap_table": "MARA",
            "field_name": "ZZNEW",
            "field_label": "新字段",
            "data_type": "string",
            "metadata_field_id": "no-such-id",
        })
        assert resp.status_code == 404
        assert resp.json()["detail"] == "关联的元数据字段不存在"

    def test_create_conflict_check_runs_after_carry_in(self, data_client, metadata_db):
        """409 唯一键检查在带入之后执行：payload 原键不冲突，带入后撞种子标准。"""
        field_id = _field_id(metadata_db, "MATNR")  # 带入后为 material/MARA/MATNR
        resp = data_client.post(STANDARDS_BASE, json={
            "entity_type": "customer",   # 原 (customer, KNA1, KUNNR) 并不冲突
            "sap_table": "KNA1",
            "field_name": "KUNNR",
            "field_label": "客户编码",
            "data_type": "string",
            "metadata_field_id": field_id,
        })
        assert resp.status_code == 409
        assert "已存在" in resp.json()["detail"]

    def test_create_without_metadata_field_id_unchanged(self, data_client, metadata_db):
        """旧行为回归：不传 metadata_field_id 时原样落库，带出字段为 None。"""
        resp = data_client.post(STANDARDS_BASE, json={
            "entity_type": "customer",
            "sap_table": "KNA1",
            "field_name": "KUNNR",
            "field_label": "客户编码",
            "data_type": "string",
            "max_length": 10,
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["field_name"] == "KUNNR"
        assert body["max_length"] == 10
        assert body["metadata_field_id"] is None
        assert body["metadata_field_label"] is None
        assert body["metadata_view_section"] is None

    def test_create_without_field_label_still_422(self, data_client, metadata_db):
        """旧行为回归：不传 metadata_field_id 且缺 field_label → 422。"""
        resp = data_client.post(STANDARDS_BASE, json={
            "entity_type": "customer",
            "sap_table": "KNA1",
            "field_name": "KUNNR",
            "data_type": "string",
        })
        assert resp.status_code == 422

    def test_update_carries_registry_fields(self, data_client, metadata_db):
        """PUT 带 metadata_field_id：身份键随登记册改写，field_label 未给则回填。"""
        standard_id = _standard_id(metadata_db, "LIFNR")  # supplier/LFA1/LIFNR 种子标准
        field_id = _field_id(metadata_db, "MAKTX")
        resp = data_client.put(
            f"{STANDARDS_BASE}/{standard_id}", json={"metadata_field_id": field_id}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["entity_type"] == "material"
        assert body["sap_table"] == "MAKT"
        assert body["field_name"] == "MAKTX"
        assert body["data_type"] == "string"
        assert body["field_label"] == "物料描述"
        assert body["metadata_field_id"] == field_id
        assert body["metadata_field_label"] == "物料描述"
        assert body["metadata_view_section"] == "基本数据"

    def test_update_explicit_field_label_wins(self, data_client, metadata_db):
        """PUT 显式给出 field_label 时保留。"""
        standard_id = _standard_id(metadata_db, "LIFNR")
        field_id = _field_id(metadata_db, "LIFNR")  # 同键带入，身份键不变
        resp = data_client.put(
            f"{STANDARDS_BASE}/{standard_id}",
            json={"metadata_field_id": field_id, "field_label": "供应商编号（治理）"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["field_name"] == "LIFNR"
        assert body["field_label"] == "供应商编号（治理）"
        assert body["metadata_field_label"] == "供应商编号"

    def test_update_unknown_metadata_field_returns_404(self, data_client, metadata_db):
        standard_id = _standard_id(metadata_db, "LIFNR")
        resp = data_client.put(
            f"{STANDARDS_BASE}/{standard_id}", json={"metadata_field_id": "no-such-id"}
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "关联的元数据字段不存在"

    def test_update_conflict_after_carry_in_returns_409(self, data_client, metadata_db):
        """PUT 带入后撞另一条标准的唯一键 → 409（排除自身）。"""
        standard_id = _standard_id(metadata_db, "LIFNR")
        field_id = _field_id(metadata_db, "MATNR")  # 带入后撞 material/MARA/MATNR 种子标准
        resp = data_client.put(
            f"{STANDARDS_BASE}/{standard_id}", json={"metadata_field_id": field_id}
        )
        assert resp.status_code == 409
        assert "已存在" in resp.json()["detail"]

    def test_update_null_metadata_field_id_unlinks(self, data_client, metadata_db):
        """PUT metadata_field_id=null 解除关联：关联清除，但已带入的字段值保留。"""
        standard_id = _standard_id(metadata_db, "LIFNR")
        field_id = _field_id(metadata_db, "LIFNR")
        # 先建立关联（同键带入，身份键不变）
        resp = data_client.put(
            f"{STANDARDS_BASE}/{standard_id}", json={"metadata_field_id": field_id}
        )
        assert resp.status_code == 200
        assert resp.json()["metadata_field_id"] == field_id

        # 显式置 null 解除关联
        resp = data_client.put(
            f"{STANDARDS_BASE}/{standard_id}", json={"metadata_field_id": None}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["metadata_field_id"] is None
        assert body["metadata_field_label"] is None
        assert body["metadata_view_section"] is None
        # 解除关联不回滚字段值
        assert body["entity_type"] == "supplier"
        assert body["sap_table"] == "LFA1"
        assert body["field_name"] == "LIFNR"
        assert body["field_label"] == "供应商编号"

    def test_update_without_metadata_field_id_unchanged(self, data_client, metadata_db):
        """旧行为回归：普通 PUT 不改身份键，不带出元数据字段。"""
        standard_id = _standard_id(metadata_db, "LIFNR")
        resp = data_client.put(
            f"{STANDARDS_BASE}/{standard_id}", json={"field_label": "供应商编号（改）"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["entity_type"] == "supplier"
        assert body["sap_table"] == "LFA1"
        assert body["field_name"] == "LIFNR"
        assert body["field_label"] == "供应商编号（改）"
        assert body["metadata_field_id"] is None
        assert body["metadata_field_label"] is None

    def test_list_carries_metadata_labels(self, client, metadata_db):
        """列表端点批量带出标签 / 视图分区（无 N+1）；未关联的为 None。"""
        field_id = _field_id(metadata_db, "MATNR")
        standard = metadata_db.query(models.DataStandard).filter(
            models.DataStandard.field_name == "MATNR"
        ).one()
        standard.metadata_field_id = field_id
        metadata_db.commit()

        body = client.get(STANDARDS_BASE).json()
        assert body["total"] == 2
        by_name = {i["field_name"]: i for i in body["items"]}
        assert by_name["MATNR"]["metadata_field_id"] == field_id
        assert by_name["MATNR"]["metadata_field_label"] == "物料编码"
        assert by_name["MATNR"]["metadata_view_section"] == "基本数据"
        assert by_name["LIFNR"]["metadata_field_id"] is None
        assert by_name["LIFNR"]["metadata_field_label"] is None
        assert by_name["LIFNR"]["metadata_view_section"] is None
