"""Release 性能统计测试（Task 12.1）。"""
from __future__ import annotations

import math

import pytest

from core.release.statistics import (
    EnvironmentIdentity,
    PerformanceSample,
    nearest_rank,
    summarize_samples,
)


def _env(**overrides) -> EnvironmentIdentity:
    base = dict(
        cpu="test-cpu",
        os="TestOS-1",
        python_version="3.10.0",
        node_version="22.x",
        lock_digests={"requirements.lock": "a", "package-lock.json": "b"},
        model_identity="m1",
        fixture_identity="f1",
        network_profile="n1",
    )
    base.update(overrides)
    return EnvironmentIdentity(**base)


def _sample(duration_ms: float, env: EnvironmentIdentity, **kw) -> PerformanceSample:
    return PerformanceSample(
        start_ns=0,
        end_ns=int(duration_ms * 1_000_000),
        result=kw.pop("result", "success"),
        environment_digest=env.digest(),
        **kw,
    )


def test_nearest_rank_p95_definition():
    values = sorted(float(i) for i in range(1, 101))  # 1..100
    assert nearest_rank(values, 0.95) == 95.0
    assert nearest_rank(values, 0.50) == 50.0
    assert nearest_rank([5.0], 0.95) == 5.0
    assert nearest_rank([1.0, 2.0, 3.0], 0.95) == 3.0
    # ceil(0.95*4)-1 = 3 -> 最大元素
    assert nearest_rank([10.0, 20.0, 30.0, 40.0], 0.95) == 40.0
    with pytest.raises(ValueError):
        nearest_rank([], 0.95)


def test_summary_passes_with_enough_matching_samples():
    env = _env()
    samples = [_sample(float(i), env) for i in range(1, 301)]
    summary = summarize_samples(
        samples, required_samples=300, baseline=_env(), environment=env
    )
    assert summary.verdict == "pass"
    assert summary.valid_count == 300
    assert summary.p95_ms == pytest.approx(285.0)
    assert summary.max_ms == 300.0
    assert summary.error_rate == 0.0


def test_insufficient_samples_is_invalid_not_passed():
    env = _env()
    samples = [_sample(1.0, env) for _ in range(10)]
    summary = summarize_samples(
        samples, required_samples=300, baseline=None, environment=env
    )
    assert summary.verdict == "invalid"
    assert any(r.startswith("insufficient_samples") for r in summary.invalid_reasons)


def test_baseline_environment_mismatch_is_invalid():
    env = _env()
    baseline = _env(cpu="different-cpu")
    samples = [_sample(1.0, env) for _ in range(300)]
    summary = summarize_samples(
        samples, required_samples=300, baseline=baseline, environment=env
    )
    assert summary.verdict == "invalid"
    assert "environment_baseline_mismatch" in summary.invalid_reasons


def test_excluded_samples_have_reasons_and_do_not_silently_drop():
    env = _env()
    good = [_sample(1.0, env) for _ in range(300)]
    bad = PerformanceSample(
        start_ns=0, end_ns=0, result="failed", exclusion_reason="warmup"
    )
    summary = summarize_samples(
        good + [bad], required_samples=300, baseline=None, environment=env
    )
    assert summary.verdict == "pass"
    assert summary.raw_count == 301
    assert summary.valid_count == 300
    assert summary.excluded == [{"reason": "warmup", "result": "failed"}]


def test_external_llm_samples_require_provider_latency():
    env = _env()
    with_provider = [
        _sample(10.0, env, provider_duration_ms=6.0) for _ in range(30)
    ]
    ok = summarize_samples(
        with_provider,
        required_samples=30,
        baseline=None,
        environment=env,
        external_llm=True,
    )
    assert ok.verdict == "pass"

    missing = [_sample(10.0, env) for _ in range(30)]
    bad = summarize_samples(
        missing,
        required_samples=30,
        baseline=None,
        environment=env,
        external_llm=True,
    )
    assert bad.verdict == "invalid"
    assert "missing_provider_latency" in bad.invalid_reasons


def test_sample_environment_mismatch_is_invalid():
    env = _env()
    foreign = _env(network_profile="other")
    samples = [_sample(1.0, env) for _ in range(30)] + [_sample(1.0, foreign)]
    summary = summarize_samples(
        samples, required_samples=30, baseline=None, environment=env
    )
    assert summary.verdict == "invalid"
    assert "sample_environment_mismatch" in summary.invalid_reasons


def test_error_rate_and_monotonic_guard():
    env = _env()
    ok = [_sample(1.0, env) for _ in range(298)]
    failed = [_sample(2.0, env, result="failed") for _ in range(2)]
    reversed_clock = PerformanceSample(start_ns=10, end_ns=5, result="success")
    summary = summarize_samples(
        ok + failed + [reversed_clock],
        required_samples=300,
        baseline=None,
        environment=env,
    )
    assert summary.verdict == "pass"
    assert summary.valid_count == 300
    assert summary.error_rate == pytest.approx(2 / 300)
    assert summary.excluded == [
        {"reason": "non_monotonic_clock", "result": "success"}
    ]
