"""CI 每回合 LLM 预算：live ≤ 2，auto fast_path ≤ 1（仅 clerk）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.ci_agent import CIAgent
from api_runtime import MockApiClient
from core.graphs.checkpoint import SqliteCheckpointStore
from core.graphs.hearing_runtime import HearingRuntime
from core.llm_client import LLMClient
from core.schemas import CaseInfo, PartyRole


def _agent(llm: LLMClient) -> CIAgent:
    agent = CIAgent(MockApiClient(), llm, instruction_mode="template", verbose=False)
    agent.case_info = CaseInfo(case_id="budget")
    return agent


def test_live_turn_calls_at_most_two(tmp_path):
    os.environ.pop("CI_LEGACY_ANALYSIS", None)
    llm = LLMClient()
    llm.enable_mock()
    agent = _agent(llm)
    store = SqliteCheckpointStore(str(tmp_path / "ckpt.sqlite3"))
    runtime = HearingRuntime(ci_agent=agent, llm=llm, store=store)
    runtime.start_court("s1", "budget", {"case_id": "budget"})
    llm.reset_metrics()
    runtime.live_turn("s1", "Plaintiff", "到庭，本人确认身份。", "budget", {"case_id": "budget"})
    purposes = [r.purpose for r in llm.get_metrics()]
    assert len(purposes) <= 2, purposes
    assert purposes.count("clerk") == 1


def test_fast_path_single_clerk_call(tmp_path):
    llm = LLMClient()
    llm.enable_mock()
    agent = _agent(llm)
    agent.fast_path = True
    store = SqliteCheckpointStore(str(tmp_path / "ckpt.sqlite3"))
    runtime = HearingRuntime(ci_agent=agent, llm=llm, store=store)
    runtime.start_court("s2", "budget", {"case_id": "budget"})
    llm.reset_metrics()
    runtime.live_turn(
        "s2", "Plaintiff", "到庭，本人确认身份。", "budget", {"case_id": "budget"}, fast_path=True,
    )
    calls = llm.get_metrics()
    assert len(calls) <= 1, [c.purpose for c in calls]
    if calls:
        assert calls[0].purpose == "clerk"


def test_clerk_analyze_is_one_json_call():
    llm = LLMClient()
    llm.enable_mock()
    agent = _agent(llm)
    llm.reset_metrics()
    analysis = agent._clerk_analyze(PartyRole.PLAINTIFF, "到庭，本人确认身份。")
    assert analysis.identity_confirmed is True
    assert len(llm.get_metrics()) == 1
    assert llm.get_metrics()[0].purpose == "clerk"
