"""SSE_Event_Codec round-trip / protocol error / terminal CAS 测试（Task 4.2）。"""
from __future__ import annotations

import pytest

from api.services.sse import (
    SseEncoder,
    SseProtocolError,
    StreamLifecycle,
    decode_frame,
    decode_stream,
    encode_frame,
    SseEventV1,
)


def _encoder():
    return SseEncoder(operation_id="op_1", request_id="req_1")


def test_encode_decode_round_trip_all_fields():
    enc = _encoder()
    frame = enc.emit(
        "delta",
        role="Lawyer",
        text="异议成立",
        degraded=True,
        sub_stage="argument",
        resource={"type": "session", "id": "s1"},
    )
    event = decode_frame(frame, "op_1", "req_1")
    assert event.sequence == 0
    assert event.type == "delta"
    assert event.role == "Lawyer"
    assert event.text == "异议成立"
    assert event.degraded is True
    assert event.sub_stage == "argument"
    assert event.resource == {"type": "session", "id": "s1"}
    assert event.schema_version == "1"
    assert event.emitted_at


def test_sequence_strictly_increasing_including_heartbeat():
    enc = _encoder()
    frames = [
        enc.emit("start"),
        enc.emit("heartbeat"),
        enc.emit("delta", text="x"),
        enc.emit("complete"),
    ]
    events = list(decode_stream(iter(frames), "op_1", "req_1"))
    assert [e.sequence for e in events] == [0, 1, 2, 3]
    assert events[-1].type == "complete"


@pytest.mark.parametrize(
    "frame,kind",
    [
        # 未知类型
        ('id: 0\nevent: bogus\ndata: {"schema_version":"1","operation_id":"op_1","request_id":"req_1","sequence":0,"type":"bogus"}\n\n', "unknown_type"),
        # 缺字段
        ('data: {"schema_version":"1","operation_id":"op_1","request_id":"req_1","sequence":0}\n\n', "missing_field"),
        # operation id 漂移
        ('id: 0\nevent: start\ndata: {"schema_version":"1","operation_id":"op_X","request_id":"req_1","sequence":0,"type":"start"}\n\n', "id_drift"),
        # request id 漂移
        ('id: 0\nevent: start\ndata: {"schema_version":"1","operation_id":"op_1","request_id":"req_X","sequence":0,"type":"start"}\n\n', "id_drift"),
        # 非递增 sequence（last_sequence=5 时又收到 sequence=5）
        ('id: 5\nevent: start\ndata: {"schema_version":"1","operation_id":"op_1","request_id":"req_1","sequence":5,"type":"start"}\n\n@LAST=5', "sequence"),
        # id 字段与 envelope sequence 漂移
        ('id: 9\nevent: start\ndata: {"schema_version":"1","operation_id":"op_1","request_id":"req_1","sequence":0,"type":"start"}\n\n', "sequence"),
    ],
)
def test_protocol_errors_produce_no_business_event(frame, kind):
    last = -1
    if "@LAST=" in frame:
        frame, marker = frame.split("@LAST=")
        last = int(marker)
    with pytest.raises(SseProtocolError) as exc:
        decode_frame(frame, "op_1", "req_1", last_sequence=last)
    assert exc.value.kind == kind


def test_terminal_cas_accepts_exactly_one():
    lifecycle = StreamLifecycle()
    assert lifecycle.accept("start")
    assert lifecycle.accept("complete")
    assert lifecycle.terminated
    # 后续 terminal 被拒绝并计数
    assert not lifecycle.accept("error")
    assert not lifecycle.accept("cancelled")
    assert lifecycle.duplicate_terminal_count == 2
    # terminal 后业务事件也被拒
    assert not lifecycle.accept("delta")


def test_encoder_suppresses_events_after_terminal():
    enc = _encoder()
    assert enc.emit("start") is not None
    assert enc.emit("complete") is not None
    assert enc.emit("delta", text="late") is None
    assert enc.emit("error") is None
    assert enc.lifecycle.duplicate_terminal_count == 1


def test_event_after_terminal_raises():
    enc = _encoder()
    frames = [enc.emit("start"), enc.emit("complete")]
    # 手工构造一个 terminal 后的合法 frame
    late = encode_frame(
        SseEventV1(
            operation_id="op_1",
            request_id="req_1",
            sequence=2,
            type="delta",
            text="late",
        )
    )
    frames.append(late)
    with pytest.raises(SseProtocolError) as exc:
        list(decode_stream(iter(frames), "op_1", "req_1"))
    assert exc.value.kind == "bad_terminal"


def test_encoder_unknown_type_raises():
    enc = _encoder()
    with pytest.raises(SseProtocolError):
        enc.emit("bogus_type")
