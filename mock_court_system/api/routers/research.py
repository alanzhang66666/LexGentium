"""Research pack listing, source lookup, and annotation overlays."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.services import annotation
from api.services.materials import PackNotFoundError, PackVersionMismatchError, ResearchPackError

router = APIRouter()


class FieldPatchRequest(BaseModel):
    field_path: str
    actor: str = "anonymous"
    note: str = ""
    value: Any = None
    review_state: Optional[str] = None
    patch: Optional[dict[str, Any]] = None
    pack_version: Optional[str] = None


class ReviewStateRequest(BaseModel):
    review_state: str
    actor: str = "anonymous"
    note: str = ""
    pack_version: Optional[str] = None
    field_path: str = Field(default="review_state")


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PackNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, PackVersionMismatchError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, annotation.FieldNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, annotation.InvalidReviewStateError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, annotation.AnnotationError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ResearchPackError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    raise exc


@router.get("/research/packs")
async def list_annotated_research_packs(dataset: Optional[str] = None):
    try:
        packs = annotation.list_annotated_packs(dataset)
        return {"packs": packs, "total": len(packs)}
    except Exception as exc:
        raise _http_error(exc)


@router.get("/research/packs/{dataset_id}/{cluster_id}")
async def get_annotated_research_pack(
    dataset_id: str,
    cluster_id: str,
    pack_version: Optional[str] = None,
    include_reference: bool = True,
):
    try:
        return annotation.get_annotated_pack(
            dataset_id,
            cluster_id,
            pack_version=pack_version,
            include_reference=include_reference,
        )
    except Exception as exc:
        raise _http_error(exc)


@router.get("/research/packs/{dataset_id}/{cluster_id}/source")
async def get_research_source(
    dataset_id: str,
    cluster_id: str,
    source_id: str,
    pack_version: Optional[str] = None,
):
    try:
        return annotation.get_source_text(
            dataset_id,
            cluster_id,
            source_id,
            pack_version=pack_version,
        )
    except Exception as exc:
        raise _http_error(exc)


@router.patch("/research/packs/{dataset_id}/{cluster_id}/fields")
async def patch_research_field(dataset_id: str, cluster_id: str, req: FieldPatchRequest):
    try:
        return annotation.patch_field(
            dataset_id,
            cluster_id,
            field_path=req.field_path,
            actor=req.actor,
            note=req.note,
            value=req.value,
            review_state=req.review_state,
            patch=req.patch,
            pack_version=req.pack_version,
        )
    except Exception as exc:
        raise _http_error(exc)


@router.patch("/research/packs/{dataset_id}/{cluster_id}/review")
async def patch_research_review(dataset_id: str, cluster_id: str, req: ReviewStateRequest):
    try:
        return annotation.patch_field(
            dataset_id,
            cluster_id,
            field_path=req.field_path or "review_state",
            actor=req.actor,
            note=req.note,
            review_state=req.review_state,
            pack_version=req.pack_version,
        )
    except Exception as exc:
        raise _http_error(exc)


@router.get("/research/packs/{dataset_id}/{cluster_id}/changelog")
async def list_research_changelog(
    dataset_id: str,
    cluster_id: str,
    pack_version: Optional[str] = None,
    limit: int = 200,
):
    try:
        return annotation.list_change_log(
            dataset_id,
            cluster_id,
            pack_version=pack_version,
            limit=limit,
        )
    except Exception as exc:
        raise _http_error(exc)


@router.get("/research/runs")
async def list_research_runs(dataset_id: Optional[str] = None, cluster_id: Optional[str] = None):
    from api.services.claims import get_store

    runs = get_store().list_runs(dataset_id=dataset_id, cluster_id=cluster_id)
    return {"runs": runs, "total": len(runs)}


@router.get("/research/runs/{run_id}")
async def get_research_run(run_id: str):
    from api.services.claims import claim_chain, get_store, list_claim_events

    record = get_store().get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"research run not found: {run_id}")
    return {
        **record,
        "claim_chain": claim_chain(run_id),
        "events": list_claim_events(run_id),
        "reviews": get_store().list_reviews(run_id),
        "eval": get_store().latest_eval(run_id),
    }


@router.post("/research/evaluate")
async def evaluate_research_run(body: dict[str, Any]):
    from api.services.research_eval import score_run

    run_id = str(body.get("run_id") or "").strip()
    session_id = str(body.get("session_id") or "").strip() or None
    if not run_id and session_id:
        from api.services.conversation import require_session
        from core.research.runtime import research_block

        research = research_block(require_session(session_id).input_json)
        run_id = str(research.get("run_id") or "")
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id or session_id is required")
    output = body.get("output") if isinstance(body.get("output"), dict) else None
    return score_run(run_id, output=output, session_id=session_id)


@router.post("/research/review")
async def review_research_run(body: dict[str, Any]):
    from api.services.research_eval import add_human_review

    run_id = str(body.get("run_id") or "").strip()
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")
    return add_human_review(
        run_id,
        review_state=str(body.get("review_state") or ""),
        reviewer=str(body.get("reviewer") or ""),
        note=str(body.get("note") or ""),
        report_id=body.get("report_id"),
    )


@router.get("/research/compare")
async def compare_research_runs(run_ids: str = ""):
    from api.services.research_eval import compare_runs

    ids = [item.strip() for item in run_ids.split(",") if item.strip()]
    return compare_runs(ids)


@router.get("/research/export/{run_id}")
async def export_research_run(run_id: str):
    from api.services.research_eval import export_bundle

    return export_bundle(run_id)
