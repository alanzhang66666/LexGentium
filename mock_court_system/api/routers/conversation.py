"""会话式模拟路由：校验与 HTTP，业务在 services.conversation。"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api import state
from api.services import conversation as conv
from api.services.sse import sse_event
from api_schemas import (
    AutoAdvanceRequest,
    AutoAdvanceResponse,
    ConversationDeriveRequest,
    ConversationImportRequest,
    ConversationImportResponse,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationStartRequest,
    ConversationStartResponse,
    ResearchClaimRequest,
)

router = APIRouter()


@router.post("/conversation/start", response_model=ConversationStartResponse)
async def start_conversation(req: ConversationStartRequest):
    try:
        return ConversationStartResponse(**conv.start_session(
            req.scenario,
            req.case_id,
            req.input_json,
            dataset_id=req.dataset_id,
            cluster_id=req.cluster_id,
            pack_version=req.pack_version,
            derived_from=req.derived_from,
            visible_materials=req.visible_materials,
            experiment_conditions=req.experiment_conditions,
            model_config=req.model_config_snapshot,
        ))
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"启动会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"启动会话失败: {str(e)}")


@router.post("/conversation/import", response_model=ConversationImportResponse)
async def import_conversation(req: ConversationImportRequest):
    try:
        data = conv.import_session(req.scenario, req.case_id, req.dialog_history, req.input_json)
        return ConversationImportResponse(**{k: data[k] for k in (
            "session_id", "scenario", "case_id", "created_at", "message_count", "is_finished",
        )})
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"导入会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入会话失败: {str(e)}")


@router.post("/conversation/{session_id}/message", response_model=ConversationMessageResponse)
async def send_message(session_id: str, req: ConversationMessageRequest):
    try:
        data = conv.send_message(session_id, req.message, req.role)
        return ConversationMessageResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"发送消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"发送消息失败: {str(e)}")


@router.get("/conversation/list")
async def list_conversations(limit: int = 50, offset: int = 0):
    try:
        return conv.list_sessions(limit=limit, offset=offset)
    except Exception as e:
        state.eval_logger.error(f"获取会话列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@router.get("/conversation/{session_id}")
async def get_conversation(session_id: str):
    try:
        return conv.get_session(session_id)
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"获取会话详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取会话详情失败: {str(e)}")


@router.delete("/conversation/{session_id}")
async def delete_conversation(session_id: str):
    try:
        return conv.delete_session(session_id)
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"删除会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")


@router.post("/conversation/{session_id}/auto-advance", response_model=AutoAdvanceResponse)
async def auto_advance_conversation(session_id: str, req: AutoAdvanceRequest):
    try:
        data = await conv.auto_advance(session_id, req.max_rounds, req.auto_reply_roles)
        return AutoAdvanceResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"自动推进失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"自动推进失败: {str(e)}")


@router.get("/conversation/{session_id}/compliance")
async def get_conversation_compliance(session_id: str):
    return conv.get_compliance(session_id)


@router.post("/conversation/derive", response_model=ConversationStartResponse)
async def derive_conversation(req: ConversationDeriveRequest):
    if not req.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    try:
        return ConversationStartResponse(**conv.derive_session(
            req.session_id,
            visible_materials=req.visible_materials,
            experiment_conditions=req.experiment_conditions,
            model_config=req.model_config_snapshot,
        ))
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"派生运行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"派生运行失败: {str(e)}")


@router.get("/conversation/{session_id}/claims")
async def get_conversation_claims(session_id: str):
    from api.services.claims import session_claim_bundle

    record = conv.require_session(session_id)
    return {"session_id": session_id, **session_claim_bundle(record)}


@router.post("/conversation/{session_id}/claims")
async def post_conversation_claim(session_id: str, req: ResearchClaimRequest):
    from api.services.claims import append_session_claim

    record = conv.require_session(session_id)
    return append_session_claim(record, req.model_dump())


@router.post("/conversation/{session_id}/message/stream")
async def stream_message(session_id: str, req: ConversationMessageRequest):
    record = conv.require_session(session_id)
    conv.append_user_message(record, req.message, req.role)

    async def event_stream():
        import asyncio as _asyncio
        import time as _time

        loop = _asyncio.get_running_loop()
        q: _asyncio.Queue = _asyncio.Queue()

        def _hook(delta: str):
            loop.call_soon_threadsafe(q.put_nowait, ("delta", delta))

        async def _run():
            try:
                state.llm_client.set_stream_hook(_hook)
                try:
                    role, text, finished = await _asyncio.to_thread(
                        state.run_agent_turn,
                        scenario=record.scenario,
                        case_id=record.case_id,
                        dialog_history=record.dialog_history,
                        input_json=conv._with_session_id(record, req.role),
                    )
                finally:
                    state.llm_client.clear_stream_hook()
            except Exception as e:
                state.eval_logger.error(f"stream message failed: {e}", exc_info=True)
                await q.put(("error", str(e)))
                return
            await q.put(("done", (role, text, finished)))

        worker = _asyncio.create_task(_run())
        last_beat = _time.time()
        try:
            while True:
                try:
                    kind, payload = await _asyncio.wait_for(q.get(), timeout=5.0)
                except _asyncio.TimeoutError:
                    if _time.time() - last_beat > 4.5:
                        last_beat = _time.time()
                        yield sse_event("heartbeat", {"type": "heartbeat"})
                    continue

                if kind == "delta":
                    last_beat = _time.time()
                    yield f"data: {json.dumps({'type': 'delta', 'text': payload}, ensure_ascii=False)}\n\n"
                elif kind == "error":
                    yield f"data: {json.dumps({'type': 'final', 'error': str(payload)}, ensure_ascii=False)}\n\n"
                    return
                else:
                    role, text, finished = payload
                    final = conv.finalize_stream_turn(record, session_id, role, text, finished)
                    yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"
                    return
        finally:
            if not worker.done():
                worker.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
