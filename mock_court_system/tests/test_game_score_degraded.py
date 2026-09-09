from core.game_engine import GameEngine, GameScore
from core.llm_client import LLMClient, degraded_json, is_degraded_json


class _DummyCI:
    def __init__(self, text=""):
        self.final_document = text


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


def test_game_score_roundtrip_keeps_degraded():
    raw = GameScore.offline("missing_api_key").to_dict()
    restored = GameScore.from_dict(raw)
    assert restored.degraded
    assert restored.details.get("reason") == "missing_api_key"
    assert is_degraded_json(degraded_json("x"))
