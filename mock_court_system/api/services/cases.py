"""1K 数据集轻量索引与按 case_id 取全文，供开庭下拉与 start_session 水合。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from api import state

_SPLIT_ORDER = ("test", "train", "val")


def _dataset_root() -> Path:
    return state.project_root / "data" / "dataset_1000"


def _case_info_paths(split: Optional[str] = None) -> List[Path]:
    root = _dataset_root()
    names: Iterable[str] = (split,) if split else _SPLIT_ORDER
    paths: List[Path] = []
    for name in names:
        if not name:
            continue
        path = root / name / "case_info.jsonl"
        if path.exists():
            paths.append(path)
    return paths


def _iter_case_rows(split: Optional[str] = None) -> Iterable[Dict[str, Any]]:
    for path in _case_info_paths(split):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    yield item


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


def get_case_full(case_id: str, split: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Load one dataset_1000 row by case_id. Searches test → train → val unless split is set."""
    wanted = (case_id or "").strip()
    if not wanted:
        return None
    for item in _iter_case_rows(split):
        if str(item.get("case_id") or "").strip() == wanted:
            return item
    return None


def hydrate_civil_input(case_id: str, input_json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merge the full 1K row into input_json so agents receive case text."""
    payload = dict(input_json or {})
    row = get_case_full(case_id)
    if row is None:
        return payload
    for key, value in row.items():
        if key not in payload or payload[key] in (None, "", [], {}):
            payload[key] = value
    payload.setdefault("case_id", row.get("case_id") or case_id)
    claims = payload.get("plaintiff_claims") or []
    if isinstance(claims, list):
        claim_text = "；".join(str(c) for c in claims if c)
    else:
        claim_text = str(claims)
    payload.setdefault("plaintiff_info", {"name": payload.get("plaintiff_name") or "原告"})
    payload.setdefault("defendant_info", {"name": payload.get("defendant_name") or "被告"})
    payload.setdefault("claim_description", claim_text or payload.get("case_description") or "")
    payload.setdefault(
        "case_info",
        {
            "case_number": payload.get("case_id") or case_id,
            "case_id": payload.get("case_id") or case_id,
            "court": payload.get("court") or "",
        },
    )
    payload.setdefault(
        "complaint",
        {
            "plaintiff_claim": claims if isinstance(claims, list) else [claim_text],
            "plaintiff_case_description": payload.get("case_description") or "",
        },
    )
    return payload
