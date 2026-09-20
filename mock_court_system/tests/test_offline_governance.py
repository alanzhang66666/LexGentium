from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from core.store.conversation_store import SqliteConversationStore
from core.store.evaluation_task_store import EvaluationTaskRecord, SqliteEvaluationTaskStore


def _runtime_path(name: str) -> Path:
    base = Path(__file__).resolve().parent / "runtime_tmp"
    base.mkdir(exist_ok=True)
    return base / f"{name}-{uuid.uuid4().hex}.sqlite3"


def _load_api_server(monkeypatch, db_path, *, demo_mode: str = "0"):
    monkeypatch.setenv("CONVERSATION_STORE", "sqlite")
    monkeypatch.setenv("CONVERSATION_DB_PATH", str(db_path))
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("LLM_DEMO_MODE", demo_mode)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")

    # 丢弃 api 包（含 state 与全部 routers）及相关配置模块，让 stores 按新环境重建
    stale = [
        m for m in list(sys.modules)
        if m == "api_server" or m == "api" or m.startswith("api.") or m in ("settings",)
    ]
    for module_name in stale:
        sys.modules.pop(module_name, None)

    import api_server
    from api import state

    def fake_run_agent_turn(*, scenario, case_id, dialog_history, input_json, reasoning_state=None, ci_agent=None):
        return "Lawyer", f"offline reply for {scenario}:{case_id}", False

    # 路由通过 state.run_agent_turn 属性访问，patch 这里才能生效
    state.run_agent_turn = fake_run_agent_turn
    return api_server


def test_health_and_llm_config_are_available_offline(monkeypatch):
    api_server = _load_api_server(monkeypatch, _runtime_path("api-health"))
    client = TestClient(api_server.app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    config = client.get("/config/llm")
    assert config.status_code == 200
    body = config.json()
    assert body["api_key_set"] is False
    assert "model" in body
    assert "base_url" in body


def test_deepseek_demo_mode_prefills_ready_config_and_serves_compatible_api(monkeypatch):
    api_server = _load_api_server(
        monkeypatch,
        _runtime_path("api-deepseek-demo"),
        demo_mode="1",
    )
    client = TestClient(api_server.app)
    config = client.get("/config/llm").json()
    assert config["demo_mode"] is True
    assert config["api_key_set"] is True
    assert config["api_key_masked"] == "demo-****"
    assert config["chat_model_ready"] is True
    assert config["model"] == "deepseek-flash"

    response = client.post(
        "/mock/deepseek/chat/completions",
        headers={"Authorization": "Bearer sk-demo-deepseek-v41-flash"},
        json={
            "model": "deepseek-flash",
            "messages": [{"role": "user", "content": "Please reply connection successful."}],
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "deepseek-flash"
    assert body["choices"][0]["message"]["content"] == "connection successful"
    assert body["usage"]["total_tokens"] > 0

    tested = client.post(
        "/config/llm/test",
        json={
            "provider": "deepseek",
            "api_key": "sk-demo-deepseek-v41-flash",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-flash",
        },
    )
    assert tested.status_code == 200
    assert tested.json()["success"] is True
    assert tested.json()["simulated"] is True


def test_conversation_lifecycle_offline(monkeypatch):
    api_server = _load_api_server(monkeypatch, _runtime_path("api-conversation"))
    client = TestClient(api_server.app)

    created = client.post(
        "/conversation/start",
        json={"scenario": "CD", "case_id": "case-1", "input_json": {"claim": "demo"}},
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    message = client.post(
        f"/conversation/{session_id}/message",
        json={"role": "Client", "message": "hello"},
    )
    assert message.status_code == 200
    assert message.json()["response"]["message"] == "offline reply for CD:case-1"
    assert len(message.json()["dialog_history"]) == 2

    detail = client.get(f"/conversation/{session_id}")
    assert detail.status_code == 200
    assert detail.json()["message_count"] == 2

    listing = client.get("/conversation/list")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    deleted = client.delete(f"/conversation/{session_id}")
    assert deleted.status_code == 200

    missing = client.get(f"/conversation/{session_id}")
    assert missing.status_code == 404


def test_sqlite_conversation_store_roundtrip():
    store = SqliteConversationStore(str(_runtime_path("conversation-store")))
    record = store.create(
        session_id="session-1",
        scenario="CD",
        case_id="case-1",
        input_json={"source": "test"},
    )
    record.dialog_history.append({"turn": 0, "role": "Client", "message": "hello"})
    store.save(record)

    loaded = store.get("session-1")
    assert loaded is not None
    assert loaded.input_json == {"source": "test"}
    assert loaded.message_count == 1

    sessions, total = store.list(limit=10, offset=0)
    assert total == 1
    assert sessions[0]["session_id"] == "session-1"

    assert store.delete("session-1") is True
    assert store.get("session-1") is None


def test_evaluation_task_store_roundtrip():
    store = SqliteEvaluationTaskStore(str(_runtime_path("evaluation-store")))
    record = EvaluationTaskRecord(
        report_id="report-1",
        status="completed",
        message="done",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        results_json=json.dumps({"score": 1}),
        report_path="evaluation/results/report.json",
    )

    store.upsert(record)
    loaded = store.get("report-1")

    assert loaded is not None
    assert loaded.status == "completed"
    assert loaded.results() == {"score": 1}
    assert store.list_recent(limit=5)[0].report_id == "report-1"
