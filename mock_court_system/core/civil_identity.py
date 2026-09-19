"""Identity resolution for the frozen dataset_1000 civil evaluation corpus."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

DATASET_ID = "dataset_1000"
SCENARIOS = ("CD", "DD", "CI")
SPLITS = ("test", "train", "val")


def dataset_version(root: Optional[Path] = None, split: str = "test") -> str:
    """Content fingerprint for the metadata and all aligned files in one split."""
    data_root = Path(root) if root else Path(__file__).resolve().parents[1] / "data"
    dataset_root = data_root / DATASET_ID
    digest = hashlib.sha256()
    meta_path = dataset_root / "dataset_meta.json"
    digest.update(meta_path.read_bytes())
    for filename in ("case_info.jsonl", *(f"{s}_ground_truth.jsonl" for s in SCENARIOS)):
        path = dataset_root / split / filename
        digest.update(filename.encode("utf-8"))
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _read_jsonl(path: Path) -> list[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_no}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"non-object JSONL row at {path}:{line_no}")
            rows.append(row)
    return rows


def get_civil_ground_truth(
    identity: Dict[str, Any], scenario: str, root: Optional[Path] = None
) -> Dict[str, Any]:
    """Resolve only an explicitly frozen same-split row identity; fail closed."""
    if not isinstance(identity, dict) or identity.get("dataset_id") != DATASET_ID:
        raise ValueError("civil identity must name dataset_1000")
    split = identity.get("split")
    if split not in SPLITS:
        raise ValueError(f"invalid civil split: {split!r}")
    scenario = str(scenario).upper()
    if scenario not in SCENARIOS:
        raise ValueError(f"invalid civil scenario: {scenario!r}")
    actual_version = dataset_version(root, split)
    if identity.get("dataset_version") != actual_version:
        raise ValueError("dataset_1000 content changed since session identity was frozen")
    scenario_identity = (identity.get("scenario_gt") or {}).get(scenario)
    if not isinstance(scenario_identity, dict):
        raise ValueError(f"missing frozen {scenario} ground-truth identity")
    if (scenario_identity.get("dataset_id"), scenario_identity.get("split")) != (DATASET_ID, split):
        raise ValueError(f"{scenario} ground-truth identity points to a different dataset or split")
    row_index = scenario_identity.get("row_index")
    if not isinstance(row_index, int) or row_index < 0 or row_index != identity.get("source_row_index"):
        raise ValueError(f"invalid frozen {scenario} row index")

    data_root = Path(root) if root else Path(__file__).resolve().parents[1] / "data"
    dataset_root = data_root / DATASET_ID
    source_rows = _read_jsonl(dataset_root / split / "case_info.jsonl")
    gt_rows = _read_jsonl(dataset_root / split / f"{scenario}_ground_truth.jsonl")
    if row_index >= len(source_rows) or row_index >= len(gt_rows):
        raise ValueError(f"{scenario} ground truth is missing the frozen source row")
    source = source_rows[row_index]
    gt = gt_rows[row_index]
    if source.get("case_id") != identity.get("source_case_id") or source.get("case_id") != f"CASE-{row_index + 1:04d}":
        raise ValueError("source case ordering changed since identity was frozen")
    expected_gt_id = f"{scenario}-{row_index + 1:04d}"
    if gt.get("scenario") != scenario or gt.get("id") != expected_gt_id or gt.get("id") != scenario_identity.get("id"):
        raise ValueError(f"{scenario} ground-truth row identity mismatch")
    if gt.get("cause") != source.get("cause"):
        raise ValueError(f"{scenario} ground-truth cause does not match source row")
    source_facts = source.get("case_description")
    gt_facts_key = {"CD": "case_details", "DD": "plaintiff_facts", "CI": "case_facts"}[scenario]
    if gt.get(gt_facts_key) != source_facts:
        raise ValueError(f"{scenario} ground-truth facts do not match source row")
    return gt
