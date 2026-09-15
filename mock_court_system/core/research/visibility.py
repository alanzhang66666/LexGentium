"""Role × stage visibility. Natural gaps are not experimental hides."""
from __future__ import annotations

from typing import Any, Optional

from .enums import ROLE_EVALUATOR


def _as_id_set(values: Any) -> set[str]:
    if not values:
        return set()
    return {str(item) for item in values if str(item).strip()}


def _empty_ids() -> dict[str, list[str]]:
    return {"document_ids": [], "source_ids": [], "rule_ids": []}


def grant_applies(grant: dict[str, Any], role: str, stage: str) -> bool:
    if str(grant.get("role") or "") != role:
        return False
    grant_stage = str(grant.get("stage") or "")
    visibility = str(grant.get("visibility") or "visible")
    if visibility == "stage_open":
        return bool(grant_stage) and grant_stage == stage
    if grant_stage and stage and grant_stage != stage:
        return False
    return True


def apply_visibility_grants(
    base: dict[str, list[str]],
    grants: Any,
    *,
    role: str,
    stage: str = "",
) -> dict[str, list[str]]:
    documents = _as_id_set(base.get("document_ids"))
    sources = _as_id_set(base.get("source_ids"))
    rules = _as_id_set(base.get("rule_ids"))
    rows = grants if isinstance(grants, list) else []
    for grant in rows:
        if not isinstance(grant, dict) or not grant_applies(grant, role, stage):
            continue
        visibility = str(grant.get("visibility") or "visible")
        availability = str(grant.get("availability") or "available")
        document_id = str(grant.get("document_id") or "")
        source_id = str(grant.get("source_id") or "")
        rule_id = str(grant.get("rule_id") or "")
        hide = visibility in {"hidden", "evaluator_only"} or availability == "experimentally_hidden"
        if visibility == "evaluator_only" and role == ROLE_EVALUATOR:
            hide = False
        if hide:
            if document_id:
                documents.discard(document_id)
            if source_id:
                sources.discard(source_id)
            if rule_id:
                rules.discard(rule_id)
            continue
        if visibility in {"visible", "stage_open"} and availability != "experimentally_hidden":
            if document_id:
                documents.add(document_id)
            if source_id:
                sources.add(source_id)
            if rule_id:
                rules.add(rule_id)
    return {
        "document_ids": sorted(documents),
        "source_ids": sorted(sources),
        "rule_ids": sorted(rules),
    }


def experiment_hidden_source_ids(research: dict[str, Any]) -> set[str]:
    conditions = research.get("experiment_conditions") or {}
    if not isinstance(conditions, dict):
        return set()
    return _as_id_set(conditions.get("hide_source_ids"))


def natural_missing_source_ids(research: dict[str, Any]) -> set[str]:
    conditions = research.get("experiment_conditions") or {}
    if not isinstance(conditions, dict):
        return set()
    return _as_id_set(conditions.get("natural_missing_source_ids"))


def resolve_stage(research: dict[str, Any], stage: Optional[str] = None) -> str:
    if stage:
        return stage
    conditions = research.get("experiment_conditions") or {}
    if isinstance(conditions, dict):
        return str(conditions.get("stage") or "")
    return ""
