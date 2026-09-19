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

def _capacity_rejection() -> JSONResponse:
    """饱和时在任何 LLM 调用/持久化之前返回 429。"""
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "capacity_exceeded",
                "message": "high-cost operation capacity saturated",
                "retry_after_seconds": state.capacity_guard.retry_after_seconds,
            }
        },
        headers={"Retry-After": str(state.capacity_guard.retry_after_seconds)},
    )


@router.post("/case/full-simulation")
async def start_full_simulation(
    request: FullSimulationRequest,
    background_tasks: BackgroundTasks,
):
    from api.services.simulation import create_simulation_task

    permit = state.capacity_guard.try_acquire()
    if permit is None:
        return _capacity_rejection()

    task_id = create_simulation_task(request.mode, request.session_id)
    if request.mode == "tournament":
        background_tasks.add_task(state._run_tournament_task, task_id, request.case_info, request.tournament_rounds, permit)
    else:
        background_tasks.add_task(state._run_full_simulation_task, task_id, request.case_info, permit)
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
    from api.middleware.request_context import current_request_context
    from api.services.operation_coordinator import CommitCapabilityLost
    from core.store.operation_store import OperationConflict, canonical_digest

    permit = state.capacity_guard.try_acquire()
    if permit is None:
        return _capacity_rejection()

    ctx = current_request_context()
    operation_id = request.operation_id or f"sim-{uuid.uuid4().hex[:16]}"
    try:
        handle = state.operation_coordinator.begin(
            operation_id,
            "case.full_simulation",
            {"mode": request.mode, "session_id": request.session_id,
             "tournament_rounds": request.tournament_rounds,
             "case_info": request.case_info},
            ctx.request_id,
        )
    except OperationConflict:
        permit.release()
        raise HTTPException(status_code=409, detail="operation_id_conflict")

    task_id = create_simulation_task(request.mode, request.session_id)
    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue = asyncio.Queue()

    def on_progress(stage, round_idx, role, finished, sub_stage=None):
        loop.call_soon_threadsafe(event_queue.put_nowait, ("stage_transition", {
            "stage": stage,
            "round": round_idx,
            "role": role,
            "finished": finished,
            "sub_stage": sub_stage,
        }))

    async def run_simulation():
        try:
            await event_queue.put(("simulation_start", {
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
            await event_queue.put(("simulation_complete", {"result": result.to_dict(), "task_id": task_id}))
        except Exception as e:
            await event_queue.put(("error", {"message": str(e)}))
        finally:
            await event_queue.put(None)

    worker = asyncio.create_task(run_simulation())
    state.simulation_tasks[task_id]["worker"] = worker
    state.operation_coordinator.mark_running(handle)

    async def event_generator():
        coordinator = state.operation_coordinator
        try:
            for f in list(handle.frames):
                yield f
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=300)
                except asyncio.TimeoutError:
                    coordinator.fail(handle, "timeout", retriable=True)
                    frame = coordinator.emit_domain(handle, "error", {"message": "timeout"})
                    if frame:
                        yield frame
                    break
                if event is None:
                    break
                etype, edata = event
                if etype == "error":
                    coordinator.fail(handle, "worker_error", retriable=True)
                elif etype == "simulation_complete":
                    try:
                        coordinator.commit(
                            handle, "simulation_task", task_id,
                            canonical_digest(edata.get("result")), "",
                        )
                    except CommitCapabilityLost:
                        etype, edata = "cancelled", {"reason": "client_disconnect"}
                frame = coordinator.emit_domain(handle, etype, edata)
                if frame:
                    yield frame
        finally:
            if not worker.done():
                worker.cancel()
            # terminal：清 queue、释放容量 permit 与 runtime 引用
            while not event_queue.empty():
                event_queue.get_nowait()
            permit.release()
            state.simulation_tasks.get(task_id, {}).pop("worker", None)
            coordinator.disconnect(operation_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )

