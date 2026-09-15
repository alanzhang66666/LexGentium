"""两个 session 交替发言互不污染；重启 SqliteSaver 后续得上。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.ci_agent import CIAgent
from api_runtime import MockApiClient
from core.graphs.checkpoint import SqliteCheckpointStore
from core.graphs.hearing_runtime import HearingRuntime, reset_hearing_runtime
from core.llm_client import LLMClient
from core.schemas import CaseInfo
from core.state_machine import StateMachine


def _runtime(db_path: str) -> HearingRuntime:
    llm = LLMClient()
    llm.enable_mock()
    agent = CIAgent(MockApiClient(), llm, instruction_mode="template", verbose=False)
    agent.case_info = CaseInfo(case_id="ckpt")
    store = SqliteCheckpointStore(db_path)
    return HearingRuntime(ci_agent=agent, llm=llm, store=store)


def test_two_sessions_do_not_cross(tmp_path):
    db = str(tmp_path / "ckpt.sqlite3")
    rt = _runtime(db)
    rt.start_court("alpha", "a", {"case_id": "a"})
    rt.start_court("beta", "b", {"case_id": "b"})
    rt.live_turn("alpha", "Plaintiff", "到庭，本人确认身份。", "a", {"case_id": "a"})
    rt.live_turn("beta", "Defendant", "听清权利义务，不申请回避。", "b", {"case_id": "b"})

    sm_a = rt.get_state_machine("alpha")
    sm_b = rt.get_state_machine("beta")
    assert sm_a is not None and sm_b is not None
    assert sm_a.opening_phase["plaintiff_verified"] is True
    assert sm_a.opening_phase["defendant_verified"] is False
    assert sm_b.opening_phase["defendant_verified"] is False or sm_b.opening_phase["rights_informed_mask"]["defendant"] is True
    assert sm_a.opening_phase["rights_informed_mask"]["defendant"] is False


def test_checkpoint_survives_runtime_reset(tmp_path):
    db = str(tmp_path / "ckpt.sqlite3")
    rt = _runtime(db)
    rt.start_court("gamma", "g", {"case_id": "g"})
    rt.live_turn("gamma", "Plaintiff", "到庭，本人确认身份。", "g", {"case_id": "g"})
    snap = rt.get_state("gamma")
    assert snap and snap.get("sm")

    reset_hearing_runtime()
    store = SqliteCheckpointStore(db)
    restored = store.load("gamma")
    assert restored is not None
    sm = StateMachine.from_dict(restored["sm"])
    assert sm.opening_phase["plaintiff_verified"] is True
    rt2 = _runtime(db)
    sm2 = rt2.get_state_machine("gamma")
    assert sm2 is not None
    assert sm2.opening_phase["plaintiff_verified"] is True
