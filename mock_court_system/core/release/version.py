"""Canonical LexGentium release version."""
from __future__ import annotations

import json
from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parents[2] / "release" / "version.json"
VERSION_ID: str = json.loads(_VERSION_FILE.read_text(encoding="utf-8"))["version"]

if VERSION_ID != "1.0.0":
    raise RuntimeError(f"unsupported release version: {VERSION_ID}")
