"""旧 process_turn 与增量图路径：阶段序列 / 合规快照一致。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.ci_agent import CIAgent
from api_runtime import MockApiClient
from core.graphs.checkpoint import SqliteCheckpointStore
from core.graphs.hearing_runtime import HearingRuntime
from core.llm_client import LLMClient
from core.schemas import CaseInfo


DIALOG = [
    {"role": "Judge", "message": "对原告说：现在开庭。请原告核实身份信息。"},
    {"role": "Plaintiff", "message": "到庭，本人确认身份。"},
    {"role": "Judge", "message": "对被告说：请核实身份。"},
    {"role": "Defendant", "message": "到庭，本人确认身份。"},
    {"role": "Judge", "message": "对原告说：请听清诉讼权利义务。"},
    {"role": "Plaintiff", "message": "听清权利义务，不申请回避，明白缺席后果。"},
]


def _fresh_agent() -> CIAgent:
    llm = LLMClient()
    llm.enable_mock()
    agent = CIAgent(MockApiClient(), llm, instruction_mode="template", verbose=False)
    agent.case_info = CaseInfo(case_id="parity", plaintiff_name="原告", defendant_name="被告")
    return agent


def _replay_process_turn(history):
    agent = _fresh_agent()
    agent.process_turn(history, "parity", {"case_id": "parity"})
    return {
        "stage": agent.state_machine.export_state(),
        "compliance": agent.state_machine.get_realtime_compliance(),
    }


def _replay_graph(history, tmp_path):
    agent = _fresh_agent()
    store = SqliteCheckpointStore(str(tmp_path / "parity.sqlite3"))
    runtime = HearingRuntime(ci_agent=agent, llm=agent.llm, store=store)
    runtime.start_court("parity", "parity", {"case_id": "parity"})
    for item in history:
        if item["role"] == "Judge":
            continue
        runtime.live_turn("parity", item["role"], item["message"], "parity", {"case_id": "parity"})
    sm = runtime.get_state_machine("parity")
    assert sm is not None
    return {
        "stage": sm.export_state(),
        "compliance": sm.get_realtime_compliance(),
    }


def test_opening_stage_parity(tmp_path):
    prefix = DIALOG[:2]
    old = _replay_process_turn(prefix)
    new = _replay_graph(prefix, tmp_path)
    assert old["stage"]["current_stage"] == new["stage"]["current_stage"]
    assert old["compliance"]["current_stage"] == new["compliance"]["current_stage"]


def test_multi_turn_stage_sequence(tmp_path):
    old_seq = []
    new_seq = []
    for end in range(2, len(DIALOG) + 1, 2):
        hist = DIALOG[:end]
        old_seq.append(_replay_process_turn(hist)["stage"]["current_stage"])
        new_seq.append(_replay_graph(hist, tmp_path / f"t{end}")["stage"]["current_stage"])
    assert old_seq == new_seq
    assert all(s.startswith("S") for s in old_seq)
