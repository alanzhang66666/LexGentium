"""会话式模拟 路由。"""
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime
import uuid
import json
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse

from api import state
from api.services.conversation import _with_session_id
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

@router.post("/conversation/start", response_model=ConversationStartResponse)
async def start_conversation(req: ConversationStartRequest):
    from api.services.conversation import start_session
    try:
        scenario = req.scenario.upper()
        result = start_session(
            scenario=scenario,
            case_id=req.case_id,
            input_json=req.input_json,
            dataset_id=req.dataset_id,
            cluster_id=req.cluster_id,
            pack_version=req.pack_version,
            derived_from=req.derived_from,
            visible_materials=req.visible_materials,
            experiment_conditions=req.experiment_conditions,
            model_config=req.model_config_,
            visibility_grants=req.visibility_grants,
        )
        return ConversationStartResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"启动会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"启动会话失败: {str(e)}")


@router.post("/conversation/import", response_model=ConversationImportResponse)
async def import_conversation(req: ConversationImportRequest):
    try:
        scenario = req.scenario.upper()
        if scenario not in ["CD", "DD", "CI"]:
            raise HTTPException(status_code=400, detail=f"Invalid scenario: {scenario}")
        if not isinstance(req.dialog_history, list):
            raise HTTPException(status_code=400, detail="error")

        session_id = state.generate_session_id()
        record = state.conversation_store.create(
            session_id=session_id,
            scenario=scenario,
            case_id=req.case_id,
            input_json=req.input_json or {},
        )

        # 清理对话历史（保留最近 turn）
        cleaned = []
        for idx, msg in enumerate(req.dialog_history):
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            message = msg.get("message")
            if not role or message is None:
                continue
            cleaned.append(
                {
                    "turn": msg.get("turn", idx),
                    "role": role,
                    "message": message,
                }
            )

        record.dialog_history = cleaned
        state.conversation_store.save(record)

        is_finished = bool(cleaned and cleaned[-1].get("role") == "Final")
        return ConversationImportResponse(
            session_id=session_id,
            scenario=scenario,
            case_id=req.case_id,
            created_at=record.created_at,
            message_count=len(cleaned),
            is_finished=is_finished,
        )
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"导入会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导入会话失败: {str(e)}")


@router.post("/conversation/{session_id}/message", response_model=ConversationMessageResponse)
async def send_message(session_id: str, req: ConversationMessageRequest):
    try:
        record = state.conversation_store.get(session_id)
        if not record:
            raise HTTPException(status_code=404, detail="error")

        scenario = record.scenario
        case_id = record.case_id
        dialog_history = record.dialog_history
        input_json = record.input_json
        
        # 确定用户角色
        user_role = req.role
        if not user_role:
            if scenario in ["CD", "DD"]:
                user_role = "Client"
            elif scenario == "CI":
                user_role = "Plaintiff"  # CI 场景默认由原告先发言
            else:
                user_role = "User"
        
        # 构造用户消息
        turn = len(dialog_history)
        user_message = {
            "turn": turn,
            "role": user_role,
            "message": req.message
        }
        dialog_history.append(user_message)

        # 研究协议停止判定：命中上限/材料不足时提交终态，不再调用 CI/support LLM
        from api.services.conversation import commit_research_stop, research_session_stop_reason
        stop_reason = research_session_stop_reason(record)
        if stop_reason:
            notice = commit_research_stop(record, stop_reason)
            return ConversationMessageResponse(
                session_id=session_id,
                response={"role": "Judge", "message": notice},
                dialog_history=list(dialog_history),
                is_finished=True,
                stop_reason=stop_reason,
            )

        reasoning_state = state.ci_reasoning_state_from_record(record)
        session_ci = state.new_session_ci_agent() if scenario == "CI" else None
        response_role, response_text, is_finished = state.run_agent_turn(
            scenario=scenario,
            case_id=case_id,
            dialog_history=dialog_history,
            input_json=_with_session_id(record, user_role),
            reasoning_state=reasoning_state,
            ci_agent=session_ci,
        )
        reasoning_meta = None
        if scenario == "CI":
            state.save_ci_reasoning_state(record, session_ci)
            reasoning_meta = {
                "judgment_status": getattr(session_ci, "judgment_status", "failed"),
                "citation_report": getattr(session_ci, "citation_report", None),
                "case_warnings": list(getattr(session_ci, "case_warnings", [])),
            }

        # 构造响应消息
        turn += 1
        response_message = {
            "turn": turn,
            "role": response_role,
            "message": response_text
        }
        dialog_history.append(response_message)

        # 保存会话记录
        record.dialog_history = dialog_history
        state.conversation_store.save(record)

        # 离线兜底模板生成的回复打上 degraded 标记，避免污染正式实验数据
        degraded = response_text.startswith("[离线模式回复]") or "（离线演示模板" in response_text

        return ConversationMessageResponse(
            session_id=session_id,
            response={"role": response_role, "message": response_text},
            dialog_history=list(dialog_history),
            is_finished=is_finished,
            degraded=degraded,
            reasoning_meta=reasoning_meta,
        )
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"发送消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"发送消息失败: {str(e)}")


