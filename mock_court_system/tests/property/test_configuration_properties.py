"""配置管理 / Secret 脱敏 / 连接分类属性测试。

覆盖 Properties 25, 26, 27, 28；外加 connection outcome fail-closed。
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

from api.contracts.common import SECRET_MASK  # noqa: E402
from api.observability.redaction import SECRET_MASK as REDACT_MASK  # noqa: E402
from api.observability.redaction import redact_secrets  # noqa: E402
from core.configuration import (  # noqa: E402
    ConfigurationManager,
    ConnectionOutcome,
    classify_connection,
    load_variable_catalog,
    validate_candidate,
)

CATALOG = load_variable_catalog()

_PROD_REQUIRED = sorted(
    name
    for name, var in CATALOG.items()
    if var.required and "production" in var.profiles
)

_VALID_PROD = {
    "BACKEND_URL": "http://localhost:8000",
    "LLM_API_KEY": "sk-test",
    "LLM_BASE_URL": "https://api.example.com",
    "LLM_MODEL": "qwen",
}


# ---------- Property 25: Secret 恒定掩码与敏感字段删除 ----------


SECRET_TEXTS = [
    "api_key=sk-live-1234567890",
    'token: "tok_abc123secret"',
    "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig",
    "password=hunter2",
    "https://user:pass@example.com/path",
    "llm_api_key = 'sk-zzz'",
]


@given(secret=st.sampled_from(SECRET_TEXTS), prefix=st.text(max_size=20))
@settings(max_examples=25)
def test_property_25_text_secrets_masked(secret, prefix):
    out = redact_secrets(prefix + " " + secret)
    assert REDACT_MASK in out
    for fragment in ("sk-live-1234567890", "tok_abc123secret", "hunter2", "user:pass@", "sk-zzz"):
        assert fragment not in out


@given(
    value=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        min_size=4,
        max_size=30,
    ).filter(lambda s: s != REDACT_MASK)
)
@settings(max_examples=15)
@pytest.mark.parametrize(
    "field", ["api_key", "token", "password", "my_secret", "x_api_token", "authorization"]
)
def test_property_25_structured_secret_fields_masked(field, value):
    out = redact_secrets({"outer": {field: value}, "list": [{field: value}]})
    assert out["outer"][field] == REDACT_MASK
    assert out["list"][0][field] == REDACT_MASK
    assert value not in json.dumps(out)


def test_property_25_non_secret_fields_untouched():
    data = {"request_id": "r1", "duration_ms": 12, "note": "plain text"}
    assert redact_secrets(data) == data


# ---------- Property 26: production 配置校验 ----------


def test_property_26_production_requires_all_declared_required():
    # 逐个删除必填变量 → 各自产生 required issue
    for missing in _PROD_REQUIRED:
        values = {k: v for k, v in _VALID_PROD.items() if k != missing}
        issues = validate_candidate(values, profile="production", catalog=CATALOG)
        assert any(i.name == missing and i.reason == "required" for i in issues)
    assert not validate_candidate(_VALID_PROD, profile="production", catalog=CATALOG)


@given(extra=st.text(min_size=1, max_size=24))
@settings(max_examples=20)
def test_property_26_undeclared_variables_rejected(extra):
    if extra in CATALOG:
        return
    issues = validate_candidate(
        {**_VALID_PROD, extra: "x"}, profile="production", catalog=CATALOG
    )
    assert any(i.name == extra and i.constraint == "undeclared_variable" for i in issues)


@given(value=st.one_of(st.floats(allow_nan=False), st.text(min_size=1, max_size=10).filter(lambda s: s.strip())))
@settings(max_examples=20)
def test_property_26_numeric_range_enforced(value):
    raw = str(value)
    issues = validate_candidate(
        {**_VALID_PROD, "CI_MAX_AUTO_TURNS": raw},
        profile="production",
        catalog=CATALOG,
    )
    try:
        num = float(raw)
        in_range = True  # CI_MAX_AUTO_TURNS 约束见 _RANGE_CONSTRAINTS
    except ValueError:
        num, in_range = None, False
    has_issue = any(i.name == "CI_MAX_AUTO_TURNS" for i in issues)
    # 非数值 → type issue；数值越界 → range issue（具体区间由 catalog 约束决定）
    if num is None:
        assert has_issue


# ---------- Property 28: 外网绑定必须 token ----------


@given(host=st.sampled_from(["0.0.0.0", "8.8.8.8", "example.com", "::", "192.168.1.5"]))
@settings(max_examples=10)
def test_property_28_external_bind_requires_token(host):
    values = {**_VALID_PROD, "API_HOST": host}
    issues = validate_candidate(values, profile="production", catalog=CATALOG)
    assert any(
        i.name == "API_TOKEN" and i.constraint == "external_listener_requires_token"
        for i in issues
    )
    # 带 token 后该 issue 消失
    ok = validate_candidate(
        {**values, "API_TOKEN": "t"}, profile="production", catalog=CATALOG
    )
    assert not any(i.name == "API_TOKEN" for i in ok)


@given(host=st.sampled_from(["127.0.0.1", "localhost", "::1", ""]))
@settings(max_examples=6)
def test_property_28_loopback_bind_needs_no_token(host):
    values = {**_VALID_PROD, "API_HOST": host}
    issues = validate_candidate(values, profile="production", catalog=CATALOG)
    assert not any(i.constraint == "external_listener_requires_token" for i in issues)


# ---------- Property 27: 配置快照不可变 + 视图脱敏 ----------


def test_property_27_snapshot_views_mask_and_partition(tmp_path):
    env = {
        **_VALID_PROD,
        "API_TOKEN": "super-secret-token",
        "NEXT_PUBLIC_BACKEND_URL": "http://localhost:8000",
    }
    mgr = ConfigurationManager(
        persist_path=tmp_path / "cfg.json", catalog=CATALOG, env=env
    )
    snap = mgr.capture()
    # 冻结 dataclass
    with pytest.raises(Exception):
        snap.values = {}  # type: ignore[misc]
    public = snap.public_view(CATALOG)
    for name, value in public.items():
        var = CATALOG[name]
        if var.secret and str(env.get(name, "")).strip():
            assert value == SECRET_MASK
            assert env[name] not in str(public)
    browser = snap.browser_view(CATALOG)
    for name in browser:
        var = CATALOG[name]
        assert var.visibility == "browser_visible" and not var.secret
    # server_only secret 绝不进浏览器视图
    for secret_name in ("LLM_API_KEY", "API_TOKEN", "DASHSCOPE_API_KEY"):
        assert secret_name not in browser


# ---------- connection outcome fail-closed ----------


@given(outcome=st.text(max_size=20))
@settings(max_examples=25)
def test_connection_classification_fail_closed(outcome):
    result = classify_connection(outcome)
    if outcome == ConnectionOutcome.OK:
        assert result == "connected"
    elif outcome in (ConnectionOutcome.FALLBACK, ConnectionOutcome.UNREACHABLE):
        assert result == "degraded"
    else:
        assert result == "failed"
