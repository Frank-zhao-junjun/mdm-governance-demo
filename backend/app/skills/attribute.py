"""Required-attribute template Skill."""
from collections.abc import Mapping
from typing import Any

from app.skills.common import EvidenceItem, SkillSuggestion, result_for_suggestions


def check_attributes(item: Mapping[str, Any], standard: Mapping[str, Any]):
    """Return L1 remediation suggestions for missing template attributes."""
    attributes = item.get("attributes", {})
    attributes = attributes if isinstance(attributes, Mapping) else {}
    required_fields = standard.get("required_fields", [])
    suggestions = [
        SkillSuggestion(
            field=str(field),
            suggestion=f"补充必填属性 {field}",
            evidence=EvidenceItem(
                level="L1",
                source="attribute:required_template",
                detail=f"属性模板要求字段 {field}，当前记录未提供有效值",
            ),
        )
        for field in required_fields
        if attributes.get(field) is None or str(attributes.get(field)).strip() == ""
    ]
    return result_for_suggestions(suggestions, blocking=True)
