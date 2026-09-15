from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

_LAB_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _LAB_DIR.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from evaluation.lab.run_two_step_small_sample import run


def parse_int_list(text: str) -> List[int]:
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def parse_method_list(text: str) -> List[str]:
    return [x.strip() for x in text.split(",") if x.strip()]


def parse_weight_grid(text: str) -> List[Tuple[float, float, float]]:
    grid: List[Tuple[float, float, float]] = []
    for block in [b.strip() for b in text.split(";") if b.strip()]:
        parts = [p.strip() for p in block.split(",") if p.strip()]
        if len(parts) != 3:
            raise ValueError(f"invalid weight triplet: {block}")
        w = tuple(float(x) for x in parts)
        if abs(sum(w) - 1.0) > 1e-6:
            raise ValueError(f"weight triplet must sum to 1: {block}")
        grid.append(w)
    if not grid:
        raise ValueError("weight grid is empty")
    return grid


def read_summary(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def objective_score(summary: Dict[str, Any]) -> float:
    step1 = summary["step1_overall"]
    step2 = summary["step2_overall"]
    delta = float(step1.get("delta_spne_minus_ne", 0.0))
    sr = float(step1.get("sr", 0.0))
    ess_consistency = 1.0 if bool(step2.get("spne_consistency", False)) else 0.0
    # Align with target: SPNE advantage first, then stability (SR), then ESS consistency.
    return 0.6 * delta + 0.25 * sr + 0.15 * ess_consistency


def cause_delta(by_cause: Dict[str, Any], key: str) -> float:
    val = by_cause.get(key, {})
    if isinstance(val, dict):
        return float(val.get("delta_spne_minus_ne", 0.0))
    return 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Improved API experiments with multi-seed, method sensitivity and payoff-weight grid search")
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--rounds", type=int, default=16)
    parser.add_argument("--evo-generations", type=int, default=120)
    parser.add_argument("--seeds", default="20260419,20260420,20260421")
    parser.add_argument("--methods", default="best_response,fictitious_play,llm_reflection")
    parser.add_argument(
        "--weight-grid",
        default="0.50,0.25,0.25;0.55,0.25,0.20;0.45,0.30,0.25",
        help="semicolon-separated triplets: win,reason,evidence",
    )
    parser.add_argument("--execution-mode", choices=["api", "api_hybrid", "local"], default="api")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--api-timeout", type=int, default=180)
    parser.add_argument("--max-api-calls-per-round", type=int, default=0)
    args = parser.parse_args()

    seeds = parse_int_list(args.seeds)
    methods = parse_method_list(args.methods)
    weights = parse_weight_grid(args.weight_grid)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = Path("results") / f"improved_api_grid_{ts}"
    root.mkdir(parents=True, exist_ok=True)

    records: List[Dict[str, Any]] = []

    for seed, method, w in itertools.product(seeds, methods, weights):
        ns = SimpleNamespace(
            n=args.n,
            rounds=args.rounds,
            input="data/dataset_1000/small_sample_100_three_causes.jsonl", window=3,
            outdir=None,
            evo_generations=args.evo_generations,
            execution_mode=args.execution_mode,
            api_base=args.api_base,
            max_api_calls_per_round=args.max_api_calls_per_round,
            api_timeout=args.api_timeout,
            evolution_method=method,
            payoff_weights=f"{w[0]},{w[1]},{w[2]}",
            seed=seed,
        )
        out_dir = run(ns)
        summary = read_summary(out_dir / "summary.json")

        s1 = summary["step1_overall"]
        s2 = summary["step2_overall"]
        api_info = summary.get("api_integration", {})
        by_cause = summary.get("step1_by_cause", {})

        rec = {
            "seed": seed,
            "method": method,
            "weights": f"{w[0]:.2f},{w[1]:.2f},{w[2]:.2f}",
            "execution_mode": summary.get("execution_mode"),
            "api_calls": int(api_info.get("api_calls", 0)),
            "api_success": int(api_info.get("api_success", 0)),
            "api_failures": int(api_info.get("api_failures", 0)),
            "api_health_ok": bool(api_info.get("health_ok", False)),
            "spne_acc": float(s1.get("spne_acc", 0.0)),
            "ne_acc": float(s1.get("ne_acc", 0.0)),
            "delta": float(s1.get("delta_spne_minus_ne", 0.0)),
            "sr": float(s1.get("sr", 0.0)),
            "ecr": float(s1.get("ecr", 0.0)),
            "ess_strategy": s2.get("overall_evolution", {}).get("ess", {}).get("ess_strategy"),
            "spne_consistency": bool(s2.get("spne_consistency", False)),
            "objective_score": objective_score(summary),
            "delta_traffic": cause_delta(by_cause, "交通事故"),
            "delta_labor": cause_delta(by_cause, "劳动争议"),
            "delta_loan": cause_delta(by_cause, "民间借贷"),
            "summary_path": str((out_dir / "summary.json").as_posix()),
        }
        records.append(rec)

    jsonl_path = root / "all_runs.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    csv_path = root / "all_runs.csv"
    if records:
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            w.writeheader()
            w.writerows(records)

    best = max(records, key=lambda x: x["objective_score"]) if records else None

    # Aggregate sensitivity by method and by weight set.
    method_stats: Dict[str, Dict[str, float]] = {}
    for m in methods:
        subset = [r for r in records if r["method"] == m]
        if not subset:
            continue
        method_stats[m] = {
            "avg_delta": sum(x["delta"] for x in subset) / len(subset),
            "avg_sr": sum(x["sr"] for x in subset) / len(subset),
            "avg_objective": sum(x["objective_score"] for x in subset) / len(subset),
            "ess_consistency_rate": sum(1.0 if x["spne_consistency"] else 0.0 for x in subset) / len(subset),
        }

    weight_stats: Dict[str, Dict[str, float]] = {}
    for w in {r["weights"] for r in records}:
        subset = [r for r in records if r["weights"] == w]
        if not subset:
            continue
        weight_stats[w] = {
            "avg_delta": sum(x["delta"] for x in subset) / len(subset),
            "avg_sr": sum(x["sr"] for x in subset) / len(subset),
            "avg_objective": sum(x["objective_score"] for x in subset) / len(subset),
            "ess_consistency_rate": sum(1.0 if x["spne_consistency"] else 0.0 for x in subset) / len(subset),
        }

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "settings": {
            "n": args.n,
            "rounds": args.rounds,
            "evo_generations": args.evo_generations,
            "seeds": seeds,
            "methods": methods,
            "weight_grid": [list(x) for x in weights],
            "execution_mode": args.execution_mode,
            "api_base": args.api_base,
        },
        "run_count": len(records),
        "best_run": best,
        "method_sensitivity": method_stats,
        "weight_robustness": weight_stats,
        "outputs": {
            "jsonl": str(jsonl_path.as_posix()),
            "csv": str(csv_path.as_posix()),
        },
    }

    report_path = root / "analysis_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "run_count": len(records),
        "report": str(report_path.as_posix()),
        "best": best,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
