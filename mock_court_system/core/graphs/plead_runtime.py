"""CD/DD 增量运行时：滚动窗口 + session checkpoint。"""
from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional, Tuple

from core.graphs.checkpoint import SqliteCheckpointStore
from core.schemas import CaseData


DEFAULT_WINDOW = 12
_RUNTIME: Optional["PleadRuntime"] = None
_RUNTIME_LOCK = threading.Lock()


def use_plead_runtime() -> bool:
    return os.getenv("PLEAD_USE_RUNTIME", "1") != "0"


def get_plead_runtime(cd_agent=None, dd_agent=None, llm=None, store: Optional[SqliteCheckpointStore] = None) -> "PleadRuntime":
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = PleadRuntime(cd_agent=cd_agent, dd_agent=dd_agent, llm=llm, store=store)
        elif cd_agent is not None or dd_agent is not None or llm is not None:
            _RUNTIME.bind(cd_agent=cd_agent, dd_agent=dd_agent, llm=llm)
        return _RUNTIME


def reset_plead_runtime() -> None:
    global _RUNTIME
    with _RUNTIME_LOCK:
        _RUNTIME = None


def _thread_id(session_id: str, scenario: str) -> str:
    return f"plead:{scenario}:{session_id}"


class PleadRuntime:
    def __init__(self, cd_agent=None, dd_agent=None, llm=None, store: Optional[SqliteCheckpointStore] = None):
        self.cd_agent = cd_agent
        self.dd_agent = dd_agent
        self.llm = llm
        self.store = store or SqliteCheckpointStore()
        self.window_k = int(os.getenv("PLEAD_WINDOW_K", str(DEFAULT_WINDOW)))
        self.last_window_size = 0
        self._cd_sessions: Dict[str, Any] = {}
        self._dd_sessions: Dict[str, Any] = {}
        self._session_locks: Dict[str, threading.Lock] = {}
        self._map_lock = threading.Lock()

    def bind(self, cd_agent=None, dd_agent=None, llm=None) -> None:
        if cd_agent is not None:
            self.cd_agent = cd_agent
        if dd_agent is not None:
            self.dd_agent = dd_agent
        if llm is not None:
            self.llm = llm
        with self._map_lock:
            self._cd_sessions.clear()
            self._dd_sessions.clear()

    def live_turn(
        self,
        session_id: str,
        scenario: str,
        dialog_history: List[Dict[str, Any]],
        case_id: str = "",
        input_json: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, bool]:
        scenario = (scenario or "").upper()
        tid = _thread_id(session_id, scenario)
        lock = self._lock_for(tid)
        with lock:
            snap = self.store.load(tid) or {
                "messages": [],
                "summary": "",
                "case_data": {},
                "finished": False,
            }
            window = list(dialog_history[-self.window_k:])
            dropped = dialog_history[:-self.window_k] if len(dialog_history) > self.window_k else []
            summary = snap.get("summary") or ""
            if dropped:
                summary = self._fold_summary(summary, dropped)
            self.last_window_size = len(window) + (1 if summary else 0)

            if scenario == "CD":
                agent = self._cd_for(session_id)
                text = agent.process_window(
                    window,
                    total_messages=len(dialog_history),
                    summary=summary,
                    case_id=case_id,
                    input_json=input_json,
                )
                finished = _is_complaint(text)
            elif scenario == "DD":
                agent = self._dd_for(session_id)
                case_data = CaseData.from_dict(snap.get("case_data"))
                if not snap.get("case_data"):
                    case_data = agent.seed_case_data(input_json, case_data)
                last = dialog_history[-1] if dialog_history else {"role": "Client", "message": ""}
                text, case_data = agent.process_window(
                    last,
                    case_data,
                    window,
                    total_messages=len(dialog_history),
                    input_json=input_json,
                )
                snap["case_data"] = case_data.to_dict()
                finished = _is_defense(text)
            else:
                raise ValueError(f"PleadRuntime 仅支持 CD/DD: {scenario}")

            snap["messages"] = window
            snap["summary"] = summary
            snap["finished"] = finished
            snap["last_text"] = text
            snap["case_id"] = case_id
            self.store.save(tid, snap)
            return text, finished

    def get_state(self, session_id: str, scenario: str) -> Optional[Dict[str, Any]]:
        return self.store.load(_thread_id(session_id, scenario))

    def _fold_summary(self, old: str, dropped: List[Dict[str, Any]]) -> str:
        extra = " ".join((m.get("message") or "")[:40] for m in dropped[-4:])
        merged = f"{old} {extra}".strip()
        return merged[:800]

    def _lock_for(self, key: str) -> threading.Lock:
        with self._map_lock:
            lock = self._session_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._session_locks[key] = lock
            return lock

    def _cd_for(self, session_id: str):
        if self.cd_agent is None:
            raise RuntimeError("PleadRuntime 未绑定 CDAgent")
        with self._map_lock:
            agent = self._cd_sessions.get(session_id)
            if agent is None:
                agent = self.cd_agent.fork_stateless()
                self._cd_sessions[session_id] = agent
            return agent

    def _dd_for(self, session_id: str):
        if self.dd_agent is None:
            raise RuntimeError("PleadRuntime 未绑定 DDAgent")
        with self._map_lock:
            agent = self._dd_sessions.get(session_id)
            if agent is None:
                agent = self.dd_agent.fork_stateless()
                self._dd_sessions[session_id] = agent
            return agent


def _is_complaint(text: str) -> bool:
    clean = (text or "").strip().replace("*", "").replace("#", "").replace(" ", "")
    return clean.startswith("民事起诉状")


def _is_defense(text: str) -> bool:
    clean = (text or "").strip().replace("*", "").replace("#", "").replace(" ", "")
    return clean.startswith("民事答辩状")
