"""Research pack access for start-session hydration. Wraps ResearchPackLoader."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core.research import (
    ROLE_AUDITOR,
    ROLE_TRIBUNAL,
    ExperimentConditions,
    InputContract,
    PackNotFoundError,
    PackVersionMismatchError,
    ResearchPack,
    ResearchPackError,
    ResearchPackLoader,
    VisibleMaterials,
    new_run_id,
    strip_reference,
    validate_run_id,
)

_DEFAULT_ROLES = {
    "enforcement_nyc": ("applicant", "respondent", ROLE_TRIBUNAL, ROLE_AUDITOR),
    "cisg_article79": ("claimant", "respondent", ROLE_TRIBUNAL, ROLE_AUDITOR),
}

_PACK_MATERIAL_FIELDS = (
    "caption",
    "documents",
    "procedural_facts",
    "party_claims",
    "court_findings",
    "legal_bases",
    "material_gaps",
    "source_anchors",
    "argument_records",
    "evidence_links",
    "rules",
    "review_state",
    "review_records",
    "notes",
)


class EmptyPackError(ResearchPackError):
    """Pack exists but has no usable documents or text."""


def get_loader() -> ResearchPackLoader:
    return ResearchPackLoader()


def raise_pack_http(exc: Exception) -> None:
    """Map pack loader errors to a clear HTTP status. Always raises."""
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, PackNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, PackVersionMismatchError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, EmptyPackError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, ResearchPackError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail=str(exc)) from exc


def list_packs(dataset_id: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        return [row.model_dump(mode="json") for row in get_loader().list_packs(dataset_id)]
    except (ResearchPackError, ValueError) as exc:
        raise_pack_http(exc)
        raise  # pragma: no cover


def get_pack(
    dataset_id: str,
    cluster_id: str,
    pack_version: Optional[str] = None,
) -> ResearchPack:
    try:
        pack = get_loader().get_pack(dataset_id, cluster_id, pack_version)
    except (ResearchPackError, ValueError) as exc:
        raise_pack_http(exc)
        raise  # pragma: no cover
    if not pack.documents:
        raise_pack_http(
            EmptyPackError(
                f"empty pack: dataset_id={dataset_id!r} cluster_id={cluster_id!r}"
            )
        )
    return pack


def get_document_text(dataset_id: str, cluster_id: str, document_id: str) -> str:
    try:
        text = get_loader().get_document_text(dataset_id, cluster_id, document_id)
    except (ResearchPackError, ValueError) as exc:
        raise_pack_http(exc)
        raise  # pragma: no cover
    return text


def list_anchors(
    dataset_id: str,
    cluster_id: str,
    pack_version: Optional[str] = None,
) -> List[Dict[str, Any]]:
    pack = get_pack(dataset_id, cluster_id, pack_version)
    return [anchor.model_dump(mode="json") for anchor in pack.source_anchors]


def attach_document_texts(pack: ResearchPack, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Copy file bodies onto the role-visible document list. Does not read reference."""
    loader = get_loader()
    documents = []
    for doc in snapshot.get("documents") or []:
        if not isinstance(doc, dict):
            continue
        document_id = str(doc.get("document_id") or "")
        row = dict(doc)
        row["text"] = loader.get_document_text(pack.dataset_id, pack.cluster_id, document_id)
        documents.append(row)
    snapshot["documents"] = documents
    return snapshot


def default_visible_materials(pack: ResearchPack) -> Dict[str, Dict[str, Any]]:
    document_ids = [doc.document_id for doc in pack.documents]
    source_ids = [anchor.source_id for anchor in pack.source_anchors]
    rule_ids = [rule.rule_id for rule in pack.rules]
    blob = VisibleMaterials(
        document_ids=document_ids,
        source_ids=source_ids,
        rule_ids=rule_ids,
    ).model_dump(mode="json")
    roles = _DEFAULT_ROLES.get(pack.task_type, (ROLE_TRIBUNAL, ROLE_AUDITOR))
    return {role: dict(blob) for role in roles}


