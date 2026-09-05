"""Tests for the suspected-duplicate / naming-convention detector (SPEC §1.6, §2.7, §5.3).

Covers both axes the spec demands:

* positive  — exact-name duplicates, Chinese-aware near duplicates / naming variants,
  naming-convention violations;
* negative  — clearly unrelated names and *below-threshold* look-alikes must not be
  flagged, suppliers must never match customers, inactive rows are out of scope;
* §5.3 hard rule — candidate narrowing happens in SQL (parameterised ``ILIKE`` on
  high-discrimination tokens), never as an O(n²) cross join. See
  :class:`TestPrefilterIsUsed`.
"""
import json
from typing import Dict, Iterable, List, Set

import pytest
from sqlalchemy import event

from app import models
from app.services.duplicate_detector import (
    DEFAULT_NAMING_CONVENTIONS,
    DEFAULT_SIMILARITY_THRESHOLD,
    DetectionKind,
    DuplicateDetectionLimitError,
    DuplicateDetector,
    DuplicateFinding,
    ErrorType,
    NamingConvention,
    normalize_name,
    tokenize_name,
)

ACTIVE = "active"
INACTIVE = "inactive"


# ========== helpers ==========

def add_material(
    db,
    code: str,
    name: str,
    *,
    status: str = ACTIVE,
    attributes: Dict[str, str] | None = None,
) -> models.MaterialRecord:
    record = models.MaterialRecord(
        material_code=code,
        material_name=name,
        attributes=attributes or {"MEINS": "PC"},
        status=status,
    )
    db.add(record)
    return record


def add_partner(
    db,
    entity_type: str,
    code: str,
    name: str,
    *,
    status: str = ACTIVE,
) -> models.PartnerRecord:
    record = models.PartnerRecord(
        entity_type=entity_type,
        partner_code=code,
        partner_name=name,
        attributes={"CITY1": "上海"},
        status=status,
    )
    db.add(record)
    return record


def detect(db, entity_type: str, **kwargs) -> List[DuplicateFinding]:
    return DuplicateDetector(db).detect(entity_type, **kwargs)


def detect_stats(db, entity_type: str, **kwargs):
    return DuplicateDetector(db).detect_with_stats(entity_type, **kwargs)


def duplicate_findings(findings: Iterable[DuplicateFinding]) -> List[DuplicateFinding]:
    return [f for f in findings if f.error_type is ErrorType.DUPLICATE]


def naming_findings(findings: Iterable[DuplicateFinding]) -> List[DuplicateFinding]:
    return [f for f in findings if f.error_type is ErrorType.NAMING]


def pairs_by_code(findings: Iterable[DuplicateFinding]) -> Set[frozenset]:
    """Unordered (code, matched_code) pairs — makes "nothing extra was flagged" assertable."""
    return {
        frozenset((f.evidence["entity_code"], f.evidence["matched_code"]))
        for f in findings
        if f.error_type is ErrorType.DUPLICATE
    }


def rules_by_name(findings: Iterable[DuplicateFinding]) -> Dict[str, Set[str]]:
    out: Dict[str, Set[str]] = {}
    for f in findings:
        if f.error_type is ErrorType.NAMING:
            out.setdefault(f.entity_label, set()).add(f.evidence["rule_code"])
    return out


@pytest.fixture()
def materials(db):
    """Material scope with one exact duplicate, one naming variant, and clean negatives."""
    add_material(db, "M10010", "环氧富锌底漆 25kg/桶")
    add_material(db, "M10011", "环氧富锌底漆25KG/桶")          # exact duplicate of M10010
    add_material(db, "M10012", "低压气动阀门 Z642Y 1.6MPa C DN150")
    add_material(db, "M10013", "低压气动阀门 Z642Y 1.6MPa C DN200")  # near duplicate
    add_material(db, "M10014", "环氧防腐涂料 20kg")            # unrelated
    add_material(db, "M10015", "手扳葫芦 HHD-3 3t")            # unrelated
    add_material(db, "M10016", "深沟球轴承 6205 2RS")          # look-alike, below threshold
    add_material(db, "M10017", "深沟球轴承 6205 ZZ")           # look-alike, below threshold
    db.commit()
    return db


