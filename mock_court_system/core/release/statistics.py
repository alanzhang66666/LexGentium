"""Release 性能样本、环境身份与 nearest-rank 统计（design.md §15）。

- 计时一律使用 ``time.perf_counter_ns()``（单调时钟）。
- p95 用 nearest-rank：升序列表下标 ``ceil(0.95*n)-1``。
- 外部 LLM 样本分别记录 provider 与 local duration。
- 样本不足或环境身份与 Approved_Baseline 不一致时，结果只能判为
  ``invalid``，不得判为 ``passed``。
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> Optional[str]:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


@dataclass(frozen=True)
class EnvironmentIdentity:
    """Approved_Baseline / Release_Test_Environment 的严格比较身份。"""

    cpu: str
    os: str
    python_version: str
    node_version: str
    lock_digests: Dict[str, str]
    model_identity: str = ""
    fixture_identity: str = ""
    network_profile: str = ""

    def digest(self) -> str:
        canonical = json.dumps(
            {
                "cpu": self.cpu,
                "os": self.os,
                "python_version": self.python_version,
                "node_version": self.node_version,
                "lock_digests": dict(sorted(self.lock_digests.items())),
                "model_identity": self.model_identity,
                "fixture_identity": self.fixture_identity,
                "network_profile": self.network_profile,
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return _sha256_text(canonical)

    def compatible_with(self, other: "EnvironmentIdentity") -> bool:
        return self.digest() == other.digest()


def _node_version() -> str:
    try:
        package = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
        engines = package.get("engines", {})
        return engines.get("node", "")
    except Exception:
        return ""


def current_environment_identity(
    *,
    model_identity: str = "",
    fixture_identity: str = "",
    network_profile: str = "",
    root: Path = PROJECT_ROOT,
) -> EnvironmentIdentity:
    """采集当前 Release_Test_Environment 身份（含 lock digest）。"""
    lock_digests: Dict[str, str] = {}
    for name in ("requirements.lock", "package-lock.json"):
        digest = file_digest(root / name)
        if digest:
            lock_digests[name] = digest
    return EnvironmentIdentity(
        cpu=platform.processor() or platform.machine(),
        os=f"{platform.system()}-{platform.release()}",
        python_version=platform.python_version(),
        node_version=_node_version(),
        lock_digests=lock_digests,
        model_identity=model_identity,
        fixture_identity=fixture_identity,
        network_profile=network_profile,
    )


@dataclass(frozen=True)
class PerformanceSample:
    """一次性能观测；duration 由单调时钟差得出。"""

    start_ns: int
    end_ns: int
    result: str  # success | failed | degraded
    correlation: Dict[str, str] = field(default_factory=dict)
    environment_digest: str = ""
    provider_duration_ms: Optional[float] = None
    exclusion_reason: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        return (self.end_ns - self.start_ns) / 1_000_000

    @property
    def local_duration_ms(self) -> float:
        if self.provider_duration_ms is None:
            return self.duration_ms
        return self.duration_ms - self.provider_duration_ms


def start_sample() -> int:
    """开始一次观测；与 end_ns 配对使用单调时钟。"""
    return time.perf_counter_ns()


def nearest_rank(sorted_values: Sequence[float], percentile: float) -> float:
    """nearest-rank 分位数：升序下标 ``ceil(p*n)-1``。"""
    if not sorted_values:
        raise ValueError("empty sample set")
    index = math.ceil(percentile * len(sorted_values)) - 1
    index = min(max(index, 0), len(sorted_values) - 1)
    return sorted_values[index]


@dataclass
class PerformanceSummary:
    raw_count: int
    valid_count: int
    excluded: List[Dict[str, str]]
    p50_ms: Optional[float]
    p95_ms: Optional[float]
    max_ms: Optional[float]
    error_rate: Optional[float]
    verdict: str  # pass | invalid
    invalid_reasons: List[str]
    test_parameter_digest: str
    environment_digest: str


def summarize_samples(
    samples: Sequence[PerformanceSample],
    *,
    required_samples: int,
    baseline: Optional[EnvironmentIdentity],
    environment: EnvironmentIdentity,
    test_parameters: Optional[Dict[str, Any]] = None,
    external_llm: bool = False,
) -> PerformanceSummary:
    """汇总样本并判定证据有效性（fail-closed）。"""
    invalid_reasons: List[str] = []

    excluded: List[Dict[str, str]] = []
    valid: List[PerformanceSample] = []
    for sample in samples:
        if sample.exclusion_reason:
            excluded.append(
                {"reason": sample.exclusion_reason, "result": sample.result}
            )
            continue
        if sample.end_ns < sample.start_ns:
            excluded.append({"reason": "non_monotonic_clock", "result": sample.result})
            continue
        valid.append(sample)

    if len(valid) < required_samples:
        invalid_reasons.append(
            f"insufficient_samples:{len(valid)}<{required_samples}"
        )

    env_digest = environment.digest()
    if baseline is not None and not environment.compatible_with(baseline):
        invalid_reasons.append("environment_baseline_mismatch")

    for sample in valid:
        if environment_digest_differs(sample, env_digest):
            invalid_reasons.append("sample_environment_mismatch")
            break

    if external_llm:
        if any(s.provider_duration_ms is None for s in valid):
            invalid_reasons.append("missing_provider_latency")

    durations = sorted(s.duration_ms for s in valid)
    errors = sum(1 for s in valid if s.result == "failed")
    error_rate = (errors / len(valid)) if valid else None

    parameter_digest = _sha256_text(
        json.dumps(test_parameters or {}, sort_keys=True, ensure_ascii=False)
    )

    return PerformanceSummary(
        raw_count=len(samples),
        valid_count=len(valid),
        excluded=excluded,
        p50_ms=nearest_rank(durations, 0.50) if durations else None,
        p95_ms=nearest_rank(durations, 0.95) if durations else None,
        max_ms=durations[-1] if durations else None,
        error_rate=error_rate,
        verdict="invalid" if invalid_reasons else "pass",
        invalid_reasons=invalid_reasons,
        test_parameter_digest=parameter_digest,
        environment_digest=env_digest,
    )


def environment_digest_differs(sample: PerformanceSample, digest: str) -> bool:
    return bool(sample.environment_digest) and sample.environment_digest != digest
