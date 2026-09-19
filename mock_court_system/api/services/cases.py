"""1K 数据集轻量索引与按 case_id 取全文，供开庭下拉与 start_session 水合。"""
from __future__ import annotations

import json
from core.civil_identity import DATASET_ID, SCENARIOS, dataset_version
from fastapi import HTTPException
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from api import state

_SPLIT_ORDER = ("test", "train", "val")

def _parse_case_ref(case_id: str) -> tuple[str, Optional[str]]:
    parts = (case_id or "").strip().split(":", 2)
    if len(parts) == 3 and parts[0] == DATASET_ID and parts[1] in _SPLIT_ORDER:
        return parts[2], parts[1]
    return (case_id or "").strip(), None


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
    if split not in _SPLIT_ORDER:
        raise ValueError(f"unsupported civil split: {split}")
    actual_split = split
    path = state.project_root / "data" / DATASET_ID / split / "case_info.jsonl"
    if not path.exists():
        actual_split = "train"
        path = state.project_root / "data" / DATASET_ID / actual_split / "case_info.jsonl"
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
            source_id = str(item.get("case_id") or "")
            rows.append({
                "case_id": f"{DATASET_ID}:{actual_split}:{source_id}",
                "source_case_id": source_id,
                "dataset_id": DATASET_ID,
                "split": actual_split,
                "cause": item.get("cause"),
                "plaintiff_name": item.get("plaintiff_name"),
                "defendant_name": item.get("defendant_name"),
                "claim_preview": claim_preview[:160],
                "description_preview": desc[:180],
            })
    return rows


def get_case_full(case_id: str, split: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Load one dataset_1000 row by case_id. Searches test → train → val unless split is set."""
    wanted, namespace_split = _parse_case_ref(case_id)
    if namespace_split and split and split != namespace_split:
        raise ValueError("explicit split conflicts with namespaced case_id")
    split = split or namespace_split
    if not wanted:
        return None
    for item in _iter_case_rows(split):
        if str(item.get("case_id") or "").strip() == wanted:
            return item
    return None


def get_civil_identity(case_id: str, split: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Freeze a dataset_1000 source row and generated CD/DD/CI target identities."""
    source_id, namespace_split = _parse_case_ref(case_id)
    if namespace_split and split and split != namespace_split:
        raise ValueError("explicit split conflicts with namespaced case_id")
    requested_split = split or namespace_split
    splits = (requested_split,) if requested_split else _SPLIT_ORDER
    for actual_split in splits:
        for ordinal, source in enumerate(_iter_case_rows(actual_split)):
            if str(source.get("case_id") or "").strip() != source_id:
                continue
            scenario_gt = {}
            for scenario in SCENARIOS:
                path = _dataset_root() / actual_split / f"{scenario}_ground_truth.jsonl"
                try:
                    with path.open("r", encoding="utf-8") as stream:
                        for index, line in enumerate(stream):
                            if index == ordinal:
                                gt = json.loads(line)
                                break
                        else:
                            return None
                except (OSError, json.JSONDecodeError):
                    return None
                if not isinstance(gt, dict) or gt.get("scenario") != scenario or gt.get("id") != f"{scenario}-{ordinal + 1:04d}" or gt.get("cause") != source.get("cause") or gt.get({"CD": "case_details", "DD": "plaintiff_facts", "CI": "case_facts"}[scenario]) != source.get("case_description"):
                    return None
                scenario_gt[scenario] = {"dataset_id": DATASET_ID, "split": actual_split, "row_index": ordinal, "id": gt["id"]}
            return {
                "dataset_id": DATASET_ID,
                "split": actual_split,
                "dataset_version": dataset_version(state.project_root / "data", actual_split),
                "source_case_id": source_id,
                "source_row_index": ordinal,
                "scenario_gt": scenario_gt,
            }
    return None


def hydrate_civil_input(case_id: str, input_json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merge the full 1K row into input_json so agents receive case text."""
    payload = dict(input_json or {})
    identity = get_civil_identity(case_id)
    row = get_case_full(case_id, split=(identity or {}).get("split"))
    if row is None:
        if case_id.startswith(f"{DATASET_ID}:"):
            raise HTTPException(status_code=404, detail="selected civil dataset case not found")
        return payload
    if identity is None:
        raise HTTPException(status_code=400, detail="civil source row has missing or inconsistent same-split ground truth")
    for key, value in row.items():
        if key not in payload or payload[key] in (None, "", [], {}):
            payload[key] = value
    payload.setdefault("case_id", row.get("case_id") or case_id)
    payload["civil_case"] = identity
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
