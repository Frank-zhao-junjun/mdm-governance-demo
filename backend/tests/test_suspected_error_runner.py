"""疑似错误检测编排测试（SPEC §2.7 重检去重语义 + §3.3 Phase 3 验收）。"""
import time
from datetime import timedelta

import pytest

from app import models
from app.services import duplicate_detector, suspected_error_runner


@pytest.fixture(scope="function")
def suspect_db(seeded_db):
    """seeded_db + 重复/近似/naming 违例脏记录（material + supplier）。

    material：M1234 与 M10001 近似（duplicate）；M10021 占位文本、M10022
    全角字母数字（naming）；M10099 供 auto-close 场景。
    supplier：1000000019 与 1000000008 完全重名（exact duplicate，
    created_at 显式错开保证 keeper 确定为 0008）。
    """
    db = seeded_db
    now = models._now_utc()
    db.add(models.MaterialRecord(
        material_code="M1234", material_name="六角螺栓 M8x30 热镀锌",
        attributes={"MTART": "ROH"}, status="active",
    ))
    db.add(models.MaterialRecord(
        material_code="M10021", material_name="测试物料 待补充",
        attributes={"MTART": "ROH"}, status="active",
    ))
    db.add(models.MaterialRecord(
        material_code="M10022", material_name="ＡＢＳ树脂 ＰＣ－２",
        attributes={"MTART": "ROH"}, status="active",
    ))
    db.add(models.MaterialRecord(
        material_code="M10099", material_name="测试占位名称",
        attributes={"MTART": "ROH"}, status="active",
    ))
    db.add(models.PartnerRecord(
        entity_type="supplier", partner_code="1000000008",
        partner_name="广州密封件工业公司", attributes={}, status="active",
        created_at=now - timedelta(days=1),
    ))
    db.add(models.PartnerRecord(
        entity_type="supplier", partner_code="1000000019",
        partner_name="广州密封件工业公司", attributes={}, status="active",
        created_at=now,
    ))
    db.commit()
    return db


def _run(db, entity_type="material", **kwargs):
    return suspected_error_runner.detect_suspected_errors(
        db, entity_type, detected_by="data001", **kwargs
    )


def _material_id(db, code):
    return (
        db.query(models.MaterialRecord)
        .filter(models.MaterialRecord.material_code == code)
        .first()
        .id
    )


def _supplier_id(db, code):
    return (
        db.query(models.PartnerRecord)
        .filter(
            models.PartnerRecord.entity_type == "supplier",
            models.PartnerRecord.partner_code == code,
        )
        .first()
        .id
    )


def _rows(db, entity_type="material"):
    return (
        db.query(models.SuspectedError)
        .filter(models.SuspectedError.entity_type == entity_type)
        .all()
    )


# ========== 创建与落库 ==========

def test_creates_rows_for_duplicate_and_naming(suspect_db):
    db = suspect_db
    counters = _run(db)
    # material：M1234↔M10001 近重复 1 + naming 违例 3（占位 / 全角 / 测试占位名称）
    assert counters == {
        "created": 4, "refreshed": 0,
        "skipped_false_positive": 0, "auto_closed": 0, "total_pending": 4,
    }

    rows = _rows(db)
    assert {r.error_type for r in rows} == {"duplicate", "naming"}
    assert all(r.status == "pending" and r.detected_by == "data001" for r in rows)

    dup = next(r for r in rows if r.error_type == "duplicate")
    assert dup.severity == "warning"  # 近重复档位
    assert dup.details["similarity"] >= 0.8
    assert "suggestion" in dup.details and "keeper_rule" in dup.details

    naming = next(r for r in rows if r.error_type == "naming")
    assert naming.matched_entity_id is None
    assert naming.details["rule_code"] in {"placeholder_text", "fullwidth_alnum"}


def test_exact_duplicate_keeper_direction(suspect_db):
    """exact duplicate：keeper=更早创建方（0008），suspect=0019（§2.7 停用优先）。"""
    db = suspect_db
    _run(db, "supplier")
    dup = next(r for r in _rows(db, "supplier") if r.error_type == "duplicate")
    assert dup.entity_id == _supplier_id(db, "1000000019")
    assert dup.matched_entity_id == _supplier_id(db, "1000000008")
    assert dup.details["similarity"] == 1.0
    assert dup.details["suggestion"] == "建议保留 1000000008 / 停用 1000000019"


# ========== 重检去重（SPEC §2.7 硬性验收：重跑不产生重复 pending）==========

def test_rerun_refreshes_instead_of_duplicating(suspect_db):
    db = suspect_db
    _run(db)
    before = {r.id: r.detected_at for r in _rows(db)}
    time.sleep(0.02)

    counters = _run(db)
    assert counters["created"] == 0
    assert counters["refreshed"] == 4
    assert counters["total_pending"] == 4

    rows = _rows(db)
    assert len(rows) == 4  # 无重复 pending
    for row in rows:
        assert row.detected_at > before[row.id]  # SPEC L428：刷新 detected_at


def test_naming_multiple_violations_aggregate_to_one_row(suspect_db):
    """同实体多条规范违例先按去重键聚合（后写覆盖），行数不随 finding 漂移。"""
    db = suspect_db
    db.add(models.MaterialRecord(
        material_code="M10077", material_name="测试ＡＢＣ",
        attributes={"MTART": "ROH"}, status="active",
    ))
    db.commit()
    _run(db)
    naming_rows = [
        r for r in _rows(db)
        if r.error_type == "naming" and r.entity_id == _material_id(db, "M10077")
    ]
    assert len(naming_rows) == 1


# ========== 误报白名单与终态（三键粒度）==========

