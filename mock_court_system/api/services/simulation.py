"""全案任务创建与会话绑定。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from api import state
from api.services.conversation import bind_session_link
from api.services.sse import sse_event


def create_simulation_task(mode: str, session_id: str | None = None) -> str:
    task_id = f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
    state.simulation_tasks[task_id] = {
        "status": "pending",
        "message": "task created",
        "current_stage": None,
        "result": None,
        "created_at": state._utcnow_iso(),
        "mode": mode,
        "session_id": session_id,
    }
    bind_session_link(session_id, task_id=task_id)
    state.persist_simulation_task(task_id)
    return task_id


def get_simulation_task(task_id: str) -> Dict[str, Any] | None:
    return state.load_simulation_task(task_id)


def bind_stream_session(session_id: str | None, task_id: str | None = None) -> None:
    if session_id and task_id:
        bind_session_link(session_id, task_id=task_id)


# Re-export so routers can keep a single import surface.
sse_event = sse_event
