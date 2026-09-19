"""Request contract 属性测试。

覆盖 Properties 14, 15。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.contracts.common import (  # noqa: E402
    STATUS_ERROR_CODES,
    PublicError,
    error_code_for_status,
    is_valid_request_id,
    new_request_id,
)


# ---------- Property 14: Request ID 归一化且端到端一致 ----------


@given(st.text(max_size=80))
@settings(max_examples=40)
def test_property_14_generated_ids_always_valid(_noise):
    rid = new_request_id()
    assert is_valid_request_id(rid)


@given(st.text(max_size=80))
@settings(max_examples=40)
def test_property_14_invalid_ids_never_pass_filter(value):
    """过滤器确定性：合法 ID 恰为 pattern 全匹配的字符串。"""
    if is_valid_request_id(value):
        assert 16 <= len(value) <= 64
        assert all(c.isalnum() or c in "._-" for c in value)


def test_property_14_status_to_error_code_is_stable():
    for status, code in STATUS_ERROR_CODES.items():
        assert error_code_for_status(status) == code
    for status in (418, 419, 599):
        assert error_code_for_status(status) in {
            "internal_error",
            "invalid_request",
        }


# ---------- Property 15: Validation Error 集合完整 ----------


@given(st.text(min_size=0, max_size=30))
@settings(max_examples=20)
def test_property_15_error_envelope_never_leaks_internals(message):
    err = PublicError(
        code="validation_failed",
        message=message,
        request_id=new_request_id(),
        retriable=False,
        field_errors=[],
    )
    dumped = json.loads(err.model_dump_json())
    assert set(dumped) == {"code", "message", "request_id", "retriable", "field_errors"}
    assert is_valid_request_id(dumped["request_id"])
    for forbidden in ("stack", "traceback", "file", "path", "exception"):
        assert forbidden not in dumped
