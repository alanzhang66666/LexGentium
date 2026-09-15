import argparse
import csv
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - optional runtime dependency
    plt = None


# Allow script-style execution: python evaluation/lab/run_pretest_experiment.py
_LAB_DIR = Path(__file__).resolve().parent
_EVAL_DIR = _LAB_DIR.parent
_PROJECT_ROOT = _EVAL_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from evaluation.lab._paths import EVAL_DIR

from evaluation.run_evaluation import load_config, run_evaluation


def _extract_scores(items: List[Dict[str, Any]]) -> List[float]:
    scores: List[float] = []
    for item in items:
        raw = item.get("score", {})
        if isinstance(raw, dict):
            val = raw.get("score")
        else:
            val = raw
        try:
            if val is not None:
                scores.append(float(val))
        except (TypeError, ValueError):
            continue
    return scores


def build_summary(report: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    summary: Dict[str, Dict[str, float]] = {}
    for scenario, items in report.items():
        scenario_scores = _extract_scores(items)
        if not scenario_scores:
            summary[scenario] = {
                "count": 0,
                "mean": 0.0,
                "median": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
            }
            continue

        summary[scenario] = {
            "count": float(len(scenario_scores)),
            "mean": float(statistics.mean(scenario_scores)),
            "median": float(statistics.median(scenario_scores)),
            "std": float(statistics.pstdev(scenario_scores)),
            "min": float(min(scenario_scores)),
            "max": float(max(scenario_scores)),
        }
    return summary


def save_summary_csv(summary: Dict[str, Dict[str, float]], output_path: Path) -> None:
    fields = ["scenario", "count", "mean", "median", "std", "min", "max"]
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for scenario in ["CD", "DD", "CI"]:
            row = {"scenario": scenario}
            row.update(summary.get(scenario, {}))
            writer.writerow(row)


def draw_plots(report: Dict[str, Any], summary: Dict[str, Dict[str, float]], output_dir: Path) -> List[Path]:
    generated: List[Path] = []
    if plt is None:
        return generated

    ordered = ["CD", "DD", "CI"]

    # Mean score bar chart
    means = [summary.get(s, {}).get("mean", 0.0) for s in ordered]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(ordered, means, color=["#4C78A8", "#F58518", "#54A24B"])
    ax.set_title("Pretest Mean Score by Scenario")
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Score")
    for bar, val in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.02, f"{val:.3f}", ha="center", va="bottom")
    fig.tight_layout()
    mean_plot = output_dir / "mean_score_bar.png"
    fig.savefig(mean_plot, dpi=180)
    plt.close(fig)
    generated.append(mean_plot)

    # Score distribution box plot
    data = [_extract_scores(report.get(s, [])) for s in ordered]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.boxplot(data, tick_labels=ordered, patch_artist=True)
    ax.set_title("Pretest Score Distribution")
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Score")
    fig.tight_layout()
    box_plot = output_dir / "score_distribution_box.png"
    fig.savefig(box_plot, dpi=180)
    plt.close(fig)
    generated.append(box_plot)

    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pretest evaluation with timestamped outputs and plots")
    parser.add_argument(
        "--pred-root",
        default=None,
        help="Prediction root directory (default: evaluation/data/real_test_pred)",
    )
    args = parser.parse_args()

    eval_dir = EVAL_DIR
    pred_root = Path(args.pred_root) if args.pred_root else eval_dir / "data" / "real_test_pred"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = eval_dir / "results" / f"pretest_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(str(eval_dir / "eval_config.yaml"))
    config["evaluation"]["paths"]["output"]["root"] = str(run_dir)

    prediction_files = {
        "CD": str(pred_root / "CD_prediction.jsonl"),
        "DD": str(pred_root / "DD_prediction.jsonl"),
        "CI": str(pred_root / "CI_prediction.jsonl"),
    }

    run_evaluation(config, scenarios=["CD", "DD", "CI"], prediction_files=prediction_files)

    report_candidates = sorted(run_dir.glob("evaluation_report_*.json"))
    if not report_candidates:
        raise FileNotFoundError(f"No report found in {run_dir}")
    report_file = report_candidates[-1]

    report = json.loads(report_file.read_text(encoding="utf-8"))
    summary = build_summary(report)

    summary_json = run_dir / "summary.json"
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_csv = run_dir / "summary.csv"
    save_summary_csv(summary, summary_csv)

    plot_files = draw_plots(report, summary, run_dir)

    metadata = {
        "timestamp": timestamp,
        "plan_source_doc": "E:/25-26-1/模拟法庭世纪杯/启研计划申请书（申请人信息）.doc",
        "prediction_files": prediction_files,
        "report_file": str(report_file),
        "summary_json": str(summary_json),
        "summary_csv": str(summary_csv),
        "plots": [str(p) for p in plot_files],
    }
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Pretest completed: {run_dir}")
    print(f"Report: {report_file}")
    print(f"Summary: {summary_json}")
    if plot_files:
        print("Plots:")
        for p in plot_files:
            print(f"  - {p}")
    else:
        print("No plots generated (matplotlib not available).")


if __name__ == "__main__":
    main()
