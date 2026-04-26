"""验证构建的数据集"""
import json, os

base = "data/dataset_1000"

print("=== 文件统计 ===")
for split in ["train", "val", "test"]:
    d = os.path.join(base, split)
    for f in sorted(os.listdir(d)):
        path = os.path.join(d, f)
        with open(path, "r", encoding="utf-8") as fh:
            lines = [l for l in fh if l.strip()]
        print(f"  {split}/{f}: {len(lines)} records")

print("\n=== CD 样例 ===")
with open(f"{base}/train/CD_ground_truth.jsonl", "r", encoding="utf-8") as f:
    sample = json.loads(f.readline())
    print(f"  ID: {sample['id']}")
    print(f"  案由: {sample['cause']}")
    p = sample["specific_characters"]["plaintiff"]
    d = sample["specific_characters"]["defendant"]
    print(f"  原告: {p['name']}  性别: {p['gender']}  出生: {p['birth_date']}")
    print(f"  被告: {d['name']}  性别: {d['gender']}  出生: {d['birth_date']}")
    print(f"  诉讼请求 ({len(sample['claims'])} 项): {str(sample['claims'][0])[:80]}...")
    print(f"  事实: {sample['case_details'][:120]}...")
    print(f"  证据: {len(sample['evidence'])} 项")

print("\n=== DD 样例 ===")
with open(f"{base}/train/DD_ground_truth.jsonl", "r", encoding="utf-8") as f:
    sample = json.loads(f.readline())
    print(f"  ID: {sample['id']}")
    print(f"  答辩: {sample['statement_of_defence'][:150]}...")

print("\n=== CI 样例 ===")
with open(f"{base}/train/CI_ground_truth.jsonl", "r", encoding="utf-8") as f:
    sample = json.loads(f.readline())
    print(f"  ID: {sample['id']}")
    print(f"  案由: {sample['cause']}")
    print(f"  法条: {sample['law']}")
    print(f"  判决: {sample['judgment_result'][:150]}...")

print("\n=== 元信息 ===")
with open(f"{base}/dataset_meta.json", "r", encoding="utf-8") as f:
    meta = json.load(f)
    print(f"  来源: {meta['source']}")
    print(f"  论文: {meta['paper']}")
    print(f"  原始规模: {meta['original_size']}")
    print(f"  选取规模: {meta['selected_size']}")
    print(f"  划分: {meta['splits']}")
    print(f"  案由分布 (前10):")
    for cause, cnt in list(meta["cause_distribution"].items())[:10]:
        print(f"    {cause}: {cnt}")
