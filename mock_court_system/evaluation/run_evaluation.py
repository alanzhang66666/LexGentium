import argparse
import os
import sys
import json
import logging
import uuid
import yaml
from datetime import datetime, timezone
from pathlib import Path

# 允许以脚本方式运行：python evaluation/run_evaluation.py
if __package__ is None and __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation.bodies import dialog_text, prediction_document
from evaluation.evaluators.evaluator_wrapper import EvaluatorWrapper

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EvaluationAttributionError(Exception):
    code = "attribution"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class EmptyEvaluationBodyError(EvaluationAttributionError):
    code = "empty_body"


class MissingFinalOutputError(EvaluationAttributionError):
    code = "missing_final_output"


class MissingPredictionError(EvaluationAttributionError):
    code = "missing_prediction"


class ScoringFailedError(EvaluationAttributionError):
    code = "scoring_failed"


class WrongClusterOrCaseError(EvaluationAttributionError):
    code = "wrong_cluster_or_case"


class MissingReferenceError(EvaluationAttributionError):
    code = "missing_reference"


def load_config(config_path="evaluation/eval_config.yaml"):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    project = Path(config_path).resolve().parent.parent
    paths = config.get("evaluation", {}).get("paths", {})
    for section in ("ground_truth", "output"):
        for key, value in paths.get(section, {}).items():
            if isinstance(value, str) and not Path(value).is_absolute():
                paths[section][key] = str(project / value)
    return config

def load_jsonl(path):
    data = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def _dialog_text(dialog_history):
    parts = []
    for msg in dialog_history or []:
        if not isinstance(msg, dict):
            continue
        text = msg.get("message") or msg.get("content") or msg.get("text") or ""
        if str(text).strip():
            parts.append(str(text).strip())
    return "\n".join(parts)


def prediction_body(pred) -> str:
    return prediction_document(pred)


def _research_identity(pred):
    research = pred.get("input_json") if isinstance(pred.get("input_json"), dict) else {}
    research = research.get("research") if isinstance(research.get("research"), dict) else {}
    dataset_id = pred.get("dataset_id") or research.get("dataset_id")
    cluster_id = pred.get("cluster_id") or research.get("cluster_id")
    pack_version = pred.get("pack_version") or research.get("pack_version")
    if dataset_id or cluster_id:
        return {
            "dataset_id": dataset_id,
            "cluster_id": cluster_id,
            "pack_version": pack_version,
        }
    return None


def _load_research_pack(dataset_id, cluster_id, pack_version=None):
    from core.research import (
        PackNotFoundError,
        PackVersionMismatchError,
        ResearchPackError,
        ResearchPackLoader,
    )
    try:
        return ResearchPackLoader().get_pack(dataset_id, cluster_id, pack_version)
    except (PackNotFoundError, PackVersionMismatchError, ResearchPackError, ValueError) as exc:
        raise WrongClusterOrCaseError(
            f"unknown research cluster or case: {dataset_id}/{cluster_id}"
        ) from exc


def _reference_payload(reference):
    if hasattr(reference, "model_dump"):
        return reference.model_dump(mode="json")
    if isinstance(reference, dict):
        return reference
    return {}


def _evaluate_research_pred(pred, identity):
    if not identity.get("dataset_id") or not identity.get("cluster_id"):
        raise WrongClusterOrCaseError("research dataset_id/cluster_id incomplete")
    if not (prediction_body(pred) or dialog_text(pred.get("dialog_history"))):
        raise EmptyEvaluationBodyError("evaluation body is empty")
    pack = _load_research_pack(
        identity["dataset_id"],
        identity["cluster_id"],
        identity.get("pack_version"),
    )
    if pack.reference is None:
        raise MissingReferenceError("research pack has no reference")
    reference = _reference_payload(pack.reference)
    return {
        "case_id": pack.cluster_id,
        "dataset_id": pack.dataset_id,
        "pack_version": pack.pack_version,
        "reference_version": reference.get("reference_version", pack.pack_version),
        "gold_labels": reference.get("gold_labels") or {},
        "acceptable_paths": reference.get("acceptable_paths") or [],
        "contrast": "pack.reference",
        "score": {
            "contrast": "pack.reference",
            "reference_version": reference.get("reference_version", pack.pack_version),
            "gold_labels": reference.get("gold_labels") or {},
            "acceptable_paths": reference.get("acceptable_paths") or [],
        },
        "reference": reference,
    }


def _civil_lookup(pred, gt_map, scenario):
    for key in (pred.get("id"), pred.get("case_id")):
        if key and key in gt_map:
            return gt_map[key]
    return None


