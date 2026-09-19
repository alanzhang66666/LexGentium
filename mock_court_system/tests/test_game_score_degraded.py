import json

import pytest

from core.game_engine import GameEngine, GameScore
from core.llm_client import LLMClient, degraded_json, is_degraded_json
from core.case_orchestrator import FullCaseResult, StageResult


class _DummyCI:
    def __init__(self, text=""):
        self.final_document = text


class _OfflineOrchestrator:
    def run_full_case(self, case_info, **kwargs):
        return FullCaseResult(
            case_id=case_info.get("case_id", "offline"),
            ci_result=StageResult(
                scenario="CI",
                dialog_history=[],
                final_document="本院认为应支持原告诉请。",
            ),
        )


def test_chat_json_without_key_is_degraded():
    llm = LLMClient(api_key=None)
    result = llm.chat_json([{"role": "user", "content": "score this judgment"}])
    assert is_degraded_json(result)
    assert result.get("reason") == "missing_api_key"


def test_evaluate_missing_document_is_degraded():
    llm = LLMClient(api_key=None)
    engine = GameEngine.__new__(GameEngine)
    engine.llm = llm
    score = GameEngine.evaluate_judgment(engine, None)
    assert score.degraded
    assert score.plaintiff_win_rate == 0.0
    score2 = GameEngine.evaluate_judgment(engine, _DummyCI(""))
    assert score2.degraded


def test_evaluate_empty_json_is_degraded_not_half():
    llm = LLMClient(api_key="sk-test")
    llm.chat_json = lambda *args, **kwargs: {}
    engine = GameEngine.__new__(GameEngine)
    engine.llm = llm
    score = GameEngine.evaluate_judgment(engine, _DummyCI("本院认为应支持原告诉请。"))
    assert score.degraded
    assert score.plaintiff_win_rate == 0.0
    assert score.details.get("reason")


def test_valid_zero_score_is_not_degraded():
    llm = LLMClient(api_key="sk-test")
    llm.chat_json = lambda *args, **kwargs: {
        "plaintiff_win_rate": 0,
        "defendant_win_rate": 0,
        "reasoning_quality": 0,
        "evidence_strength": 0,
        "analysis": "valid zero result",
    }
    engine = GameEngine.__new__(GameEngine)
    engine.llm = llm
    score = GameEngine.evaluate_judgment(engine, _DummyCI("判决正文"))
    assert not score.degraded
    assert score.plaintiff_win_rate == 0.0


@pytest.mark.parametrize("bad_value", [True, None, "bad", -0.1, 1.1, float("nan"), float("inf")])
def test_invalid_score_is_degraded(bad_value):
    payload = dict.fromkeys(("plaintiff_win_rate", "defendant_win_rate", "reasoning_quality", "evidence_strength"), 0.5)
    payload["plaintiff_win_rate"] = bad_value
    llm = LLMClient(api_key="sk-test")
    llm.chat_json = lambda *args, **kwargs: payload
    engine = GameEngine.__new__(GameEngine)
    engine.llm = llm
    assert engine.evaluate_judgment(_DummyCI("判决正文")).degraded
    assert GameScore.from_dict(payload).degraded


def test_empty_snapshot_score_is_degraded():
    assert GameScore.from_dict({}).degraded


def test_degraded_round_does_not_update_nash_matrix():
    engine = GameEngine(_OfflineOrchestrator(), LLMClient(api_key=None))
    before = engine.nash_tracker.export_state()
    game_round = engine.run_game_round({"case_id": "offline"}, 0)
    after = engine.nash_tracker.export_state()
    assert game_round.score.degraded
    assert after == before
    strategies = engine.export_snapshot()["strategies"]
    engine.evolve_both_strategies(game_round, method="best_response")
    assert engine.export_snapshot()["strategies"] == strategies
    assert engine.get_strategy_history() == []


def test_game_score_roundtrip_keeps_degraded():
    raw = GameScore.offline("missing_api_key").to_dict()
    restored = GameScore.from_dict(raw)
    assert restored.degraded
    assert restored.details.get("reason") == "missing_api_key"
    assert is_degraded_json(degraded_json("x"))


@pytest.mark.parametrize("stream", [False, True])
def test_http_round_returns_degraded_and_restores_snapshot(tmp_path, monkeypatch, stream):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api import state
    from api.routers.game import router
    from api.services.game import restore_game
    from core.store.game_session_store import GameSessionStore

    engine = GameEngine(_OfflineOrchestrator(), LLMClient(api_key=None))
    store = GameSessionStore(str(tmp_path / "games.sqlite3"))
    sessions = {
        "game_offline": {
            "engine": engine,
            "config": {"max_rounds": 2, "enable_dynamic_strategy": True},
            "case_info": {"case_id": "offline"},
            "rounds_completed": 0,
            "created_at": "2026-09-19T00:00:00Z",
            "status": "created",
            "session_id": None,
        }
    }
    monkeypatch.setattr(state, "_game_store", store)
    monkeypatch.setattr(state, "game_sessions", sessions)
    monkeypatch.setattr(state, "_orchestrator", _OfflineOrchestrator())
    monkeypatch.setattr(state, "llm_client", LLMClient(api_key=None))

    app = FastAPI()
    app.include_router(router)
    path = "/game/game_offline/stream-round" if stream else "/game/game_offline/round"
    response = TestClient(app).post(path, json={})
    assert response.status_code == 200, response.text
    if stream:
        assert "event: error" not in response.text
        assert "event: round_complete" in response.text
        payloads = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        completion = next(item for item in payloads if "rounds_completed" in item)
    else:
        completion = response.json()
    assert completion["degraded"] is True
    assert completion["rounds_completed"] == 1
    assert engine.nash_tracker.export_state()["history"] == []

    stored = store.get("game_offline")
    assert stored["result"]["snapshot_version"] == 1
    assert stored["result"]["rounds"][0]["score"]["degraded"] is True

    state.game_sessions = {}
    restored = restore_game("game_offline")
    assert restored is not None
    assert restored["rounds_completed"] == 1
    assert len(restored["engine"].strategy_history) == 1
    assert restored["engine"].strategy_history[0].score.degraded
