"""HearingSubgraph 外壳。生产路径是 HearingRuntime，本图仅供全案编排可选包装。

未接线（本轮不做）：Send 并行抽取、astream_events、live interrupt。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from core.graphs.hearing_runtime import HearingRuntime
from core.graphs.hearing_state import HearingState
from core.schemas import CourtState
from core.state_machine import StateMachine


def hearing_config(session_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": session_id}}


def _route_after_apply(state: HearingState) -> str:
    sm = StateMachine.from_dict(state.get("sm") or {})
    if state.get("finished") or sm.current_state in (CourtState.JUDGMENT, CourtState.CLOSED):
        return "make_judgment"
    return "judge_speak"


def compile_hearing_graph(runtime: HearingRuntime, checkpointer=None):
    """薄包装：ingest → apply(HearingRuntime) → judge/verdict。"""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return None

    def ingest_party_turn(state: HearingState) -> Dict[str, Any]:
        messages = list(state.get("messages") or [])
        role = state.get("last_party_role") or ""
        content = state.get("last_party_content") or ""
        if role and content:
            messages.append({"role": role, "content": content})
        return {"messages": messages}

    def apply_state_machine(state: HearingState) -> Dict[str, Any]:
        session_id = state["session_id"]
        role = state.get("last_party_role") or "Plaintiff"
        content = state.get("last_party_content") or ""
        fast = state.get("mode") == "auto"
        if content:
            text, finished = runtime.live_turn(
                session_id,
                role,
                content,
                state.get("case_id") or "",
                state.get("input_json") or {},
                fast_path=fast,
            )
            snap = runtime.get_state(session_id) or {}
            return {
                "sm": snap.get("sm") or {},
                "extracted": snap.get("extracted") or {},
                "evidences": snap.get("evidences") or [],
                "messages": snap.get("messages") or state.get("messages") or [],
                "case_info": snap.get("case_info") or {},
                "last_analysis": snap.get("last_analysis"),
                "finished": finished,
                "last_judge_text": text,
                "summary": snap.get("summary") or "",
            }
        return state

    def judge_speak(state: HearingState) -> Dict[str, Any]:
        return {"last_judge_text": state.get("last_judge_text") or ""}

    def make_judgment(state: HearingState) -> Dict[str, Any]:
        return {"finished": True, "last_judge_text": state.get("last_judge_text") or ""}

    builder = StateGraph(HearingState)
    builder.add_node("ingest_party_turn", ingest_party_turn)
    builder.add_node("apply_state_machine", apply_state_machine)
    builder.add_node("judge_speak", judge_speak)
    builder.add_node("make_judgment", make_judgment)
    builder.add_edge(START, "ingest_party_turn")
    builder.add_edge("ingest_party_turn", "apply_state_machine")
    builder.add_conditional_edges(
        "apply_state_machine",
        _route_after_apply,
        {"make_judgment": "make_judgment", "judge_speak": "judge_speak"},
    )
    builder.add_edge("judge_speak", END)
    builder.add_edge("make_judgment", END)

    if checkpointer is None:
        checkpointer = _build_langgraph_checkpointer()
    try:
        return builder.compile(checkpointer=checkpointer)
    except Exception:
        return builder.compile()


def _build_langgraph_checkpointer():
    path = os.getenv("HEARING_CHECKPOINT_PATH", os.path.join("data", "checkpoints.sqlite3"))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        import sqlite3
        conn = sqlite3.connect(path, check_same_thread=False)
        return SqliteSaver(conn)
    except Exception:
        try:
            from langgraph.checkpoint.memory import MemorySaver
            return MemorySaver()
        except Exception:
            return None


def invoke_hearing_turn(
    runtime: HearingRuntime,
    session_id: str,
    role: str,
    content: str,
    case_id: str = "",
    input_json: Optional[Dict[str, Any]] = None,
    *,
    fast_path: bool = False,
    graph=None,
) -> tuple:
    """生产默认 HearingRuntime；仅当调用方传入已编译 graph 时才走图。"""
    if graph is not None:
        try:
            config = hearing_config(session_id)
            payload = {
                "session_id": session_id,
                "last_party_role": role,
                "last_party_content": content,
                "case_id": case_id,
                "input_json": input_json or {},
                "mode": "auto" if fast_path else "live",
                "messages": [],
                "sm": {},
                "extracted": {},
                "evidences": [],
                "finished": False,
            }
            result = graph.invoke(payload, config)
            return result.get("last_judge_text") or "", bool(result.get("finished"))
        except Exception:
            pass
    return runtime.live_turn(session_id, role, content, case_id, input_json, fast_path=fast_path)
