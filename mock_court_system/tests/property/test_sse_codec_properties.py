"""SSE_Event_Codec 属性测试。

覆盖 Properties 8, 9, 17, 18, 19, 20, 21。
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.sse import (  # noqa: E402
    EVENT_TYPES,
    TERMINAL_TYPES,
    SseEncoder,
    SseProtocolError,
    decode_frame,
    decode_stream,
)

OP = "op_test"
REQ = "req_test"


def _encoder() -> SseEncoder:
    return SseEncoder(OP, REQ)


# ---------- Property 8/20: envelope 身份一致 + codec roundtrip ----------


@given(
    texts=st.lists(st.text(max_size=40), min_size=0, max_size=6),
    degraded=st.booleans(),
)
@settings(max_examples=25)
def test_property_8_20_roundtrip_preserves_identity(texts, degraded):
    enc = _encoder()
    last = -1
    for i, text in enumerate(texts):
        frame = enc.emit("delta", text=text, role="plaintiff", degraded=degraded)
        assert frame is not None
        ev = decode_frame(frame, OP, REQ, last)
        assert ev.operation_id == OP and ev.request_id == REQ
        assert ev.sequence == i
        assert ev.text == text and ev.degraded == degraded
        last = ev.sequence


@given(
    wrong_op=st.text(min_size=1, max_size=12).filter(lambda s: s != OP),
    wrong_req=st.text(min_size=1, max_size=12).filter(lambda s: s != REQ),
)
@settings(max_examples=15)
def test_property_8_identity_drift_rejected(wrong_op, wrong_req):
    frame = _encoder().emit("delta", text="x")
    with pytest.raises(SseProtocolError) as e1:
        decode_frame(frame, wrong_op, REQ)
    assert e1.value.kind == "id_drift"
    with pytest.raises(SseProtocolError) as e2:
        decode_frame(frame, OP, wrong_req)
    assert e2.value.kind == "id_drift"


# ---------- Property 17/18/19: sequence 严格递增 + terminal 恰一次 ----------


@given(
    n=st.integers(min_value=1, max_value=8),
    terminal=st.sampled_from(list(TERMINAL_TYPES)),
)
@settings(max_examples=20)
def test_property_17_18_ordering_and_single_terminal(n, terminal):
    enc = _encoder()
    frames = [enc.emit("delta", text=str(i)) for i in range(n)]
    frames.append(enc.emit(terminal))
    assert all(f is not None for f in frames)

    events = list(decode_stream(iter(frames), OP, REQ))
    seqs = [e.sequence for e in events]
    assert seqs == sorted(seqs) == list(range(n + 1))  # 严格递增、无空洞
    assert events[-1].type == terminal

    # terminal 之后一切业务/terminal 事件被拒（commit 边界）
    assert enc.emit("delta", text="late") is None
    assert enc.emit(terminal) is None
    for other in TERMINAL_TYPES:
        assert enc.emit(other) is None
    assert enc.lifecycle.duplicate_terminal_count >= 3


@given(n_late=st.integers(min_value=1, max_value=4))
@settings(max_examples=10)
def test_property_18_decoder_rejects_post_terminal_events(n_late):
    enc = _encoder()
    frames = [enc.emit("complete")]
    # 手工伪造 terminal 后到达的 frame（sequence 仍递增）
    enc2 = SseEncoder(OP, REQ)
    enc2._sequence = len(frames)
    for _ in range(n_late):
        frames.append(enc2.emit("delta", text="late"))
    with pytest.raises(SseProtocolError) as exc:
        list(decode_stream(iter(frames), OP, REQ))
    assert exc.value.kind == "bad_terminal"


@given(n=st.integers(min_value=1, max_value=8))
@settings(max_examples=10)
def test_property_9_ordered_deltas_exactly_once_final(n):
    """有序 delta 序列 + 恰一次 final（Property 9）。"""
    enc = _encoder()
    frames = [enc.emit("delta", text=f"chunk-{i}") for i in range(n)]
    frames.append(enc.emit("complete"))
    events = list(decode_stream(iter(frames), OP, REQ))
    assert [e.text for e in events[:-1]] == [f"chunk-{i}" for i in range(n)]
    assert events[-1].type == "complete"
    # 重复 terminal 不产生第二个 final
    assert enc.emit("complete") is None


def test_property_19_terminal_marks_commit_boundary():
    """terminal 帧即 commit 边界；其后事件全部拒绝（Property 19）。"""
    enc = _encoder()
    enc.emit("delta", text="pre-commit")
    final = enc.emit("complete")
    assert final is not None
    assert enc.lifecycle.terminated
    # commit 边界后无任何业务事件发出
    for t in ("delta", "progress", "heartbeat", "start"):
        assert enc.emit(t, text="x") is None


@given(text=st.text(max_size=60))
@settings(max_examples=20)
def test_property_20_codec_roundtrip(text):
    """encode → decode 保留全部 envelope 字段（Property 20）。"""
    enc = _encoder()
    frame = enc.emit("delta", text=text, role="defendant", degraded=True)
    ev = decode_frame(frame, OP, REQ)
    assert ev.type == "delta" and ev.text == text
    assert ev.role == "defendant" and ev.degraded is True
    assert ev.operation_id == OP and ev.request_id == REQ


# ---------- Property 21: 非法事件不产生业务事件 ----------


BAD_FRAMES = [
    "data: not-json\n\n",
    'data: {"type":"delta"}\n\n',  # 缺字段
    'data: {"schema_version":"2","operation_id":"op_test","request_id":"req_test","sequence":0,"type":"delta"}\n\n',
    'data: {"schema_version":"1","operation_id":"op_test","request_id":"req_test","sequence":0,"type":"bogus"}\n\n',
    'data: {"schema_version":"1","operation_id":"op_test","request_id":"req_test","sequence":-1,"type":"delta"}\n\n',
    'id: 9\ndata: {"schema_version":"1","operation_id":"op_test","request_id":"req_test","sequence":0,"type":"delta"}\n\n',
]


@pytest.mark.parametrize("frame", BAD_FRAMES)
def test_property_21_invalid_frames_raise_typed_error(frame):
    with pytest.raises(SseProtocolError):
        decode_frame(frame, OP, REQ)
