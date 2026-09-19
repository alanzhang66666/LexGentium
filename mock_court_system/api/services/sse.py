"""SSE_Event_Codec（Python 侧，design §4）。

统一业务事件类型：``start|heartbeat|delta|progress|complete|error|cancelled``。
envelope（schema_version=1）写入 ``data:``，``sequence`` 同时写入 ``id:``，
``type`` 写入 ``event:``。sequence 从 0 严格递增，heartbeat 也占号。

decoder 对未知类型、缺字段、operation/request ID 漂移、非递增 sequence
返回 ``SseProtocolError``，绝不产生业务事件。

``StreamLifecycle`` 维护 terminal CAS：``complete|error|cancelled`` 只接受
一次；后续 terminal 被忽略并计入 ``duplicate_terminal_count``。

保留旧 ``sse_event`` 兼容助手（无 envelope），供未迁移路由过渡使用。
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterator, Optional

EVENT_TYPES = (
    "start",
    "heartbeat",
    "delta",
    "progress",
    "complete",
    "error",
    "cancelled",
)
TERMINAL_TYPES = ("complete", "error", "cancelled")
SCHEMA_VERSION = "1"


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class SseProtocolError(Exception):
    """typed decode error：unknown_type|missing_field|id_drift|sequence|bad_terminal。"""

    def __init__(self, kind: str, detail: str = ""):
        self.kind = kind
        super().__init__(f"sse protocol error[{kind}]: {detail}")


@dataclass(frozen=True)
class SseEventV1:
    operation_id: str
    request_id: str
    sequence: int
    type: str
    schema_version: str = SCHEMA_VERSION
    role: Optional[str] = None
    text: Optional[str] = None
    degraded: bool = False
    sub_stage: Optional[str] = None
    resource: Optional[Dict[str, str]] = None
    error: Optional[Dict[str, Any]] = None
    # 域事件载荷：迁移期携带原事件体，原始事件名在 payload["event"]
    payload: Optional[Dict[str, Any]] = None
    emitted_at: str = ""

    def envelope(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def encode_frame(event: SseEventV1) -> str:
    """event → SSE wire frame：id=sequence, event=type, data=envelope JSON。"""
    payload = json.dumps(event.envelope(), ensure_ascii=False, default=str)
    return f"id: {event.sequence}\nevent: {event.type}\ndata: {payload}\n\n"


class SseEncoder:
    """per-operation 编码器：sequence 从 0 严格递增；terminal 后不再产生业务事件。"""

    def __init__(self, operation_id: str, request_id: str):
        self.operation_id = operation_id
        self.request_id = request_id
        self._sequence = 0
        self._lifecycle = StreamLifecycle()

    @property
    def lifecycle(self) -> "StreamLifecycle":
        return self._lifecycle

    def emit(
        self,
        type: str,
        *,
        role: Optional[str] = None,
        text: Optional[str] = None,
        degraded: bool = False,
        sub_stage: Optional[str] = None,
        resource: Optional[Dict[str, str]] = None,
        error: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """生成一个 frame；terminal 后或非首 terminal 返回 None。"""
        if type not in EVENT_TYPES:
            raise SseProtocolError("unknown_type", type)
        if not self._lifecycle.accept(type):
            return None
        event = SseEventV1(
            operation_id=self.operation_id,
            request_id=self.request_id,
            sequence=self._sequence,
            type=type,
            role=role,
            text=text,
            degraded=degraded,
            sub_stage=sub_stage,
            resource=resource,
            error=error,
            payload=payload,
            emitted_at=_utcnow_iso(),
        )
        self._sequence += 1
        return encode_frame(event)

    # 域事件名 → 统一类型；原名保存在 payload["event"]，前端可还原
    _DOMAIN_TERMINAL = {"final", "simulation_complete", "round_complete"}
    _DOMAIN_MAP = {
        "delta": "delta",
        "heartbeat": "heartbeat",
        "error": "error",
        "cancelled": "cancelled",
    }

    def emit_domain(self, type: str, data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """域事件 → envelope frame；terminal 语义经 lifecycle CAS。"""
        payload = dict(data or {})
        payload.setdefault("event", type)
        if type in self._DOMAIN_TERMINAL:
            mapped = "complete"
        else:
            mapped = self._DOMAIN_MAP.get(type, "progress")
        return self.emit(
            mapped,
            role=payload.get("role") if isinstance(payload.get("role"), str) else None,
            text=payload.get("text") if isinstance(payload.get("text"), str) else None,
            degraded=bool(payload.get("degraded", False)),
            sub_stage=payload.get("sub_stage") if isinstance(payload.get("sub_stage"), str) else None,
            error=payload.get("error") if isinstance(payload.get("error"), dict) else None,
            payload=payload,
        )


class StreamLifecycle:
    """terminal CAS：恰一个 terminal；terminal 后业务事件被拒绝。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.terminal_type: Optional[str] = None
        self.duplicate_terminal_count = 0

    @property
    def terminated(self) -> bool:
        return self.terminal_type is not None

    def accept(self, type: str) -> bool:
        """事件是否可接受。重复 terminal 递增计数并返回 False。"""
        with self._lock:
            if self.terminal_type is not None:
                if type in TERMINAL_TYPES:
                    self.duplicate_terminal_count += 1
                return False
            if type in TERMINAL_TYPES:
                self.terminal_type = type
            return True