@router.get("/conversation/list")
async def list_conversations(limit: int = 50, offset: int = 0):
    try:
        from api.services.conversation import list_sessions
        return list_sessions(limit=limit, offset=offset)
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"获取会话列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@router.get("/conversation/{session_id}")
async def get_conversation(session_id: str):
    try:
        from api.services.conversation import get_session
        return get_session(session_id)
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"获取会话详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取会话详情失败: {str(e)}")


@router.delete("/conversation/{session_id}")
async def delete_conversation(session_id: str):
    try:
        ok = state.conversation_store.delete(session_id)
        if not ok:
            raise HTTPException(status_code=404, detail="error")
        
        return {"message": "deleted", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"删除会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")


@router.post("/conversation/{session_id}/auto-advance", response_model=AutoAdvanceResponse)
async def auto_advance_conversation(session_id: str, req: AutoAdvanceRequest):
    # Auto-advance conversation by alternating agent turns.
    # Stops when max_rounds is reached or the session is finished.
    #
    try:
        record = state.conversation_store.get(session_id)
        if not record:
            raise HTTPException(status_code=404, detail="error")

        scenario = record.scenario
        case_id = record.case_id
        dialog_history = list(record.dialog_history)
        input_json = record.input_json
        auto_roles = state._determine_auto_roles(scenario, req.auto_reply_roles)

        # 研究协议停止判定：命中上限/材料不足时提交终态，本轮不再推进
        from api.services.conversation import commit_research_stop, research_session_stop_reason
        stop_reason = research_session_stop_reason(record)
        if stop_reason:
            commit_research_stop(record, stop_reason)
            return AutoAdvanceResponse(
                session_id=session_id,
                rounds_played=0,
                dialog_history=list(record.dialog_history),
                is_finished=True,
                current_stage="stopped",
                next_speaker=None,
                available_actions=[],
                stop_reason=stop_reason,
            )

        rounds_played = 0
        is_finished = False

        for _ in range(req.max_rounds):
            # --- Step A: 各 Agent 依次推进一步 ---
            response_role, response_text, finished = state.run_agent_turn(
                scenario=scenario,
                case_id=case_id,
                dialog_history=dialog_history,
                input_json=_with_session_id(record, dialog_history[-1].get("role") if dialog_history else None),
            )

            turn = len(dialog_history)
            dialog_history.append({
                "turn": turn,
                "role": response_role,
                "message": response_text,
            })
            rounds_played += 1

            if finished:
                is_finished = True
                break

            # --- Step B: SimAgent 按策略生成当事人发言 ---
            meta = state._infer_conversation_meta(scenario, dialog_history)
            sim_role = meta.get("next_speaker")
            if not sim_role or sim_role not in auto_roles:
                break

            sim_text = await asyncio.to_thread(
                state.sim_agent.simulate_role,
                sim_role,
                dialog_history,
                _with_session_id(record, sim_role),
                scenario,
            )

            turn = len(dialog_history)
            dialog_history.append({
                "turn": turn,
                "role": sim_role,
                "message": sim_text,
            })

            # 轮内达到研究上限即停，不再发起下一轮 CI/support 调用
            record.dialog_history = dialog_history
            stop_reason = research_session_stop_reason(record)
            if stop_reason:
                break

        record.dialog_history = dialog_history
        state.conversation_store.save(record)

        if stop_reason:
            commit_research_stop(record, stop_reason)
            return AutoAdvanceResponse(
                session_id=session_id,
                rounds_played=rounds_played,
                dialog_history=list(record.dialog_history),
                is_finished=True,
                current_stage="stopped",
                next_speaker=None,
                available_actions=[],
                stop_reason=stop_reason,
            )

        final_meta = state._infer_conversation_meta(scenario, dialog_history)

        return AutoAdvanceResponse(
            session_id=session_id,
            rounds_played=rounds_played,
            dialog_history=dialog_history,
            is_finished=final_meta["is_finished"],
            current_stage=final_meta["current_stage"],
            next_speaker=final_meta["next_speaker"],
            available_actions=final_meta["available_actions"],
        )
    except HTTPException:
        raise
    except Exception as e:
        state.eval_logger.error(f"获取合规报告失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取合规报告失败: {str(e)}")


