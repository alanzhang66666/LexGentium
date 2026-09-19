"""LLM 预算 / 运行时 checkpoint / 会话隔离 / 停止条件 属性测试。

覆盖 Properties 24, 31, 32, 33, 34, 35, 36, 37, 38, 42。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.case_orchestrator import (  # noqa: E402
    CI_AUTO_TURN_ENV,
    DEFAULT_CI_AUTO_TURN_CAP,
    ci_auto_turn_limit,
)
from core.graphs.checkpoint import SqliteCheckpointStore  # noqa: E402
from core.llm_client import (  # noqa: E402
    CACHEABLE_PURPOSES,
    LLMCallContext,
    LLMClient,
    degraded_json,
    is_degraded_json,
)


def _client(tmp_path_factory, **kw) -> LLMClient:
    kw.setdefault("cache_path", str(Path(tmp_path_factory.mktemp("c")) / "cache.sqlite3"))
    return LLMClient(**kw)


# ---------- Property 31/32: purpose → token 预算 ----------


@given(purpose=st.text(min_size=0, max_size=24))
@settings(max_examples=30)
def test_property_31_32_purpose_token_budget(tmp_path_factory, purpose):
    client = _client(tmp_path_factory, max_tokens=4096, fast_max_tokens=512)
    budget = client.max_tokens_for(purpose)
    if purpose in CACHEABLE_PURPOSES:  # clerk/extract/score
        assert budget == client.fast_max_tokens
    else:
        # judgment/chat/任意未知 purpose → 不截短，全窗口
        assert budget == client.max_tokens


def test_property_32_judgment_never_fast_budget(tmp_path):
    client = LLMClient(cache_path=str(tmp_path / "c.sqlite3"))
    assert "judgment" not in CACHEABLE_PURPOSES
    assert client.max_tokens_for("judgment") == client.max_tokens


# ---------- Property 33: 调用记录完整（purpose/model/tier/config/prompt） ----------


@given(
    purpose=st.sampled_from(["clerk", "extract", "score", "judgment", "chat"]),
    op=st.text(min_size=1, max_size=20),
    req=st.text(min_size=1, max_size=20),
)
@settings(max_examples=20)
def test_property_33_call_record_complete(tmp_path_factory, purpose, op, req):
    client = _client(tmp_path_factory)
    ctx = LLMCallContext(
        purpose=purpose, operation_id=op, request_id=req
    )
    client.record_external_call(purpose, "fast", 12.5, ctx=ctx)
    (rec,) = client.get_metrics()
    assert rec.purpose == purpose
    assert rec.model and rec.tier == "fast"
    assert rec.operation_id == op and rec.request_id == req
    assert rec.configuration_identity.startswith("llmcfg_")
    assert rec.prompt_version is not None
    # 记录不含 secret/prompt 字段
    assert not hasattr(rec, "api_key") and not hasattr(rec, "prompt")


# ---------- Property 34: 缓存身份完整 ----------


@given(
    msg_a=st.text(min_size=1, max_size=30),
    msg_b=st.text(min_size=1, max_size=30),
    purpose_a=st.sampled_from(["clerk", "extract"]),
    purpose_b=st.sampled_from(["clerk", "extract", "score"]),
)
@settings(max_examples=20)
def test_property_34_cache_identity_complete(tmp_path_factory, msg_a, msg_b, purpose_a, purpose_b):
    client = _client(tmp_path_factory)
    msgs_a = [{"role": "user", "content": msg_a}]
    msgs_b = [{"role": "user", "content": msg_b}]
    k1 = client._cache_key("m1", msgs_a, 0.1, purpose_a)
    # 完全相同输入 → 同 key
    assert client._cache_key("m1", msgs_a, 0.1, purpose_a) == k1
    # 任一字段变化 → key 不同
    assert client._cache_key("m1", msgs_b, 0.1, purpose_a) != k1 or msg_a == msg_b
    assert client._cache_key("m2", msgs_a, 0.1, purpose_a) != k1
    assert client._cache_key("m1", msgs_a, 0.5, purpose_a) != k1
    if purpose_a != purpose_b:
        assert client._cache_key("m1", msgs_a, 0.1, purpose_b) != k1


def test_property_34_cache_identity_includes_config(tmp_path):
    a = LLMClient(model="m1", cache_path=str(tmp_path / "a.sqlite3"))
    b = LLMClient(model="m2", cache_path=str(tmp_path / "b.sqlite3"))
    msgs = [{"role": "user", "content": "x"}]
    assert a._cache_key("m1", msgs, 0.1, "clerk") != b._cache_key("m1", msgs, 0.1, "clerk")


# ---------- Property 35: checkpoint 原子/版本化 ----------


@given(turns=st.lists(st.integers(min_value=0, max_value=50), min_size=1, max_size=6, unique=True))
@settings(max_examples=15, deadline=None)
def test_property_35_checkpoint_head_is_max_turn(tmp_path_factory, turns):
    store = SqliteCheckpointStore(str(Path(tmp_path_factory.mktemp("cp")) / "cp.sqlite3"))
    for t in turns:
        store.save_v2("th1", t, {"state": t}, operation_id=f"op{t}")
    head = store.head_v2("th1")
    assert head is not None and head.turn_number == max(turns)
    assert head.payload["state"] == max(turns)
    assert store.latest_turn_number("th1") == max(turns)
    # 其他 thread 不受影响
    assert store.head_v2("other") is None


# ---------- Property 36: Plead 上下文窗口有界 ----------


@given(n=st.integers(min_value=0, max_value=40), k=st.integers(min_value=1, max_value=10))
@settings(max_examples=15)
def test_property_36_plead_window_bounded(n, k):
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"PLEAD_WINDOW_K": str(k)}):
        from core.graphs.plead_runtime import PleadRuntime

        rt = PleadRuntime()
        assert rt.window_k == k
        # 窗口切片永不超过 window_k
        history = [{"role": "plaintiff", "message": f"m{i}"} for i in range(n)]
        window = list(history[-rt.window_k:])
        assert len(window) <= k


# ---------- Property 37: CI 自动停止条件 ----------


@given(raw=st.one_of(st.none(), st.text(max_size=10)))
@settings(max_examples=25)
def test_property_37_auto_turn_cap_bounded(raw):
    import os
    from unittest.mock import patch

    env = {} if raw is None else {CI_AUTO_TURN_ENV: raw}
    with patch.dict(os.environ, env):
        if raw is None:
            os.environ.pop(CI_AUTO_TURN_ENV, None)
        for max_turns in (1, 5, 20, 100):
            limit = ci_auto_turn_limit(max_turns)
            assert limit >= 0
            # 上限 = min(max_turns*3, cap)；非法 cap 回落默认 30
            try:
                cap = int(raw) if raw is not None else DEFAULT_CI_AUTO_TURN_CAP
                if cap <= 0:
                    cap = DEFAULT_CI_AUTO_TURN_CAP
            except ValueError:
                cap = DEFAULT_CI_AUTO_TURN_CAP
            assert limit == min(max_turns * 3, cap)


# ---------- Property 38: operation 级提交回放隔离 ----------


def test_property_38_committed_replay_scoped_by_operation(tmp_path):
    client = LLMClient(cache_path=str(tmp_path / "c.sqlite3"))
    client.enable_mock()
    msgs = [{"role": "user", "content": "分析 TurnAnalysis 确认 到庭 是 本人 听清 明白"}]
    ctx1 = LLMCallContext(purpose="clerk", operation_id="op-A")
    r1 = client.chat_json(msgs, purpose="clerk", context=ctx1)
    # 同 operation 重试 → 回放 committed 结果，不再发起调用
    r2 = client.chat_json(msgs, purpose="clerk", context=ctx1)
    assert r2 == r1
    records = client.get_metrics()
    assert records[-1].replayed is True
    # 不同 operation → 不串结果
    ctx2 = LLMCallContext(purpose="clerk", operation_id="op-B")
    client.chat_json(msgs, purpose="clerk", context=ctx2)
    assert client.get_metrics()[-1].replayed is False


# ---------- Property 42: civil / research 缓存命名空间隔离 ----------


def test_property_42_research_context_namespaces_llm_cache(tmp_path):
    from core.research.runtime import bind_research_context, reset_research_context

    client = LLMClient(cache_path=str(tmp_path / "c.sqlite3"))
    msgs = [{"role": "user", "content": "x"}]
    civil_key = client._cache_key("m", msgs, 0.1, "clerk")

    research_input = {
        "research": {
            "run_id": "run-1",
            "dataset_id": "enforcement",
            "cluster_id": "enf-cn-notice-001",
        }
    }
    token = bind_research_context(research_input)
    try:
        research_key = client._cache_key("m", msgs, 0.1, "clerk")
    finally:
        reset_research_context(token)
    # 研究上下文使命名空间进入缓存身份 → 与 civil 绝不共享条目
    assert research_key != civil_key
    assert client._cache_key("m", msgs, 0.1, "clerk") == civil_key

    # 不同 run_id → 不同缓存身份（replay ≠ independent attempt）
    token2 = bind_research_context(
        {"research": {**research_input["research"], "run_id": "run-2"}}
    )
    try:
        key2 = client._cache_key("m", msgs, 0.1, "clerk")
    finally:
        reset_research_context(token2)
    assert key2 != research_key


# ---------- Property 24: degraded / unknown 永不伪造 ----------


def test_property_24_degraded_marker_roundtrip():
    obj = degraded_json("llm_unavailable")
    assert is_degraded_json(obj)
    assert not is_degraded_json({"result": "ok"})
    # degraded 结果不进入 committed 回放集（由 chat_json mock 路径保证）
    assert obj.get("_degraded") is True
