"""Read-only checks against the legal annotation workbook."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_CORE_DIR = Path(__file__).resolve().parents[1] / "core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from research.workbook import (  # noqa: E402
    default_workbook_path,
    map_workbook_label,
    validate_workbook,
    validate_workbook_or_raise,
)


def test_workbook_label_maps_stay_on_runtime_tokens():
    assert map_workbook_label("missing", "NR") == "NR"
    assert map_workbook_label("missing", "yes") is None
    assert map_workbook_label("actor", "申请人") == "applicant"
    assert map_workbook_label("visibility", "仅评价侧") == "evaluator_only"
    assert map_workbook_label("availability", "自然缺失") == "natural_missing"
    assert map_workbook_label("action", "承认材料不足") == "admit_insufficient"
    assert map_workbook_label("argumentkind", "教学示例") == "teaching"


def test_missing_workbook_is_an_error(tmp_path):
    report = validate_workbook(tmp_path / "does-not-exist.xlsx")
    assert report.ok is False
    assert report.errors[0].code == "workbook_missing"


def test_annotation_workbook_matches_field_dictionary():
    path = default_workbook_path()
    if not path.is_file():
        pytest.skip(f"annotation workbook not in repo: {path}")
    report = validate_workbook(path)
    assert report.ok, [item.message for item in report.errors]
    assert len(report.sheets) == 24
    assert "raw_locator" in report.field_keys
    assert len(report.field_keys) >= 384
    validate_workbook_or_raise(path)
