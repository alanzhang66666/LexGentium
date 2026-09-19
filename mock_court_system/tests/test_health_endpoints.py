"""/health/live 与 /health/ready 拆分测试（Task 9.1）。"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _runtime_path(name: str) -> Path:
    base = Path(__file__).resolve().parent / "runtime_tmp"
    base.mkdir(exist_ok=True)
    return base / f"{name}-{uuid.uuid4().hex}.sqlite3"


def _load_api_server(monkeypatch, data_root: Path):
    monkeypatch.setenv("CONVERSATION_STORE", "sqlite")
    monkeypatch.setenv("RUNTIME_DATA_ROOT", str(data_root))
    monkeypatch.setenv("CONVERSATION_DB_PATH", str(data_root / "conversations.sqlite3"))
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")
    monkeypatch.delenv("APP_PROFILE", raising=False)

    stale = [
        m
        for m in list(sys.modules)
        if m == "api_server" or m == "api" or m.startswith("api.") or m in ("settings",)
    ]
    for module_name in stale:
        sys.modules.pop(module_name, None)

    import api_server

    return api_server


def test_live_is_process_only(monkeypatch, tmp_path):
    api_server = _load_api_server(monkeypatch, tmp_path)
    client = TestClient(api_server.app)
    res = client.get("/health/live")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["version"] == "1.0.0"
    assert body["request_id"]
    # live 不探测组件
    assert "components" not in body
    assert "paths" not in body


def test_ready_reports_all_components(monkeypatch, tmp_path):
    api_server = _load_api_server(monkeypatch, tmp_path)
    client = TestClient(api_server.app)
    res = client.get("/health/ready")
    body = res.json()
    components = body["components"]
    for name in (
        "configuration",
        "conversation_store",
        "runtime_store",
        "evaluation_store",
        "research_store",
        "law_retrieval",
        "hearing_runtime",
        "plead_runtime",
    ):
        assert name in components
        assert set(components[name].keys()) == {"ok", "reason"}
    # 无路径/文件名/secret 泄露
    text = res.text
    assert str(tmp_path) not in text
    assert ".sqlite3" not in text


def test_ready_503_on_required_failure(monkeypatch, tmp_path):
    api_server = _load_api_server(monkeypatch, tmp_path)
    from api.routers import health as health_router

    monkeypatch.setattr(
        health_router,
        "_check_store",
        lambda name: {"ok": False, "reason": "open_failed"}
        if name == "conversation_store"
        else {"ok": True, "reason": None},
    )
    client = TestClient(api_server.app)
    res = client.get("/health/ready")
    assert res.status_code == 503
    body = res.json()
    assert body["code"] == "not_ready"
    assert body["failed"] == [{"component": "conversation_store", "reason": "open_failed"}]


def test_failed_set_matches_actual_failures(monkeypatch, tmp_path):
    """Property 48：failed 集合恰等于真实失败集合。"""
    api_server = _load_api_server(monkeypatch, tmp_path)
    from api.routers import health as health_router

    failing = {"evaluation_store", "law_retrieval"}

    def fake_store(name):
        return {"ok": name not in failing, "reason": None if name not in failing else "probe_failed"}

    monkeypatch.setattr(health_router, "_check_store", fake_store)
    monkeypatch.setattr(
        health_router,
        "_check_law_retrieval",
        lambda: {"ok": False, "reason": "unavailable"},
    )
    client = TestClient(api_server.app)
    res = client.get("/health/ready")
    assert res.status_code == 503
    got = {item["component"] for item in res.json()["failed"]}
    assert got == failing


def test_legacy_health_no_path_leak(monkeypatch, tmp_path):
    api_server = _load_api_server(monkeypatch, tmp_path)
    client = TestClient(api_server.app)
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "paths" not in body
    assert str(tmp_path) not in res.text
    assert body["hint"]