def hash_materials(payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def current_model_config() -> Dict[str, Any]:
    try:
        from api import state

        client = state.llm_client
        return {
            "provider": getattr(client, "provider", "") or "",
            "model": getattr(client, "model", "") or "",
            "temperature": getattr(client, "temperature", None),
        }
    except Exception:
        return {}


def freeze_role_snapshot(
    dataset_id: str,
    cluster_id: str,
    pack_version: str,
    *,
    derived_from: Optional[str] = None,
    model_config: Optional[Dict[str, Any]] = None,
    visible_materials: Optional[Dict[str, Any]] = None,
    experiment_conditions: Optional[Dict[str, Any]] = None,
    visibility_grants: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Role-visible InputContract + pack materials. Never copies ``reference``."""
    if derived_from:
        try:
            derived_from = validate_run_id(derived_from)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    pack = get_pack(dataset_id, cluster_id, pack_version)
    try:
        snapshot = attach_document_texts(pack, pack.role_view())
    except (ResearchPackError, ValueError) as exc:
        raise_pack_http(exc)
        raise  # pragma: no cover
    if "reference" in snapshot:
        raise HTTPException(status_code=500, detail="role snapshot leaked reference")

    texts = [str(doc.get("text") or "") for doc in snapshot.get("documents") or []]
    if not texts or not any(text.strip() for text in texts):
        raise_pack_http(
            EmptyPackError(
                f"empty pack: dataset_id={dataset_id!r} cluster_id={cluster_id!r}"
            )
        )

    conditions = ExperimentConditions().model_dump(mode="json")
    if experiment_conditions:
        conditions.update(experiment_conditions)

    contract = InputContract.model_validate(
        {
            "dataset_id": pack.dataset_id,
            "cluster_id": pack.cluster_id,
            "pack_version": pack.pack_version,
            "task_type": pack.task_type,
            "visible_materials": visible_materials or default_visible_materials(pack),
            "visibility_grants": visibility_grants or [],
            "experiment_conditions": conditions,
            "model_config": model_config if model_config is not None else current_model_config(),
            "task_labels": snapshot.get("task_labels"),
        }
    )
    contract_view = contract.role_view()
    if "reference" in contract_view:
        raise HTTPException(status_code=500, detail="role snapshot leaked reference")

    materials_payload = {
        key: snapshot.get(key)
        for key in _PACK_MATERIAL_FIELDS
        if key in snapshot
    }
    materials_payload["visible_materials"] = contract_view.get("visible_materials")
    materials_payload["visibility_grants"] = contract_view.get("visibility_grants") or []
    materials_payload["experiment_conditions"] = contract_view.get("experiment_conditions")
    materials_payload["model_config"] = contract_view.get("model_config")
    materials_hash = hash_materials(materials_payload)
    run_id = new_run_id()

    research: Dict[str, Any] = {
        **contract_view,
        **materials_payload,
        "run_id": run_id,
        "materials_hash": materials_hash,
    }
    if derived_from:
        research["derived_from"] = derived_from
    return strip_reference(research)


def find_source_anchor(pack: Dict[str, Any], source_id: str) -> Dict[str, Any]:
    for anchor in pack.get("source_anchors") or []:
        if isinstance(anchor, dict) and anchor.get("source_id") == source_id:
            return anchor
    raise PackNotFoundError(f"source_id not found: {source_id!r}")


def extract_source_span(document_text: str, anchor: Dict[str, Any]) -> Dict[str, Any]:
    start = anchor.get("start_offset")
    end = anchor.get("end_offset")
    quote = str(anchor.get("quote") or "")
    excerpt = ""
    if isinstance(start, int):
        excerpt = document_text[start:end] if end is not None else document_text[start:]
    if not excerpt and quote:
        idx = document_text.find(quote)
        if idx >= 0:
            start = idx
            end = idx + len(quote)
            excerpt = document_text[idx:end]
        else:
            excerpt = quote
    if not excerpt:
        locator = str(anchor.get("locator") or "")
        token = f"[{locator}]" if locator else ""
        if token:
            idx = document_text.find(token)
            if idx >= 0:
                start = idx
                line_end = document_text.find("\n", idx)
                end = line_end if line_end >= 0 else len(document_text)
                excerpt = document_text[idx:end]
    return {
        "source_id": anchor.get("source_id"),
        "document_id": anchor.get("document_id"),
        "locator": anchor.get("locator") or "",
        "quote": quote,
        "excerpt": excerpt,
        "start_offset": start,
        "end_offset": end,
        "source_tier": anchor.get("source_tier"),
        "review_state": anchor.get("review_state"),
        "notes": anchor.get("notes") or "",
    }


def pack_public_view(
    dataset_id: str,
    cluster_id: str,
    pack_version: Optional[str] = None,
) -> Dict[str, Any]:
    """GET payload: role-visible pack + document text. No reference layer."""
    pack = get_pack(dataset_id, cluster_id, pack_version)
    snapshot = attach_document_texts(pack, pack.role_view())
    snapshot["source_anchors"] = list_anchors(dataset_id, cluster_id, pack.pack_version)
    return strip_reference(snapshot)
