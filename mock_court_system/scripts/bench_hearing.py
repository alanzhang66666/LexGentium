"""CI 庭审 LLM 调用基线：mock 跑 20 回合，输出 calls/turn、p50/p95。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.ci_agent import CIAgent
from core.graphs.hearing_runtime import HearingRuntime
from core.graphs.checkpoint import SqliteCheckpointStore
from core.llm_client import LLMClient
from api_runtime import MockApiClient


SCRIPT = [
    ("Plaintiff", "到庭，本人确认身份。"),
    ("Defendant", "到庭，本人确认身份。"),
    ("Plaintiff", "听清权利义务，不申请回避，明白缺席后果。"),
    ("Defendant", "听清权利义务，不申请回避，明白缺席后果。"),
    ("Plaintiff", "诉讼请求：判令被告返还借款五万元并支付利息。"),
    ("Defendant", "答辩：不同意原告诉请，借款已部分偿还。"),
    ("Plaintiff", "提交借条作为证据。"),
    ("Defendant", "对借条无异议。"),
    ("Plaintiff", "无新证据，举证完毕。"),
    ("Defendant", "无新证据，举证完毕。"),
]


def build_agent(llm: LLMClient) -> CIAgent:
    return CIAgent(MockApiClient(), llm, instruction_mode="template", verbose=False)


def run_incremental(turns: int, fast_path: bool, db_path: str) -> dict:
    llm = LLMClient()
    llm.enable_mock()
    llm.reset_metrics()
    agent = build_agent(llm)
    store = SqliteCheckpointStore(db_path)
    runtime = HearingRuntime(ci_agent=agent, llm=llm, store=store)
    sid = "bench_hearing"
    runtime.init_session(sid, case_id="bench", input_json={"case_id": "bench"}, mode="auto")
    runtime.start_court(sid, "bench", {"case_id": "bench"})
    per_turn = []
    for i in range(turns):
        role, msg = SCRIPT[i % len(SCRIPT)]
        before = len(llm.get_metrics())
        runtime.live_turn(sid, role, msg, "bench", {"case_id": "bench"}, fast_path=fast_path)
        after = len(llm.get_metrics())
        per_turn.append(after - before)
    summary = llm.metrics_summary()
    summary["turns"] = turns
    summary["calls_per_turn"] = round(summary["calls"] / max(1, turns), 3)
    summary["calls_per_turn_series"] = per_turn
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=int, default=20)
    parser.add_argument("--fast-path", action="store_true")
    parser.add_argument("--db", default=str(ROOT / "data" / "bench_checkpoints.sqlite3"))
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.db), exist_ok=True)
    result = run_incremental(args.turns, args.fast_path, args.db)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