# ========== 规范化与中文感知分词 ==========

class TestNormalizationAndTokenizing:
    def test_case_width_and_punctuation_are_folded(self):
        assert normalize_name(" 六角螺栓 M8×30 镀锌 ") == normalize_name("六角螺栓m8x30镀锌")
        assert normalize_name("Ｍ８") == "m8"

    def test_unterminated_input_is_safe(self):
        assert normalize_name(None) == ""
        assert tokenize_name(None) == set()
        assert tokenize_name("！！！") == set()

    def test_legal_form_suffix_is_not_a_similarity_diluter(self):
        """华成精密机械有限公司 vs 华成精密机械 must land on the same token set."""
        assert tokenize_name("华成精密机械有限公司") == tokenize_name("华成精密机械")

    def test_chunking_is_bigram_based_for_cjk_and_split_for_alnum(self):
        assert tokenize_name("深沟球轴承 6205 2RS") == {
            "深沟",
            "沟球",
            "球轴",
            "轴承",
            "62052",  # 去空白后数字段合并
            "rs",
        }
        assert tokenize_name("六角螺栓") == {"六角", "角螺", "螺栓"}
        assert tokenize_name("阀") == {"阀"}

    def test_unrelated_names_share_no_token(self):
        assert not tokenize_name("六角螺栓 M8×30 镀锌") & tokenize_name("环氧防腐涂料 20kg")


# ========== 精确重复 ==========

class TestExactDuplicate:
    def test_same_normalized_name_is_flagged_with_full_similarity(self, seeded_db):
        """seeded_db 已含「六角螺栓 M8×30 镀锌」，再录一条只差空格/大小写的记录。"""
        add_partner(seeded_db, "supplier", "1000000002", "上海电气自动化设备有限公司")
        add_partner(seeded_db, "supplier", "1000000003", "上海电气自动化设备有限公司 ")
        seeded_db.commit()

        findings = duplicate_findings(detect(seeded_db, "supplier"))
        exact = [f for f in findings if f.detect_kind is DetectionKind.EXACT_NAME]

        assert len(exact) == 1
        finding = exact[0]
        assert finding.similarity == 1.0
        assert finding.severity == "error"
        assert finding.error_type is ErrorType.DUPLICATE
        assert finding.matched_entity_id is not None
        assert finding.evidence["strategy"] == "exact_name"
        assert finding.evidence["normalized_name"] == "上海电气自动化设备有限公司"
        assert finding.dedupe_key == (
            finding.entity_id,
            finding.matched_entity_id,
            "duplicate",
        )

    def test_keeper_is_earliest_record_and_suggestion_is_deactivate_not_delete(self, materials):
        """§2.7：处置建议 =「保留 X / 停用 Y」，停用优先于删除，且一律人工执行。"""
        exact = [
            f
            for f in duplicate_findings(detect(materials, "material"))
            if f.detect_kind is DetectionKind.EXACT_NAME
        ]
        assert len(exact) == 1
        finding = exact[0]
        assert finding.entity_id != finding.matched_entity_id
        assert finding.matched_label == "环氧富锌底漆 25kg/桶"  # keeper = created first
        assert "建议保留 M10010 / 停用 M10011" in finding.evidence["suggestion"]
        assert "删除" not in finding.evidence["suggestion"]
        assert "人工执行" in finding.description

    def test_three_way_duplicate_group_emits_two_findings(self, materials):
        add_material(materials, "M10018", "环氧富锌底漆  25KG /桶")  # consecutive space
        materials.commit()
        exact = [
            f
            for f in duplicate_findings(detect(materials, "material"))
            if f.detect_kind is DetectionKind.EXACT_NAME
        ]
        assert len(exact) == 2
        assert {f.evidence["matched_code"] for f in exact} == {"M10010"}


# ========== 近重复 / 命名变体 ==========

class TestNearDuplicate:
    def test_chinese_naming_variant_is_flagged(self, seeded_db):
        """华成精密机械有限公司 vs 华成精密机械（§1.6 要求的中文场景）。"""
        add_partner(seeded_db, "supplier", "1000000002", "华成精密机械")
        seeded_db.commit()

        findings = duplicate_findings(detect(seeded_db, "supplier"))
        assert len(findings) == 1
        finding = findings[0]
        assert finding.detect_kind is DetectionKind.TOKEN_OVERLAP
        assert DEFAULT_SIMILARITY_THRESHOLD <= finding.similarity < 1.0
        assert finding.severity == "warning"
        # 判定理由必须可解释
        assert finding.evidence["shared_tokens"]
        assert finding.evidence["normalized_entity_name"] != finding.evidence["normalized_matched_name"]
        assert "duplicate_check" == finding.evidence["rule"]

    def test_spec_example_variant_pair_is_flagged(self, materials):
        """SPEC §1.6.1 示例：DN150 / DN200 同族阀门应作为「可能重复」候选输出。"""
        finding = next(
            f
            for f in duplicate_findings(detect(materials, "material"))
            if f.detect_kind is DetectionKind.TOKEN_OVERLAP
        )
        assert {f.evidence["entity_code"] for f in [finding]} == {"M10013"}
        assert finding.evidence["matched_code"] == "M10012"
        assert finding.similarity >= 0.8

    def test_similarity_threshold_is_configurable(self, materials):
        """放宽阈值后，2RS/ZZ 这种同族不同型号的 look-alike 才会浮出来。"""
        strict = pairs_by_code(detect(materials, "material"))
        assert frozenset({"M10016", "M10017"}) not in strict

        relaxed = pairs_by_code(detect(materials, "material", similarity_threshold=0.6))
        assert frozenset({"M10016", "M10017"}) in relaxed

    def test_threshold_boundary_validation(self, materials):
        for bad in (0.0, -1.0, 1.5):
            with pytest.raises(ValueError):
                detect(materials, "material", similarity_threshold=bad)


# ========== 负例：不该报的不能报 ==========

class TestNegativeCases:
    def test_unrelated_names_are_not_flagged(self, materials):
        """整个物料作用域里只允许出现设计中埋入的两对重复。"""
        findings = duplicate_findings(detect(materials, "material"))
        assert pairs_by_code(findings) == {
            frozenset({"M10010", "M10011"}),
            frozenset({"M10012", "M10013"}),
        }

    def test_clean_records_produce_no_findings_at_all(self, db):
        add_material(db, "M20001", "六角螺栓 M8×30 镀锌")
        add_material(db, "M20002", "环氧防腐涂料 20kg")
        add_material(db, "M20003", "手扳葫芦 HHD-3 3t")
        db.commit()
        assert detect(db, "material") == []

    def test_suppliers_never_match_customers(self, db):
        """partner_records 共表存储，entity_type 必须把作用域切开。"""
        add_partner(db, "supplier", "3000000001", "华成精密机械有限公司")
        add_partner(db, "customer", "4000000001", "华成精密机械有限公司")
        db.commit()
        assert detect(db, "supplier") == []
        assert detect(db, "customer") == []

    def test_inactive_records_are_out_of_scope(self, db):
        add_partner(db, "supplier", "3000000002", "海天精密铸造有限公司")
        add_partner(db, "supplier", "3000000003", "海天精密铸造", status=INACTIVE)
        db.commit()
        assert detect(db, "supplier") == []
        assert len(detect(db, "supplier", include_inactive=True)) == 1

    def test_entity_ids_narrows_the_scope(self, materials):
        scoped = duplicate_findings(
            detect(
                materials,
                "material",
                entity_ids=[
                    m.id
                    for m in materials.query(models.MaterialRecord)
                    .filter(models.MaterialRecord.material_code.in_(["M10012", "M10013"]))
                    .all()
                ],
            )
        )
        assert pairs_by_code(scoped) == {frozenset({"M10012", "M10013"})}

    def test_empty_entity_ids_is_rejected(self, materials):
        with pytest.raises(ValueError):
            detect(materials, "material", entity_ids=[])


# ========== 命名规范违例 ==========

