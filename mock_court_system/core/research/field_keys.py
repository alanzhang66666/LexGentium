"""Controlled six-column field keys. Values must match ``lib/research/field_keys.ts``."""
from __future__ import annotations

from .enums import CISG_ART79_ELEMENT_IDS, TaskType


# Procedural-fact keys used by the frozen research packs.
# Workbook 20 is the annotation dictionary; these are the runtime slice.
CISG_FACT_FIELD_KEYS: tuple[str, ...] = (
    "parties_places_of_business",
    "governing_instrument",
    "alleged_impediment",
    "notice_date",
)

ENFORCEMENT_FACT_FIELD_KEYS: tuple[str, ...] = (
    "award_seat",
    "arbitration_institution",
    "enforcement_forum",
    "notice_of_proceedings",
    "award_date",
)

FACT_FIELD_KEYS_BY_TASK: dict[TaskType, tuple[str, ...]] = {
    "cisg_article79": CISG_FACT_FIELD_KEYS,
    "enforcement_nyc": ENFORCEMENT_FACT_FIELD_KEYS,
}

ALL_FACT_FIELD_KEYS: tuple[str, ...] = tuple(
    dict.fromkeys((*CISG_FACT_FIELD_KEYS, *ENFORCEMENT_FACT_FIELD_KEYS))
)

# Gaps may point at a fact key, an Art. 79 element, a six-column name, or a missing document.
GAP_RELATED_FIELDS: tuple[str, ...] = tuple(
    dict.fromkeys(
        (
            *ALL_FACT_FIELD_KEYS,
            *CISG_ART79_ELEMENT_IDS,
            "procedural_facts",
            "party_claims",
            "court_findings",
            "legal_bases",
            "material_gaps",
            "source_anchors",
            "award_text",
        )
    )
)


def validate_fact_field_key(task_type: TaskType, field_key: str) -> str:
    allowed = FACT_FIELD_KEYS_BY_TASK[task_type]
    if field_key not in allowed:
        raise ValueError(
            f"field_key {field_key!r} is not in the {task_type} dictionary; "
            f"allowed={allowed}"
        )
    return field_key


def validate_gap_related_field(field: str) -> str:
    if field not in GAP_RELATED_FIELDS:
        raise ValueError(
            f"related_field {field!r} is not in the gap dictionary; "
            f"allowed={GAP_RELATED_FIELDS}"
        )
    return field
