"""Common Pydantic base for research contracts."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from .enums import REFERENCE_FIELD, ROLE_VIEW_EXCLUDED_FIELDS


class ResearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def role_view(self) -> dict[str, Any]:
        """Dump without the evaluation ``reference`` layer."""
        return strip_reference(self.model_dump(mode="json"))


def strip_reference(payload: Any) -> Any:
    """Recursively drop ``reference`` so it cannot leak into a role view."""
    if isinstance(payload, dict):
        return {
            key: strip_reference(value)
            for key, value in payload.items()
            if key not in ROLE_VIEW_EXCLUDED_FIELDS and key != REFERENCE_FIELD
        }
    if isinstance(payload, list):
        return [strip_reference(item) for item in payload]
    return payload
