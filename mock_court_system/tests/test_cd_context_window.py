"""CD 长对话送入模型的窗口有上界。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.cd_agent import CDAgent
from api.runtime import MockApiClient
from core.graphs.checkpoint import SqliteCheckpointStore
from core.graphs.plead_runtime import DEFAULT_WINDOW, PleadRuntime, reset_plead_runtime
from core.llm_client import LLMClient


def test_window_bounded_after_thirty_turns(tmp_path):
    reset_plead_runtime()
    llm = LLMClient()
    llm.enable_mock()
    rt = PleadRuntime(
        cd_agent=CDAgent(MockApiClient(), llm),
        llm=llm,
        store=SqliteCheckpointStore(str(tmp_path / "win.sqlite3")),
    )
    history = []
    for i in range(30):
        history.append({"role": "Client", "message": f"补充事实第{i}条。"})
        rt.live_turn("win", "CD", history, "win", {})
        history.append({"role": "Lawyer", "message": "请继续。"})
    assert rt.last_window_size <= DEFAULT_WINDOW + 1
    snap = rt.get_state("win", "CD")
    assert len(snap["messages"]) <= DEFAULT_WINDOW
    assert snap.get("summary")
