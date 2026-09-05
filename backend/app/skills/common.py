"""Shared result contract for deterministic governance Skills."""
from typing import Literal

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """A governance recommendation's verifiable source and trust grade."""

    level: Literal["L1", "L2", "L3"]
    source: str
    detail: str


class SkillSuggestion(BaseModel):
    field: str
    suggestion: str
    evidence: EvidenceItem
    auto_fixable: bool = False


class SkillResult(BaseModel):
    status: Literal["pass", "warn", "block", "suggest"]
    suggestions: list[SkillSuggestion] = Field(default_factory=list)
    conflicts: list[dict] = Field(default_factory=list)


def result_for_suggestions(suggestions: list[SkillSuggestion], *, blocking: bool) -> SkillResult:
    if not suggestions:
        return SkillResult(status="pass")
    return SkillResult(status="block" if blocking else "suggest", suggestions=suggestions)
