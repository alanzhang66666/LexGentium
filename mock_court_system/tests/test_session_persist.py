import json

import pytest

from core.game_engine import GameEngine, GameRound, GameScore
from core.store.game_session_store import GameSessionStore
from core.case_orchestrator import FullCaseResult, StageResult
from core.mediation_engine import MediationEngine, MediationStage
from core.llm_client import LLMClient


class _FakeOrch:
    pass


def test_game_snapshot_roundtrip():
    llm = LLMClient(api_key=None)
    engine = GameEngine(_FakeOrch(), llm)
    engine.set_strategy("plaintiff", "competing")
    engine.set_strategy("defendant", "avoiding")
    engine.strategy_history.append(
        GameRound(
            round_index=0,
            cd_strategy="competing",
            dd_strategy="avoiding",
            case_result=FullCaseResult(
                case_id="c1",
                ci_result=StageResult(scenario="CI", dialog_history=[], final_document="判决主文"),
            ),
            score=GameScore.offline("missing_api_key"),
        )
    )
    snap = engine.export_snapshot()
    assert snap["snapshot_version"] == 1
    other = GameEngine(_FakeOrch(), llm)
    other.import_snapshot(snap)
    assert other._plaintiff_strategy_type == "competing"
    assert other._defendant_strategy_type == "avoiding"
    assert len(other.get_strategy_history()) == 2
    assert other.strategy_history[0].score.degraded
    assert other.strategy_history[0].case_result.ci_result.final_document == "判决主文"


def test_game_store_saves_snapshot(tmp_path):
    store = GameSessionStore(str(tmp_path / "games.sqlite3"))
    store.save("game_1", {"plaintiff_strategy": "competing"}, {"case_id": "c1"}, "in_progress", 1, {"rounds": []})
    row = store.get("game_1")
    assert row["status"] == "in_progress"
    assert row["rounds_completed"] == 1
    assert row["result"]["rounds"] == []


def test_full_game_snapshot_preserves_payoffs_and_custom_state():
    llm = LLMClient(api_key=None)
    engine = GameEngine(_FakeOrch(), llm)
    engine._ess_seed = 42
    engine.set_strategy("plaintiff", "competing", custom_instruction="自定义原告策略")
    engine.set_strategy("defendant", "avoiding", custom_instruction="自定义被告策略")
    engine._dispute_cause = "合同纠纷"
    engine._dispute_cause_detail = "付款争议"
    score = GameScore(0.8, 0.2, 0.7, 0.9)
    engine.nash_tracker.record_round("competing", "avoiding", score.to_dict())
    engine.strategy_history.append(GameRound(
        round_index=0, cd_strategy="competing", dd_strategy="avoiding", score=score,
        case_result=FullCaseResult(case_id="c1", ci_result=StageResult(
            scenario="CI", dialog_history=[{"role": "judge", "content": "判决"}],
            final_document="判决主文", extracted_info={"award": 100}, metadata={"final": True},
        )),
    ))
    snapshot = json.loads(json.dumps(engine.export_snapshot()))
    restored = GameEngine(_FakeOrch(), llm)
    restored.import_snapshot(snapshot)
    assert restored.export_snapshot() == snapshot


def test_restore_rejects_completed_game_without_history(tmp_path, monkeypatch):
    from api import state
    from api.services.game import restore_game

    store = GameSessionStore(str(tmp_path / "legacy.sqlite3"))
    store.save("legacy", {}, {"case_id": "c1"}, "in_progress", 1, None)
    monkeypatch.setattr(state, "_game_store", store)
    monkeypatch.setattr(state, "game_sessions", {})
    with pytest.raises(ValueError, match="存档缺失"):
        restore_game("legacy")
    assert "legacy" not in state.game_sessions


def test_mediation_survives_new_engine(tmp_path):
    db = str(tmp_path / "med.sqlite3")
    llm = LLMClient(api_key=None)
    first = MediationEngine(llm, persist_path=db)
    created = first.create_session("med_1", {"case_id": "c1"}, ["申请人", "被申请人"])
    assert created["session_id"] == "med_1"
    first._sessions["med_1"]["stage"] = MediationStage.STATEMENT
    first._save("med_1")

    second = MediationEngine(llm, persist_path=db)
    status = second.get_session_status("med_1")
    assert status["stage"] == "statement"
    assert status["party_names"] == ["申请人", "被申请人"]
