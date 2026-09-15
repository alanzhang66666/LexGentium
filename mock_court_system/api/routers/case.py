"""全流程案件模拟与锦标赛 路由。"""
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime
import uuid
import json
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse

from api import state
from api.services.sse import sse_event
from api.schemas import (
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
    from api.services.simulation import create_simulation_task

    task_id = create_simulation_task(request.mode, request.session_id)
    if request.mode == "tournament":
        background_tasks.add_task(state._run_tournament_task, task_id, request.case_info, request.tournament_rounds)
    else:
        background_tasks.add_task(state._run_full_simulation_task, task_id, request.case_info)
    label = "tournament" if request.mode == "tournament" else "full simulation"
    return {
        "task_id": task_id,
        "status": "pending",
        "message": f"{label} task started",
        "mode": request.mode,
        "session_id": request.session_id,
    }



@router.get("/case/full-simulation/{task_id}")
async def get_full_simulation_status(task_id: str):
    task = state.load_simulation_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return FullSimulationStatusResponse(
        task_id=task_id,
        status=task["status"],
        message=task["message"],
        current_stage=task.get("current_stage"),
        result=task.get("result"),
    )



@router.post("/case/full-simulation/stream")
async def stream_full_simulation(request: FullSimulationRequest):
    from api.services.simulation import create_simulation_task

    task_id = create_simulation_task(request.mode, request.session_id)
    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue = asyncio.Queue()

    def on_progress(stage, round_idx, role, finished, sub_stage=None):
        loop.call_soon_threadsafe(event_queue.put_nowait, sse_event("stage_transition", {
            "stage": stage,
            "round": round_idx,
            "role": role,
            "finished": finished,
            "sub_stage": sub_stage,
        }))

    async def run_simulation():
        try:
            await event_queue.put(sse_event("simulation_start", {
                "mode": request.mode,
                "task_id": task_id,
                "session_id": request.session_id,
                "case_info_keys": list(request.case_info.keys()),
            }))
            if request.mode == "tournament":
                result = await asyncio.to_thread(
                    state._game_engine.run_tournament,
                    request.case_info,
                    request.tournament_rounds,
                    on_progress=on_progress,
                )
            else:
                result = await asyncio.to_thread(
                    state._orchestrator.run_full_case,
                    request.case_info,
                    on_progress=on_progress,
                )
            await event_queue.put(sse_event("simulation_complete", {"result": result.to_dict(), "task_id": task_id}))
        except Exception as e:
            await event_queue.put(sse_event("error", {"message": str(e)}))
        finally:
            await event_queue.put(None)

    worker = asyncio.create_task(run_simulation())

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=300)
                except asyncio.TimeoutError:
                    yield sse_event("error", {"message": "timeout"})
                    break
                if event is None:
                    break
                yield event
        finally:
            if not worker.done():
                worker.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )

