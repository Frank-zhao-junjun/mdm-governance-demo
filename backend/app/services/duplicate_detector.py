"""疑似重复 / 命名规范检测服务（SPEC v1.3 §1.6、§2.7、§5.3、Phase 3）.

本模块只产出**检测结论（findings）**，不做持久化：调用方（疑似错误 API）负责把
findings 映射为 ``SuspectedError`` 行（§2.7），包括重检去重与误报白名单
（``(entity_id, matched_entity_id, error_type)``）。因此每条 finding 都携带
§2.7 去重键所需的最小充分信息：``entity_id`` / ``matched_entity_id`` /
``error_type`` / ``similarity`` / ``evidence``。

覆盖的错误类型（§2.7 error_type）：

* ``duplicate`` —— 同一实体内的名称重复，两种判定（§1.6）：

  - ``exact_name``：规范化名称完全相同（相似度恒为 1.0）；
  - ``token_overlap``：近重复 / 命名变体，中文感知分词后的词元重叠度 ≥ 阈值
    （如「华成精密机械有限公司」vs「华成精密机械」）。

* ``naming`` —— 主数据名称本身违反命名规范（占位文本、全角字母数字、首尾空格等），
  属于单实体问题，``matched_entity_id`` 恒为 None、``similarity`` 恒为 0.0。

分类（classification）与计量单位（unit）类错误不由本模块产出：前者需要分类体系
数据源，后者由质量规则引擎（``quality_check_rules``）承接，同时避免与并行开发的
``quality_engine`` 产生耦合。

性能硬约束（§5.3、§8）
----------------------
**禁止全量两两比较**（jaccard O(n²) 不可接受）。执行分三步：

1. 一次投影查询取回作用域内的 (id, code, name, status, created_at)，只用于计算
   分词与文档频率（DF）—— O(n)，且不含任何两两比较；
2. 精确重复用规范化名称哈希分组（O(n)）；近重复则对每条探针记录发起一次
   **SQL 预筛**：``WHERE <作用域条件> AND id > :probe AND (name ILIKE :k1 OR …)``。
   预筛键 = 该记录中 DF 最低、且有区分度的词元（DF 必须落在
   ``(1, key_df_ceiling]``，``key_df_ceiling = min(blocking_max_df,
   max(2, ceil(作用域规模 × blocking_max_df_ratio)))``：DF=1 的私有词元召不回候选，
   覆盖过广的词元（「公司」「型号」）会把半张表拉进候选集），词元值全部通过
   SQLAlchemy **绑定参数**传入（配合 ``ESCAPE`` 转义 ``% _ \\``），并对候选数设上限
   ``max_candidates_per_probe``；
3. 只有预筛返回的这一个小候选集才在 Python 里打分。

因此打分对数上界为 ``probes × max_candidates_per_probe``，而不是 ``n(n-1)/2``。
``PrefilterStats`` 把这一事实暴露出来（``pairs_scored`` / ``full_pairwise_pairs`` /
``prefilter_queries``），便于测试与线上巡检断言预筛确实生效（见
``tests/test_duplicate_detector.py::TestPrefilterIsUsed``）。

召回率说明：SQL 预筛是**近似**的——若一对记录只在探针方未选中的低区分度词元上
相同，可能漏召回。这是以有界开销换取的可控取舍，可通过调大 ``max_blocking_keys`` /
``max_candidates_per_probe`` / ``blocking_max_df_ratio`` 提高召回。
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import models

__all__ = [
    "ENTITY_TYPES",
    "MAX_ENTITIES_PER_RUN",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "ErrorType",
    "DetectionKind",
    "DuplicateFinding",
    "PrefilterStats",
    "NamingConvention",
    "DEFAULT_NAMING_CONVENTIONS",
    "DuplicateDetectionLimitError",
    "DuplicateDetector",
    "normalize_name",
    "tokenize_name",
    "detect_duplicates",
    "detect_duplicates_with_stats",
]

# ========== 常量 ==========

ENTITY_MATERIAL = "material"
ENTITY_SUPPLIER = "supplier"
ENTITY_CUSTOMER = "customer"
ENTITY_TYPES: Tuple[str, ...] = (ENTITY_MATERIAL, ENTITY_SUPPLIER, ENTITY_CUSTOMER)

ACTIVE_STATUS = "active"

#: 单次同步检测上限，与质量检测一致（SPEC v1 限 5000 实体同步执行，超出提示分批）。
MAX_ENTITIES_PER_RUN = 5_000

#: 近重复默认阈值，与 §2.4 duplicate_check 的 rule_config.similarity_threshold 示例一致。
DEFAULT_SIMILARITY_THRESHOLD = 0.8

#: 1.0 专用于规范化名称完全相同的精确重复；文本相似但不完全相同最高报 0.99。
NEAR_DUPLICATE_CEILING = 0.99

_ESCAPE_CHAR = "\\"

#: 名称字段对应的 SAP 字段名（§10），写进 evidence 便于溯源到数据标准。
_SAP_NAME_FIELD = {
    ENTITY_MATERIAL: "MAKTX",
    ENTITY_SUPPLIER: "NAME1",
    ENTITY_CUSTOMER: "NAME1",
}


class ErrorType(str, PyEnum):
    """§2.7 ``suspected_errors.error_type`` 中由本模块负责取值的两个子集。"""

    DUPLICATE = "duplicate"
    NAMING = "naming"


class DetectionKind(str, PyEnum):
    """判定方式，写进 evidence，供审核页展示「对应规则 / 判定理由」。"""

    EXACT_NAME = "exact_name"
    TOKEN_OVERLAP = "token_overlap"
    CONVENTION = "convention"


class DuplicateDetectionLimitError(ValueError):
    """作用域实体数超过 ``max_entities``（§5.2），要求分批检测。"""


# ========== 文本规范化与中文感知分词 ==========

_CJK = "\u4e00-\u9fff\u3400-\u4dbf"
_KEEP_CHARS = re.compile(f"[{_CJK}a-z0-9×]+")
_ALNUM_RUN = re.compile(r"[a-z]+|[0-9]+")
_CJK_RUN = re.compile(f"[{_CJK}]+")

#: 组织形式/法律形式后缀：中文企业名中的低区分度成分。判近重复时先行剥离，
#: 因此「华成精密机械有限公司」与「华成精密机械」核心名一致可被识别为命名变体。
_LEGAL_FORM_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "集团有限公司",
    "股份公司",
    "集团公司",
    "分公司",
    "研究院",
    "研究所",
    "设计院",
    "事务所",
    "交易中心",
    "公司",
    "集团",
    "企业",
    "商行",
    "商店",
    "工作室",
    "中心",
    "厂",
)


def normalize_name(raw: Optional[str]) -> str:
    """规范化主数据名称：NFKC、小写、全角/数学符号统一、去空白与标点。

    「六角螺栓 M8×30 镀锌」与「 六角螺栓M8*30镀锌 」都会得到
    「六角螺栓m8x30镀锌」，精确重复即按此判定。
    """
    text = unicodedata.normalize("NFKC", raw or "").casefold()
    text = text.replace("×", "x").replace("\u2219", "-").replace("\u2212", "-")
    text = re.sub(r"[ \t\r\n\f\v]+", "", text)
    return "".join(_KEEP_CHARS.findall(text))


def _strip_legal_suffix(normalized: str) -> str:
    core = normalized
    for suffix in _LEGAL_FORM_SUFFIXES:
        if len(core) > len(suffix) and core.endswith(suffix):
            core = core[: -len(suffix)]
            break
    return core or normalized


def tokenize_name(raw: Optional[str]) -> Set[str]:
    """中文感知分词：拉丁/数字按字母段与数字段切分，中文按字符二元组（bigram）。

    先剥离组织形式后缀，避免「有限公司」这类通用尾巴把真实变体的相似度拉低。
    """
    core = _strip_legal_suffix(normalize_name(raw))
    if not core:
        return set()
    tokens: Set[str] = set(_ALNUM_RUN.findall(core))
    for run in _CJK_RUN.findall(core):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def _dice(a: Set[str], b: Set[str]) -> float:
    """Dice 系数 2|A∩B|/(|A|+|B|)，比 Jaccard 对长度差异更宽容。"""
    if not a or not b:
        return 0.0
    shared = len(a & b)
    if not shared:
        return 0.0
    return 2.0 * shared / (len(a) + len(b))


def _like_pattern(token: str) -> str:
    """把词元包成 LIKE 模式值并转义通配符。

    返回值是**绑定参数的值**，绝不拼进 SQL 文本（SPEC 安全约束：无 f-string SQL）。
    """
    escaped = token
    for ch in (_ESCAPE_CHAR, "%", "_"):
        escaped = escaped.replace(ch, _ESCAPE_CHAR + ch)
    return f"%{escaped}%"


def _preview(value: Optional[str], limit: int = 80) -> str:
    text = value if value is not None else ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _as_naive_utc(value: Optional[datetime]) -> datetime:
    """SQLite 的 DATETIME 不带时区，统一降为 naive-UTC 才能安全比较。"""
    if value is None:
        return datetime.min
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


# ========== 命名规范（规范性维度，§1.5.5） ==========

_PLACEHOLDER_CJK = re.compile(
    f"[{_CJK}]*(?:测试|待定|临时|示例|占位|待补充|待核实|未知|暂无|无名称)[{_CJK}]*"
)
_PLACEHOLDER_LATIN = re.compile(
    r"(?<![a-z0-9])(?:tbd|todo|test|null|nil|x{3,}|n/?a|\?+)(?![a-z0-9])"
)
_FULLWIDTH_ALNUM = re.compile(r"[Ａ-Ｚａ-ｚ０-９]")
_FORBIDDEN_CHARS = re.compile(r"[&|#@\\<>\uffe3\uff06\uff5c\uff20\uff3c\uff1c\uff1e]")
_REPEATED_CHAR = re.compile(r"^(.)\1{2,}$")
_PURE_CODE = re.compile(r"[a-z]*[0-9]+[a-z0-9]*")


@dataclass(frozen=True)
class NamingConvention:
    """一条命名规范检查；``check`` 返回违反映述（None 表示通过）。"""

    code: str
    label: str
    severity: str  # error / warning / info（对齐 §2.6/§2.7 severity 取值）
    check: Callable[[str, str], Optional[str]] = field(compare=False, hash=False)


def _check_placeholder(raw: str, normalized: str) -> Optional[str]:
    hit = _PLACEHOLDER_CJK.search(normalized) or _PLACEHOLDER_LATIN.search(normalized)
    return f"命中占位/无意义文本「{hit.group(0)}」" if hit else None


def _check_fullwidth(raw: str, normalized: str) -> Optional[str]:
    hit = _FULLWIDTH_ALNUM.findall(raw)
    return f"含全角字母/数字「{''.join(hit[:6])}」，应使用半角" if hit else None


def _check_edge_space(raw: str, normalized: str) -> Optional[str]:
    return f"名称首/尾含空白字符：{raw!r}" if raw != raw.strip() else None


def _check_consecutive_space(raw: str, normalized: str) -> Optional[str]:
    return "名称含连续空格或全角空格" if re.search(r"\s{2,}|\u3000", raw) else None


def _check_forbidden_char(raw: str, normalized: str) -> Optional[str]:
    hit = _FORBIDDEN_CHARS.findall(raw)
    return f"含禁用字符「{''.join(sorted(set(hit)))}」" if hit else None


def _check_too_short(raw: str, normalized: str) -> Optional[str]:
    if not normalized:
        return "名称为空或无任何有效字符"
    if len(normalized) < 4:
        return f"规范化后名称仅 {len(normalized)} 个字符，无法有效标识对象"
    return None


def _check_pure_code_like(raw: str, normalized: str) -> Optional[str]:
    return "名称退化为编码/纯数字，缺少业务语义" if _PURE_CODE.fullmatch(normalized) else None


def _check_repeated_char(raw: str, normalized: str) -> Optional[str]:
    hit = _REPEATED_CHAR.match(normalized)
    return f"名称由重复字符「{hit.group(1)}」构成" if hit else None


#: 默认命名规范集合；可用 ``conventions=`` 覆盖（后续可接 DataStandard.pattern 配置化）。
DEFAULT_NAMING_CONVENTIONS: Tuple[NamingConvention, ...] = (
    NamingConvention("placeholder_text", "名称含占位或无意义文本", "error", _check_placeholder),
    NamingConvention("fullwidth_alnum", "名称含全角字母/数字", "info", _check_fullwidth),
    NamingConvention("edge_space", "名称首尾含空白字符", "warning", _check_edge_space),
    NamingConvention("consecutive_space", "名称含连续空格", "info", _check_consecutive_space),
    NamingConvention("forbidden_char", "名称含禁用字符", "warning", _check_forbidden_char),
    NamingConvention("too_short", "名称过短", "warning", _check_too_short),
    NamingConvention("pure_code_like", "名称退化为编码/纯数字", "warning", _check_pure_code_like),
    NamingConvention("repeated_char", "名称由重复字符构成", "warning", _check_repeated_char),
)


# ========== 输出结构 ==========

@dataclass(frozen=True)
class DuplicateFinding:
    """一条检测结论，字段足以映射为 §2.7 ``SuspectedError`` 行。

    * ``entity_id`` / ``matched_entity_id``：§2.7 去重键与误报白名单用。重复类 finding
      中 ``entity_id`` 是**建议停用/待处理**的那条，``matched_entity_id`` 是**建议保留**
      的那条（keeper 规则见 ``evidence["keeper_rule"]``）；规范类 finding 无匹配对象，
      ``matched_entity_id`` 为 None。
    * ``similarity``：精确重复恒为 1.0，近重复上界 0.99，规范违例恒为 0.0。
    * ``evidence``：判定依据（候选编码、名称、相似率、对应规则、共享词元、处置建议）。
    """

    entity_type: str
    entity_id: str
    entity_label: str
    matched_entity_id: Optional[str]
    matched_label: Optional[str]
    error_type: ErrorType
    detect_kind: DetectionKind
    similarity: float
    severity: str
    title: str
    description: str
    field_name: str
    evidence: Dict[str, Any] = field(hash=False)

    @property
    def dedupe_key(self) -> Tuple[str, Optional[str], str]:
        """§2.7 去重键：``(entity_id, matched_entity_id, error_type)``。"""
        return (self.entity_id, self.matched_entity_id, self.error_type.value)

    def to_dict(self) -> Dict[str, Any]:
        """纯 dict 视图（枚举降为字符串），便于直接写库或返回 JSON。"""
        data = asdict(self)
        data["error_type"] = self.error_type.value
        data["detect_kind"] = self.detect_kind.value
        return data


@dataclass(frozen=True)
class PrefilterStats:
    """预筛执行画像 —— 用于断言 §5.3「禁止全量两两比较」确实被满足。"""

    entity_type: str
    total_records: int
    distinct_normalized_names: int = 0
    exact_duplicate_groups: int = 0
    prefilter_queries: int = 0
    probes_issued: int = 0
    probes_skipped: int = 0
    candidates_fetched: int = 0
    pairs_scored: int = 0
    candidate_truncated: int = 0

    @property
    def full_pairwise_pairs(self) -> int:
        """若不做预筛，两两比较的对数。"""
        n = self.total_records
        return n * (n - 1) // 2

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["full_pairwise_pairs"] = self.full_pairwise_pairs
        return data


@dataclass(frozen=True)
class _Record:
    id: str
    code: str
    name: str
    status: str
    created_at: Optional[datetime]

    @property
    def keeper_key(self) -> Tuple[datetime, str]:
        """keeper 排序键：创建更早者优先，其次编码字典序（与遍历顺序无关）。"""
        return (_as_naive_utc(self.created_at), self.code)


@dataclass(frozen=True)
class _EntitySpec:
    entity_type: str
    model: Any
    id: Any
    code: Any
    name: Any
    status: Any
    created_at: Any
    column: str
    display_label: str


# ========== 检测器 ==========

class DuplicateDetector:
    """基于名称的疑似重复 + 命名规范检测（只读，不写库、不改库）。"""

    def __init__(self, db: Session):
        self.db = db

    # ---------- public ----------

    def detect(
        self,
        entity_type: str,
        *,
        entity_ids: Optional[Sequence[str]] = None,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        max_candidates_per_probe: int = 50,
        max_blocking_keys: int = 5,
        blocking_max_df: int = 500,
        blocking_max_df_ratio: float = 0.05,
        include_inactive: bool = False,
        conventions: Optional[Sequence[NamingConvention]] = None,
        max_entities: int = MAX_ENTITIES_PER_RUN,
    ) -> List[DuplicateFinding]:
        """返回该 ``entity_type`` 作用域内的全部检测结论（重复 + 命名规范）。"""
        findings, _stats = self.detect_with_stats(
            entity_type,
            entity_ids=entity_ids,
            similarity_threshold=similarity_threshold,
            max_candidates_per_probe=max_candidates_per_probe,
            max_blocking_keys=max_blocking_keys,
            blocking_max_df=blocking_max_df,
            blocking_max_df_ratio=blocking_max_df_ratio,
            include_inactive=include_inactive,
            conventions=conventions,
            max_entities=max_entities,
        )
        return findings

    def detect_with_stats(
        self,
        entity_type: str,
        *,
        entity_ids: Optional[Sequence[str]] = None,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        max_candidates_per_probe: int = 50,
        max_blocking_keys: int = 5,
        blocking_max_df: int = 500,
        blocking_max_df_ratio: float = 0.05,
        include_inactive: bool = False,
        conventions: Optional[Sequence[NamingConvention]] = None,
        max_entities: int = MAX_ENTITIES_PER_RUN,
    ) -> Tuple[List[DuplicateFinding], PrefilterStats]:
        """同 :meth:`detect`，另外返回 :class:`PrefilterStats` 以证明预筛生效。"""
        if not 0.0 < similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold 必须落在 (0, 1] 区间")
        if max_candidates_per_probe < 1 or max_blocking_keys < 1:
            raise ValueError("max_candidates_per_probe 与 max_blocking_keys 必须 >= 1")
        if not 0.0 < blocking_max_df_ratio <= 1.0:
            raise ValueError("blocking_max_df_ratio 必须落在 (0, 1] 区间")

        spec = _resolve_spec(entity_type)
        scope = _scope_conditions(spec, entity_ids, include_inactive)
        records = self._load(spec, scope, max_entities)
        rules = tuple(conventions if conventions is not None else DEFAULT_NAMING_CONVENTIONS)

        stats = PrefilterStats(entity_type=entity_type, total_records=len(records))
        if not records:
            return [], stats

        # 预筛键必须「有区分度」：词元最多覆盖作用域的 blocking_max_df_ratio。
        # 下界取 2 保证小样本里成对的真实变体仍然可筛（DF=1 只有自己，不可能召回）。
        key_df_ceiling = min(
            blocking_max_df,
            max(2, math.ceil(len(records) * blocking_max_df_ratio)),
        )

        tokens_by_id = {r.id: tokenize_name(r.name) for r in records}
        doc_freq: Dict[str, int] = {}
        for tokens in tokens_by_id.values():
            for token in tokens:
                doc_freq[token] = doc_freq.get(token, 0) + 1

        findings: List[DuplicateFinding] = []
        findings.extend(self._convention_findings(spec, records, rules))

        exact_findings, exact_pairs, stats = self._exact_findings(spec, records, stats)
        findings.extend(exact_findings)

        near_findings, stats = self._near_findings(
            spec,
            scope,
            records,
            tokens_by_id,
            doc_freq,
            exact_pairs,
            stats,
            similarity_threshold=similarity_threshold,
            max_candidates_per_probe=max_candidates_per_probe,
            max_blocking_keys=max_blocking_keys,
            key_df_ceiling=key_df_ceiling,
        )
        findings.extend(near_findings)

        findings.sort(key=lambda f: (-f.similarity, f.error_type.value, f.entity_id))
        return findings, stats

    # ---------- stage 1: 作用域加载（一次投影查询，O(n)，无两两比较） ----------

    def _load(
        self,
        spec: _EntitySpec,
        scope: List[Any],
        max_entities: int,
    ) -> List[_Record]:
        stmt = select(
            spec.id, spec.code, spec.name, spec.status, spec.created_at
        ).where(*scope)
        rows = self.db.execute(stmt.limit(max_entities + 1)).all()
        if len(rows) > max_entities:
            raise DuplicateDetectionLimitError(
                f"{spec.entity_type} 作用域实体超过单次检测上限 {max_entities}，"
                "请分批检测（SPEC §5.2）"
            )
        return [_Record(*row) for row in rows]

    # ---------- stage 2: 精确重复（规范化名称哈希分组，O(n)） ----------

    def _exact_findings(
        self,
        spec: _EntitySpec,
        records: List[_Record],
        stats: PrefilterStats,
    ) -> Tuple[List[DuplicateFinding], Set[Tuple[str, str]], PrefilterStats]:
        """规范化名称相同的记录按 keeper 做**星形**输出：k 条重复只产生 k-1 条 finding
        （都指向 keeper），而不是 k(k-1)/2 条两两组合，避免复制粘贴簇把 suspected_errors 撑爆。
        """
        groups: Dict[str, List[_Record]] = {}
        for record in records:
            groups.setdefault(normalize_name(record.name), []).append(record)

        findings: List[DuplicateFinding] = []
        found_pairs: Set[Tuple[str, str]] = set()
        for normalized, members in groups.items():
            if len(members) < 2:
                continue
            members.sort(key=lambda r: r.keeper_key)
            keeper = members[0]
            for suspect in members[1:]:
                found_pairs.add(_pair_key(keeper.id, suspect.id))
                findings.append(
                    self._pair_finding(
                        spec,
                        keeper,
                        suspect,
                        kind=DetectionKind.EXACT_NAME,
                        similarity=1.0,
                        severity="error",
                        reason="规范化名称完全相同",
                        extra={"normalized_name": normalized},
                    )
                )
        stats = _replace_stats(
            stats,
            distinct_normalized_names=len(groups),
            exact_duplicate_groups=sum(1 for m in groups.values() if len(m) > 1),
        )
        return findings, found_pairs, stats

    # ---------- stage 3: 近重复（SQL 预筛收窄候选，只有小候选集在 Python 打分） ----------

    def _near_findings(
        self,
        spec: _EntitySpec,
        scope: List[Any],
        records: List[_Record],
        tokens_by_id: Dict[str, Set[str]],
        doc_freq: Dict[str, int],
        already_found: Set[Tuple[str, str]],
        stats: PrefilterStats,
        *,
        similarity_threshold: float,
        max_candidates_per_probe: int,
        max_blocking_keys: int,
        key_df_ceiling: int,
    ) -> Tuple[List[DuplicateFinding], PrefilterStats]:
        probes_issued = prefilter_queries = candidates_fetched = pairs_scored = truncated = 0
        skipped = 0
        findings: List[DuplicateFinding] = []

        for probe in sorted(records, key=lambda r: r.id):
            keys = _blocking_keys(
                tokens_by_id[probe.id], doc_freq, max_blocking_keys, key_df_ceiling
            )
            if not keys:
                # 词元全是私有（DF=1）或过泛（DF>key_df_ceiling）：不可能召回候选，跳过整次预筛
                skipped += 1
                continue

            # 候选集在 SQL 侧收窄：作用域条件必须重复施加（否则 supplier 会命中
            # customer 行），词元走绑定参数；id > probe.id 保证每个无序对只评估一次。
            stmt = (
                select(spec.id, spec.code, spec.name, spec.status, spec.created_at)
                .where(
                    *scope,
                    spec.id > probe.id,
                    or_(
                        *[
                            spec.name.ilike(_like_pattern(key), escape=_ESCAPE_CHAR)
                            for key in keys
                        ]
                    ),
                )
                .order_by(spec.id)
                .limit(max_candidates_per_probe + 1)
            )
            rows = self.db.execute(stmt).all()
            probes_issued += 1
            prefilter_queries += 1

            candidates = [_Record(*row) for row in rows]
            if len(candidates) > max_candidates_per_probe:
                truncated += 1
                candidates = candidates[:max_candidates_per_probe]
            candidates_fetched += len(candidates)

            probe_tokens = tokens_by_id[probe.id]
            for candidate in candidates:
                if _pair_key(probe.id, candidate.id) in already_found:
                    continue  # 已由精确重复分组覆盖，不再产出低一档的重复结论
                candidate_tokens = tokens_by_id[candidate.id]
                pairs_scored += 1
                similarity = _dice(probe_tokens, candidate_tokens)
                if similarity < similarity_threshold:
                    continue
                findings.append(
                    self._pair_finding(
                        spec,
                        *self._order_keeper(probe, candidate),
                        kind=DetectionKind.TOKEN_OVERLAP,
                        similarity=min(round(similarity, 4), NEAR_DUPLICATE_CEILING),
                        severity="warning",
                        reason=(
                            f"名称词元重叠度 {similarity:.0%} ≥ 阈值 "
                            f"{similarity_threshold:.0%}（规范化名称不同，属命名变体）"
                        ),
                        extra={
                            "shared_tokens": sorted(probe_tokens & candidate_tokens),
                            "shared_token_count": len(probe_tokens & candidate_tokens),
                            "token_overlap": round(similarity, 4),
                            "similarity_formula": "dice = 2*|A∩B| / (|A|+|B|)，中文按字二元组分词",
                            "threshold": similarity_threshold,
                            "prefilter_keys": keys,
                            "prefilter_mode": "sql_ilike",
                            "entity_name_tokens": len(probe_tokens),
                            "matched_name_tokens": len(candidate_tokens),
                            "normalized_entity_name": normalize_name(probe.name),
                            "normalized_matched_name": normalize_name(candidate.name),
                        },
                    )
                )

        stats = _replace_stats(
            stats,
            probes_issued=probes_issued,
            probes_skipped=skipped,
            prefilter_queries=prefilter_queries,
            candidates_fetched=candidates_fetched,
            pairs_scored=pairs_scored,
            candidate_truncated=truncated,
        )
        return findings, stats

    def _order_keeper(self, a: _Record, b: _Record) -> Tuple[_Record, _Record]:
        """返回 (keeper, suspect)：keeper = 更早创建/编码更小的那条。"""
        return (a, b) if a.keeper_key <= b.keeper_key else (b, a)

    # ---------- stage 4: 命名规范（单实体检查，天然无两两比较） ----------

    def _convention_findings(
        self,
        spec: _EntitySpec,
        records: List[_Record],
        rules: Sequence[NamingConvention],
    ) -> List[DuplicateFinding]:
        findings: List[DuplicateFinding] = []
        for record in records:
            normalized = normalize_name(record.name)
            for rule in rules:
                violation = rule.check(record.name, normalized)
                if not violation:
                    continue
                findings.append(
                    DuplicateFinding(
                        entity_type=spec.entity_type,
                        entity_id=record.id,
                        entity_label=_preview(record.name),
                        matched_entity_id=None,
                        matched_label=None,
                        error_type=ErrorType.NAMING,
                        detect_kind=DetectionKind.CONVENTION,
                        similarity=0.0,
                        severity=rule.severity,
                        title=f"命名不规范：{record.code} {_preview(record.name, 60)}",
                        description=(
                            f"{spec.display_label}「{_preview(record.name, 60)}」违反命名规范"
                            f"「{rule.label}」：{violation}"
                        ),
                        field_name=_SAP_NAME_FIELD[spec.entity_type],
                        evidence={
                            "rule_code": rule.code,
                            "rule_label": rule.label,
                            "rule": f"naming_convention:{rule.code}",
                            "violation": violation,
                            "field": _SAP_NAME_FIELD[spec.entity_type],
                            "column": spec.column,
                            "entity_code": record.code,
                            "raw_value": _preview(record.name),
                            "normalized_value": normalized,
                        },
                    )
                )
        return findings

    # ---------- 重复 finding 组装 ----------

    def _pair_finding(
        self,
        spec: _EntitySpec,
        keeper: _Record,
        suspect: _Record,
        *,
        kind: DetectionKind,
        similarity: float,
        severity: str,
        reason: str,
        extra: Dict[str, Any],
    ) -> DuplicateFinding:
        """keeper = 建议保留，suspect = 建议停用（§2.7：停用优先于删除，一律人工执行）。"""
        evidence: Dict[str, Any] = {
            "strategy": kind.value,
            "rule": "duplicate_check",
            "reason": reason,
            "similarity": similarity,
            "field": _SAP_NAME_FIELD[spec.entity_type],
            "column": spec.column,
            "entity_code": suspect.code,
            "entity_name": _preview(suspect.name),
            "matched_code": keeper.code,
            "matched_name": _preview(keeper.name),
            "suggestion": f"建议保留 {keeper.code} / 停用 {suspect.code}",
            "keeper_rule": "created_at 最早（其次编码字典序）保留，另一条建议停用",
        }
        evidence.update(extra)
        return DuplicateFinding(
            entity_type=spec.entity_type,
            entity_id=suspect.id,
            entity_label=_preview(suspect.name),
            matched_entity_id=keeper.id,
            matched_label=_preview(keeper.name),
            error_type=ErrorType.DUPLICATE,
            detect_kind=kind,
            similarity=similarity,
            severity=severity,
            title=(
                f"疑似重复：{suspect.code} {_preview(suspect.name, 40)}"
                f" ↔ {keeper.code} {_preview(keeper.name, 40)}"
            ),
            description=(
                f"{spec.display_label}相似度 {similarity:.0%}，{reason}。"
                f"处置建议：{evidence['suggestion']}（人工执行，系统不自动停用）。"
            ),
            field_name=_SAP_NAME_FIELD[spec.entity_type],
            evidence=evidence,
        )


# ========== helpers ==========

def _pair_key(a: str, b: str) -> Tuple[str, str]:
    return (a, b) if a < b else (b, a)


def _blocking_keys(
    tokens: Set[str],
    doc_freq: Dict[str, int],
    max_keys: int,
    key_df_ceiling: int,
) -> List[str]:
    """取 DF 最低的若干词元作为预筛键：DF 越低区分度越高、命中候选越少。

    * ``DF == 1``：只有自身含该词元，不可能召回任何候选，跳过；
    * ``DF > key_df_ceiling``：词元过泛（如「公司」「型号」），作键会把大半个表
      拉进候选集，破坏有界开销，同样跳过。
    """
    candidates = [t for t in tokens if 1 < doc_freq.get(t, 0) <= key_df_ceiling]
    candidates.sort(key=lambda t: (doc_freq[t], -len(t), t))
    return candidates[:max_keys]


def _replace_stats(stats: PrefilterStats, **updates: int) -> PrefilterStats:
    data = asdict(stats)
    data.update(updates)
    return PrefilterStats(**data)


def _scope_conditions(
    spec: _EntitySpec,
    entity_ids: Optional[Sequence[str]],
    include_inactive: bool,
) -> List[Any]:
    """作用域条件：加载与预筛共用，保证两侧口径一致。"""
    conditions: List[Any] = []
    if spec.entity_type in (ENTITY_SUPPLIER, ENTITY_CUSTOMER):
        conditions.append(spec.model.entity_type == spec.entity_type)
    if not include_inactive:
        conditions.append(spec.status == ACTIVE_STATUS)
    if entity_ids is not None:
        ids = [str(i) for i in entity_ids if str(i)]
        if not ids:
            raise ValueError("entity_ids 不能为空集合；全量作用域请传 None")
        conditions.append(spec.id.in_(ids))
    return conditions


def _resolve_spec(entity_type: str) -> _EntitySpec:
    if entity_type == ENTITY_MATERIAL:
        model = models.MaterialRecord
        column, display = "material_name", "物料名称"
    elif entity_type in (ENTITY_SUPPLIER, ENTITY_CUSTOMER):
        model = models.PartnerRecord
        column, display = "partner_name", "供应商/客户名称"
    else:
        raise ValueError(
            f"Unsupported entity_type {entity_type!r}; expected one of {ENTITY_TYPES}"
        )
    return _EntitySpec(
        entity_type=entity_type,
        model=model,
        id=model.id,
        code=getattr(model, "material_code" if model is models.MaterialRecord else "partner_code"),
        name=getattr(model, column),
        status=model.status,
        created_at=model.created_at,
        column=column,
        display_label=display,
    )


# ========== 模块级便捷入口（Session + entity_type → findings） ==========

def detect_duplicates(
    db: Session,
    entity_type: str,
    **kwargs: Any,
) -> List[DuplicateFinding]:
    """:meth:`DuplicateDetector.detect` 的函数式封装。"""
    return DuplicateDetector(db).detect(entity_type, **kwargs)


def detect_duplicates_with_stats(
    db: Session,
    entity_type: str,
    **kwargs: Any,
) -> Tuple[List[DuplicateFinding], PrefilterStats]:
    """:meth:`DuplicateDetector.detect_with_stats` 的函数式封装。"""
    return DuplicateDetector(db).detect_with_stats(entity_type, **kwargs)
