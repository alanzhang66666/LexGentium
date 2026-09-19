"""Validate deployment docs + command catalog (task 13.1).

``--check`` verifies:
- ``deploy/commands.yaml`` parses and every command declares cwd,
  preconditions, a command, and an expected exit or result.
- ``docs/INSTALL.md`` / ``docs/DEPLOY.md`` contain no forbidden patterns:
  unlocked installs (``npm install``, ``pip install -r requirements.txt``),
  ``nohup``, ``User=root``, machine-local absolute paths, or filled secrets.
- Required deployment topics are present (non-root, TLS/proxy/token,
  startup/shutdown order, health/metrics, backup/restore/upgrade/rollback,
  and the disclosed data facts).
- Deploy unit templates exist and declare a non-root User.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMMANDS_YAML = ROOT / "deploy" / "commands.yaml"
INSTALL_MD = ROOT / "docs" / "INSTALL.md"
DEPLOY_MD = ROOT / "docs" / "DEPLOY.md"
UNIT_FILES = [
    ROOT / "deploy" / "lexgentium-api.service",
    ROOT / "deploy" / "lexgentium-web.service",
]

FORBIDDEN_PATTERNS = [
    (re.compile(r"\bnpm install\b"), "unlocked npm install"),
    (re.compile(r"pip install -r requirements\.txt"), "unlocked pip install (use requirements.lock)"),
    (re.compile(r"\bnohup\b"), "nohup example"),
    (re.compile(r"User=root"), "root service account"),
    (re.compile(r"/root/"), "absolute /root/ path"),
    (re.compile(r"[A-Za-z]:\\\\|[A-Za-z]:/Users|/Users/"), "machine-local absolute path"),
    (re.compile(r"(API_KEY|API_TOKEN|SECRET)[ \t]*=[ \t]*[A-Za-z0-9_\-]{8,}"), "filled secret value"),
]

REQUIRED_INSTALL_TOPICS = [
    "mock_court_system",
    "requirements.lock",
    "npm ci",
    "api_server.py",
    "next start",
    "main.py",
    "api_reconstructor",
]

REQUIRED_DEPLOY_TOPICS = [
    "mock_court_system",
    "api_server.py",
    "next start",
    "main.py",
    "non-root",
    "TLS",
    "proxy",
    "API_TOKEN",
    "startup order",
    "readiness",
    "shutdown",
    "log",
    "metric",
    "backup",
    "restore",
    "upgrade",
    "rollback",
    "0",
    "SAMPLE",
    "15",
    "25",
    "dataset",
]

SMOKE_JOURNEYS = {
    "configuration", "conversation", "simulate", "full_simulation",
    "mediation", "research", "evaluation", "system",
}


def _errors() -> list[str]:
    errors: list[str] = []

    if not COMMANDS_YAML.exists():
        errors.append(f"missing {COMMANDS_YAML}")
        catalog = {"commands": []}
    else:
        try:
            catalog = yaml.safe_load(COMMANDS_YAML.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # noqa: BLE001
            errors.append(f"commands.yaml parse error: {exc}")
            catalog = {"commands": []}

    commands = catalog.get("commands") or []
    if not commands:
        errors.append("commands.yaml declares no commands")
    seen_ids = set()
    journeys = set()
    for entry in commands:
        cid = entry.get("id")
        if not cid:
            errors.append("command entry missing id")
            continue
        if cid in seen_ids:
            errors.append(f"duplicate command id: {cid}")
        seen_ids.add(cid)
        for key in ("cwd", "preconditions", "command"):
            if key not in entry:
                errors.append(f"{cid}: missing {key}")
        if "expected_exit" not in entry and "expected_result" not in entry:
            errors.append(f"{cid}: missing expected_exit/expected_result")
        cwd = str(entry.get("cwd", "")).rstrip("/")
        if cwd != "mock_court_system":
            errors.append(f"{cid}: cwd must be mock_court_system, got {entry.get('cwd')!r}")
        if entry.get("journey"):
            journeys.add(entry["journey"])

    missing_journeys = SMOKE_JOURNEYS - journeys
    if missing_journeys:
        errors.append(f"missing smoke commands for journeys: {sorted(missing_journeys)}")

    for doc_path, topics in ((INSTALL_MD, REQUIRED_INSTALL_TOPICS), (DEPLOY_MD, REQUIRED_DEPLOY_TOPICS)):
        if not doc_path.exists():
            errors.append(f"missing {doc_path}")
            continue
        text = doc_path.read_text(encoding="utf-8")
        for pattern, label in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                errors.append(f"{doc_path.name}: forbidden pattern — {label}")
        lowered = text.lower()
        for topic in topics:
            if topic.lower() not in lowered:
                errors.append(f"{doc_path.name}: missing required topic '{topic}'")

    for unit in UNIT_FILES:
        if not unit.exists():
            errors.append(f"missing deploy template {unit.name}")
            continue
        body = unit.read_text(encoding="utf-8")
        if "User=root" in body or not re.search(r"^User=\w+", body, re.M):
            errors.append(f"{unit.name}: must declare a non-root User")
        if "ReadWritePaths" not in body:
            errors.append(f"{unit.name}: missing ReadWritePaths least-privilege rule")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="validate_deployment_docs")
    parser.add_argument("--check", action="store_true", help="validate and exit non-zero on violations")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args(argv)

    errors = _errors()
    report = {"ok": not errors, "errors": errors}
    if args.json or True:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
