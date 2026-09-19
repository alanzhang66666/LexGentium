"""Source-control scope and sensitive-artifact scan (task 10.3).

Read-only and secret-safe: the scan only enumerates paths. It never reads
file contents, never uploads anything, and never deletes user data. Any
violation becomes blocker evidence for the release gate.

Violations (each produces a finding):
- tracked ``.env`` files
- tracked ``*.sqlite3`` files
- tracked paths under ``data/session_predictions/``
- empty legal-material directories (selection/source/rule-card asset roots
  must be absent rather than empty when no source file exists)
- tracked runtime/evidence artifacts inside the immutable source tree
  (evidence must live outside application source)

The scope report lists every inspected product path and every excluded
Observation_Presentation path; excluded paths are reported, never inspected.
"""
from __future__ import annotations

import fnmatch
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

# Observation_Presentation: excluded from this feature's scope entirely.
EXCLUDED_PATH_PATTERNS = (
    "components/hearing-3d/*",
    "components/hearing-3d",
    "app/hearing-3d/*",
    "app/hearing-3d",
    "app/court3d/*",
    "app/court3d",
    "pages/court3d*",
    "public/hearing-3d/*",
)

# Roots whose directories must not exist empty (legal material asset roots).
LEGAL_ASSET_ROOTS = (
    "data/research_packs",
    "data/legal_materials",
    "data/selection",
    "data/source_texts",
    "data/rule_cards",
)

# Tracked artifacts that must live outside the immutable source tree.
RUNTIME_ARTIFACT_PATTERNS = (
    "data/evidence/*",
    "data/evidence/**",
    "runtime_data/*",
    "runtime_data/**",
    "release/evidence/generated/*",
    "*.evidence.json",
    "evidence-*.json",
)

_SENSITIVE_FILE_PATTERNS = {
    "tracked_env": (".env", "*.env"),
    "tracked_sqlite": ("*.sqlite3", "*.sqlite3-*"),
    "tracked_session_predictions": ("data/session_predictions/*", "data/session_predictions/**"),
}

# .env files with these suffixes are documented templates, not secrets.
_ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template")


def _is_env_violation(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if name == ".env" or name.endswith(".env"):
        return True
    if name.startswith(".env."):
        return not name.endswith(_ENV_TEMPLATE_SUFFIXES)
    return False

_SKIP_DIR_NAMES = {".git", ".venv", "node_modules", "__pycache__", ".next", "dist"}


@dataclass(frozen=True)
class SourceScanFinding:
    kind: str
    path: str
    detail: str


@dataclass
class SourceScanReport:
    root: str
    inspected_paths: List[str] = field(default_factory=list)
    excluded_paths: List[str] = field(default_factory=list)
    findings: List[SourceScanFinding] = field(default_factory=list)
    tracked_file_count: int = 0
    git_available: bool = True

    @property
    def ok(self) -> bool:
        return not self.findings

    def to_dict(self) -> Dict[str, object]:
        return {
            "root": self.root,
            "ok": self.ok,
            "tracked_file_count": self.tracked_file_count,
            "git_available": self.git_available,
            "inspected_paths": sorted(self.inspected_paths),
            "excluded_paths": sorted(self.excluded_paths),
            "findings": [
                {"kind": f.kind, "path": f.path, "detail": f.detail}
                for f in self.findings
            ],
            "blocker_count": len(self.findings),
        }


def _norm(path: str) -> str:
    path = path.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path.lstrip("/")


def _matches(path: str, patterns: Iterable[str]) -> bool:
    path = _norm(path)
    for pattern in patterns:
        pattern = _norm(pattern)
        if fnmatch.fnmatch(path, pattern):
            return True
        if pattern.endswith("/**") and path.startswith(pattern[:-3].rstrip("/") + "/"):
            return True
        if pattern.endswith("/*") and path.startswith(pattern[:-2].rstrip("/") + "/"):
            return True
    return False


def _git_tracked_files(root: Path) -> List[str]:
    """Paths tracked by git, relative to ``root``. Raises on failure."""
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=str(root),
        capture_output=True,
        check=True,
    )
    return [p for p in proc.stdout.decode("utf-8", "replace").split("\0") if p]


def _worktree_files(root: Path) -> List[str]:
    """Fallback enumeration of the worktree when git is unavailable."""
    files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIR_NAMES]
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            files.append(_norm(rel))
    return files


def _empty_dirs_under(root: Path, asset_root: str) -> List[str]:
    base = root / asset_root
    if not base.is_dir():
        return []
    empty: List[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIR_NAMES]
        if filenames:
            continue
        # A directory is "empty" when it holds no files at any depth.
        has_files = False
        for _, _, nested in os.walk(dirpath):
            if nested:
                has_files = True
                break
        if not has_files:
            empty.append(_norm(os.path.relpath(dirpath, root)))
    return empty


def scan_source(
    root: Path | str,
    *,
    tracked_files: Optional[List[str]] = None,
) -> SourceScanReport:
    """Scan ``root`` for scope and sensitive-artifact violations.

    ``tracked_files`` may be injected for tests; by default the tracked set is
    enumerated via ``git ls-files`` and falls back to a worktree walk (marked
    ``git_available=False``) when git is absent.
    """
    root = Path(root).resolve()
    report = SourceScanReport(root=str(root))

    if tracked_files is None:
        try:
            tracked = _git_tracked_files(root)
        except Exception:
            report.git_available = False
            tracked = _worktree_files(root)
    else:
        tracked = [_norm(p) for p in tracked_files]

    report.tracked_file_count = len(tracked)

    for rel in tracked:
        rel = _norm(rel)
        if _matches(rel, EXCLUDED_PATH_PATTERNS):
            report.excluded_paths.append(rel)
            continue
        report.inspected_paths.append(rel)

        if _is_env_violation(rel):
            report.findings.append(SourceScanFinding(
                "tracked_env", rel, "tracked .env file must not enter source control"))
        if _matches(rel, _SENSITIVE_FILE_PATTERNS["tracked_sqlite"]):
            report.findings.append(SourceScanFinding(
                "tracked_sqlite", rel, "tracked SQLite artifact must not enter source control"))
        if _matches(rel, _SENSITIVE_FILE_PATTERNS["tracked_session_predictions"]):
            report.findings.append(SourceScanFinding(
                "tracked_session_predictions", rel,
                "data/session_predictions/ must not be tracked or read"))
        if _matches(rel, RUNTIME_ARTIFACT_PATTERNS):
            report.findings.append(SourceScanFinding(
                "evidence_in_source", rel,
                "runtime/evidence artifact inside immutable source tree"))

    for asset_root in LEGAL_ASSET_ROOTS:
        for rel_dir in _empty_dirs_under(root, asset_root):
            report.findings.append(SourceScanFinding(
                "empty_legal_directory", rel_dir,
                "empty legal-material directory must be absent, not created"))

    report.excluded_paths.sort()
    report.inspected_paths.sort()
    return report
