"""CD/DD 两 session 交替发言互不污染。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.cd_agent import CDAgent
from agents.dd_agent import DDAgent
from api.runtime import MockApiClient
from core.graphs.checkpoint import SqliteCheckpointStore
from core.graphs.plead_runtime import PleadRuntime, reset_plead_runtime
from core.llm_client import LLMClient


def _runtime(tmp_path: Path) -> PleadRuntime:
    reset_plead_runtime()
    llm = LLMClient()
    llm.enable_mock()
    api = MockApiClient()
    return PleadRuntime(
        cd_agent=CDAgent(api, llm),
        dd_agent=DDAgent(api, llm),
        llm=llm,
        store=SqliteCheckpointStore(str(tmp_path / "plead.sqlite3")),
    )


def test_cd_sessions_isolated(tmp_path):
    rt = _runtime(tmp_path)
    hist_a = [{"role": "Client", "message": "我要起诉张三借款不还。"}]
    hist_b = [{"role": "Client", "message": "公司名称是星河科技。"}]
    text_a, _ = rt.live_turn("alpha", "CD", hist_a, "a", {})
    text_b, _ = rt.live_turn("beta", "CD", hist_b, "b", {})
    snap_a = rt.get_state("alpha", "CD")
    snap_b = rt.get_state("beta", "CD")
    assert snap_a["messages"][0]["message"] != snap_b["messages"][0]["message"]
    assert text_a
    assert text_b


def test_dd_case_data_isolated(tmp_path):
    rt = _runtime(tmp_path)
    hist_a = [{"role": "Client", "message": "我是自然人，不同意原告诉请。"}]
    hist_b = [{"role": "Client", "message": "我们是有限公司，法定代表人王五。"}]
    rt.live_turn("d1", "DD", hist_a, "d1", {})
    rt.live_turn("d2", "DD", hist_b, "d2", {})
    a = rt.get_state("d1", "DD")["case_data"]
    b = rt.get_state("d2", "DD")["case_data"]
    assert a.get("user_entity_type") != b.get("user_entity_type") or a.get("org_info") != b.get("org_info")