@router.get("/conversation/{session_id}/compliance")
async def get_conversation_compliance(session_id: str):
    record = state.conversation_store.get(session_id)
    if not record:
        raise HTTPException(status_code=404, detail="error")

    if record.scenario != "CI":
        return {
            "session_id": session_id,
            "scenario": record.scenario,
            "compliance": {"message": "PFS compliance tracking only applies to CI scenario"},
        }

    try:
        realtime = state.ci_agent.state_machine.get_realtime_compliance()
    except Exception as e:
        realtime = {"error": f"合规追踪失败: {str(e)}"}

    return {
        "session_id": session_id,
        "scenario": record.scenario,
        "compliance": realtime,
    }


@router.post("/conversation/{session_id}/message/stream")
async def stream_message(session_id: str, req: ConversationMessageRequest):
    """流式对话消息：SSE 返回。

    事件序列：
      {"type":"delta","text":...}      —— 生成增量（可多次）
      {"type":"final", ...}            —— 完整响应（字段与 POST /message 一致，含 degraded）
    """
    try:
        record = state.conversation_store.get(session_id)
    except Exception:
        record = None
    if not record:
        raise HTTPException(status_code=404, detail="error")

    scenario = record.scenario
    case_id = record.case_id
    dialog_history = record.dialog_history
    input_json = record.input_json

    # 确定用户角色（与非流式端点保持一致）
    user_role = req.role
    if not user_role:
        if scenario in ["CD", "DD"]:
            user_role = "Client"
        elif scenario == "CI":
            user_role = "Plaintiff"
        else:
            user_role = "User"

    turn = len(dialog_history)
    dialog_history.append({
        "turn": turn,
        "role": user_role,
        "message": req.message,
    })

    session_ci = state.new_session_ci_agent() if scenario == "CI" else None

    # Operation ledger：begin 同步发 start；冲突 op-id → 409；已提交 → 回放
    from api.middleware.request_context import current_request_context
    from api.services.operation_coordinator import CommitCapabilityLost
    from core.store.operation_store import OperationConflict, canonical_digest

    ctx = current_request_context()
    operation_id = req.operation_id or f"msg-{uuid.uuid4().hex[:16]}"
    try:
        handle = state.operation_coordinator.begin(
            operation_id,
            "conversation.message",
            {"session_id": session_id, "message": req.message, "role": user_role},
            ctx.request_id,
            state_fingerprint=canonical_digest(record.dialog_history),
        )
    except OperationConflict:
        raise HTTPException(status_code=409, detail="operation_id_conflict")

    stream_headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

    if handle.replayed:
        # 已提交操作：从 store 重建 final，不重复 LLM
        fresh = state.conversation_store.get(session_id)
        final_payload = {
            "session_id": session_id,
            "response": (fresh.dialog_history[-1] if fresh and fresh.dialog_history else {}),
            "dialog_history": list(fresh.dialog_history) if fresh else [],
            "is_finished": True,
            "replayed": True,
            "degraded": False,
            "reasoning_meta": None,
        }

        async def replay_stream():
            try:
                yield handle.encoder.emit("start") or ""
                frame = state.operation_coordinator.emit_domain(handle, "final", final_payload)
                if frame:
                    yield frame
            finally:
                state.operation_coordinator.disconnect(operation_id)

        return StreamingResponse(replay_stream(), media_type="text/event-stream", headers=stream_headers)

    state.operation_coordinator.mark_running(handle)

    # 研究协议停止判定：命中上限/材料不足时直接发终态事件，不再调 LLM
    from api.services.conversation import commit_research_stop, research_session_stop_reason
    stop_reason = research_session_stop_reason(record)
    if stop_reason:
        notice = commit_research_stop(record, stop_reason)

        async def stopped_stream():
            try:
                for f in list(handle.frames):
                    yield f
                final = {
                    "session_id": session_id,
                    "response": {"role": "Judge", "message": notice},
                    "dialog_history": list(record.dialog_history),
                    "is_finished": True,
                    "stop_reason": stop_reason,
                    "degraded": False,
                    "reasoning_meta": None,
                }
                try:
                    from api.services.runtime_unit_of_work import (
                        RuntimeUnitOfWork,
                        UnitOfWorkError,
                    )

                    fingerprint = canonical_digest(record.dialog_history)
                    with RuntimeUnitOfWork(
                        state.checkpoint_store,
                        operation_store=state.operation_store,
                        conversation_store=state.conversation_store,
                    ) as uow:
                        uow.save_conversation(record)
                        uow.commit_operation(
                            operation_id,
                            "conversation_message",
                            f"{session_id}:{turn}",
                            canonical_digest(final),
                            fingerprint,
                        )
                        uow.save_checkpoint(
                            f"conversation:{session_id}",
                            turn,
                            {"dialog_history": list(record.dialog_history),
                             "stop_reason": stop_reason},
                            state_fingerprint=fingerprint,
                            operation_id=operation_id,
                        )
                    handle.record = state.operation_store.get(operation_id) or handle.record
                except (CommitCapabilityLost, UnitOfWorkError):
                    pass
                frame = state.operation_coordinator.emit_domain(handle, "final", final)
                if frame:
                    yield frame
            finally:
                state.operation_coordinator.disconnect(operation_id)

        return StreamingResponse(stopped_stream(), media_type="text/event-stream", headers=stream_headers)

    async def event_stream():
        import queue as _queue
        import threading as _threading

        q: _queue.Queue = _queue.Queue()
        coordinator = state.operation_coordinator

        def _hook(delta: str):
            q.put(("delta", delta))

        def _run():
            try:
                if handle.token.cancelled:
                    return
                state.llm_client.set_stream_hook(_hook)
                try:
                    rs = state.ci_reasoning_state_from_record(record)
                    role, text, finished = state.run_agent_turn(
                        scenario=scenario,
                        case_id=case_id,
                        dialog_history=dialog_history,
                        input_json=_with_session_id(record, user_role),
                        reasoning_state=rs,
                        ci_agent=session_ci,
                    )
                    if scenario == "CI":
                        state.save_ci_reasoning_state(record, session_ci)
                finally:
                    state.llm_client.clear_stream_hook()
            except Exception as e:  # 生成失败也要推给前端，不能静默断流
                state.eval_logger.error(f"stream message failed: {e}", exc_info=True)
                q.put(("error", str(e)))
                return
            q.put(("done", (role, text, finished, session_ci)))

        worker = _threading.Thread(target=_run, daemon=True)
        worker.start()

        import time as _time
        last_beat = _time.time()
        try:
            for f in list(handle.frames):
                yield f
            while True:
                try:
                    kind, payload = q.get(timeout=5.0)
                except _queue.Empty:
                    # 心跳，防止代理/浏览器 idle 超时断流
                    if _time.time() - last_beat > 4.5:
                        last_beat = _time.time()
                        frame = coordinator.emit_domain(handle, "heartbeat")
                        if frame:
                            yield frame
                    continue

                if kind == "delta":
                    last_beat = _time.time()
                    frame = coordinator.emit_domain(handle, "delta", {"text": payload})
                    if frame:
                        yield frame
                elif kind == "error":
                    coordinator.fail(handle, "worker_error", retriable=True)
                    frame = coordinator.emit_domain(handle, "error", {"message": str(payload)})
                    if frame:
                        yield frame
                    return
                else:  # done
                    role, text, finished, ci_agent = payload
                    if handle.token.cancelled:
                        frame = coordinator.emit_domain(handle, "cancelled", {"reason": "client_disconnect"})
                        if frame:
                            yield frame
                        return
                    new_turn = turn + 1
                    response_message = {
                        "turn": new_turn,
                        "role": role,
                        "message": text,
                    }
                    dialog_history.append(response_message)
                    record.dialog_history = dialog_history

                    degraded = text.startswith("[离线模式回复]") or "（离线演示模板" in text
                    final = {
                        "session_id": session_id,
                        "response": {"role": role, "message": text},
                        "dialog_history": list(dialog_history),
                        "is_finished": finished,
                        "degraded": degraded,
                        "reasoning_meta": ({
                            "judgment_status": getattr(ci_agent, "judgment_status", "failed"),
                            "citation_report": getattr(ci_agent, "citation_report", None),
                            "case_warnings": list(getattr(ci_agent, "case_warnings", [])),
                        } if scenario == "CI" else None),
                    }
                    fingerprint = canonical_digest(dialog_history)
                    try:
                        # 原子提交：session + operation + checkpoint v2 同一事务
                        from api.services.runtime_unit_of_work import (
                            RuntimeUnitOfWork,
                            UnitOfWorkError,
                        )

                        with RuntimeUnitOfWork(
                            state.checkpoint_store,
                            operation_store=state.operation_store,
                            conversation_store=state.conversation_store,
                        ) as uow:
                            uow.save_conversation(record)
                            uow.commit_operation(
                                operation_id,
                                "conversation_message",
                                f"{session_id}:{new_turn}",
                                canonical_digest(final),
                                fingerprint,
                            )
                            uow.save_checkpoint(
                                f"conversation:{session_id}",
                                new_turn,
                                {"dialog_history": list(dialog_history)},
                                state_fingerprint=fingerprint,
                                operation_id=operation_id,
                            )
                        # 同步 coordinator 内存中的 record 视图
                        handle.record = coordinator.store.get(operation_id) or handle.record
                    except (CommitCapabilityLost, UnitOfWorkError):
                        frame = coordinator.emit_domain(handle, "cancelled", {"reason": "client_disconnect"})
                        if frame:
                            yield frame
                        return
                    frame = coordinator.emit_domain(handle, "final", final)
                    if frame:
                        yield frame
                    return
        finally:
            coordinator.disconnect(operation_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=stream_headers,
    )
