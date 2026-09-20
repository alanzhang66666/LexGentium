"""SSE HTTP smoke test with the real dispatcher and an offline CI agent."""
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_ci_stream_emits_delta_and_final_with_session_metadata(monkeypatch):
    from api import state
    from api.routers.conversation import router
    from core.store.conversation_store import MemoryConversationStore

    store = MemoryConversationStore()
    store.create(session_id="stream-session", scenario="CI", case_id="test", input_json={})
    monkeypatch.setattr(state, "conversation_store", store)
    hooks = {}
    llm = SimpleNamespace(
        set_stream_hook=lambda hook: hooks.update(hook=hook),
        clear_stream_hook=lambda: hooks.pop("hook", None),
    )
    monkeypatch.setattr(state, "llm_client", llm)

    class Agent:
        judgment_status = "verified"
        citation_report = {"checked": True}
        case_warnings = ["sample only"]
        state_machine = SimpleNamespace(export_state=lambda: {"is_finished": True})

    def run_turn(*, scenario, case_id, dialog_history, input_json, reasoning_state=None, ci_agent=None):
        assert input_json["_session_id"] == "stream-session"
        hooks["hook"]("最终")
        hooks["hook"]("文书")
        return "Final", "最终文书", True

    monkeypatch.setattr(state, "run_agent_turn", run_turn)
    monkeypatch.setattr(state, "new_session_ci_agent", lambda: Agent())
    monkeypatch.setattr(state, "save_ci_reasoning_state", lambda record, supplied: None)
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).post(
        "/conversation/stream-session/message/stream",
        json={"message": "请继续", "role": "Plaintiff"},
    )
    assert response.status_code == 200
    events = []
    for chunk in response.text.strip().split("\n\n"):
        if not chunk.strip():
            continue
        data_line = next((line[6:] for line in chunk.splitlines() if line.startswith("data: ")), None)
        if data_line is not None:
            events.append(json.loads(data_line))
    assert events[0]["type"] == "start"
    assert [event["type"] for event in events if event["type"] == "delta"] == ["delta", "delta"]
    terminals = [event for event in events if event["type"] in ("complete", "error", "cancelled")]
    assert len(terminals) == 1
    final = terminals[0]["payload"]
    assert final["event"] == "final"
    assert final["response"] == {"role": "Final", "message": "最终文书"}
    assert final["is_finished"] is True
    assert final["reasoning_meta"]["judgment_status"] == "verified"
    assert store.get("stream-session").dialog_history[-1]["role"] == "Final"
    assert hooks == {}
