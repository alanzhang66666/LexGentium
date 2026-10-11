from __future__ import annotations

from pathlib import Path
import shutil

import pytest
import yaml

from core.release.catalog import (
    all_versions_match,
    build_inventory_report,
    build_route_diff,
    load_configuration_catalog,
    load_route_catalog,
    version_surfaces,
)
from core.release.version import VERSION_ID

ROOT = Path(__file__).resolve().parents[2]


def test_route_catalog_strictly_classifies_actual_fastapi_and_next_routes() -> None:
    report = build_route_diff(ROOT)

    assert report["is_clean"], report
    assert report["unclassified"] == []
    assert report["ambiguous"] == []
    assert report["classified"]["stable"]
    assert report["classified"]["experimental"]
    demo_routes = [
        route for route in report["classified"]["experimental"]
        if route["path"] == "/mock/deepseek/chat/completions"
    ]
    assert len(demo_routes) == 1
    assert demo_routes[0]["method"] == "POST"
    assert demo_routes[0]["response_mode"] == "json_or_sse"

    for route in report["classified"]["stable"]:
        assert route["method"]
        assert route["path"].startswith("/")
        assert route["auth"]
        assert route["response_mode"] in {"html", "json", "sse"}
        assert route["journey"]


def test_observation_routes_are_excluded_and_legacy_court3d_is_redirect_only() -> None:
    catalog = load_route_catalog(ROOT)
    report = build_route_diff(ROOT)
    redirect_paths = {item["path"] for item in report["classified"]["redirect"]}
    stable_paths = {item["path"] for item in report["classified"]["stable"]}
    experimental_paths = {item["path"] for item in report["classified"]["experimental"]}

    assert redirect_paths == {"/court3d", "/court3d/[sessionId]", "/court3d/replay"}
    assert not redirect_paths & stable_paths
    assert not redirect_paths & experimental_paths
    assert catalog["scope"]["excluded_paths"] == [
        {"path": "components/hearing-3d", "reason": "observation_visual_quality", "gate_effect": "none"},
        {"path": "app/hearing-3d", "reason": "observation_presentation", "gate_effect": "none"},
    ]
    assert {item["path"] for item in report["classified"]["excluded"]} == {"/hearing-3d"}


def test_authoritative_inventory_matches_repository_without_creating_materials() -> None:
    report = build_inventory_report(ROOT)

    assert report["is_consistent"], report
    assert report["formal_pack_count"] == 0
    assert {item["id"] for item in report["technical_fixtures"]} == {
        "enf-cn-notice-001",
        "cisg-art79-sample-001",
    }
    assert all(item["classification"] == "technical_fixture" and item["exists"] for item in report["technical_fixtures"])
    assert report["unreviewed_annotations"] == {
        "count": 15,
        "independent_review_complete": False,
        "formal_eligible": False,
    }
    assert report["case_25"]["classification"] == "ai_assisted_initial_annotation"
    assert report["case_25"]["confirmation"] == "pending"
    assert report["missing_civil_splits"] == []
    assert report["expected_missing_civil_splits"] == []
    gaps = yaml.safe_load((ROOT / "release/gaps.yaml").read_text(encoding="utf-8"))["gaps"]
    civil_gap = next(gap for gap in gaps if gap["gap_id"] == "gap-civil-dataset-splits")
    assert civil_gap["status"] == "closed"
    assert len(report["candidate_packs"]) == 1
    candidate = report["candidate_packs"][0]
    assert candidate["id"] == "enf-us-yingfan-amazon-001"
    assert candidate["classification"] == "candidate"
    assert candidate["exists"]
    assert candidate["independent_review_complete"] is False
    assert candidate["formal_eligible"] is False
    assert report["observation_presentation"]["gate_effect"] == "none"


@pytest.mark.parametrize("missing_path", [
    "data/dataset_1000/train/case_info.jsonl",
    "data/dataset_1000/val/case_info.jsonl",
    "data/dataset_1000/test/case_info.jsonl",
    "data/research_packs/enforcement/enf-cn-notice-001/pack.json",
    "data/research_packs/cisg/cisg-art79-sample-001/pack.json",
    "data/research_packs/enforcement/enf-us-yingfan-amazon-001/pack.json",
])
def test_inventory_rejects_missing_split_or_pack_manifest(tmp_path: Path, missing_path: str) -> None:
    for directory in ("release", "docs", "data/dataset_1000", "data/research_packs"):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    assert build_inventory_report(tmp_path)["is_consistent"]

    (tmp_path / missing_path).unlink()

    report = build_inventory_report(tmp_path)
    assert not report["is_consistent"], report
    if "dataset_1000" in missing_path:
        split = missing_path.split("/")[2]
        assert report["missing_civil_splits"] == [{"val": "validation"}.get(split, split)]
    else:
        packs = report["technical_fixtures"] + report["candidate_packs"]
        assert [p["path"] + "/pack.json" for p in packs if not p["exists"]] == [missing_path]


def test_configuration_catalog_has_unique_complete_security_classification() -> None:
    variables = load_configuration_catalog(ROOT)["variables"]
    names = [item["name"] for item in variables]

    assert len(names) == len(set(names))
    assert {"LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_FAST_MAX_TOKENS", "CI_MAX_AUTO_TURNS"} <= set(names)
    assert all(item["visibility"] in {"browser_visible", "server_only"} for item in variables)
    assert all(isinstance(item["secret"], bool) and isinstance(item["required"], bool) for item in variables)
    assert all(item["visibility"] == "server_only" for item in variables if item["secret"])


def test_all_version_surfaces_use_shared_1_0_0() -> None:
    surfaces = version_surfaces(ROOT)

    assert VERSION_ID == "1.0.0"
    assert all_versions_match(ROOT)
    assert set(surfaces.values()) == {"1.0.0"}
    assert '"version": "1.0.0"' in (ROOT / "package.json").read_text(encoding="utf-8")
    assert "APP_VERSION" in (ROOT / "components" / "footer.tsx").read_text(encoding="utf-8")
    assert "VERSION_ID" in (ROOT / "api" / "routers" / "health.py").read_text(encoding="utf-8")
