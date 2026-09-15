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
    other = GameEngine(_FakeOrch(), llm)
    other.import_snapshot(snap)
    assert other._plaintiff_strategy_type == "competing"
    assert other.strategy_history[0].score.degraded
    assert other.strategy_history[0].case_result.ci_result.final_document == "判决主文"


def test_game_store_saves_snapshot(tmp_path):
    store = GameSessionStore(str(tmp_path / "games.sqlite3"))
    store.save("game_1", {"plaintiff_strategy": "competing"}, {"case_id": "c1"}, "in_progress", 1, {"rounds": []})
    row = store.get("game_1")
    assert row["status"] == "in_progress"
    assert row["rounds_completed"] == 1
    assert row["result"]["rounds"] == []


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
