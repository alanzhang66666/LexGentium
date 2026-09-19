"""BFF route contract: every app/api route uses the shared proxy and is
catalog-covered; no route forwards browser Authorization or hardcodes a
backend origin."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.release.catalog import build_route_diff  # noqa: E402

ROUTE_DIR = ROOT / "app" / "api"
PROXY_RE = re.compile(r"proxyJson|proxySse")
FORBIDDEN_RE = re.compile(
    r"headers\[?\s*[\"']authorization[\"']|"
    r"forward.*authorization|"
    r"localhost:8000|127\.0\.0\.1:8000|"
    r"process\.env\.BACKEND_URL|"
    r"backendFetch\(",
    re.IGNORECASE,
)


def _route_files() -> list[Path]:
    return sorted(ROUTE_DIR.rglob("route.ts"))


def test_every_bff_route_uses_shared_proxy():
    files = _route_files()
    assert files, "no BFF route files found"
    offenders = [p for p in files if not PROXY_RE.search(p.read_text(encoding="utf-8"))]
    assert not offenders, f"routes not using shared proxy: {[str(p) for p in offenders]}"


@pytest.mark.parametrize("route_file", _route_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_route_does_not_leak_auth_or_backend_origin(route_file: Path):
    text = route_file.read_text(encoding="utf-8")
    assert not FORBIDDEN_RE.search(text), f"forbidden pattern in {route_file}"


def test_all_bff_routes_are_catalog_covered():
    diff = build_route_diff(ROOT)
    uncovered = [
        r for r in diff.get("uncovered", [])
        if r.get("surface") in ("next_bff", "bff") or "app/api" in str(r.get("source", ""))
    ]
    assert not uncovered, f"uncovered BFF routes: {uncovered}"
    assert not diff.get("mismatched", []), f"catalog mismatches: {diff['mismatched']}"
