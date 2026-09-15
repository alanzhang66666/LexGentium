"""Inference budget: short clerk tokens, research protocol stop, auto CI cap."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.case_orchestrator import ci_auto_turn_limit
from core.llm_client import LLMClient


def test_fast_token_cap_is_purpose_based():
    llm = LLMClient(max_tokens=4096, fast_max_tokens=512)
    assert llm.max_tokens_for("clerk") == 512
    assert llm.max_tokens_for("extract") == 512
    assert llm.max_tokens_for("score") == 512
    assert llm.max_tokens_for("json") == 4096
    assert llm.max_tokens_for("judgment") == 4096


def test_ci_auto_turn_limit_defaults_to_30(monkeypatch):
    monkeypatch.delenv("CI_MAX_AUTO_TURNS", raising=False)
    assert ci_auto_turn_limit(20) == 30
    assert ci_auto_turn_limit(8) == 24
    assert ci_auto_turn_limit(20, cap=60) == 60
    monkeypatch.setenv("CI_MAX_AUTO_TURNS", "12")
    assert ci_auto_turn_limit(20) == 12
    monkeypatch.setenv("CI_MAX_AUTO_TURNS", "bad")
    assert ci_auto_turn_limit(20) == 30