class TestNamingConventions:
    @pytest.fixture()
    def dirty(self, db):
        add_material(db, "M30001", "测试备件")
        add_material(db, "M30002", "待定")
        add_material(db, "M30003", "Ｍ８内六角扳手")
        add_material(db, "M30004", "12345")
        db.commit()
        return db

    def test_each_planted_violation_is_detected(self, dirty):
        rules = rules_by_name(detect(dirty, "material"))
        assert rules == {
            "测试备件": {"placeholder_text"},
            "待定": {"placeholder_text", "too_short"},
            "Ｍ８内六角扳手": {"fullwidth_alnum"},
            "12345": {"pure_code_like"},
        }

    def test_convention_finding_shape(self, dirty):
        finding = next(f for f in detect(dirty, "material") if f.entity_label == "测试备件")
        assert finding.error_type is ErrorType.NAMING
        assert finding.detect_kind is DetectionKind.CONVENTION
        assert finding.matched_entity_id is None      # §2.7 单实体问题无匹配对象
        assert finding.matched_label is None
        assert finding.similarity == 0.0
        assert finding.severity == "error"
        assert finding.field_name == "MAKTX"          # §10.1 物料描述
        assert finding.evidence["column"] == "material_name"
        assert finding.evidence["rule"] == "naming_convention:placeholder_text"
        assert "占位" in finding.evidence["violation"]
        assert finding.dedupe_key == (finding.entity_id, None, "naming")

    def test_conventions_are_replaceable(self, dirty):
        only_placeholder = [c for c in DEFAULT_NAMING_CONVENTIONS if c.code == "placeholder_text"]
        rules = rules_by_name(detect(dirty, "material", conventions=only_placeholder))
        assert rules == {"测试备件": {"placeholder_text"}, "待定": {"placeholder_text"}}

    def test_clean_stock_has_no_naming_violations(self, materials):
        assert naming_findings(detect(materials, "material")) == []

    def test_partner_name_field_is_reported_for_partners(self, db):
        add_partner(db, "supplier", "3000000009", "临时供应商")
        db.commit()
        finding = naming_findings(detect(db, "supplier"))[0]
        assert finding.field_name == "NAME1"
        assert finding.evidence["column"] == "partner_name"


# ========== §5.3：候选必须先在 SQL 侧收窄 ==========

class TestPrefilterIsUsed:
    def _capture(self, db, entity_type: str, **kwargs):
        engine = db.get_bind()
        captured: List = []

        def listener(conn, cursor, statement, parameters, context, executemany):
            captured.append((statement, parameters))

        event.listen(engine, "before_cursor_execute", listener)
        try:
            findings, stats = detect_stats(db, entity_type, **kwargs)
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        return findings, stats, captured

    def test_candidates_come_from_parameterised_ilike_not_from_python_scan(self, materials):
        _findings, stats, captured = self._capture(materials, "material")
        selects = [(s, p) for s, p in captured if s.strip().upper().startswith("SELECT")]
        ilike = [(s, p) for s, p in selects if "LIKE" in s.upper()]

        assert ilike, "近重复检测未使用 SQL 预筛"
        statement, parameters = ilike[0]
        # 词元只能出现在绑定参数里，绝不允许拼进 SQL 文本
        assert "%" not in statement, f"LIKE 模式被拼进了 SQL 文本: {statement}"
        patterns = [v for v in _flat_params(parameters) if isinstance(v, str)]
        assert any(p.startswith("%") and p.endswith("%") for p in patterns), patterns
        assert not any("阀门" in s or "底漆" in s for s, _ in selects), "SQL 文本被拼接了字面量"
        assert stats.prefilter_queries == len(ilike)

    def test_no_statement_is_a_cross_join(self, materials):
        _findings, _stats, captured = self._capture(materials, "material")
        for statement, _params in captured:
            upper = " ".join(statement.upper().split())
            assert " JOIN " not in upper, f"出现自连接: {statement}"
            from_clause = upper.split(" FROM ", 1)[1].split(" WHERE ", 1)[0] if " FROM " in upper else ""
            assert from_clause.count("MATERIAL_RECORDS") <= 1, f"疑似两两比较查询: {statement}"

    def test_scored_pairs_are_bounded_not_quadratic(self, materials):
        _findings, stats, _captured = self._capture(materials, "material")
        n = stats.total_records
        assert n == 8
        assert stats.full_pairwise_pairs == n * (n - 1) // 2
        assert stats.pairs_scored < stats.full_pairwise_pairs
        assert stats.pairs_scored <= stats.probes_issued * 50  # max_candidates_per_probe
        assert stats.prefilter_queries == stats.probes_issued
        assert stats.probes_skipped + stats.probes_issued == n
        assert stats.exact_duplicate_groups == 1
        assert stats.distinct_normalized_names < n

    def test_candidate_cap_is_enforced(self, materials):
        _findings, stats, _captured = self._capture(
            materials, "material", max_candidates_per_probe=1
        )
        assert stats.candidates_fetched <= stats.probes_issued
        assert stats.pairs_scored <= stats.probes_issued

    def test_records_without_shared_tokens_issue_no_prefilter_query(self, db):
        add_material(db, "M40001", "六角螺栓 M8×30 镀锌")
        add_material(db, "M40002", "环氧防腐涂料 20kg")
        db.commit()
        _findings, stats, captured = self._capture(db, "material")
        assert stats.probes_issued == 0
        assert stats.prefilter_queries == 0
        assert stats.pairs_scored == 0
        # 只有一条作用域投影查询，没有任何按记录的预筛
        selects = [s for s, _ in captured if s.strip().upper().startswith("SELECT")]
        assert len(selects) == 1

    def test_detector_never_writes(self, materials):
        engine = materials.get_bind()
        seen: List[str] = []

        def listener(conn, cursor, statement, parameters, context, executemany):
            seen.append(statement)

        event.listen(engine, "before_cursor_execute", listener)
        try:
            detect(materials, "material")
        finally:
            event.remove(engine, "before_cursor_execute", listener)
        assert [s for s in seen if s.strip().upper().startswith(("INSERT", "UPDATE", "DELETE"))] == []


