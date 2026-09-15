from __future__ import annotations

import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from api.services.links import compact_links, extract_links, merge_link


def _runtime_path(name: str) -> Path:
    base = Path(__file__).resolve().parent / "runtime_tmp"
    base.mkdir(exist_ok=True)
    return base / f"{name}-{uuid.uuid4().hex}.sqlite3"


def _load_api_server(monkeypatch, db_path):
    monkeypatch.setenv("CONVERSATION_STORE", "sqlite")
    monkeypatch.setenv("CONVERSATION_DB_PATH", str(db_path))
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")

    stale = [
        m
        for m in list(sys.modules)
        if m == "api_server" or m == "api" or m.startswith("api.") or m in ("settings",)
    ]
    for module_name in stale:
        sys.modules.pop(module_name, None)

    import api_server
    from api import state

    def fake_run_agent_turn(*, scenario, case_id, dialog_history, input_json):
        return "Lawyer", f"offline reply for {scenario}:{case_id}", False

    state.run_agent_turn = fake_run_agent_turn
    return api_server


def test_merge_and_compact_links():
    merged = merge_link({}, task_id="sim_1", game_id="game_2")
    assert extract_links(merged)["task_id"] == "sim_1"
    assert compact_links(merged) == {"task_id": "sim_1", "game_id": "game_2"}


def test_get_conversation_expands_bound_links(monkeypatch):
    api_server = _load_api_server(monkeypatch, _runtime_path("session-links"))
    client = TestClient(api_server.app)

    started = client.post("/conversation/start", json={"scenario": "CI", "case_id": "case_links_1"})
    assert started.status_code == 200
    session_id = started.json()["session_id"]

    from api.services.conversation import bind_session_link
    from api.services.simulation import create_simulation_task

    task_id = create_simulation_task("single", session_id)
    bind_session_link(session_id, game_id="game_bound_1")

    detail = client.get(f"/conversation/{session_id}")
    assert detail.status_code == 200
    links = detail.json()["links"]
    assert links["task_id"] == task_id
    assert links["game_id"] == "game_bound_1"

    listed = client.get("/conversation/list?limit=10")
    assert listed.status_code == 200
    row = next(s for s in listed.json()["sessions"] if s["session_id"] == session_id)
    assert row["links"]["task_id"] == task_id


def test_reference_cases_endpoint(monkeypatch):
    api_server = _load_api_server(monkeypatch, _runtime_path("ref-cases"))
    client = TestClient(api_server.app)
    res = client.get("/reference/cases?limit=5")
    assert res.status_code == 200
    body = res.json()
    assert "cases" in body
    assert "total" in body