def run_evaluation(config, scenarios=None, prediction_files=None, report_id=None, run_id=None):
    # The structure evaluator is local. Never overwrite process-wide LLM credentials.
    root_output = config["evaluation"]["paths"]["output"]["root"]
    report_id = str(uuid.UUID(str(report_id))) if report_id else str(uuid.uuid4())
    scenarios = ["CD", "DD", "CI"] if scenarios is None else list(dict.fromkeys(scenarios))
    if not scenarios:
        raise EmptyEvaluationBodyError("no scenarios selected")
    results = {}
    for scenario in scenarios:
        if scenario not in {"CD", "DD", "CI"} or not config["evaluation"]["scenarios"].get(scenario, {}).get("enabled", False):
            raise EvaluationAttributionError(f"scenario is invalid or disabled: {scenario}")
        pred_path = (prediction_files.get(scenario) if prediction_files is not None
                     else str(Path("data/output") / f"{scenario}_prediction.jsonl"))
        if not pred_path or not Path(pred_path).is_file():
            raise MissingPredictionError(f"prediction file missing for {scenario}")
        try:
            pred_data = load_jsonl(pred_path)
        except (OSError, ValueError) as exc:
            raise MissingPredictionError(f"prediction file unreadable for {scenario}: {exc}") from exc
        if not pred_data:
            raise EmptyEvaluationBodyError(f"no predictions for {scenario}")
        scenario_results = []
        legacy_gt_map = None
        for pred in pred_data:
            if not isinstance(pred, dict):
                raise EvaluationAttributionError("prediction must be an object")
            if pred.get("scenario") and pred["scenario"] != scenario:
                raise WrongClusterOrCaseError("prediction scenario does not match requested scenario")
            identity = _research_identity(pred)
            if identity:
                scenario_results.append(_evaluate_research_pred(pred, identity))
                continue
            body = prediction_body(pred)
            if not body:
                raise EmptyEvaluationBodyError("generated document is empty; user dialogue cannot be scored")
            civil_identity = pred.get("civil_case") or (pred.get("input_json") or {}).get("civil_case")
            if civil_identity:
                from core.civil_identity import get_civil_ground_truth
                try:
                    gt = get_civil_ground_truth(civil_identity, scenario)
                    source_id = civil_identity["source_case_id"]
                    qualified_id = f"{civil_identity['dataset_id']}:{civil_identity['split']}:{source_id}"
                    valid_ids = {source_id, qualified_id, gt["id"]}
                    row_ids = [pred[key] for key in ("case_id", "id") if pred.get(key)]
                    if not row_ids or any(value not in valid_ids for value in row_ids):
                        raise ValueError("prediction case ID differs from frozen civil identity")
                except (ValueError, OSError, KeyError) as exc:
                    raise WrongClusterOrCaseError(f"civil dataset identity mismatch: {exc}") from exc
            else:
                gt_path = config["evaluation"]["paths"]["ground_truth"][scenario.lower()]
                if legacy_gt_map is None:
                    try:
                        gt_data = load_jsonl(gt_path)
                        legacy_gt_map = {row["id"]: row for row in gt_data}
                        if len(legacy_gt_map) != len(gt_data):
                            raise ValueError("duplicate reference IDs")
                    except (OSError, ValueError, KeyError) as exc:
                        raise WrongClusterOrCaseError(f"civil ground truth invalid for {scenario}") from exc
                gt = _civil_lookup(pred, legacy_gt_map, scenario)
                if gt is None:
                    raise WrongClusterOrCaseError(f"civil case not found in ground truth: {pred.get('id') or pred.get('case_id')}")
            adapted = dict(pred, model_output=body, generated_doc=body)
            wrapper = EvaluatorWrapper(scenario, "", root_output)
            try:
                score = wrapper.evaluate_one(adapted, gt)
            except Exception as exc:
                raise ScoringFailedError(f"scoring failed for {scenario}: {exc}") from exc
            scenario_results.append({
                "case_id": pred.get("case_id") or pred.get("id"),
                "reference_id": gt["id"],
                "civil_case": civil_identity,
                "score": score,
                "model_output": body,
                "input_hash": pred.get("input_hash"),
            })
        results[scenario] = scenario_results
    count = sum(len(rows) for rows in results.values())
    if not count:
        raise EmptyEvaluationBodyError("no valid samples were evaluated")
    report_payload = {
        "report_id": report_id,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": {"evaluated_samples": count},
        **results,
    }
    Path(root_output).mkdir(parents=True, exist_ok=True)
    report_file = Path(root_output) / f"evaluation_report_{report_id}.json"
    report_file.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"report_id": report_id, "run_id": run_id, "report_path": str(report_file), "results": results}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", nargs="+", help="Scenarios to evaluate (CD DD CI)")
    parser.add_argument("--cd-pred", help="Path to CD predictions")
    parser.add_argument("--dd-pred", help="Path to DD predictions")
    parser.add_argument("--ci-pred", help="Path to CI predictions")
    parser.add_argument("--report-id", help="UUID report_id used in the result filename")
    parser.add_argument("--run-id", help="Optional run_id to bind on the report")
    
    args = parser.parse_args()
    
    pred_files = {}
    if args.cd_pred: pred_files['CD'] = args.cd_pred
    if args.dd_pred: pred_files['DD'] = args.dd_pred
    if args.ci_pred: pred_files['CI'] = args.ci_pred
    
    config = load_config()
    run_evaluation(config, args.scenarios, pred_files, report_id=args.report_id, run_id=args.run_id)
