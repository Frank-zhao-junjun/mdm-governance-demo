"""Naming standard Skill."""
from collections.abc import Mapping
from typing import Any

from app.services.duplicate_detector import DEFAULT_NAMING_CONVENTIONS
from app.skills.common import EvidenceItem, SkillSuggestion, result_for_suggestions


def check_naming(item: Mapping[str, Any], standard: Mapping[str, Any] | None = None):
    """Check a material name against deterministic naming conventions."""
    name = str(item.get("name", item.get("material_name", "")))
    suggestions: list[SkillSuggestion] = []
    for convention in DEFAULT_NAMING_CONVENTIONS:
        violation = convention.check(name, name)
        if violation:
            suggestions.append(SkillSuggestion(
                field="name",
                suggestion=f"按命名规范修正：{convention.label}",
                evidence=EvidenceItem(level="L1", source=f"naming:{convention.code}", detail=violation),
                auto_fixable=False,
            ))

    return result_for_suggestions(suggestions, blocking=any(
        suggestion.evidence.source in {"naming:placeholder_text"} for suggestion in suggestions
    ))
