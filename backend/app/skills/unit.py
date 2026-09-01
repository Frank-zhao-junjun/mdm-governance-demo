"""Unit normalization Skill."""
from collections.abc import Mapping
from typing import Any

from app.skills.common import EvidenceItem, SkillResult, SkillSuggestion


def check_unit(item: Mapping[str, Any], standard: Mapping[str, Any]) -> SkillResult:
    """Suggest canonical units only from an explicit, deterministic mapping."""
    unit = str(item.get("unit", item.get("MEINS", ""))).strip()
    canonical_unit = str(standard.get("canonical_unit", "")).strip()
    aliases = standard.get("aliases", {})
    aliases = aliases if isinstance(aliases, Mapping) else {}
    normalized = str(aliases.get(unit, unit)).strip()

    if not unit or not canonical_unit or unit == canonical_unit:
        return SkillResult(status="pass")
    if unit in aliases:
        return SkillResult(
            status="suggest",
            suggestions=[SkillSuggestion(
                field="unit",
                suggestion=canonical_unit,
                evidence=EvidenceItem(
                    level="L1",
                    source="unit:conversion_mapping",
                    detail=f"单位映射表将 {unit} 规范为 {canonical_unit}",
                ),
                auto_fixable=True,
            )],
        )
    return SkillResult(
        status="warn",
        suggestions=[SkillSuggestion(
            field="unit",
            suggestion=f"确认单位是否应为 {canonical_unit}",
            evidence=EvidenceItem(
                level="L3",
                source="unit:unmapped_alias",
                detail=f"单位 {unit} 未命中受控换算映射，需人工确认",
            ),
        )],
    )
