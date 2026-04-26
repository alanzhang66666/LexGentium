import argparse
import os
import sys
import json
import logging
import yaml
from datetime import datetime
from tqdm import tqdm

# 允许以脚本方式运行：python evaluation/run_evaluation.py
if __package__ is None and __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation.adapters.output_adapter import CDOutputAdapter, DDOutputAdapter, CIOutputAdapter
from evaluation.evaluators.evaluator_wrapper import EvaluatorWrapper

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

def run_evaluation(config, scenarios=None, prediction_files=None):
    # Set API Env vars from config
    if 'api' in config['evaluation']:
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
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(root_output, f"evaluation_report_{timestamp}.json")
    
    results = {}
    
    if not scenarios:
        scenarios = ['CD', 'DD', 'CI']
        
    for scenario in scenarios:
        if not config['evaluation']['scenarios'].get(scenario, {}).get('enabled', False):
            continue
            
        logger.info(f"Starting evaluation for {scenario}...")
        
        # 1. Load Ground Truth
        gt_path = config['evaluation']['paths']['ground_truth'][scenario.lower()]
        try:
            gt_data = load_jsonl(gt_path)
            gt_map = {item['id']: item for item in gt_data}
            logger.info(f"Loaded {len(gt_data)} ground truth records for {scenario}")
        except Exception as e:
            logger.error(f"Failed to load GT for {scenario}: {e}")
            continue

        # 2. Load Predictions
        # Assuming predictions are in prediction_files dict or default location
        pred_path = prediction_files.get(scenario) if prediction_files else \
                    os.path.join("data", "output", f"{scenario}_prediction.jsonl")
        
        # Fallback to local test file if main output not found
        if not os.path.exists(pred_path):
             # Try to find standard output from mock_court
             pred_path = os.path.join(f"{scenario}_prediction.jsonl") # Root
        
        if not os.path.exists(pred_path):
            logger.warning(f"Prediction file not found: {pred_path}")
            continue
            
        try:
            pred_data = load_jsonl(pred_path)
            logger.info(f"Loaded {len(pred_data)} predictions for {scenario}")
        except Exception as e:
            logger.error(f"Failed to load predictions: {e}")
            continue
            
        # 3. Initialize Evaluator
        try:
            wrapper = EvaluatorWrapper(scenario, gt_path, root_output)
        except Exception as e:
            logger.error(f"Failed to initialize evaluator for {scenario}: {e}")
            continue
            
        # 4. Initialize Adapter
        if scenario == 'CD':
            adapter = CDOutputAdapter()
        elif scenario == 'DD':
            adapter = DDOutputAdapter()
        else:
            adapter = CIOutputAdapter()
            
        scenario_results = []
        
        # 5. Run Loop
        for pred in tqdm(pred_data, desc=f"Evaluating {scenario}"):
            case_id = pred.get('id')
            if not case_id:
                # If ID is missing, try to infer or skip
                continue
            
            # Match IDs carefully (CD-1 vs CD-01 etc)
            # Simple exact match first
            gt = gt_map.get(case_id)
            if not gt:
                # Try finding by numeric part
                import re
                num_match = re.search(r'\d+', str(case_id))
                if num_match:
                    num = num_match.group(0)
                    # Look for GT with same number
                    for k, v in gt_map.items():
                        if re.search(rf'{scenario}-{num}$', str(k)):
                            gt = v
                            break
                            
            if not gt:
                logger.warning(f"Ground truth not found for {case_id}")
                continue
                
            # Adapt
            adapted_pred = adapter.adapt(pred)
            
            # Evaluate
            try:
                score = wrapper.evaluate_one(adapted_pred, gt)
                scenario_results.append({
                    "case_id": case_id,
                    "score": score
                })
            except Exception as e:
                logger.error(f"Error evaluating {case_id}: {e}")
                
        results[scenario] = scenario_results
        
    # Save Report
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Evaluation complete. Report saved to {report_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", nargs="+", help="Scenarios to evaluate (CD DD CI)")
    parser.add_argument("--cd-pred", help="Path to CD predictions")
    parser.add_argument("--dd-pred", help="Path to DD predictions")
    parser.add_argument("--ci-pred", help="Path to CI predictions")
    
    args = parser.parse_args()
    
    pred_files = {}
    if args.cd_pred: pred_files['CD'] = args.cd_pred
    if args.dd_pred: pred_files['DD'] = args.dd_pred
    if args.ci_pred: pred_files['CI'] = args.ci_pred
    
    config = load_config()
    run_evaluation(config, args.scenarios, pred_files)




