"""Side-effect-free merge execution preflight Skill."""
from collections.abc import Mapping
from typing import Any

from app.skills.common import SkillResult


def prepare_merge_execution(ticket: Mapping[str, Any]) -> SkillResult:
    """Permit an external executor only after a human approved the merge ticket."""
    golden_ids = ticket.get("golden_ids", ticket.get("candidate_golden_ids", []))
    if ticket.get("status") != "approved":
        return SkillResult(
            status="block",
            conflicts=[{
                "type": "approval_required",
                "level": "L1",
                "message": "归并执行必须先获得人工批准",
            }],
        )
    if not isinstance(golden_ids, list) or len(golden_ids) < 2:
        return SkillResult(
            status="block",
            conflicts=[{
                "type": "insufficient_candidates",
                "level": "L1",
                "message": "归并至少需要两条金标记录",
            }],
        )
    return SkillResult(status="pass")