def _flat_params(parameters) -> Iterable:
    if parameters is None:
        return ()
    if isinstance(parameters, dict):
        return parameters.values()
    flat: List = []
    for item in parameters:
        flat.extend(item if isinstance(item, (list, tuple)) else [item])
    return flat


# ========== 入口与健壮性 ==========

class TestEntryPointAndGuards:
    def test_unknown_entity_type_is_rejected(self, db):
        with pytest.raises(ValueError, match="Unsupported entity_type"):
            detect(db, "golden_record")

    def test_batch_limit_is_enforced(self, materials):
        with pytest.raises(DuplicateDetectionLimitError):
            detect(materials, "material", max_entities=5)

    def test_empty_scope_returns_nothing(self, db):
        findings, stats = detect_stats(db, "customer")
        assert findings == []
        assert stats.total_records == 0
        assert stats.full_pairwise_pairs == 0

    def test_findings_are_json_ready_for_suspected_error_details(self, materials):
        finding = detect(materials, "material")[0]
        payload = finding.to_dict()
        assert payload["error_type"] in {"duplicate", "naming"}
        assert payload["detect_kind"] in {"exact_name", "token_overlap", "convention"}
        assert json.loads(json.dumps(payload, ensure_ascii=False))["entity_id"] == finding.entity_id

    def test_duplicate_findings_are_deterministic(self, materials):
        first = [f.dedupe_key for f in detect(materials, "material")]
        second = [f.dedupe_key for f in detect(materials, "material")]
        assert first == second

    def test_dedupe_keys_are_unique_per_combination(self, materials):
        keys = [f.dedupe_key for f in detect(materials, "material")]
        assert len(keys) == len(set(keys))

    def test_module_level_entry_matches_class_api(self, materials):
        from app.services.duplicate_detector import (
            detect_duplicates,
            detect_duplicates_with_stats,
        )

        via_function = detect_duplicates(materials, "material")
        via_class = detect(materials, "material")
        assert [f.dedupe_key for f in via_function] == [f.dedupe_key for f in via_class]

        findings, stats = detect_duplicates_with_stats(materials, "material")
        assert stats.entity_type == "material"
        assert [f.dedupe_key for f in findings] == [f.dedupe_key for f in via_class]

    def test_custom_naming_convention_object_is_honoured(self, materials):
        add_material(materials, "M90001", "六角螺栓 M8×30 镀锌")
        materials.commit()
        rule = NamingConvention(
            code="no_bolt_wording",
            label="物料名称不得含「螺栓」",
            severity="warning",
            check=lambda raw, normalized: "含「螺栓」" if "螺栓" in normalized else None,
        )
        findings = naming_findings(detect(materials, "material", conventions=[rule]))
        assert [(f.entity_label, f.severity) for f in findings] == [
            ("六角螺栓 M8×30 镀锌", "warning")
        ]
        assert findings[0].evidence["rule"] == "naming_convention:no_bolt_wording"


