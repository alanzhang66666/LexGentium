"""Source scan: scope report, sensitive artifacts, empty legal dirs."""
from __future__ import annotations

import sys
from pathlib import Path

_PRODUCT_ROOT = Path(__file__).resolve().parents[2]
if str(_PRODUCT_ROOT / "core") not in sys.path:
    sys.path.insert(0, str(_PRODUCT_ROOT / "core"))

from release.source_scan import scan_source  # noqa: E402


def _kinds(report):
    return {f.kind for f in report.findings}


def test_clean_tree_produces_scope_report(tmp_path):
    report = scan_source(
        tmp_path,
        tracked_files=[
            "api_server.py",
            "core/store/registry.py",
            "components/hearing-3d/Stage.tsx",
            "app/hearing-3d/page.tsx",
        ],
    )
    assert report.ok
    assert report.tracked_file_count == 4
    assert "api_server.py" in report.inspected_paths
    assert "core/store/registry.py" in report.inspected_paths
    # Observation_Presentation paths are reported as excluded, not inspected.
    assert set(report.excluded_paths) == {
        "components/hearing-3d/Stage.tsx",
        "app/hearing-3d/page.tsx",
    }
    assert "components/hearing-3d/Stage.tsx" not in report.inspected_paths


def test_tracked_env_sqlite_and_predictions_are_blockers(tmp_path):
    report = scan_source(
        tmp_path,
        tracked_files=[
            ".env",
            "config/prod.env",
            ".env.production",
            "data/store.sqlite3",
            "data/session_predictions/run-1.jsonl",
            ".env.example",
            "docs/DEPLOY.md",
        ],
    )
    kinds = _kinds(report)
    assert "tracked_env" in kinds
    assert "tracked_sqlite" in kinds
    assert "tracked_session_predictions" in kinds
    env_paths = {f.path for f in report.findings if f.kind == "tracked_env"}
    assert ".env" in env_paths
    assert "config/prod.env" in env_paths
    assert ".env.production" in env_paths
    # Documented templates are allowed.
    assert ".env.example" not in env_paths
    assert not report.ok


def test_evidence_artifacts_must_live_outside_source(tmp_path):
    report = scan_source(
        tmp_path,
        tracked_files=[
            "data/evidence/run-1.json",
            "release/evidence/generated/manifest.json",
            "core/release/gate.py",
        ],
    )
    kinds = _kinds(report)
    assert "evidence_in_source" in kinds
    assert "core/release/gate.py" in report.inspected_paths


def test_empty_legal_material_directory_flagged(tmp_path):
    empty_dir = tmp_path / "data" / "research_packs" / "empty-pack" / "sources"
    empty_dir.mkdir(parents=True)
    full_dir = tmp_path / "data" / "research_packs" / "real-pack"
    full_dir.mkdir(parents=True)
    (full_dir / "pack.json").write_text("{}", encoding="utf-8")

    report = scan_source(tmp_path, tracked_files=["data/research_packs/real-pack/pack.json"])
    kinds = _kinds(report)
    assert "empty_legal_directory" in kinds
    flagged = {f.path for f in report.findings if f.kind == "empty_legal_directory"}
    assert any("empty-pack" in p for p in flagged)
    assert not any("real-pack" in p for p in flagged)


def test_missing_legal_asset_root_is_not_flagged(tmp_path):
    report = scan_source(tmp_path, tracked_files=["api_server.py"])
    assert report.ok


def test_scan_never_reads_file_contents(tmp_path):
    secret = tmp_path / ".env"
    secret.write_text("LLM_API_KEY=super-secret\n", encoding="utf-8")
    report = scan_source(tmp_path, tracked_files=[".env"])
    # Findings carry the path and rule kind only — never file content.
    blob = report.to_dict()
    assert "super-secret" not in str(blob)
    assert "LLM_API_KEY" not in str(blob)


def test_real_product_root_scan_runs():
    # Smoke: scanning the real product root must not raise and must not
    # report the fixture packs or tracked sources as violations.
    report = scan_source(_PRODUCT_ROOT)
    kinds = _kinds(report)
    assert "tracked_env" not in kinds
    assert "tracked_sqlite" not in kinds
    assert "tracked_session_predictions" not in kinds
    assert report.tracked_file_count > 0
