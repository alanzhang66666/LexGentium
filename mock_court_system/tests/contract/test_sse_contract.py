"""SSE contract: envelope、sequence 严格递增、恰一 terminal、幂等回放（Task 4.4）。

经 TestClient 走真实路由；run_agent_turn 由 _load_api_server stub 成离线回复。
"""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from tests.test_offline_governance import _load_api_server, _runtime_path


def _client(monkeypatch, name="sse"):
    monkeypatch.setenv("OPERATION_DB_PATH", str(_runtime_path(f"ops-{name}")))
    api_server = _load_api_server(monkeypatch, _runtime_path(f"api-{name}"))
    return api_server, TestClient(api_server.app)


def _seed_session(api_server, session_id="s-sse"):
    from api import state
    return state.conversation_store.create(
        session_id=session_id, scenario="CD", case_id="case-1", input_json={}
    )


def _parse_stream(body: str):
    """SSE body → [(event_line, data_json)]。"""
    out = []
    for chunk in body.split("\n\n"):
        if not chunk.strip():
            continue
        fields = {}
        for line in chunk.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fields[k.strip()] = v.strip()
        if "data" in fields:
            out.append((fields.get("event"), json.loads(fields["data"]), fields.get("id")))
    return out


def test_stream_envelope_sequence_single_terminal(monkeypatch):
    api_server, client = _client(monkeypatch, "contract")
    _seed_session(api_server)

    res = client.post(
        "/conversation/s-sse/message/stream",
        json={"message": "hello"},
    )
    assert res.status_code == 200
    frames = _parse_stream(res.text)
    assert len(frames) >= 2

    # 首事件是 start（accept 时同步发出）
    assert frames[0][0] == "start"
    env0 = frames[0][1]
    assert env0["schema_version"] == "1"
    assert env0["type"] == "start"
    operation_id = env0["operation_id"]
    request_id = env0["request_id"]
    assert operation_id and request_id

    # sequence 严格递增且与 id: 字段一致
    for i, (_, env, wire_id) in enumerate(frames):
        assert env["sequence"] == i
        assert wire_id == str(i)
        assert env["operation_id"] == operation_id
        assert env["request_id"] == request_id

    # 恰一 terminal，且是 complete（域 final）
    terminals = [e for _, e, _ in frames if e["type"] in ("complete", "error", "cancelled")]
    assert len(terminals) == 1
    final = terminals[0]
    assert final["type"] == "complete"
    assert final["payload"]["event"] == "final"
    assert final["payload"]["response"]["message"].startswith("offline reply")


def test_stream_idempotent_replay_no_second_llm(monkeypatch):
    api_server, client = _client(monkeypatch, "replay")
    _seed_session(api_server)
    from api import state

    calls = {"n": 0}
    original = state.run_agent_turn

    def counting(**kw):
        calls["n"] += 1
        return original(**kw)

    state.run_agent_turn = counting
    op_id = f"op-{uuid.uuid4().hex[:12]}"

    first = client.post("/conversation/s-sse/message/stream",
                        json={"message": "hi", "operation_id": op_id})
    assert first.status_code == 200
    assert calls["n"] == 1

    second = client.post("/conversation/s-sse/message/stream",
                         json={"message": "hi", "operation_id": op_id})
    assert second.status_code == 200
    assert calls["n"] == 1  # 回放不重复 LLM

    frames = _parse_stream(second.text)
    terminals = [e for _, e, _ in frames if e["type"] in ("complete", "error", "cancelled")]
    assert len(terminals) == 1
    assert terminals[0]["payload"].get("replayed") is True


def test_stream_conflicting_operation_id_rejected(monkeypatch):
    api_server, client = _client(monkeypatch, "conflict")
    _seed_session(api_server)
    op_id = f"op-{uuid.uuid4().hex[:12]}"

    ok = client.post("/conversation/s-sse/message/stream",
                     json={"message": "a", "operation_id": op_id})
    assert ok.status_code == 200
    conflict = client.post("/conversation/s-sse/message/stream",
                           json={"message": "different", "operation_id": op_id})
    assert conflict.status_code == 409


def test_worker_error_emits_single_error_terminal(monkeypatch):
    api_server, client = _client(monkeypatch, "err")
    _seed_session(api_server)
    from api import state

    def boom(**kw):
        raise RuntimeError("llm down")

    state.run_agent_turn = boom
    res = client.post("/conversation/s-sse/message/stream", json={"message": "x"})
    assert res.status_code == 200
    frames = _parse_stream(res.text)
    terminals = [e for _, e, _ in frames if e["type"] in ("complete", "error", "cancelled")]
    assert len(terminals) == 1
    assert terminals[0]["type"] == "error"
    assert "llm down" in terminals[0]["payload"]["message"]

    # ledger 记录为 failed
    record = state.operation_store.get(frames[0][1]["operation_id"])
    assert record.status == "failed"
    assert record.commit_count == 0
