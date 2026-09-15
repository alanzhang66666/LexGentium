"""两场 CI 可重叠执行，checkpoint 互不污染。"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.ci_agent import CIAgent
from api_runtime import MockApiClient
from core.graphs.checkpoint import SqliteCheckpointStore
from core.graphs.hearing_runtime import HearingRuntime, reset_hearing_runtime
from core.llm_client import LLMClient
from core.schemas import CaseInfo


def _runtime(tmp_path: Path, delay: float = 0.15) -> HearingRuntime:
    reset_hearing_runtime()
    llm = LLMClient()
    llm.enable_mock()
    llm.mock_delay_s = delay
    agent = CIAgent(MockApiClient(), llm, instruction_mode="template", verbose=False)
    agent.case_info = CaseInfo(case_id="conc")
    return HearingRuntime(ci_agent=agent, llm=llm, store=SqliteCheckpointStore(str(tmp_path / "ckpt.sqlite3")))


def test_two_sessions_overlap_faster_than_serial(tmp_path):
    rt = _runtime(tmp_path, delay=0.15)
    rt.start_court("sA", "a", {"case_id": "a"})
    rt.start_court("sB", "b", {"case_id": "b"})

    errors = []

    def run_a():
        try:
            rt.live_turn("sA", "Plaintiff", "到庭，本人确认身份。", "a", {"case_id": "a"})
        except Exception as exc:
            errors.append(exc)

    def run_b():
        try:
            rt.live_turn("sB", "Defendant", "听清权利义务，不申请回避。", "b", {"case_id": "b"})
        except Exception as exc:
            errors.append(exc)

    t0 = time.perf_counter()
    ta = threading.Thread(target=run_a)
    tb = threading.Thread(target=run_b)
    ta.start()
    tb.start()
    ta.join()
    tb.join()
    elapsed = time.perf_counter() - t0
    assert not errors
    assert elapsed < 0.28, elapsed

    sm_a = rt.get_state_machine("sA")
    sm_b = rt.get_state_machine("sB")
    assert sm_a.opening_phase["plaintiff_verified"] is True
    assert sm_a.opening_phase["rights_informed_mask"]["defendant"] is False
    assert sm_b.opening_phase["rights_informed_mask"]["defendant"] is True
    assert sm_b.opening_phase["plaintiff_verified"] is False
