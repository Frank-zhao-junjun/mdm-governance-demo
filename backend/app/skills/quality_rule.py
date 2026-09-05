"""Adapter from the deterministic quality engine to the Skill contract."""
from typing import Any, Iterable, Sequence

from app.services.quality_engine import run_quality_checks
from app.skills.common import EvidenceItem, SkillSuggestion, result_for_suggestions


def check_quality_rules(entity_type: str, records: Sequence[Any], standards: Iterable[Any]):
    """Run configured quality standards without persisting findings."""
    run = run_quality_checks(entity_type, records, standards=standards)
    suggestions = [
        SkillSuggestion(
            field=finding.field_name,
            suggestion=finding.message,
            evidence=EvidenceItem(
                level="L1",
                source=f"quality_rule:{finding.rule_code}",
                detail=f"标准字段 {finding.field_name} 的规则校验未通过",
            ),
        )
        for finding in run.findings
    ]
    return result_for_suggestions(suggestions, blocking=any(
        finding.severity == "error" for finding in run.findings
    ))
