import threading

import pytest

from core.dual_mode_reasoning import DualModeReasoner
from core.game_engine import GameEngine


def test_dual_mode_generates_concurrently_before_evaluation():
    reasoner = DualModeReasoner(None)
    barrier = threading.Barrier(2, timeout=2)
    completed = []

    def generate(label):
        barrier.wait()
        completed.append(label)
        return label

    reasoner.fast_judgment = lambda *args: generate("fast")
    reasoner.slow_judgment = lambda *args: generate("slow")

    def evaluate(fast, slow, use_llm):
        assert set(completed) == {"fast", "slow"}
        assert (fast, slow, use_llm) == ("fast", "slow", False)
        return {"final_information_gain": 0.5, "confidence_level": "high"}

    reasoner.compute_information_gain = evaluate
    result = reasoner.dual_mode_judgment("facts", "claims", use_llm_eval=False)
    assert result["recommended_output"] == "slow"


@pytest.mark.parametrize("method", ["best_response", "fictitious_play", "llm_reflection"])
def test_strategy_updates_keep_order_and_calling_thread(method):
    engine = GameEngine.__new__(GameEngine)
    caller = threading.get_ident()
    history = []

    def evolve(party, last_round, method):
        assert threading.get_ident() == caller
        if party == "defendant":
            assert history == ["plaintiff"]
        history.append(party)
        return party

    engine.evolve_strategy = evolve
    engine.evolve_both_strategies(None, method=method)
    assert history == ["plaintiff", "defendant"]
