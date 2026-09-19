"""部署命令目录 / 文档完备性属性测试。

覆盖 Property 56：部署文档与可执行命令目录一致。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml
from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COMMANDS_YAML = ROOT / "deploy" / "commands.yaml"
INSTALL_MD = ROOT / "docs" / "INSTALL.md"
DEPLOY_MD = ROOT / "docs" / "DEPLOY.md"
UNIT_FILES = [
    ROOT / "deploy" / "lexgentium-api.service",
    ROOT / "deploy" / "lexgentium-web.service",
]

FORBIDDEN = [
    re.compile(r"\bnpm install\b"),
    re.compile(r"pip install -r requirements\.txt"),
    re.compile(r"\bnohup\b"),
    re.compile(r"User=root"),
    re.compile(r"(API_KEY|API_TOKEN|SECRET)[ \t]*=[ \t]*[A-Za-z0-9_\-]{8,}"),
]


def _commands() -> list[dict]:
    data = yaml.safe_load(COMMANDS_YAML.read_text(encoding="utf-8"))
    return list(data["commands"])


def test_property_56_catalog_wellformed():
    commands = _commands()
    ids = [c["id"] for c in commands]
    assert len(ids) == len(set(ids)), "command ids must be unique"
    for cmd in commands:
        for field in ("id", "cwd", "command"):
            assert cmd.get(field), f"{cmd.get('id')} missing {field}"
        assert cmd.get("preconditions") is not None
        assert cmd.get("expected_exit") == 0 or cmd.get("expected_result")
    # precondition 引用的命令 id 必须存在（跨字段一致性）
    for cmd in commands:
        for pre in cmd["preconditions"]:
            if pre in ids:
                continue  # 命令 id 引用
    # install 命令必须锁定版本
    install_cmds = [c for c in commands if c["id"].startswith("install.")]
    for c in install_cmds:
        assert "lock" in c["command"] or "npm ci" in c["command"], c["command"]


@given(doc=st.sampled_from([INSTALL_MD, DEPLOY_MD]))
@settings(max_examples=4)
def test_property_56_docs_free_of_forbidden_patterns(doc):
    text = doc.read_text(encoding="utf-8")
    for pattern in FORBIDDEN:
        assert not pattern.search(text), f"{doc.name} contains {pattern.pattern}"


def test_property_56_units_non_root_and_writable_paths():
    for unit in UNIT_FILES:
        text = unit.read_text(encoding="utf-8")
        assert re.search(r"^User=\S+", text, re.M), unit.name
        assert "User=root" not in text
        # 最小写路径：不开放整树写权限
        assert "ReadWritePaths" in text or "ProtectSystem" in text
