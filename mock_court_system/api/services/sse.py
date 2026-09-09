"""SSE 帧拼装。"""
from __future__ import annotations

import json
from typing import Any


def sse_event(event_type: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"