def decode_frame(frame: str, expected_operation_id: str, expected_request_id: str,
                 last_sequence: int = -1) -> SseEventV1:
    """解析单个 SSE frame 并验证不变量；返回业务事件或抛 SseProtocolError。"""
    fields: Dict[str, str] = {}
    # 只按 \n 分行：data JSON 可能含 U+2028/U+2029 等 splitlines 会误切的字符
    for line in frame.strip().split("\n"):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()

    if "data" not in fields:
        raise SseProtocolError("missing_field", "data")
    try:
        env = json.loads(fields["data"])
    except (ValueError, TypeError):
        raise SseProtocolError("missing_field", "data not json")
    if not isinstance(env, dict):
        raise SseProtocolError("missing_field", "envelope not object")

    for required in ("schema_version", "operation_id", "request_id", "sequence", "type"):
        if required not in env:
            raise SseProtocolError("missing_field", required)
    if env["schema_version"] != SCHEMA_VERSION:
        raise SseProtocolError("missing_field", "schema_version != 1")
    if env["type"] not in EVENT_TYPES:
        raise SseProtocolError("unknown_type", str(env["type"]))
    if env["operation_id"] != expected_operation_id:
        raise SseProtocolError("id_drift", "operation_id")
    if env["request_id"] != expected_request_id:
        raise SseProtocolError("id_drift", "request_id")

    sequence = env["sequence"]
    if not isinstance(sequence, int) or sequence < 0:
        raise SseProtocolError("sequence", "non-negative int required")
    wire_id = fields.get("id")
    if wire_id is not None and wire_id != str(sequence):
        raise SseProtocolError("sequence", "id field drift")
    if sequence <= last_sequence:
        raise SseProtocolError("sequence", "non-increasing")

    return SseEventV1(
        operation_id=env["operation_id"],
        request_id=env["request_id"],
        sequence=sequence,
        type=env["type"],
        schema_version=env["schema_version"],
        role=env.get("role"),
        text=env.get("text"),
        degraded=bool(env.get("degraded", False)),
        sub_stage=env.get("sub_stage"),
        resource=env.get("resource"),
        error=env.get("error"),
        payload=env.get("payload"),
        emitted_at=env.get("emitted_at", ""),
    )


def decode_stream(
    frames: Iterator[str], operation_id: str, request_id: str
) -> Iterator[SseEventV1]:
    """按序 decode；terminal 后到达的事件抛 bad_terminal。"""
    last = -1
    terminated = False
    for frame in frames:
        if not frame.strip():
            continue
        event = decode_frame(frame, operation_id, request_id, last)
        if terminated:
            raise SseProtocolError("bad_terminal", "event after terminal")
        if event.type in TERMINAL_TYPES:
            terminated = True
        last = event.sequence
        yield event


# ---------- 旧兼容助手（无 envelope，迁移期保留） ----------


def sse_event(event_type: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"
