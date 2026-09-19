"""性能统计与 fail-closed 证据属性测试。

覆盖 Properties 52, 53。
"""
from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.release.statistics import (  # noqa: E402
    EnvironmentIdentity,
    PerformanceSample,
    nearest_rank,
    summarize_samples,
)

ENV = EnvironmentIdentity(cpu="c", os="o", python_version="p", node_version="n", lock_digests={})


# ---------- Property 52: nearest-rank p95 正确性 ----------


@given(st.lists(st.floats(min_value=0.0, max_value=10000.0, allow_nan=False), min_size=1, max_size=60))
@settings(max_examples=30)
def test_property_52_nearest_rank_p95_correct(values):
    ordered = sorted(values)
    p95 = nearest_rank(ordered, 0.95)
    # nearest-rank：至少 95% 的样本 <= p95，且 p95 是样本中的值
    assert p95 in ordered
    assert sum(1 for v in ordered if v <= p95) / len(ordered) >= 0.95


# ---------- Property 53: 性能证据 fail-closed ----------


def _samples(n: int, ms: float = 1.0):
    return [
        PerformanceSample(start_ns=i * 10, end_ns=i * 10 + int(ms * 1e6), result="success")
        for i in range(n)
    ]


@given(n_valid=st.integers(min_value=0, max_value=10), required=st.integers(min_value=1, max_value=30))
@settings(max_examples=25)
def test_property_53_insufficient_samples_invalid(n_valid, required):
    samples = _samples(n_valid)
    summary = summarize_samples(
        samples, required_samples=required, baseline=ENV, environment=ENV
    )
    if n_valid < required:
        assert summary.verdict == "invalid"
        assert any("insufficient_samples" in r for r in summary.invalid_reasons)
    else:
        assert summary.verdict == "pass"
        assert summary.p95_ms is not None


def test_property_53_invalid_conditions():
    # 环境不匹配 → invalid
    other = EnvironmentIdentity(cpu="x", os="o", python_version="p", node_version="n", lock_digests={})
    out = summarize_samples(_samples(5), required_samples=1, baseline=ENV, environment=other)
    assert out.verdict == "invalid"
    assert "environment_baseline_mismatch" in out.invalid_reasons

    # 样本环境 digest 不一致 → invalid
    mismatched = PerformanceSample(
        start_ns=0, end_ns=10, result="success", environment_digest="other"
    )
    out = summarize_samples(
        [mismatched], required_samples=1, baseline=ENV, environment=ENV
    )
    assert out.verdict == "invalid"

    # 外部 LLM 计时缺失 → invalid
    out = summarize_samples(
        _samples(3), required_samples=1, baseline=ENV, environment=ENV,
        external_llm=True,
    )
    assert out.verdict == "invalid"
    assert "missing_provider_latency" in out.invalid_reasons

    # 非单调时钟样本被排除且不计入有效样本
    bad = PerformanceSample(start_ns=100, end_ns=50, result="success")
    out = summarize_samples([bad], required_samples=1, baseline=ENV, environment=ENV)
    assert out.verdict == "invalid"
    assert out.valid_count == 0
    assert out.excluded and out.excluded[0]["reason"] == "non_monotonic_clock"
