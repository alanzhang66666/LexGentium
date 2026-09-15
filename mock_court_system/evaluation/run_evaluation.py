import argparse
import os
import sys
import json
import logging
import uuid
import yaml
from pathlib import Path
from tqdm import tqdm

# 允许以脚本方式运行：python evaluation/run_evaluation.py
if __package__ is None and __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation.adapters.output_adapter import CDOutputAdapter, DDOutputAdapter, CIOutputAdapter
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


class WrongClusterOrCaseError(EvaluationAttributionError):
    code = "wrong_cluster_or_case"


class MissingReferenceError(EvaluationAttributionError):
    code = "missing_reference"


def load_config(config_path="evaluation/eval_config.yaml"):
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

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
    for key in ("model_output", "generated_doc"):
        if str(pred.get(key) or "").strip():
            return str(pred.get(key)).strip()
    return _dialog_text(pred.get("dialog_history"))


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
    if not prediction_body(pred):
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
    # Set API Env vars from config
    if config.get('evaluation', {}).get('api'):
        api_conf = config['evaluation']['api']
        if 'base_url' in api_conf:
            os.environ['OPENAI_BASE_URL'] = api_conf['base_url']
            os.environ['LLM_BASE_URL'] = api_conf['base_url']
        if 'api_key' in api_conf:
            os.environ['OPENAI_API_KEY'] = api_conf['api_key']
            os.environ['LLM_API_KEY'] = api_conf['api_key']
        if 'model' in api_conf:
            os.environ['EVAL_MODEL_NAME'] = api_conf['model']

    root_output = config['evaluation']['paths']['output']['root']
    os.makedirs(root_output, exist_ok=True)

    if report_id:
        try:
            report_id = str(uuid.UUID(str(report_id)))
        except (TypeError, ValueError) as exc:
            raise ValueError("report_id must be a UUID string") from exc
    else:
        report_id = str(uuid.uuid4())

    report_file = os.path.join(root_output, f"evaluation_report_{report_id}.json")

    results = {}

    if not scenarios:
        scenarios = ['CD', 'DD', 'CI']

    for scenario in scenarios:
        if not config['evaluation']['scenarios'].get(scenario, {}).get('enabled', False):
            continue

        logger.info(f"Starting evaluation for {scenario}...")

        pred_path = prediction_files.get(scenario) if prediction_files else \
                    os.path.join("data", "output", f"{scenario}_prediction.jsonl")

        if not os.path.exists(pred_path):
             pred_path = os.path.join(f"{scenario}_prediction.jsonl")

        if not os.path.exists(pred_path):
            logger.warning(f"Prediction file not found: {pred_path}")
            continue

        try:
            pred_data = load_jsonl(pred_path)
            logger.info(f"Loaded {len(pred_data)} predictions for {scenario}")
        except Exception as e:
            logger.error(f"Failed to load predictions: {e}")
            continue

        if not pred_data:
            raise EmptyEvaluationBodyError("evaluation body is empty")

        research_rows = []
        civil_rows = []
        for pred in pred_data:
            identity = _research_identity(pred)
            if identity:
                research_rows.append((pred, identity))
            else:
                civil_rows.append(pred)

        scenario_results = []

        for pred, identity in research_rows:
            scenario_results.append(_evaluate_research_pred(pred, identity))

        if civil_rows:
            gt_path = config['evaluation']['paths']['ground_truth'][scenario.lower()]
            try:
                gt_data = load_jsonl(gt_path)
                gt_map = {item['id']: item for item in gt_data}
                logger.info(f"Loaded {len(gt_data)} ground truth records for {scenario}")
            except Exception as e:
                logger.error(f"Failed to load GT for {scenario}: {e}")
                raise WrongClusterOrCaseError(f"civil ground truth missing for {scenario}") from e

            try:
                wrapper = EvaluatorWrapper(scenario, gt_path, root_output)
            except Exception as e:
                logger.error(f"Failed to initialize evaluator for {scenario}: {e}")
                continue

            if scenario == 'CD':
                adapter = CDOutputAdapter()
            elif scenario == 'DD':
                adapter = DDOutputAdapter()
            else:
                adapter = CIOutputAdapter()

            for pred in tqdm(civil_rows, desc=f"Evaluating {scenario}"):
                if not prediction_body(pred):
                    raise EmptyEvaluationBodyError("evaluation body is empty")
                case_id = pred.get('id') or pred.get('case_id')
                gt = _civil_lookup(pred, gt_map, scenario)
                if not gt:
                    raise WrongClusterOrCaseError(
                        f"civil case not found in ground truth: {case_id}"
                    )

                adapted_pred = adapter.adapt(pred)
                if not adapted_pred.get("model_output"):
                    adapted_pred["model_output"] = prediction_body(pred)
                try:
                    score = wrapper.evaluate_one(adapted_pred, gt)
                    scenario_results.append({
                        "case_id": case_id,
                        "score": score,
                        "model_output": prediction_body(pred),
                    })
                except Exception as e:
                    logger.error(f"Error evaluating {case_id}: {e}")

        results[scenario] = scenario_results

    report_payload = {
        "report_id": report_id,
        "run_id": run_id,
        **results,
    }
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report_payload, f, ensure_ascii=False, indent=2)

    logger.info(f"Evaluation complete. Report saved to {report_file}")
    return {
        "report_id": report_id,
        "run_id": run_id,
        "report_path": report_file,
        "results": results,
    }

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
