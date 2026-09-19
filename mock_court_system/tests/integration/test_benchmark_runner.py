"""benchmark_release runner 测试（Task 12.2）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import benchmark_release as bench  # noqa: E402
from core.release.statistics import current_environment_identity  # noqa: E402


def test_collect_samples_respects_deadline():
    def slow(_i):
        import time

        time.sleep(0.01)
        return {"result": "success"}

    samples = bench.collect_samples(slow, count=10, max_seconds=0.03)
    assert len(samples) == 10
    assert any(s.exclusion_reason == "deadline" for s in samples)


def test_collect_records_exceptions_as_excluded():
    def boom(_i):
        raise RuntimeError("x")

    samples = bench.collect_samples(boom, count=2, max_seconds=5)
    assert all(s.result == "failed" for s in samples)
    assert all(s.exclusion_reason.startswith("exception:") for s in samples)


def test_run_suite_mock_produces_pass_evidence(tmp_path):
    env = current_environment_identity(fixture_identity="non_llm")
    summary, payload = bench.run_suite(
        "non_llm",
        samples=300,
        max_seconds=60,
        work_fn=bench.mock_work_fn,
        baseline=env,  # 同环境 → 匹配
        environment=env,
        command="benchmark_release.py --suite non_llm --mock",
    )
    assert summary.verdict == "pass"
    assert summary.valid_count == 300
    assert payload["result"] == "pass"
    assert payload["sample_count"] == 300
    assert len(payload["commit_id"]) == 40
    assert payload["check_id"] == "benchmark_non_llm"


def test_insufficient_samples_invalid():
    env = current_environment_identity(fixture_identity="runtime")
    summary, payload = bench.run_suite(
        "runtime",
        samples=10,  # < required 30
        max_seconds=30,
        work_fn=bench.mock_work_fn,
        baseline=None,
        environment=env,
        command="x",
    )
    assert summary.verdict == "invalid"
    assert any("insufficient_samples" in r for r in summary.invalid_reasons)
    assert payload["result"] == "invalid"
    assert payload["exit_code"] == bench.EXIT_INVALID


def test_baseline_mismatch_is_invalid_not_pass():
    env = current_environment_identity(fixture_identity="non_llm")
    other = current_environment_identity(fixture_identity="different_fixture")
    summary, _ = bench.run_suite(
        "non_llm",
        samples=300,
        max_seconds=60,
        work_fn=bench.mock_work_fn,
        baseline=other,
        environment=env,
        command="x",
    )
    assert summary.verdict == "invalid"
    assert "environment_baseline_mismatch" in summary.invalid_reasons


def test_llm_suite_requires_provider_latency():
    env = current_environment_identity(fixture_identity="llm")

    def no_provider(_i):
        return {"result": "success"}  # 缺 provider_duration_ms

    summary, _ = bench.run_suite(
        "llm",
        samples=30,
        max_seconds=30,
        work_fn=no_provider,
        baseline=None,
        environment=env,
        command="x",
    )
    assert summary.verdict == "invalid"
    assert "missing_provider_latency" in summary.invalid_reasons


def test_llm_suite_separates_provider_duration():
    env = current_environment_identity(fixture_identity="llm")

    def with_provider(_i):
        import time

        time.sleep(0.001)
        return {"result": "success", "provider_duration_ms": 0.5}

    summary, _ = bench.run_suite(
        "llm",
        samples=30,
        max_seconds=30,
        work_fn=with_provider,
        baseline=None,
        environment=env,
        command="x",
    )
    assert summary.verdict == "pass"


def test_main_writes_evidence_file(tmp_path):
    out = tmp_path / "evidence"
    code = bench.main(
        [
            "--suite",
            "non_llm",
            "--mock",
            "--samples",
            "300",
            "--max-seconds",
            "60",
            "--output",
            str(out),
        ]
    )
    assert code == bench.EXIT_PASS
    evidence = json.loads((out / "benchmark_non_llm.json").read_text())
    assert evidence["result"] == "pass"
    assert evidence["sample_count"] == 300


def test_main_is_bounded_and_not_watch(tmp_path):
    import subprocess

    # --help 是有限命令
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "benchmark_release.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "--suite" in result.stdout
