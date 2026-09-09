"""CI 庭审增量运行时：状态落 checkpoint，按 session_id 隔离。"""
from __future__ import annotations

import os
import threading
from typing import Any, Dict, Optional, Tuple

from core.graphs.checkpoint import SqliteCheckpointStore
from core.graphs.hearing_state import HearingState, empty_hearing_state
from core.schemas import CaseInfo, CourtState
from core.state_machine import StateMachine


_RUNTIME: Optional["HearingRuntime"] = None
_RUNTIME_LOCK = threading.Lock()


def get_hearing_runtime(ci_agent=None, llm=None, store: Optional[SqliteCheckpointStore] = None) -> "HearingRuntime":
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = HearingRuntime(ci_agent=ci_agent, llm=llm, store=store)
        elif ci_agent is not None or llm is not None:
            _RUNTIME.bind(ci_agent=ci_agent, llm=llm)
        return _RUNTIME


def reset_hearing_runtime() -> None:
    global _RUNTIME
    with _RUNTIME_LOCK:
        _RUNTIME = None


def use_hearing_graph() -> bool:
    return os.getenv("CI_USE_GRAPH", "1") != "0"


class HearingRuntime:
    """节点逻辑：ingest → clerk → apply → judge/verdict。

    每 session 一份 CIAgent 可变状态；llm / chain / 法条检索器共享。
    同会话串行，异会话可并行。
    """

    def __init__(self, ci_agent=None, llm=None, store: Optional[SqliteCheckpointStore] = None):
        self.ci_agent = ci_agent
        self.llm = llm
        self.store = store or SqliteCheckpointStore()
        self._sessions: Dict[str, Any] = {}
        self._session_locks: Dict[str, threading.Lock] = {}
        self._map_lock = threading.Lock()
        self._summary_window = int(os.getenv("HEARING_SUMMARY_WINDOW", "24"))

    def bind(self, ci_agent=None, llm=None) -> None:
        if ci_agent is not None:
            self.ci_agent = ci_agent
        if llm is not None:
            self.llm = llm
        with self._map_lock:
            self._sessions.clear()

    def get_state(self, session_id: str) -> Optional[HearingState]:
        snap = self.store.load(session_id)
        return snap  # type: ignore[return-value]

    def get_state_machine(self, session_id: str) -> Optional[StateMachine]:
        snap = self.get_state(session_id)
        if not snap or not snap.get("sm"):
            return None
        return StateMachine.from_dict(snap["sm"])

    def init_session(
        self,
        session_id: str,
        *,
        case_id: str = "",
        input_json: Optional[Dict[str, Any]] = None,
        mode: str = "live",
        strategy: Optional[Dict[str, Any]] = None,
    ) -> HearingState:
        existing = self.get_state(session_id)
        if existing:
            if input_json:
                existing["input_json"] = input_json
            if case_id:
                existing["case_id"] = case_id
            existing["mode"] = mode
            if strategy:
                existing["strategy"] = strategy
            self.store.save(session_id, existing)
            return existing
        state = empty_hearing_state(session_id, mode=mode)
        state["case_id"] = case_id
        state["input_json"] = input_json or {}
        state["strategy"] = strategy or {"plaintiff": None, "defendant": None}
        self.store.save(session_id, state)
        return state

    def live_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        case_id: str = "",
        input_json: Optional[Dict[str, Any]] = None,
        *,
        fast_path: bool = False,
    ) -> Tuple[str, bool]:
        """处理一方发言并生成审判长回复。"""
        lock = self._lock_for(session_id)
        with lock:
            ci = self._session_agent(session_id)
            snap = self.store.load(session_id)
            ci.restore_state(snap)
            ci.fast_path = fast_path
            if input_json and (not getattr(ci, "case_info", None) or not getattr(ci.case_info, "case_id", "")):
                ci.case_info = ci._build_case_info(input_json)
                if case_id:
                    ci.case_info.case_id = case_id
            elif not getattr(ci, "case_info", None):
                ci.case_info = CaseInfo(case_id=case_id)
            if not snap and not content:
                text = ci._start_court()
            else:
                text = ci.process_incremental(role, content, case_id, input_json)
            out = ci.snapshot_state()
            out["session_id"] = session_id
            out["mode"] = (snap or {}).get("mode", "live")
            out["strategy"] = (snap or {}).get("strategy") or {"plaintiff": None, "defendant": None}
            out["case_id"] = case_id or (snap or {}).get("case_id", "")
            out["input_json"] = input_json or (snap or {}).get("input_json") or {}
            out["last_party_role"] = role
            out["last_party_content"] = content
            out["last_judge_text"] = text
            out["summary"] = (snap or {}).get("summary", "") or ci.extracted.get("summary", "")
            self._maybe_summarize(ci, out)
            self.store.save(session_id, out)
            finished = bool(out.get("finished")) or ci.state_machine.current_state in (
                CourtState.JUDGMENT,
                CourtState.CLOSED,
            )
            return text, finished

    def start_court(self, session_id: str, case_id: str = "", input_json: Optional[Dict[str, Any]] = None) -> Tuple[str, bool]:
        lock = self._lock_for(session_id)
        with lock:
            ci = self._session_agent(session_id)
            snap = self.store.load(session_id)
            ci.restore_state(snap)
            if input_json:
                ci.case_info = ci._build_case_info(input_json)
                if case_id:
                    ci.case_info.case_id = case_id
            text = ci._start_court()
            out = ci.snapshot_state()
            out["session_id"] = session_id
            out["mode"] = (snap or {}).get("mode", "auto")
            out["strategy"] = (snap or {}).get("strategy") or {}
            out["case_id"] = case_id
            out["input_json"] = input_json or {}
            out["last_judge_text"] = text
            self.store.save(session_id, out)
            return text, bool(out.get("finished"))

    def next_party_role(self, dialog_history: list) -> str:
        from core.case_orchestrator import FullCaseOrchestrator
        return FullCaseOrchestrator._ci_next_role(dialog_history)

    def _maybe_summarize(self, ci, out: Dict[str, Any]) -> None:
        messages = out.get("messages") or []
        if len(messages) <= self._summary_window:
            return
        try:
            summary = ci._summarize_dialogue()
            ci.extracted["summary"] = summary
            out["summary"] = summary
            out["extracted"] = dict(ci.extracted)
        except Exception:
            pass

    def _lock_for(self, session_id: str) -> threading.Lock:
        with self._map_lock:
            lock = self._session_locks.get(session_id)
            if lock is None:
                lock = threading.Lock()
                self._session_locks[session_id] = lock
            return lock

    def _session_agent(self, session_id: str):
        proto = self._require_agent()
        with self._map_lock:
            agent = self._sessions.get(session_id)
            if agent is None:
                agent = proto.fork_stateless()
                self._sessions[session_id] = agent
            return agent

    def _require_agent(self):
        if self.ci_agent is None:
            raise RuntimeError("HearingRuntime 未绑定 CIAgent")
        return self.ci_agent
