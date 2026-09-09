"""1K 数据集轻量索引，供开庭下拉。"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from api import state


def list_case_index(limit: int = 40, split: str = "test") -> List[Dict[str, Any]]:
    path = state.project_root / "data" / "dataset_1000" / split / "case_info.jsonl"
    if not path.exists():
        path = state.project_root / "data" / "dataset_1000" / "train" / "case_info.jsonl"
    if not path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= max(1, min(limit, 200)):
                break
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            claims = item.get("plaintiff_claims") or []
            if isinstance(claims, list):
                claim_preview = "；".join(str(c) for c in claims[:2])
            else:
                claim_preview = str(claims)
            desc = str(item.get("case_description") or "")
            rows.append({
                "case_id": item.get("case_id"),
                "cause": item.get("cause"),
                "plaintiff_name": item.get("plaintiff_name"),
                "defendant_name": item.get("defendant_name"),
                "claim_preview": claim_preview[:160],
                "description_preview": desc[:180],
            })
    return rows
