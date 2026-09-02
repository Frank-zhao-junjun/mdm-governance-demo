"""疑似错误检测编排（SPEC §2.7 重检去重 + §3.3 三端点）。

介于 API 与纯函数检测器（duplicate_detector）之间，只做三件事：
类型校验（400 前置）→ 执行检测器 → findings 按 §2.7 去重键映射为
``SuspectedError`` 行，**同一事务**落库。

去重语义（SPEC §2.7，Plan agent 评审定稿）：

* 去重键为**三键** ``(entity_id, matched_entity_id, error_type)`` —— 两键会让
  A↔B、A↔C 多匹配对互相覆盖、行内容振荡（SPEC L430 同款理由）；
* 一次预载 entity_type 全部行 → 内存三映射（fp / pending / terminal），
  findings 先按去重键聚合（后写覆盖，检测器输出序确定性已证）；
* pending 命中 → 只刷新白名单字段（含 detected_at，SPEC L428），
  不触碰 status / resolved_* / resolution_note / detected_by / 身份键；
* false_positive 命中 → 白名单跳过并计数；confirmed / resolved → 静默跳过；
* pending 行实体不存在或失效 → 自动关闭为 resolved（resolved_by=None），
  恒按 entity_type 全量 pending 评估，不受 entity_ids 收窄；
* ``details`` 直接取 finding.evidence（模型无 field_name 列，evidence 是
  唯一载体，含相似率 / 保留停用建议 / 规则依据 / 共享词元）。

审计由 API 层完成（沿用 quality_checks 的两段提交模式）。
"""
from typing import Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy.orm import Session

from app import crud, models
from app.services import duplicate_detector

#: v1 仅支持这两类（SPEC §7 Phase 3 范围）；classification / unit 无检测数据源。
SUPPORTED_ERROR_TYPES: frozenset = frozenset({"duplicate", "naming"})

AUTO_CLOSE_NOTE = "实体已删除/失效，自动关闭"

_DedupeKey = Tuple[str, Optional[str], str]


class SuspectedErrorRunError(Exception):
    """检测无法执行（API 层映射为 400）。"""


class UnsupportedErrorType(SuspectedErrorRunError):
    def __init__(self, unsupported: Set[str]):
        self.unsupported = sorted(unsupported)
        super().__init__(
            f"不支持的错误类型: {', '.join(self.unsupported)}；"
            f"v1 仅支持 {', '.join(sorted(SUPPORTED_ERROR_TYPES))}"
        )


def _norm_ids(entity_ids: Optional[Sequence[str]]) -> Optional[List[str]]:
    # []→None：检测器对空集合抛 ValueError（§5.2），全量作用域必须传 None
    ids = [str(i) for i in entity_ids] if entity_ids else []
    return ids or None


def _refresh_row(row: models.SuspectedError, finding: duplicate_detector.DuplicateFinding, now) -> None:
    """刷新白名单字段（SPEC L428 要求 detected_at 随刷新更新）。"""
    row.entity_label = finding.entity_label
    row.matched_entity_id = finding.matched_entity_id
    row.severity = finding.severity
    row.title = finding.title
    row.description = finding.description
    row.details = finding.evidence
    row.detected_at = now


def detect_suspected_errors(
    db: Session,
    entity_type: str,
    error_types: Optional[Sequence[str]] = None,
    entity_ids: Optional[Sequence[str]] = None,
    detected_by: str = "system",
) -> Dict[str, int]:
    """执行一次疑似错误检测并落库，返回 §2.7 五计数器。

    * ``error_types`` 为空 = 全部支持类型；含 classification / unit → 400；
    * ``entity_ids`` 为空 = 该实体类型全量 active 作用域；
    * 检测器抛 ``DuplicateDetectionLimitError`` 时原样上抛（API 映射 400）。
    """
    types = set(error_types or []) or SUPPORTED_ERROR_TYPES
    unsupported = types - SUPPORTED_ERROR_TYPES
    if unsupported:
        raise UnsupportedErrorType(unsupported)
    ids = _norm_ids(entity_ids)

    # 单次检测器调用同时产出 duplicate + naming 全部 findings（无类型开关）
    findings, _stats = duplicate_detector.DuplicateDetector(db).detect_with_stats(
        entity_type, entity_ids=ids
    )
    findings = [f for f in findings if f.error_type.value in types]

    # 一次预载该实体类型全部行 → 三键映射
    rows = crud.get_suspected_errors_by_entity_type(db, entity_type)
    fp_map: Dict[_DedupeKey, models.SuspectedError] = {}
    pend_map: Dict[_DedupeKey, models.SuspectedError] = {}
    term_map: Dict[_DedupeKey, models.SuspectedError] = {}
    pending_rows: List[models.SuspectedError] = []
    for row in rows:
        key = (row.entity_id, row.matched_entity_id, row.error_type)
        if row.status == "false_positive":
            fp_map[key] = row
        elif row.status == "pending":
            pend_map[key] = row
            pending_rows.append(row)
        else:  # confirmed / resolved：终态静默
            term_map[key] = row

    now = models._now_utc()

    # 自动关闭：先于映射；恒按 entity_type 全量 pending 评估
    auto_closed = 0
    if pending_rows:
        active_ids = crud.existing_entity_ids(
            db, entity_type, [row.entity_id for row in pending_rows]
        )
        for row in pending_rows:
            if row.entity_id in active_ids:
                continue
            row.status = "resolved"
            row.resolution_note = AUTO_CLOSE_NOTE
            row.resolved_at = now
            row.resolved_by = None
            auto_closed += 1

    # 同键多违例（naming 一条实体多个规范违例）按去重键聚合，后写覆盖保证确定性
    agg: Dict[_DedupeKey, duplicate_detector.DuplicateFinding] = {}
    for finding in findings:
        agg[finding.dedupe_key] = finding

    created = refreshed = skipped_false_positive = 0
    for key, finding in agg.items():
        if key in fp_map:
            skipped_false_positive += 1
            continue
        if key in term_map:
            continue
        if key in pend_map:
            _refresh_row(pend_map[key], finding, now)
            refreshed += 1
            continue
        row = models.SuspectedError(
            entity_type=entity_type,
            entity_id=finding.entity_id,
            entity_label=finding.entity_label,
            error_type=finding.error_type.value,
            severity=finding.severity,
            title=finding.title,
            description=finding.description,
            details=finding.evidence,
            status="pending",
            matched_entity_id=finding.matched_entity_id,
            detected_at=now,
            detected_by=detected_by,
        )
        db.add(row)
        # 防御：同 run 内同键重复 finding（聚合后不应发生）走刷新而非二次创建
        pend_map[key] = row
        created += 1

    db.commit()
    return {
        "created": created,
        "refreshed": refreshed,
        "skipped_false_positive": skipped_false_positive,
        "auto_closed": auto_closed,
        # 算术口径：预载 pending − 自动关闭 + 新建，免二次 COUNT
        "total_pending": len(pending_rows) - auto_closed + created,
    }
