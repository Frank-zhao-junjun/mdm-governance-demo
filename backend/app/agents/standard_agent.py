"""Read-only agent for material standard checks."""
from typing import Any

from app.agents.base import BaseAgent
from app.skills.attribute import check_attributes
from app.skills.naming import check_naming
from app.skills.unit import check_unit


class StandardAgent(BaseAgent):
    name = "standard-agent"

    def _execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        items = payload.get("items", [])
        if not isinstance(items, list):
            raise ValueError("items must be a list")
        attribute_standard = payload.get("attribute_standard", {})
        unit_standard = payload.get("unit_standard", {})
        results = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("each item must be an object")
            results.append({
                "naming": check_naming(item).model_dump(mode="json"),
                "attributes": check_attributes(item, attribute_standard).model_dump(mode="json"),
                "unit": check_unit(item, unit_standard).model_dump(mode="json"),
            })
        return {"items": results}
