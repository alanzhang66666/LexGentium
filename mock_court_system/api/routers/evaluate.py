"""评估任务 路由。"""
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime
import json
import os
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse

from api import state
from api.services.evaluation import (
    EvaluationAttributionError,
    MissingFinalOutputError,
    evaluation_error,
    execute_evaluation_task,
    start_evaluation_task,
)
from api.services.evaluation_input import MissingEvaluationInputError
from api.schemas import (
    ApiRequest, ApiResponse, AutoAdvanceRequest, AutoAdvanceResponse,
    ConversationImportRequest, ConversationImportResponse,
    ConversationMessageRequest, ConversationMessageResponse,
    ConversationStartRequest, ConversationStartResponse,
    DualModeRequest, EvaluationReportSummary, EvaluationReportsResponse,
    EvaluationRequest, EvaluationResponse, EvaluationTaskStatus,
    FullSimulationRequest, FullSimulationStatusResponse,
    GameCounterfactualRequest, GameCreateRequest, GameEvaluateRequest,
    GameRoundRequest, GameStrategySetRequest, LawSearchRequest,
    LawSearchResponse, LiabilityCounterfactualRequest, LLMConfigRequest,
    MediationBargainRequest, MediationCreateRequest, MediationStatementRequest,
    MultiJudgeRequest, ProgressiveRAGRequest,
)

router = APIRouter()


def _task_response(
    *,
    report_id: str,
    status: EvaluationTaskStatus,
    message: str,
    results: Optional[Dict[str, Any]] = None,
    report_path: Optional[str] = None,
    session_id: Optional[str] = None,
    run_id: Optional[str] = None,
    error: Optional[Dict[str, str]] = None,
) -> EvaluationResponse:
    from api.services.evaluation import evaluation_provenance_view
    from api.schemas import CorrelationContext, EvaluationProvenanceView

    prov = evaluation_provenance_view(report_id)
    return EvaluationResponse(
        report_id=report_id,
        status=status,
        message=message,
        results=results,
        report_path=report_path,
        session_id=session_id,
        run_id=run_id,
        error=error if error is not None else evaluation_error(status, message),
        provenance=EvaluationProvenanceView(**prov) if prov else None,
        correlation=CorrelationContext(
            session_id=session_id,
            operation_id=f"eval:{report_id}",
            report_id=report_id,
            run_id=run_id,
        ),
    )


@router.post("/evaluate", response_model=EvaluationResponse)
async def start_evaluation(
    request: EvaluationRequest,
    background_tasks: BackgroundTasks,
):
    try:
        report_id, files = start_evaluation_task(
            request.scenarios,
            request.prediction_files,
            request.session_id,
            request.use_default_predictions,
            run_id=request.run_id,
        )
        background_tasks.add_task(execute_evaluation_task, report_id, request.scenarios, files)
        rec = state.evaluation_task_store.get(report_id)
        return _task_response(
            report_id=report_id,
            status="running",
            message="evaluation task started",
            session_id=request.session_id,
            run_id=rec.run_id if rec else request.run_id,
        )
    except HTTPException:
        raise
    except MissingFinalOutputError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": e.code, "message": str(e)},
        )
    except MissingEvaluationInputError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "code": e.code,
                "message": str(e),
                "field_errors": e.field_errors,
            },
        )
    except EvaluationAttributionError as e:
        raise HTTPException(
            status_code=400 if e.code in {"empty_body", "missing_final_output"} else 422,
            detail={
                "code": e.code,
                "message": str(e),
                "field_errors": [{"path": "/body", "reason": e.code}],
            },
        )
    except Exception:
        state.eval_logger.error("failed to start evaluation", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"code": "evaluation_start_failed", "message": "failed to start evaluation"},
        )



@router.get("/evaluation/status/{report_id}", response_model=EvaluationResponse)
async def get_evaluation_status(report_id: str):
    rec = state.evaluation_task_store.get(report_id)
    memory = state.evaluation_tasks.get(report_id) or {}
    if rec:
        return _task_response(
            report_id=report_id,
            status=rec.status,
            message=rec.message,
            results=rec.results(),
            report_path=rec.report_path,
            session_id=rec.session_id,
            run_id=rec.run_id,
            error=memory.get("error"),
        )
    if memory:
        return _task_response(
            report_id=report_id,
            status=memory["status"],
            message=memory["message"],
            results=memory.get("results"),
            report_path=memory.get("report_path"),
            session_id=memory.get("session_id"),
            run_id=memory.get("run_id"),
            error=memory.get("error"),
        )
    raise HTTPException(status_code=404, detail="evaluation task not found")



@router.get("/evaluation/results", response_model=EvaluationReportsResponse)
async def list_evaluation_results():
    results_dir = state.project_root / "evaluation" / "results"
    if not results_dir.exists():
        return EvaluationReportsResponse(reports=[])
    report_files = sorted(results_dir.glob("evaluation_report_*.json"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
    reports = []
    for report_file in report_files[:20]:
        try:
            with open(report_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            stem_id = report_file.stem.replace("evaluation_report_", "")
            scenarios = []
            if isinstance(data, dict):
                scenarios = [k for k in ("CD", "DD", "CI") if isinstance(data.get(k), list)]
            reports.append(EvaluationReportSummary(
                report_id=data.get("report_id", stem_id) if isinstance(data, dict) else stem_id,
                file_name=report_file.name,
                file_path=str(report_file),
                created_at=data.get("created_at") or datetime.fromtimestamp(report_file.stat().st_mtime).isoformat(),
                scenarios=scenarios,
            ))
        except Exception as e:
            state.eval_logger.warning(f"failed to read evaluation report {report_file}: {e}")
    return EvaluationReportsResponse(reports=reports)



@router.get("/evaluation/reports/{report_id}", response_model=EvaluationResponse)
async def get_evaluation_report(report_id: str):
    rec = state.evaluation_task_store.get(report_id)
    memory = state.evaluation_tasks.get(report_id) or {}
    if rec and rec.results():
        return _task_response(
            report_id=report_id,
            status=rec.status,
            message=rec.message,
            results=rec.results(),
            report_path=rec.report_path,
            session_id=rec.session_id,
            run_id=rec.run_id,
            error=memory.get("error"),
        )
    if memory.get("results"):
        return _task_response(
            report_id=report_id,
            status=memory["status"],
            message=memory["message"],
            results=memory["results"],
            report_path=memory.get("report_path"),
            session_id=memory.get("session_id"),
            run_id=memory.get("run_id"),
            error=memory.get("error"),
        )
    results_dir = state.project_root / "evaluation" / "results"
    report_file = results_dir / f"evaluation_report_{report_id}.json"
    if report_file.is_file():
        with open(report_file, "r", encoding="utf-8") as f:
            results = json.load(f)
        return _task_response(
            report_id=report_id,
            status="completed",
            message="evaluation report loaded",
            results=results,
            report_path=str(report_file),
            session_id=rec.session_id if rec else None,
            run_id=rec.run_id if rec else None,
        )
    raise HTTPException(status_code=404, detail="evaluation report not found")
