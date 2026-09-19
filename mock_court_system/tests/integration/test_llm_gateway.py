"""LLM gateway contract tests (Task 5.4 / Requirements 9.1–9.12).

覆盖：purpose→tier/token 预算、LLMCallContext 关联字段、缓存身份全等、
同 Operation 重试回放、绝对 deadline、空白不伪成功、无 raw prompt。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.llm_client import (  # noqa: E402
    LLMCallContext,
    LLMClient,
    LLMDeadlineExceeded,
    is_degraded_json,
)


def _client(tmp_path, **kw) -> LLMClient:
    llm = LLMClient(cache_path=str(tmp_path / "llm_cache.sqlite3"), **kw)
    llm.enable_mock()
    return llm


# ---------- Req 9.1–9.4: purpose → tier / token 预算 ----------


def test_clerk_extract_score_use_fast_tier_budget(tmp_path):
    llm = _client(tmp_path)
    assert llm.max_tokens_for("clerk") == 512
    assert llm.max_tokens_for("extract") == 512
    assert llm.max_tokens_for("score") == 512
    # judgment 走 strong 全窗口，不做应用层截短
    assert llm.max_tokens_for("judgment") == llm.max_tokens
    assert llm.model_for_tier("fast") == llm.fast_model
    assert llm.model_for_tier("strong") == llm.model


def test_configured_fast_max_tokens_respected(tmp_path):
    llm = _client(tmp_path, fast_max_tokens=256)
    assert llm.max_tokens_for("clerk") == 256
    assert llm.max_tokens_for("judgment") == llm.max_tokens


# ---------- Req 9.7: 调用记录含关联身份且无 raw prompt ----------


def test_call_record_carries_correlation_identities(tmp_path):
    llm = _client(tmp_path)
    ctx = LLMCallContext(
        purpose="clerk",
        tier="fast",
        operation_id="op_9",
        request_id="req_9",
        session_id="sess_9",
    )
    llm.chat_json(
        [{"role": "user", "content": "开庭准备 发言人 原告 到庭确认"}],
        purpose="clerk",
        context=ctx,
    )
    rec = llm.get_metrics()[-1]
    assert rec.purpose == "clerk"
    assert rec.operation_id == "op_9"
    assert rec.request_id == "req_9"
    assert rec.configuration_identity and rec.configuration_identity.startswith("llmcfg_")
    assert rec.prompt_version
    assert rec.tier == "fast"
    assert rec.model
    # 记录不得携带 raw prompt / 消息内容
    for value in vars(rec).values():
        assert "到庭" not in str(value)


# ---------- Req 9.9–9.10: 缓存身份全等才命中 ----------


def test_cache_identity_requires_all_fields(tmp_path):
    llm = _client(tmp_path)
    messages = [{"role": "user", "content": "开庭准备 发言人 原告 到庭确认"}]
    llm.chat_json(messages, purpose="clerk", temperature=0.0)
    calls = len(llm.get_metrics())

    # 同 purpose/model/config/prompt-version/输入 → 命中
    hit = llm.chat_json(messages, purpose="clerk", temperature=0.0)
    assert llm.get_metrics()[-1].cached is True

    # prompt_version 不同 → miss
    other = LLMCallContext(purpose="clerk", prompt_version="clerk-analysis-v999")
    llm.chat_json(messages, purpose="clerk", temperature=0.0, context=other)
    assert llm.get_metrics()[-1].cached is False

    # configuration identity 不同 → miss
    cfg_other = LLMCallContext(purpose="clerk", configuration_identity="llmcfg_other")
    llm.chat_json(messages, purpose="clerk", temperature=0.0, context=cfg_other)
    assert llm.get_metrics()[-1].cached is False

    # 输入不同 → miss
    llm.chat_json(
        [{"role": "user", "content": "开庭准备 发言人 被告 不同意回避"}],
        purpose="clerk",
        temperature=0.0,
    )
    assert llm.get_metrics()[-1].cached is False
    assert len(llm.get_metrics()) == calls + 4


# ---------- Req 9.11: 同 Operation 已提交结果 → 回放 ----------


def test_same_operation_replays_committed_without_provider_call(tmp_path):
    llm = _client(tmp_path)
    ctx = LLMCallContext(purpose="chat", operation_id="op_replay")
    first = llm.chat_json(
        [{"role": "user", "content": "提取诉讼请求：原告要求被告还款"}],
        context=ctx,
    )
    assert not is_degraded_json(first)
    n = len(llm.get_metrics())

    second = llm.chat_json(
        [{"role": "user", "content": "提取诉讼请求：原告要求被告还款"}],
        context=ctx,
    )
    assert second == first
    rec = llm.get_metrics()[-1]
    assert rec.replayed is True
    assert len(llm.get_metrics()) == n + 1  # 只记回放记录，未再发起请求


# ---------- Req 9.5/9.6: deadline 与空白 ----------


def test_late_response_is_degraded_not_committed(tmp_path):
    llm = _client(tmp_path)
    ctx = LLMCallContext(
        purpose="json",
        operation_id="op_late",
        deadline=time.monotonic() - 1,  # 已过期
    )
    out = llm.chat_json(
        [{"role": "user", "content": "提取诉讼请求：原告要求还款"}],
        context=ctx,
    )
    assert is_degraded_json(out)
    assert out["reason"] == "late_response"
    assert llm.get_metrics()[-1].degraded is True
    # 不进入 committed：同 operation 再调可正常执行
    ctx2 = LLMCallContext(purpose="json", operation_id="op_late")
    ok = llm.chat_json(
        [{"role": "user", "content": "提取诉讼请求：原告要求还款"}],
        context=ctx2,
    )
    assert not is_degraded_json(ok)


def test_chat_completion_past_deadline_raises(tmp_path):
    llm = _client(tmp_path)
    ctx = LLMCallContext(purpose="chat", deadline=time.monotonic() - 1)
    with pytest.raises(LLMDeadlineExceeded):
        llm.chat_completion([{"role": "user", "content": "hi"}], context=ctx)
    assert llm.get_metrics()[-1].degraded is True


def test_whitespace_response_marks_degraded(tmp_path):
    llm = _client(tmp_path)
    llm.chat_model = None

    class _BlankApi:
        @staticmethod
        def _chat_with_api(messages, temperature=None):
            return "   "

    llm._chat_with_api = _BlankApi._chat_with_api  # type: ignore[method-assign]
    llm.chat_completion([{"role": "user", "content": "hi"}])
    assert llm.get_metrics()[-1].degraded is True


# ---------- prompt registry ----------


def test_prompt_registry_versions():
    from core.prompt_registry import prompt_version, register_prompt

    assert prompt_version("clerk") == "clerk-analysis-v2"
    assert prompt_version("judgment") == "judgment-v1"
    assert prompt_version("nonexistent").startswith("unversioned:")
    register_prompt("custom", "v7")
    assert prompt_version("custom") == "v7"
