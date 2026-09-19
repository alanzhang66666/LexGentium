"""Conversation Archive Codec 属性测试。

覆盖 Property 39：parse-all-errors / 稳定 roundtrip / 未知字段拒绝。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.archive.conversation import (  # noqa: E402
    SCHEMA_VERSION,
    ArchiveValidationError,
    ConversationArchive,
    ConversationArchiveCodec,
)

CODEC = ConversationArchiveCodec()


def _archive(**kw) -> ConversationArchive:
    base = dict(
        session_id="sess-1",
        scenario="ci",
        case_id="case-1",
        stage="investigation",
        dialog=[{"turn": 1, "role": "plaintiff", "message": "hello"}],
        links={"a": "b"},
        input_json={"k": "v"},
    )
    base.update(kw)
    return ConversationArchive(**base)


@given(messages=st.lists(st.text(max_size=30), min_size=0, max_size=5))
@settings(max_examples=15)
def test_property_39_archive_roundtrip_stable(messages):
    archive = _archive(
        dialog=[{"turn": i + 1, "role": "plaintiff", "message": m} for i, m in enumerate(messages)]
    )
    text = CODEC.dumps(archive)
    reparsed = CODEC.parse(text)
    assert CODEC.semantic_digest(reparsed) == CODEC.semantic_digest(archive)
    # 二次 dump 字节稳定（无语义空白差异）
    assert CODEC.dumps(reparsed) == text


@given(key=st.text(min_size=1, max_size=20))
@settings(max_examples=20)
def test_property_39_unknown_fields_rejected(key):
    payload = json.loads(CODEC.dumps(_archive()))
    if key in payload:
        return
    payload[key] = "x"
    with pytest.raises(ArchiveValidationError) as exc:
        CODEC.parse(payload)
    assert any(e["path"] == f"/{key}" and e["reason"] == "extra" for e in exc.value.errors)


def test_property_39_parse_collects_all_errors():
    payload = {
        "schema_version": "99",
        "session_policy": "bogus",
        "scenario": 42,
        "unknown_key": 1,
    }
    with pytest.raises(ArchiveValidationError) as exc:
        CODEC.parse(payload)
    paths = {e["path"] for e in exc.value.errors}
    # 全部可判定违规一次性报告，而非首个失败
    assert "/schema_version" in paths
    assert "/session_policy" in paths
    assert "/scenario" in paths
    assert "/unknown_key" in paths


def test_property_39_valid_parse_requires_schema_version():
    payload = {"schema_version": "1", "scenario": "ci", "case_id": "c"}
    archive = CODEC.parse(payload)
    assert archive.to_normalized_dict()["schema_version"] == SCHEMA_VERSION
