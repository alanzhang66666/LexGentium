"""
Run J1Bench CI evaluator on mock_court_multiagents predictions.

Workflow:
1) Convert CI_prediction.jsonl dialog history to J1Bench format.
2) Drop the converted file under J1Bench data/dialog_history/<model_name>/CI_dialog_history.jsonl.
3) Invoke J1Bench CI evaluator with configurable paths.

Example:
  python eval_ci_with_j1bench.py \
    --pred-file output/CI_prediction.jsonl \
    --j1bench-src ../J1Bench/src \
    --model-name mock_court \
    --api-key $OPENAI_API_KEY
"""
import argparse
import json
import os
import sys
from argparse import Namespace
from pathlib import Path
from typing import Dict, List


def load_jsonl(path: Path) -> List[Dict]:
    records: List[Dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def safe_mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def normalize_dialog_history(record: Dict, force_prefix: bool = False) -> Dict:
    case_id = record.get("case_id") or record.get("id")
    if case_id is not None:
        case_id = str(case_id)
        if case_id.startswith("SF-"):
            case_id = case_id[len("SF-"):]
        if force_prefix and not case_id.startswith("CI-"):
            case_id = f"CI-{case_id}"

    dialog_history = []
    turns = record.get("dialog_history") or record.get("history") or []
    for idx, turn in enumerate(turns, 1):
        role = turn.get("role", "Unknown")
        if role == "Plaintiff":
            role = "Plaintiff's Lawyer"
        elif role == "Defendant":
            role = "Defendant's Lawyer"

        content = turn.get("content") or turn.get("message") or ""
        dialog_history.append({
            "turn": turn.get("turn", idx),
            "role": role,
            "content": content,
        })

    return {
        "case_id": case_id,
        "dialog_history": dialog_history,
        "model_answer": record.get("model_answer"),
    }


def compute_pfs(dialog_history: List[Dict]) -> Dict:
    procedures = {
        "开庭审理": {
            "核实身份": {
                "options": ["核实双方当事人的身份", "核实双方当事人身份", "核实当事人身份", "核实身份"],
                "flag": False,
            },
            "审判庭构成": {
                "options": ["构成", "合议庭", "本庭构成"],
                "flag": False,
            },
            "适用程序": {
                "options": ["适用简易程序", "适用程序", "程序"],
                "flag": False,
            },
            "诉讼权利": {
                "options": ["诉讼权利", "告知双方当事人在诉讼中的权利"],
                "flag": False,
            },
            "申请回避": {
                "options": ["回避"],
                "flag": False,
            },
            "缺席后果": {
                "options": ["缺席审理", "缺席后果"],
                "flag": False,
            },
        },
        "法庭调查": {
            "原告陈述": {
                "options": ["诉讼请求", "起诉事实"],
                "flag": False,
            },
            "被告答辩": {
                "options": ["辩护", "答辩", "辩称"],
                "flag": False,
            },
            "举证质证": {
                "options": ["出示证据", "质证"],
                "flag": False,
            },
            "法官发问": {
                "options": ["发问"],
                "flag": False,
            },
        },
        "庭审辩论": {
            "争议焦点": {
                "options": ["争议焦点"],
                "flag": False,
            },
            "最后陈述": {
                "options": ["其他想要说", "其他要说", "其他陈述", "陈述"],
                "flag": False,
            },
        },
        "法庭调解": {
            "询问是否同意调解": {
                "options": ["调解"],
                "flag": False,
            }
        },
    }

    UNI = 0
    ACT = 0
    judge_dialog = [dh for dh in dialog_history if dh.get("role") == "Judge"]
    for jd in dialog_history:
        content = jd.get("content", "")
        role = jd.get("role")
        if role == "Judge":
            count = 0
            for marker in ["<开庭审理>", "<法庭调查>", "<庭审辩论>", "<法庭调解>"]:
                if marker in content:
                    count += 1
                if count == 3:
                    return {
                        "UNI": 0,
                        "STA": 0,
                        "ACT": 0,
                        "check": procedures,
                    }

    STA = 0
    scored_procedures = set()
    for idx, jd in enumerate(dialog_history):
        content = jd.get("content", "")
        role = jd.get("role")
        if role == "Judge":
            UNI = 1
            if idx < len(dialog_history) - 1:
                next_turn = dialog_history[idx + 1]
                if next_turn.get("role") in {"Plaintiff's Lawyer", "Defendant's Lawyer"}:
                    for proc_name, actions in procedures.items():
                        for action_name, payload in actions.items():
                            if not payload["flag"]:
                                if any(option in content for option in payload["options"]):
                                    ACT += 1
                                    payload["flag"] = True
                                    break

            for proc_name, actions in procedures.items():
                if proc_name in scored_procedures:
                    continue
                if all(payload["flag"] for payload in actions.values()):
                    STA += 1
                    scored_procedures.add(proc_name)

    total_ACT = sum(len(actions) for actions in procedures.values())
    return {
        "UNI": UNI,
        "STA": STA / 4,
        "ACT": ACT / total_ACT if total_ACT else 0,
        "check": procedures,
    }


def save_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def convert_predictions(pred_file: Path, out_dir: Path, model_name: str) -> Path:
    records = load_jsonl(pred_file)
    normalized = [normalize_dialog_history(r, force_prefix=True) for r in records]

    target_dir = out_dir / model_name
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / "CI_dialog_history.jsonl"

    with out_file.open("w", encoding="utf-8") as f:
        for item in normalized:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return out_file


def run_pfs_only(converted_file: Path, intermediate_eval: Path, final_eval: Path, model_name: str) -> None:
    records = load_jsonl(converted_file)
    intermediate_model_folder = intermediate_eval / model_name / "CI"
    intermediate_model_folder.mkdir(parents=True, exist_ok=True)

    uni_scores: List[float] = []
    sta_scores: List[float] = []
    act_scores: List[float] = []
    pfs_scores: List[float] = []

    for record in records:
        case_id = record.get("case_id") or record.get("id") or "CI-unknown"
        dialog_history = record.get("dialog_history", [])
        pfs = compute_pfs(dialog_history)

        result = {
            "REA": 0,
            "LAW": 0,
            "JUD": 0,
            "PFS": pfs,
            "dialog_history": dialog_history,
        }
        save_json(intermediate_model_folder / f"{case_id}.json", result)

        last_turn = dialog_history[-1]["turn"] if dialog_history else 0
        uni = float(pfs["UNI"])
        sta = float(pfs["STA"])
        act = float(pfs["ACT"])
        pfs_score = uni * safe_mean([sta, act])

        if last_turn < 4:
            uni = sta = act = pfs_score = 0.0

        uni_scores.append(uni)
        sta_scores.append(sta)
        act_scores.append(act)
        pfs_scores.append(pfs_score)

    summary = {
        "model": model_name,
        "REA": 0.0,
        "LAW": 0.0,
        "JUD": 0.0,
        "STA": safe_mean(sta_scores),
        "ACT": safe_mean(act_scores),
        "UNI": safe_mean(uni_scores),
        "PFS": safe_mean(pfs_scores),
    }

    print("REA", summary["REA"])
    print("LAW", summary["LAW"])
    print("JUD", summary["JUD"])
    print("PFS", summary["PFS"])
    print("UNI", summary["UNI"])
    print("STA", summary["STA"])
    print("ACT", summary["ACT"])

    save_json(final_eval / f"{model_name}_final.json", summary)


def run_evaluation(args: argparse.Namespace) -> None:
    j1bench_src = Path(args.j1bench_src).resolve()
    dialog_history_dir = Path(args.dialog_history_dir or j1bench_src / "data" / "dialog_history").resolve()
    intermediate_eval = Path(args.intermediate_eval or j1bench_src / "Eval" / "eval_result").resolve()
    final_eval = Path(args.final_eval or j1bench_src / "Eval" / "final_result" / "CI").resolve()
    ground_truth = Path(args.ground_truth or j1bench_src / "data" / "case" / "J1-Eval_CI.jsonl").resolve()

    converted_file = convert_predictions(
        Path(args.pred_file).resolve(),
        dialog_history_dir,
        args.model_name,
    )
    print(f"Converted predictions written to: {converted_file}")

    if args.pfs_only:
        print("PFS-only flag detected; skipping JUD/REA/LAW scoring.")
        run_pfs_only(converted_file, intermediate_eval, final_eval, args.model_name)
        return

    sys.path.insert(0, str(j1bench_src))
    from Eval.bench.CI.CI import CIEvaluator
    import utils.utils_func as func

    api_key = args.api_key or os.getenv("OPENAI_API_KEY") or func.api_key
    api_base = args.api_base or os.getenv("OPENAI_API_BASE") or func.api_base
    if api_key:
        func.api_key = api_key
        os.environ["OPENAI_API_KEY"] = api_key
    if api_base:
        func.api_base = api_base
        os.environ["OPENAI_API_BASE"] = api_base

    eval_args = Namespace(
        dialog_history_dir=str(dialog_history_dir),
        intermediate_eval=str(intermediate_eval),
        final_eval=str(final_eval),
        ground_truth=str(ground_truth),
    )

    evaluator = CIEvaluator(eval_args)
    evaluator.iterate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate CI predictions with J1Bench")
    parser.add_argument("--pred-file", default="output/CI_prediction.jsonl", help="Path to CI_prediction.jsonl")
    parser.add_argument("--j1bench-src", default="../J1Bench/src", help="Path to J1Bench/src directory")
    parser.add_argument("--model-name", default="mock_court", help="Folder name under J1Bench data/dialog_history")
    parser.add_argument("--dialog-history-dir", default=None, help="Override dialog history root directory")
    parser.add_argument("--intermediate-eval", default=None, help="Override intermediate eval output directory")
    parser.add_argument("--final-eval", default=None, help="Override final eval output directory")
    parser.add_argument("--ground-truth", default=None, help="Override ground truth CI JSONL path")
    parser.add_argument("--api-key", default=None, help="OpenAI API key for evaluator LLM grading")
    parser.add_argument("--api-base", default=None, help="OpenAI API base for evaluator LLM grading")
    parser.add_argument("--pfs-only", action="store_true", help="Skip JUD/REA/LAW scoring and compute only PFS")

    run_evaluation(parser.parse_args())
