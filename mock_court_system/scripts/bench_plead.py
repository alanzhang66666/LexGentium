"""CD 滚动窗口基线：30 轮后窗口大小与 calls。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.cd_agent import CDAgent
from api.runtime import MockApiClient
from core.graphs.checkpoint import SqliteCheckpointStore
from core.graphs.plead_runtime import PleadRuntime
from core.llm_client import LLMClient


def main():
    llm = LLMClient()
    llm.enable_mock()
    llm.reset_metrics()
    rt = PleadRuntime(
        cd_agent=CDAgent(MockApiClient(), llm),
        llm=llm,
        store=SqliteCheckpointStore(str(ROOT / "data" / "bench_plead.sqlite3")),
    )
    history = []
    for i in range(20):
        history.append({"role": "Client", "message": f"事实{i}"})
        rt.live_turn("bench", "CD", history, "bench", {})
        history.append({"role": "Lawyer", "message": "已记录。"})
    out = llm.metrics_summary()
    out["last_window_size"] = rt.last_window_size
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
