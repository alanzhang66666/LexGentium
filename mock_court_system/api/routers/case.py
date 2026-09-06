"""全流程案件模拟与锦标赛 路由。"""
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime
import uuid
import json
import queue
import threading
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse

from api import state
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

@router.post("/case/full-simulation")
async def start_full_simulation(
    request: FullSimulationRequest,
    background_tasks: BackgroundTasks,
):
    task_id = f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    state.simulation_tasks[task_id] = {
        "status": "pending",
        "message": "task created",
        "current_stage": None,
        "result": None,
        "created_at": state._utcnow_iso(),
        "mode": request.mode,
    }
    if request.mode == "tournament":
        background_tasks.add_task(state._run_tournament_task, task_id, request.case_info, request.tournament_rounds)
    else:
        background_tasks.add_task(state._run_full_simulation_task, task_id, request.case_info)
    label = "tournament" if request.mode == "tournament" else "full simulation"
    return {"task_id": task_id, "status": "pending", "message": f"{label} task started", "mode": request.mode}



@router.get("/case/full-simulation/{task_id}")
async def get_full_simulation_status(task_id: str):
    if task_id not in state.simulation_tasks:
        raise HTTPException(status_code=404, detail="task not found")
    task = state.simulation_tasks[task_id]
    return FullSimulationStatusResponse(
        task_id=task_id,
        status=task["status"],
        message=task["message"],
        current_stage=task.get("current_stage"),
        result=task.get("result"),
    )



@router.post("/case/full-simulation/stream")
async def stream_full_simulation(request: FullSimulationRequest):
    event_queue: queue.Queue = queue.Queue()

    def on_progress(stage, round_idx, role, finished):
        event_queue.put(state._sse_event("stage_transition", {"stage": stage, "round": round_idx, "role": role, "finished": finished}))

    def run_simulation():
        try:
            event_queue.put(state._sse_event("simulation_start", {"mode": request.mode, "case_info_keys": list(request.case_info.keys())}))
            if request.mode == "tournament":
                result = state._game_engine.run_tournament(request.case_info, rounds=request.tournament_rounds, on_progress=on_progress)
            else:
                result = state._orchestrator.run_full_case(request.case_info, on_progress=on_progress)
            event_queue.put(state._sse_event("simulation_complete", {"result": result.to_dict()}))
        except Exception as e:
            event_queue.put(state._sse_event("error", {"message": str(e)}))
        finally:
            event_queue.put(None)

    thread = threading.Thread(target=run_simulation, daemon=True)
    thread.start()

    async def event_generator():
        while True:
            try:
                event = await asyncio.to_thread(event_queue.get, timeout=300)
            except Exception:
                yield state._sse_event("error", {"message": "timeout"})
                break
            if event is None:
                break
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )

