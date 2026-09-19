"""Civil case identity stays tied to its dataset split and generated GT row."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from api.services import cases
from core.civil_identity import get_civil_ground_truth

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"


def test_namespaced_selection_and_legacy_test_preference():
    selected = cases.list_case_index(limit=1, split="train")[0]
    assert selected["case_id"] == "dataset_1000:train:CASE-0001"
    assert selected["source_case_id"] == "CASE-0001"
    assert selected["split"] == "train"
    assert cases.get_civil_identity("CASE-0001")["split"] == "test"
    assert cases.get_civil_identity("dataset_1000:val:CASE-0001")["split"] == "val"
    with pytest.raises(ValueError, match="conflicts"):
        cases.get_case_full("dataset_1000:val:CASE-0001", split="train")


@pytest.mark.parametrize("split", ["test", "train", "val"])
def test_frozen_identity_resolves_same_source_row(split):
    ref = f"dataset_1000:{split}:CASE-0001"
    identity = cases.get_civil_identity(ref)
    assert identity is not None
    assert identity["dataset_id"] == "dataset_1000"
    assert identity["source_case_id"] == "CASE-0001"
    assert identity["split"] == split
    for scenario, fact_key in (("CD", "case_details"), ("DD", "plaintiff_facts"), ("CI", "case_facts")):
        gt = get_civil_ground_truth(identity, scenario)
        source = cases.get_case_full(ref)
        assert gt["id"] == f"{scenario}-0001"
        assert gt[fact_key] == source["case_description"]
        assert gt["cause"] == source["cause"]


def test_gt_lookup_fails_when_frozen_dataset_changes(tmp_path):
    source = DATA_ROOT / "dataset_1000"
    target = tmp_path / "dataset_1000"
    shutil.copytree(source, target)
    identity = cases.get_civil_identity("dataset_1000:test:CASE-0001")
    assert identity is not None
    path = target / "test" / "CI_ground_truth.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["case_facts"] = "reordered or changed data"
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="content changed"):
        get_civil_ground_truth(identity, "CI", root=tmp_path)