def test_false_positive_skipped_and_counted(suspect_db):
    db = suspect_db
    _run(db)
    dup = next(r for r in _rows(db) if r.error_type == "duplicate")
    dup.status = "false_positive"
    dup.resolution_note = "人工判定为误报"
    db.commit()

    counters = _run(db)
    assert counters["skipped_false_positive"] == 1
    assert counters["created"] == 0
    assert counters["total_pending"] == 3

    row = db.query(models.SuspectedError).filter(
        models.SuspectedError.id == dup.id
    ).first()
    assert row.status == "false_positive"
    assert row.resolution_note == "人工判定为误报"  # 白名单行不被刷新触碰


def test_terminal_rows_untouched_by_rerun(suspect_db):
    db = suspect_db
    _run(db)
    naming = next(r for r in _rows(db) if r.error_type == "naming")
    naming.status = "confirmed"
    naming.resolved_by = "data001"
    naming.resolution_note = "已确认为问题"
    naming.resolved_at = models._now_utc()
    db.commit()
    detected_at_before = naming.detected_at

    counters = _run(db)
    assert counters["refreshed"] == 3  # 终态行不参与刷新
    assert counters["created"] == 0

    row = db.query(models.SuspectedError).filter(
        models.SuspectedError.id == naming.id
    ).first()
    assert row.status == "confirmed"
    assert row.resolution_note == "已确认为问题"
    assert row.detected_at == detected_at_before  # 终态行 detected_at 不动


# ========== 自动关闭（实体消失/失效）==========

def test_auto_close_inactive_entity(suspect_db):
    db = suspect_db
    _run(db)
    inactive = (
        db.query(models.MaterialRecord)
        .filter(models.MaterialRecord.material_code == "M10099")
        .first()
    )
    inactive.status = "inactive"
    db.commit()

    counters = _run(db)
    assert counters["auto_closed"] == 1
    row = next(
        r for r in _rows(db)
        if r.entity_id == inactive.id and r.error_type == "naming"
    )
    assert row.status == "resolved"
    assert row.resolution_note == suspected_error_runner.AUTO_CLOSE_NOTE
    assert row.resolved_by is None
    assert row.resolved_at is not None


def test_auto_close_deleted_entity(suspect_db):
    db = suspect_db
    _run(db)
    victim = (
        db.query(models.MaterialRecord)
        .filter(models.MaterialRecord.material_code == "M10099")
        .first()
    )
    db.delete(victim)
    db.commit()

    counters = _run(db)
    assert counters["auto_closed"] == 1
    row = next(r for r in _rows(db) if r.entity_id == victim.id)
    assert row.status == "resolved"


def test_auto_close_scans_all_pending_regardless_of_scope(suspect_db):
    """自动关闭恒按 entity_type 全量 pending 评估，不受 entity_ids 收窄。"""
    db = suspect_db
    _run(db, "supplier")
    keeper_id = _supplier_id(db, "1000000008")
    suspect_id = _supplier_id(db, "1000000019")

    # 0019 仍 active：收窄到 0008 的检测不得自动关闭指向 0019 的 pending 行
    counters = _run(db, "supplier", entity_ids=[keeper_id])
    assert counters["auto_closed"] == 0

    # 0019 失效：即使不在本次作用域内也要自动关闭
    suspect = db.query(models.PartnerRecord).filter(
        models.PartnerRecord.id == suspect_id
    ).first()
    suspect.status = "inactive"
    db.commit()
    counters = _run(db, "supplier", entity_ids=[keeper_id])
    assert counters["auto_closed"] == 1


# ========== 类型过滤与入参归一化 ==========

def test_error_types_filter(suspect_db):
    db = suspect_db
    counters = _run(db, error_types=["naming"])
    assert counters["created"] == 3
    assert all(r.error_type == "naming" for r in _rows(db))

    # error_types=[] 归一为全部支持类型：duplicate 补建 + naming 刷新
    counters = _run(db, error_types=[])
    assert counters["created"] == 1
    assert counters["refreshed"] == 3


def test_unsupported_error_type_raises(suspect_db):
    db = suspect_db
    with pytest.raises(suspected_error_runner.UnsupportedErrorType) as excinfo:
        _run(db, error_types=["classification"])
    assert "classification" in str(excinfo.value)
    with pytest.raises(suspected_error_runner.UnsupportedErrorType):
        _run(db, error_types=["duplicate", "unit"])


def test_empty_entity_ids_treated_as_full_scope(suspect_db):
    """entity_ids=[] 归一为 None：不触发检测器 ValueError，等价全量。"""
    db = suspect_db
    counters = _run(db, entity_ids=[])
    assert counters["created"] == 4


def test_entity_ids_subset(suspect_db):
    db = suspect_db
    counters = _run(
        db,
        entity_ids=[_material_id(db, "M10001"), _material_id(db, "M1234")],
    )
    assert counters["created"] == 1  # 只有近似重复对，naming 违例不在作用域


def test_total_pending_arithmetic(suspect_db):
    db = suspect_db
    counters = _run(db)
    assert counters["total_pending"] == 4

    dup = next(r for r in _rows(db) if r.error_type == "duplicate")
    dup.status = "false_positive"
    db.commit()
    counters = _run(db)
    assert counters["total_pending"] == 3


def test_detector_limit_error_propagates(suspect_db, monkeypatch):
    """检测器超限异常原样上抛（API 层映射 400）。"""

    def boom(self, entity_type, *, entity_ids=None, **kwargs):
        raise duplicate_detector.DuplicateDetectionLimitError("超限")

    monkeypatch.setattr(duplicate_detector.DuplicateDetector, "detect_with_stats", boom)
    with pytest.raises(duplicate_detector.DuplicateDetectionLimitError):
        _run(suspect_db)
