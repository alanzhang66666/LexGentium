"""ConfigurationManager / 生产配置校验测试（Task 3.1）。"""
from __future__ import annotations

import json
import os
import stat
import threading

import pytest

from core.configuration import (
    SECRET_MASK,
    ConfigurationError,
    ConfigurationManager,
    ConfigVariable,
    classify_connection,
    current_profile,
    load_variable_catalog,
    validate_candidate,
)

CATALOG = load_variable_catalog()


def _manager(tmp_path, env=None):
    return ConfigurationManager(
        persist_path=tmp_path / "config.runtime.json", catalog=CATALOG, env=env or {}
    )


def test_profile_parsing():
    assert current_profile({}) == "development"
    assert current_profile({"APP_PROFILE": "production"}) == "production"
    assert current_profile({"APP_PROFILE": "bogus"}) == "development"


def test_production_requires_llm_variables():
    issues = validate_candidate({}, profile="production", catalog=CATALOG)
    names = {i.name for i in issues if i.reason == "required"}
    assert {"LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"} <= names


def test_production_external_host_requires_token():
    values = {
        "LLM_API_KEY": "k",
        "LLM_BASE_URL": "https://x",
        "LLM_MODEL": "m",
        "API_HOST": "0.0.0.0",
    }
    issues = validate_candidate(values, profile="production", catalog=CATALOG)
    assert any(i.name == "API_TOKEN" and i.reason == "required" for i in issues)

    ok = dict(values, API_TOKEN="t")
    assert not [
        i for i in validate_candidate(ok, profile="production", catalog=CATALOG)
        if i.name == "API_TOKEN"
    ]
    # loopback 不需要 token
    local = dict(values, API_HOST="127.0.0.1")
    assert not [
        i for i in validate_candidate(local, profile="production", catalog=CATALOG)
        if i.name == "API_TOKEN"
    ]


def test_range_and_type_validation():
    issues = validate_candidate(
        {"LLM_TIMEOUT": "0", "LLM_FAST_MAX_TOKENS": "abc", "CI_MAX_AUTO_TURNS": "500"},
        profile="development",
        catalog=CATALOG,
    )
    by_name = {i.name: i.reason for i in issues}
    assert by_name["LLM_TIMEOUT"] == "range"
    assert by_name["LLM_FAST_MAX_TOKENS"] == "type"
    assert by_name["CI_MAX_AUTO_TURNS"] == "range"


def test_undeclared_variable_rejected():
    issues = validate_candidate(
        {"NOPE_VAR": "1"}, profile="development", catalog=CATALOG
    )
    assert any(i.name == "NOPE_VAR" and i.reason == "conflict" for i in issues)


def test_flag_format():
    issues = validate_candidate(
        {"LLM_CACHE": "maybe"}, profile="development", catalog=CATALOG
    )
    assert any(i.name == "LLM_CACHE" and i.reason == "format" for i in issues)


def test_connection_classification_never_connected_except_ok():
    assert classify_connection("ok") == "connected"
    assert classify_connection("fallback") == "degraded"
    assert classify_connection("unreachable") == "degraded"
    for bad in ("empty", "auth_failure", "timeout", "garbage", ""):
        assert classify_connection(bad) == "failed"


def test_secret_masking(tmp_path):
    mgr = _manager(tmp_path, env={"LLM_API_KEY": "sk-real", "LLM_MODEL": "m"})
    snap = mgr.capture()
    view = snap.public_view(CATALOG)
    assert view["LLM_API_KEY"] == SECRET_MASK
    assert "sk-real" not in json.dumps(view)
    # browser view 不含 server_only 变量
    assert "LLM_API_KEY" not in snap.browser_view(CATALOG)
    assert "LLM_MODEL" not in snap.browser_view(CATALOG)


def test_atomic_update_and_identity_change(tmp_path):
    mgr = _manager(tmp_path)
    old = mgr.capture()
    new = mgr.update(
        {"LLM_MODEL": "new-model", "LLM_TIMEOUT": "30"}, profile="development"
    )
    assert new.identity != old.identity
    assert mgr.capture().identity == new.identity
    # 持久化文件已原子替换且含新值
    persisted = json.loads((tmp_path / "config.runtime.json").read_text())
    assert persisted["values"]["LLM_MODEL"] == "new-model"


def test_failed_update_preserves_old_snapshot(tmp_path):
    mgr = _manager(tmp_path, env={"LLM_MODEL": "stable"})
    old = mgr.capture()
    with pytest.raises(ConfigurationError):
        mgr.update({"LLM_TIMEOUT": "99999"}, profile="development")
    assert mgr.capture().identity == old.identity
    assert not (tmp_path / "config.runtime.json").exists()

    with pytest.raises(ConfigurationError):
        mgr.update(
            {"LLM_MODEL": "x"}, profile="development", connection_outcome="auth_failure"
        )
    assert mgr.capture().identity == old.identity


def test_snapshot_isolation_across_operations(tmp_path):
    """新旧并发操作不串配置：旧操作保持捕获时的 snapshot。"""
    mgr = _manager(tmp_path, env={"LLM_MODEL": "v1"})
    captured_by_op_a = mgr.capture()
    mgr.update({"LLM_MODEL": "v2"}, profile="development")
    captured_by_op_b = mgr.capture()
    assert captured_by_op_a.get("LLM_MODEL") == "v1"
    assert captured_by_op_b.get("LLM_MODEL") == "v2"
    assert captured_by_op_a.identity != captured_by_op_b.identity


def test_concurrent_capture_consistent(tmp_path):
    mgr = _manager(tmp_path, env={"LLM_MODEL": "v1"})
    seen = []

    def worker():
        seen.append(mgr.capture().identity)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(seen)) == 1


def test_file_permissions_restricted(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX permission check")
    mgr = _manager(tmp_path)
    mgr.update({"LLM_MODEL": "x"}, profile="development")
    mode = stat.S_IMODE((tmp_path / "config.runtime.json").stat().st_mode)
    assert mode & (stat.S_IRWXG | stat.S_IRWXO) == 0
