import os
import json
import pandas as pd

two_step_dirs = [d for d in os.listdir("evaluation/results") if d.startswith("two_step_small_sample_")]
grid_dirs = [d for d in os.listdir("results") if d.startswith("improved_api_grid_")]

available_two_step = []
unavailable_two_step = []
total_sample_size = 0
total_case_records = 0

for d in two_step_dirs:
    path = os.path.join("evaluation/results", d)
    files = ["step1_spne_vs_ne.json", "step2_ess_validation.json", "summary.json"]
    all_exist = all(os.path.exists(os.path.join(path, f)) for f in files)
    
    if all_exist:
        try:
            with open(os.path.join(path, "step1_spne_vs_ne.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
                available_two_step.append(d)
                total_sample_size += data.get("sample_size", 0)
                total_case_records += len(data.get("case_records", []))
        except Exception:
            unavailable_two_step.append(d)
    else:
        unavailable_two_step.append(d)

available_grid = []
unavailable_grid = []
total_run_count = 0

for d in grid_dirs:
    path = os.path.join("results", d)
    files = ["analysis_report.json", "all_runs.csv"]
    all_exist = all(os.path.exists(os.path.join(path, f)) for f in files)
    
    if all_exist:
        try:
            with open(os.path.join(path, "analysis_report.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
                available_grid.append(d)
                total_run_count += data.get("run_count", 0)
        except Exception:
            unavailable_grid.append(d)
    else:
        unavailable_grid.append(d)

print(f"可用 two-step 组数: {len(available_two_step)}")
print(f"可用 grid 组数: {len(available_grid)}")
print(f"合计可用组数: {len(available_two_step) + len(available_grid)}")
print(f"two-step 累计 sample_size: {total_sample_size}")
print(f"two-step 累计 case_records: {total_case_records}")
print(f"grid 累计 run_count: {total_run_count}")
print("\n--- 可用 two-step 目录 ---")
for d in available_two_step: print(d)
print("\n--- 不可用 two-step 目录 ---")
for d in unavailable_two_step: print(d)
print("\n--- 可用 grid 目录 ---")
for d in available_grid: print(d)
print("\n--- 不可用 grid 目录 ---")
for d in unavailable_grid: print(d)