# ========== 规模下的召回与开销 ==========

CATEGORY_WORDS = (
    "液压阀",
    "轴承座",
    "减速机",
    "密封圈",
    "电缆桥架",
    "温度传感器",
    "法兰盘",
    "齿轮泵",
    "变频器",
    "伺服电机",
    "空气过滤器",
    "电磁阀",
    "液位计",
    "联轴器",
    "直线导轨",
    "千斤顶",
)

#: (keeper_code, keeper_name, suspect_code, suspect_name, expected detect_kind)
PLANTED_PAIRS = (
    ("S001", "高压球阀 Q11F-16P DN25", "S011", "高压球阀Q11F16P DN25", "exact_name"),
    ("S002", "推力球轴承 51205", "S012", "推力球轴承5120 5", "exact_name"),
    ("S003", "行星减速机 PLF120-64", "S013", "行星减速机 PLF120-100", "token_overlap"),
    ("S004", "氟橡胶密封圈 DN80", "S014", "氟橡胶密封圈 DN80X", "token_overlap"),
)


class TestScaleAndRecall:
    """预筛必须有界，同时不能把埋进存量里的真重复筛掉（§5.3 的召回侧）。"""

    @pytest.fixture()
    def stock(self, db):
        for keeper_code, keeper_name, suspect_code, suspect_name, _kind in PLANTED_PAIRS:
            add_material(db, keeper_code, keeper_name)
            add_material(db, suspect_code, suspect_name)
        # 噪声：160 条互不相同的正常名称，只有品类词与无区分度的骨架词相同
        for i in range(160):
            word = CATEGORY_WORDS[i % len(CATEGORY_WORDS)]
            add_material(db, f"N{i:04d}", f"{word} XQ{i:03d}W{i}")
        db.commit()
        return db

    def test_planted_duplicates_are_recalled_with_no_false_positives(self, stock):
        findings = duplicate_findings(detect(stock, "material"))
        assert pairs_by_code(findings) == {
            frozenset((keeper, suspect))
            for keeper, _kn, suspect, _sn, _k in PLANTED_PAIRS
        }

    def test_each_pair_is_classified_by_the_right_strategy(self, stock):
        by_pair = {
            (f.evidence["matched_code"], f.evidence["entity_code"]): f
            for f in duplicate_findings(detect(stock, "material"))
        }
        for keeper, _kn, suspect, _sn, kind in PLANTED_PAIRS:
            finding = by_pair[(keeper, suspect)]
            assert finding.detect_kind.value == kind
            if kind == "exact_name":
                assert finding.similarity == 1.0
                assert finding.severity == "error"
            else:
                assert DEFAULT_SIMILARITY_THRESHOLD <= finding.similarity < 1.0
                assert finding.evidence["prefilter_mode"] == "sql_ilike"

    def test_work_stays_bounded_at_scale(self, stock):
        _findings, stats = detect_stats(stock, "material")
        assert stats.total_records == 168
        assert stats.full_pairwise_pairs == 168 * 167 // 2
        # 无区分度的词元（品类词 DF=10、骨架词 DF=160）不会被选作预筛键
        assert stats.probes_issued <= 12
        assert stats.probes_skipped >= stats.total_records - 12
        assert stats.pairs_scored < stats.full_pairwise_pairs / 20
        assert stats.pairs_scored <= stats.probes_issued * 50
        assert stats.exact_duplicate_groups == 2
        assert stats.prefilter_queries == stats.probes_issued
