"""会话：CRUD、发言、自动推进、合规、links 读写。"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from api import state
from api.services.links import compact_links, merge_link


def bind_session_link(session_id: Optional[str], **updates: Optional[str]) -> None:
    if not session_id:
        return
    record = state.conversation_store.get(session_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    record.input_json = merge_link(record.input_json, **updates)
    state.conversation_store.save(record)


def session_payload(record) -> Dict[str, Any]:
    meta = state._infer_conversation_meta(record.scenario, list(record.dialog_history), record.session_id)
    return {
        "session_id": record.session_id,
        "scenario": record.scenario,
        "case_id": record.case_id,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "message_count": record.message_count,
        "dialog_history": list(record.dialog_history),
        "links": compact_links(record.input_json),
        **meta,
    }


def _normalize_scenario(scenario: str) -> str:
    value = (scenario or "").upper()
    if value not in ("CD", "DD", "CI"):
        raise HTTPException(status_code=400, detail=f"Invalid scenario: {scenario}")
    return value


def resolve_user_role(scenario: str, role: Optional[str]) -> str:
    if role:
        return role
    if scenario in ("CD", "DD"):
        return "Client"
    if scenario == "CI":
        return "Plaintiff"
    return "User"


def is_degraded(text: str) -> bool:
    return text.startswith("[离线模式回复]") or "（离线演示模板" in text


def start_session(scenario: str, case_id: str, input_json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    scenario = _normalize_scenario(scenario)
    session_id = state.generate_session_id()
    record = state.conversation_store.create(
        session_id=session_id,
        scenario=scenario,
        case_id=case_id,
        input_json=input_json or {},
    )
    return {
        "session_id": session_id,
        "scenario": scenario,
        "case_id": case_id,
        "created_at": record.created_at,
    }


def import_session(
    scenario: str,
    case_id: str,
    dialog_history: List[Dict[str, Any]],
    input_json: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    scenario = _normalize_scenario(scenario)
    if not isinstance(dialog_history, list):
        raise HTTPException(status_code=400, detail="error")

    session_id = state.generate_session_id()
    record = state.conversation_store.create(
        session_id=session_id,
        scenario=scenario,
        case_id=case_id,
        input_json=input_json or {},
    )

    cleaned: List[Dict[str, Any]] = []
    for idx, msg in enumerate(dialog_history):
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        message = msg.get("message")
        if not role or message is None:
            continue
        cleaned.append({
            "turn": msg.get("turn", idx),
            "role": role,
            "message": message,
        })

    record.dialog_history = cleaned
    state.conversation_store.save(record)
    return {
        "session_id": session_id,
        "scenario": scenario,
        "case_id": case_id,
        "created_at": record.created_at,
        "message_count": len(cleaned),
        "is_finished": bool(cleaned and cleaned[-1].get("role") == "Final"),
        "links": compact_links(record.input_json),
    }


def require_session(session_id: str):
    record = state.conversation_store.get(session_id)
    if not record:
        raise HTTPException(status_code=404, detail="error")
    return record


def list_sessions(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    state.cleanup_old_sessions()
    result, total = state.conversation_store.list(limit=limit, offset=offset)
    return {
        "sessions": result,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_session(session_id: str) -> Dict[str, Any]:
    return session_payload(require_session(session_id))


def delete_session(session_id: str) -> Dict[str, Any]:
    ok = state.conversation_store.delete(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="error")
    return {"message": "deleted", "session_id": session_id}


def append_user_message(record, message: str, role: Optional[str]) -> str:
    user_role = resolve_user_role(record.scenario, role)
    record.dialog_history.append({
        "turn": len(record.dialog_history),
        "role": user_role,
        "message": message,
    })
    return user_role


def persist_agent_reply(record, role: str, text: str) -> None:
    record.dialog_history.append({
        "turn": len(record.dialog_history),
        "role": role,
        "message": text,
    })
    state.conversation_store.save(record)


def _with_session_id(record) -> Dict[str, Any]:
    payload = dict(record.input_json or {})
    payload["_session_id"] = record.session_id
    return payload


def send_message(session_id: str, message: str, role: Optional[str] = None) -> Dict[str, Any]:
    record = require_session(session_id)
    append_user_message(record, message, role)

    response_role, response_text, is_finished = state.run_agent_turn(
        scenario=record.scenario,
        case_id=record.case_id,
        dialog_history=record.dialog_history,
        input_json=_with_session_id(record),
    )
    persist_agent_reply(record, response_role, response_text)

    return {
        "session_id": session_id,
        "response": {"role": response_role, "message": response_text},
        "dialog_history": list(record.dialog_history),
        "is_finished": is_finished,
        "degraded": is_degraded(response_text),
    }


async def auto_advance(
    session_id: str,
    max_rounds: int = 5,
    auto_reply_roles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    record = require_session(session_id)
    dialog_history = list(record.dialog_history)
    auto_roles = state._determine_auto_roles(record.scenario, auto_reply_roles)
    rounds_played = 0

    for _ in range(max_rounds):
        response_role, response_text, finished = state.run_agent_turn(
            scenario=record.scenario,
            case_id=record.case_id,
            dialog_history=dialog_history,
            input_json=_with_session_id(record),
        )
        dialog_history.append({
            "turn": len(dialog_history),
            "role": response_role,
            "message": response_text,
        })
        rounds_played += 1
        if finished:
            break

        meta = state._infer_conversation_meta(record.scenario, dialog_history, session_id)
        sim_role = meta.get("next_speaker")
        if not sim_role or sim_role not in auto_roles:
            break

        sim_text = await asyncio.to_thread(
            state.sim_agent.simulate_role,
            sim_role,
            dialog_history,
            record.input_json,
            record.scenario,
        )
        dialog_history.append({
            "turn": len(dialog_history),
            "role": sim_role,
            "message": sim_text,
        })

    record.dialog_history = dialog_history
    state.conversation_store.save(record)
    final_meta = state._infer_conversation_meta(record.scenario, dialog_history, session_id)
    return {
        "session_id": session_id,
        "rounds_played": rounds_played,
        "dialog_history": dialog_history,
        "is_finished": final_meta["is_finished"],
        "current_stage": final_meta["current_stage"],
        "next_speaker": final_meta["next_speaker"],
        "available_actions": final_meta["available_actions"],
    }


def get_compliance(session_id: str) -> Dict[str, Any]:
    record = require_session(session_id)
    if record.scenario != "CI":
        return {
            "session_id": session_id,
            "scenario": record.scenario,
            "compliance": {"message": "PFS compliance tracking only applies to CI scenario"},
        }
    try:
        from core.graphs.hearing_runtime import get_hearing_runtime, use_hearing_graph
        if use_hearing_graph():
            sm = get_hearing_runtime(ci_agent=state.ci_agent).get_state_machine(session_id)
            if sm:
                realtime = sm.get_realtime_compliance()
            else:
                realtime = state.ci_agent.state_machine.get_realtime_compliance()
        else:
            realtime = state.ci_agent.state_machine.get_realtime_compliance()
    except Exception as exc:
        realtime = {"error": f"合规追踪失败: {str(exc)}"}
    return {
        "session_id": session_id,
        "scenario": record.scenario,
        "compliance": realtime,
        "links": compact_links(record.input_json),
    }


def finalize_stream_turn(record, session_id: str, role: str, text: str, finished: bool) -> Dict[str, Any]:
    persist_agent_reply(record, role, text)
    meta = state._infer_conversation_meta(record.scenario, list(record.dialog_history), session_id)
    return {
        "type": "final",
        "session_id": session_id,
        "response": {"role": role, "message": text},
        "dialog_history": list(record.dialog_history),
        "is_finished": finished,
        "degraded": is_degraded(text),
        **meta,
    }
