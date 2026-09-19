from __future__ import annotations

from pathlib import Path

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
    assert report["missing_civil_splits"] == ["test", "train", "validation"]
    assert report["observation_presentation"]["gate_effect"] == "none"


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
