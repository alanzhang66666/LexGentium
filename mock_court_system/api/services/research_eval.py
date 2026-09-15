"""Research rubric scoring, human review, multi-run compare, and export."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException

from api.services import claims as claim_service
from api.services.materials import get_loader, raise_pack_http
from core.research import EvalContract, new_report_id
from core.research.runtime import RESEARCH_DISCLAIMER, compact_research_meta, research_block
from evaluation.lib.research_rubric import RUBRIC_VERSION, score_research_output


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _session_for_run(run_id: str):
    from api import state

    indexed = claim_service.get_store().get_run(run_id)
    session_id = indexed.get("session_id") if indexed else None
    if session_id:
        record = state.conversation_store.get(session_id)
        if record:
            return record
    _, total = state.conversation_store.list(limit=200, offset=0)
    scanned = 0
    offset = 0
    while scanned < min(total, 400):
        rows, _ = state.conversation_store.list(limit=50, offset=offset)
        if not rows:
            break
        for row in rows:
            record = state.conversation_store.get(row["session_id"])
            if not record:
                continue
            if research_block(record.input_json).get("run_id") == run_id:
                return record
        offset += 50
        scanned += 50
    return None


def _reference_for_research(research: dict[str, Any]) -> Optional[dict[str, Any]]:
    dataset_id = research.get("dataset_id")
    cluster_id = research.get("cluster_id")
    if not dataset_id or not cluster_id:
        return None
    try:
        pack = get_loader().get_pack(dataset_id, cluster_id, research.get("pack_version"))
    except Exception as exc:
        raise_pack_http(exc)
        raise
    if pack.reference is None:
        return None
    return pack.reference.model_dump(mode="json")


def _output_from_record(record) -> dict[str, Any]:
    texts = []
    for msg in record.dialog_history or []:
        if isinstance(msg, dict) and msg.get("message"):
            texts.append(str(msg["message"]))
    return {"text": "\n".join(texts)}


def score_run(
    run_id: str,
    *,
    output: Optional[dict[str, Any]] = None,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    record = _session_for_run(run_id)
    if session_id and not record:
        from api import state

        record = state.conversation_store.get(session_id)
    research = research_block(record.input_json) if record else {}
    if record and research.get("run_id") and research.get("run_id") != run_id:
        raise HTTPException(status_code=400, detail="run_id does not match session")
    if not research and record is None:
        indexed = claim_service.get_store().get_run(run_id)
        if not indexed:
            raise HTTPException(status_code=404, detail=f"research run not found: {run_id}")
        research = indexed
    chain = claim_service.claim_chain(run_id)
    reference = _reference_for_research(research) if research.get("dataset_id") else None
    payload = score_research_output(
        output=output or (_output_from_record(record) if record else {}),
        claims=chain,
        reference=reference,
        leaked_reference=False,
    )
    report_id = new_report_id()
    created_at = _utcnow_iso()
    contract = EvalContract(
        report_id=report_id,
        run_id=run_id,
        reference_version=str((reference or {}).get("reference_version") or ""),
        rubric_version=RUBRIC_VERSION,
        machine_checks=payload["machine_checks"],
        legal_quality=payload["legal_quality"],
        review_records=claim_service.get_store().list_reviews(run_id),
        created_at=created_at,
    )
    result = {
        "report_id": report_id,
        "run_id": run_id,
        "session_id": record.session_id if record else session_id,
        "materials_hash": research.get("materials_hash"),
        "eval_contract": contract.model_dump(mode="json"),
        "rubric": payload,
        "disclaimer": RESEARCH_DISCLAIMER,
        "created_at": created_at,
    }
    claim_service.get_store().save_eval(
        {
            "report_id": report_id,
            "run_id": run_id,
            "session_id": result["session_id"],
            "payload": result,
            "created_at": created_at,
        }
    )
    return result


def add_human_review(
    run_id: str,
    *,
    review_state: str,
    reviewer: str = "",
    note: str = "",
    report_id: Optional[str] = None,
) -> dict[str, Any]:
    from core.research.enums import REVIEW_STATES

    if review_state not in REVIEW_STATES:
        raise HTTPException(status_code=400, detail=f"invalid review_state: {review_state}")
    if not claim_service.get_store().get_run(run_id) and _session_for_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"research run not found: {run_id}")
    record = {
        "review_id": str(uuid.uuid4()),
        "run_id": run_id,
        "report_id": report_id,
        "reviewer": reviewer,
        "review_state": review_state,
        "note": note,
        "created_at": _utcnow_iso(),
    }
    return claim_service.get_store().add_review(record)


def compare_runs(run_ids: list[str]) -> dict[str, Any]:
    cleaned = [item.strip() for item in run_ids if str(item).strip()]
    if len(cleaned) < 2:
        raise HTTPException(status_code=400, detail="compare requires at least two run_ids")
    runs = []
    for run_id in cleaned:
        record = _session_for_run(run_id)
        research = research_block(record.input_json) if record else {}
        indexed = claim_service.get_store().get_run(run_id) or {}
        eval_row = claim_service.get_store().latest_eval(run_id)
        runs.append(
            {
                "run_id": run_id,
                "derived_from": research.get("derived_from") or indexed.get("derived_from"),
                "session_id": record.session_id if record else indexed.get("session_id"),
                "dataset_id": research.get("dataset_id") or indexed.get("dataset_id"),
                "cluster_id": research.get("cluster_id") or indexed.get("cluster_id"),
                "pack_version": research.get("pack_version") or indexed.get("pack_version"),
                "materials_hash": research.get("materials_hash") or indexed.get("materials_hash"),
                "conditions": {
                    "visible_materials": research.get("visible_materials"),
                    "experiment_conditions": research.get("experiment_conditions"),
                    "model_config": research.get("model_config") or research.get("model_config_snapshot"),
                },
                "claim_count": len(claim_service.list_claim_events(run_id)),
                "eval": (eval_row or {}).get("payload"),
            }
        )
    clusters = {row.get("cluster_id") for row in runs if row.get("cluster_id")}
    hashes = {row.get("materials_hash") for row in runs}
    return {
        "runs": runs,
        "same_cluster": len(clusters) <= 1,
        "condition_differs": len(hashes) > 1,
        "disclaimer": RESEARCH_DISCLAIMER,
    }


def export_bundle(run_id: str) -> dict[str, Any]:
    record = _session_for_run(run_id)
    indexed = claim_service.get_store().get_run(run_id)
    if record is None and indexed is None:
        raise HTTPException(status_code=404, detail=f"research run not found: {run_id}")
    research = research_block(record.input_json) if record else {}
    meta = compact_research_meta(record.input_json) if record else {
        "run_id": run_id,
        "derived_from": (indexed or {}).get("derived_from"),
        "dataset_id": (indexed or {}).get("dataset_id"),
        "cluster_id": (indexed or {}).get("cluster_id"),
        "pack_version": (indexed or {}).get("pack_version"),
        "materials_hash": (indexed or {}).get("materials_hash"),
        "disclaimer": RESEARCH_DISCLAIMER,
    }
    eval_row = claim_service.get_store().latest_eval(run_id)
    eval_payload = (eval_row or {}).get("payload")
    if eval_payload is None:
        eval_payload = score_run(run_id, session_id=record.session_id if record else None)
    rubric = eval_payload.get("rubric") if isinstance(eval_payload, dict) else {}
    return {
        "run_id": run_id,
        "materials_hash": (meta or {}).get("materials_hash") or (indexed or {}).get("materials_hash"),
        "case": {
            "caption": research.get("caption") or (meta or {}).get("caption"),
            "dataset_id": (meta or {}).get("dataset_id"),
            "cluster_id": (meta or {}).get("cluster_id"),
            "pack_version": (meta or {}).get("pack_version"),
            "procedural_facts": research.get("procedural_facts") or [],
            "party_claims": research.get("party_claims") or [],
            "court_findings": research.get("court_findings") or [],
            "material_gaps": research.get("material_gaps") or [],
        },
        "rules": research.get("rules") or [],
        "conditions": {
            "visible_materials": research.get("visible_materials"),
            "experiment_conditions": research.get("experiment_conditions"),
            "model_config": research.get("model_config") or research.get("model_config_snapshot"),
            "derived_from": research.get("derived_from") or (indexed or {}).get("derived_from"),
        },
        "claims": claim_service.claim_chain(run_id),
        "audit": {
            "events": claim_service.list_claim_events(run_id),
            "reviews": claim_service.get_store().list_reviews(run_id),
            "dialog_history": list(record.dialog_history) if record else [],
        },
        "eval": eval_payload,
        "failures": (rubric or {}).get("failures") or [],
        "disputes": (rubric or {}).get("disagreements") or [],
        "undecidable": (rubric or {}).get("undecidable") or [],
        "disclaimer": RESEARCH_DISCLAIMER,
        "exported_at": _utcnow_iso(),
    }
