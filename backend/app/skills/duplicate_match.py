"""Duplicate candidate evaluation and L1 strength-conflict guard."""
from collections.abc import Mapping
from typing import Any

from app.skills.common import EvidenceItem, SkillResult, SkillSuggestion


def _strength(record: Mapping[str, Any]) -> str:
    return str(record.get("strength", record.get("attributes", {}).get("strength", ""))).strip()


def evaluate_duplicate_candidates(candidate: Mapping[str, Any]) -> SkillResult:
    """Block merge advice whenever same-spec candidates have different strength grades."""
    left = candidate.get("left", {})
    right = candidate.get("right", {})
    left = left if isinstance(left, Mapping) else {}
    right = right if isinstance(right, Mapping) else {}
    left_strength, right_strength = _strength(left), _strength(right)

    if left_strength and right_strength and left_strength != right_strength:
        return SkillResult(
            status="block",
            conflicts=[{
                "type": "strength_conflict",
                "level": "L1",
                "message": "不建议合并",
                "detail": f"强度等级冲突：{left_strength} vs {right_strength}",
            }],
        )
    if candidate.get("llm_suggestion") == "merge":
        return SkillResult(
            status="suggest",
            suggestions=[SkillSuggestion(
                field="candidate_cluster",
                suggestion="候选记录相似，需人工确认是否归并",
                evidence=EvidenceItem(
                    level="L3",
                    source="duplicate:llm_semantic_recall",
                    detail="语义相似仅用于候选召回，不得自动归并",
                ),
            )],
        )
    return SkillResult(status="pass")
