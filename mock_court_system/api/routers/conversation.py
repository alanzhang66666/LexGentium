"""会话式模拟 路由。"""
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime
import uuid
import json
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

@router.post("/conversation/start", response_model=ConversationStartResponse)
async def start_conversation(req: ConversationStartRequest):
    try:
        session_id = state.generate_session_id()
        scenario = req.scenario.upper()
        
        if scenario not in ["CD", "DD", "CI"]:
            raise HTTPException(status_code=400, detail=f"Invalid scenario: {scenario}")

        record = state.conversation_store.create(
            session_id=session_id,
            scenario=scenario,
            case_id=req.case_id,
            input_json=req.input_json or {},
        )
        
        return ConversationStartResponse(
            session_id=session_id,
            scenario=scenario,
            case_id=req.case_id,
            created_at=record.created_at
        )
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

        reasoning_state = state.ci_reasoning_state_from_record(record)
        session_ci = state.new_session_ci_agent() if scenario == "CI" else None
        response_role, response_text, is_finished = state.run_agent_turn(
            scenario=scenario,
            case_id=case_id,
            dialog_history=dialog_history,
            input_json=input_json,
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
        # 清理过期会话
        state.cleanup_old_sessions()

        result, total = state.conversation_store.list(limit=limit, offset=offset)

        return {
            "sessions": result,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        state.eval_logger.error(f"获取会话列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@router.get("/conversation/{session_id}")
async def get_conversation(session_id: str):
    try:
        record = state.conversation_store.get(session_id)
        if not record:
            raise HTTPException(status_code=404, detail="error")

        meta = state._infer_conversation_meta(record.scenario, list(record.dialog_history))

        return {
            "session_id": session_id,
            "scenario": record.scenario,
            "case_id": record.case_id,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "message_count": record.message_count,
            "dialog_history": list(record.dialog_history),
            **meta,
        }
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

        rounds_played = 0
        is_finished = False

        for _ in range(req.max_rounds):
            # --- Step A: 各 Agent 依次推进一步 ---
            response_role, response_text, finished = state.run_agent_turn(
                scenario=scenario,
                case_id=case_id,
                dialog_history=dialog_history,
                input_json=input_json,
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
                input_json,
                scenario,
            )

            turn = len(dialog_history)
            dialog_history.append({
                "turn": turn,
                "role": sim_role,
                "message": sim_text,
            })

        record.dialog_history = dialog_history
        state.conversation_store.save(record)

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

    async def event_stream():
        import queue as _queue
        import threading as _threading

        q: _queue.Queue = _queue.Queue()
        heartbeat = {"stop": False}

        def _hook(delta: str):
            q.put(("delta", delta))

        def _run():
            try:
                state.llm_client.set_stream_hook(_hook)
                session_ci = state.new_session_ci_agent() if scenario == "CI" else None
                try:
                    rs = state.ci_reasoning_state_from_record(record)
                    role, text, finished = state.run_agent_turn(
                        scenario=scenario,
                        case_id=case_id,
                        dialog_history=dialog_history,
                        input_json=input_json,
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
            q.put(("done", (role, text, finished)))

        worker = _threading.Thread(target=_run, daemon=True)
        worker.start()

        import time as _time
        last_beat = _time.time()
        try:
            while True:
                try:
                    kind, payload = q.get(timeout=5.0)
                except _queue.Empty:
                    # 心跳，防止代理/浏览器 idle 超时断流
                    if _time.time() - last_beat > 4.5:
                        last_beat = _time.time()
                        yield f"data: {json.dumps({'type': 'heartbeat'}, ensure_ascii=False)}\n\n"
                    continue

                if kind == "delta":
                    last_beat = _time.time()
                    yield f"data: {json.dumps({'type': 'delta', 'text': payload}, ensure_ascii=False)}\n\n"
                elif kind == "error":
                    yield f"data: {json.dumps({'type': 'final', 'error': str(payload)}, ensure_ascii=False)}\n\n"
                    return
                else:  # done
                    role, text, finished = payload
                    new_turn = turn + 1
                    response_message = {
                        "turn": new_turn,
                        "role": role,
                        "message": text,
                    }
                    dialog_history.append(response_message)
                    record.dialog_history = dialog_history
                    state.conversation_store.save(record)

                    degraded = text.startswith("[离线模式回复]") or "（离线演示模板" in text
                    final = {
                        "type": "final",
                        "session_id": session_id,
                        "response": {"role": role, "message": text},
                        "dialog_history": list(dialog_history),
                        "is_finished": finished,
                        "degraded": degraded,
                        "reasoning_meta": ({
                            "judgment_status": getattr(session_ci, "judgment_status", "failed"),
                            "citation_report": getattr(session_ci, "citation_report", None),
                            "case_warnings": list(getattr(session_ci, "case_warnings", [])),
                        } if scenario == "CI" else None),
                    }
                    yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"
                    return
        finally:
            heartbeat["stop"] = True

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
