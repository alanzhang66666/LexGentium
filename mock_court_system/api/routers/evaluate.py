"""评估任务 路由。"""
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime
import json
import os
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse

from api import state
from api.services.evaluation import EvaluationAttributionError, start_evaluation_task
from api_schemas import (
    ApiRequest, ApiResponse, AutoAdvanceRequest, AutoAdvanceResponse,
    ConversationImportRequest, ConversationImportResponse,
    ConversationMessageRequest, ConversationMessageResponse,
    ConversationStartRequest, ConversationStartResponse,
    DualModeRequest, EvaluationRequest, EvaluationResponse,
    FullSimulationRequest, FullSimulationStatusResponse,
    GameCounterfactualRequest, GameCreateRequest, GameEvaluateRequest,
    GameRoundRequest, GameStrategySetRequest, LawSearchRequest,
    LawSearchResponse, LiabilityCounterfactualRequest, LLMConfigRequest,
    MediationBargainRequest, MediationCreateRequest, MediationStatementRequest,
    MultiJudgeRequest, ProgressiveRAGRequest,
)

router = APIRouter()

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
        background_tasks.add_task(state.run_evaluation_task, report_id, request.scenarios, files)
        rec = state.evaluation_task_store.get(report_id)
        return EvaluationResponse(
            report_id=report_id,
            status="running",
            message="evaluation task started",
            results=None,
            report_path=None,
            session_id=request.session_id,
            run_id=rec.run_id if rec else request.run_id,
        )
    except HTTPException:
        raise
    except EvaluationAttributionError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": str(e)})
    except Exception as e:
        state.eval_logger.error(f"failed to start evaluation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"failed to start evaluation: {str(e)}")



@router.get("/evaluation/status/{report_id}")
async def get_evaluation_status(report_id: str):
    rec = state.evaluation_task_store.get(report_id)
    if rec:
        return EvaluationResponse(
            report_id=report_id,
            status=rec.status,
            message=rec.message,
            results=rec.results(),
            report_path=rec.report_path,
            session_id=rec.session_id,
            run_id=rec.run_id,
        )
    if report_id in state.evaluation_tasks:
        task = state.evaluation_tasks[report_id]
        return EvaluationResponse(
            report_id=report_id,
            status=task["status"],
            message=task["message"],
            results=task.get("results"),
            report_path=task.get("report_path"),
            session_id=task.get("session_id"),
            run_id=task.get("run_id"),
        )
    raise HTTPException(status_code=404, detail="evaluation task not found")



@router.get("/evaluation/results")
async def list_evaluation_results():
    results_dir = state.project_root / "evaluation" / "results"
    if not results_dir.exists():
        return {"reports": []}
    report_files = sorted(results_dir.glob("evaluation_report_*.json"), reverse=True)
    reports = []
    for report_file in report_files[:20]:
        try:
            with open(report_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            stem_id = report_file.stem.replace("evaluation_report_", "")
            scenarios = []
            if isinstance(data, dict):
                scenarios = [k for k in data.keys() if k not in {"report_id", "run_id", "eval_contract"}]
            reports.append({
                "report_id": data.get("report_id", stem_id) if isinstance(data, dict) else stem_id,
                "file_name": report_file.name,
                "file_path": str(report_file),
                "created_at": stem_id,
                "scenarios": scenarios,
            })
        except Exception as e:
            state.eval_logger.warning(f"failed to read evaluation report {report_file}: {e}")
    return {"reports": reports}



@router.get("/evaluation/reports/{report_id}")
async def get_evaluation_report(report_id: str):
    rec = state.evaluation_task_store.get(report_id)
    if rec and rec.results():
        return {"report_id": report_id, "status": rec.status, "results": rec.results(), "report_path": rec.report_path}
    if report_id in state.evaluation_tasks:
        task = state.evaluation_tasks[report_id]
        if task.get("results"):
            return {"report_id": report_id, "status": task["status"], "results": task["results"], "report_path": task.get("report_path")}
    results_dir = state.project_root / "evaluation" / "results"
    report_file = results_dir / f"evaluation_report_{report_id}.json"
    if report_file.is_file():
        with open(report_file, "r", encoding="utf-8") as f:
            results = json.load(f)
        return {"report_id": report_id, "status": "completed", "results": results, "report_path": str(report_file)}
    raise HTTPException(status_code=404, detail="evaluation report not found")

