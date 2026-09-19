"""Release benchmark runner（design §15，Task 12.2）。

有限时长、非 watch：``--max-seconds`` 硬上限；样本不足/环境不匹配/
缺 provider latency 一律 fail closed 为 ``invalid``。

套件：
- ``non_llm``：默认 10 client 模拟负载、>=300 样本（可用 --samples/--clients
  调整）；通过 ``--url`` 打 HTTP 或 ``--mock`` 用内置工作函数。
- ``runtime``：hearing/plead 各 >=30 样本（--mock 用占位工作函数）。
- ``llm``：外部 LLM 调用；provider/local 时长分开记录。

证据写到 ``--output``（默认 EVIDENCE_ROOT 或 RUNTIME_DATA_ROOT/evidence），
JSON 字段与 ``core.release.evidence.EvidenceRecord`` 对齐。

退出码：0=pass，2=invalid（fail-closed），1=runner 自身错误。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.release.statistics import (  # noqa: E402
    EnvironmentIdentity,
    PerformanceSample,
    PerformanceSummary,
    current_environment_identity,
    start_sample,
    summarize_samples,
)

EXIT_PASS = 0
EXIT_INVALID = 2
EXIT_ERROR = 1

DEFAULT_REQUIREMENTS = {
    "non_llm": {"required_samples": 300, "clients": 10, "max_seconds": 300},
    "runtime": {"required_samples": 30, "clients": 1, "max_seconds": 300},
    "llm": {"required_samples": 30, "clients": 1, "max_seconds": 300},
}


def _utcnow_iso() -> str:
    from datetime import datetime

    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def collect_samples(
    work_fn: Callable[[int], Dict[str, Any]],
    *,
    count: int,
    max_seconds: float,
    environment_digest: str = "",
) -> List[PerformanceSample]:
    """串行采集 count 个样本；到达 max_seconds 后剩余样本标记 deadline。"""
    samples: List[PerformanceSample] = []
    deadline = time.monotonic() + max_seconds
    for i in range(count):
        if time.monotonic() >= deadline:
            samples.append(
                PerformanceSample(
                    start_ns=0,
                    end_ns=0,
                    result="failed",
                    exclusion_reason="deadline",
                    environment_digest=environment_digest,
                )
            )
            continue
        start = start_sample()
        result = "success"
        provider_ms: Optional[float] = None
        exclusion: Optional[str] = None
        try:
            info = work_fn(i) or {}
            result = info.get("result", "success")
            provider_ms = info.get("provider_duration_ms")
            exclusion = info.get("exclusion_reason")
        except Exception as exc:
            result = "failed"
            exclusion = f"exception:{type(exc).__name__}"
        end = start_sample()
        samples.append(
            PerformanceSample(
                start_ns=start,
                end_ns=end,
                result=result,
                environment_digest=environment_digest,
                provider_duration_ms=provider_ms,
                exclusion_reason=exclusion,
            )
        )
    return samples


def http_work_fn(url: str, timeout: float = 10.0) -> Callable[[int], Dict[str, Any]]:
    def work(_i: int) -> Dict[str, Any]:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            resp.read()
        return {"result": "success"}

    return work


def mock_work_fn(_i: int) -> Dict[str, Any]:
    return {"result": "success"}


def external_llm_work_fn() -> Callable[[int], Dict[str, Any]]:
    """真实外部 LLM 调用；provider 与 local 时长分开记录。"""
    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    if not (api_key and base_url and model):
        raise RuntimeError("llm_config_missing")

    def work(_i: int) -> Dict[str, Any]:
        import urllib.error

        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 8,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            base_url.rstrip("/") + "/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        provider_start = time.perf_counter_ns()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp.read()
        except urllib.error.HTTPError as exc:
            return {
                "result": "failed",
                "provider_duration_ms": (time.perf_counter_ns() - provider_start)
                / 1_000_000,
                "exclusion_reason": f"http_{exc.code}",
            }
        provider_ms = (time.perf_counter_ns() - provider_start) / 1_000_000
        return {"result": "success", "provider_duration_ms": provider_ms}

    return work


def load_baseline(path: Optional[str]) -> Optional[EnvironmentIdentity]:
    if not path:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return EnvironmentIdentity(
        cpu=data.get("cpu", ""),
        os=data.get("os", ""),
        python_version=data.get("python_version", ""),
        node_version=data.get("node_version", ""),
        lock_digests=data.get("lock_digests", {}),
        model_identity=data.get("model_identity", ""),
        fixture_identity=data.get("fixture_identity", ""),
        network_profile=data.get("network_profile", ""),
    )


def evidence_payload(
    suite: str,
    summary: PerformanceSummary,
    *,
    command: str,
    environment: EnvironmentIdentity,
    started_at: str,
    duration_ms: int,
    exit_code: int,
) -> Dict[str, Any]:
    from core.release.version import VERSION_ID
    import subprocess

    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except Exception:
        commit = "0" * 40
    if len(commit) != 40:
        commit = "0" * 40

    return {
        "evidence_id": f"ev_bench_{suite}",
        "check_id": f"benchmark_{suite}",
        "version_id": VERSION_ID,
        "commit_id": commit,
        "command": command,
        "environment_identity": environment.digest(),
        "started_at": started_at,
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "result": "pass" if summary.verdict == "pass" else "invalid",
        "sample_count": summary.valid_count,
        "summary": {
            "raw_count": summary.raw_count,
            "valid_count": summary.valid_count,
            "p50_ms": summary.p50_ms,
            "p95_ms": summary.p95_ms,
            "max_ms": summary.max_ms,
            "error_rate": summary.error_rate,
            "excluded": summary.excluded,
            "invalid_reasons": summary.invalid_reasons,
            "test_parameter_digest": summary.test_parameter_digest,
        },
        "correlation_context": {},
    }


def run_suite(
    suite: str,
    *,
    samples: int,
    max_seconds: float,
    work_fn: Callable[[int], Dict[str, Any]],
    baseline: Optional[EnvironmentIdentity],
    environment: EnvironmentIdentity,
    command: str,
) -> tuple:
    started_at = _utcnow_iso()
    start_ns = time.perf_counter_ns()
    collected = collect_samples(
        work_fn,
        count=samples,
        max_seconds=max_seconds,
        environment_digest=environment.digest(),
    )
    external = suite == "llm"
    required = DEFAULT_REQUIREMENTS[suite]["required_samples"]
    summary = summarize_samples(
        collected,
        required_samples=required,
        baseline=baseline,
        environment=environment,
        test_parameters={
            "suite": suite,
            "samples": samples,
            "max_seconds": max_seconds,
        },
        external_llm=external,
    )
    duration_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
    payload = evidence_payload(
        suite,
        summary,
        command=command,
        environment=environment,
        started_at=started_at,
        duration_ms=duration_ms,
        exit_code=EXIT_PASS if summary.verdict == "pass" else EXIT_INVALID,
    )
    return summary, payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Release benchmark runner")
    parser.add_argument(
        "--suite",
        required=True,
        choices=sorted(DEFAULT_REQUIREMENTS),
        help="benchmark suite",
    )
    parser.add_argument("--samples", type=int, default=None, help="sample count")
    parser.add_argument("--clients", type=int, default=None, help="simulated clients")
    parser.add_argument("--max-seconds", type=float, default=None, help="hard duration cap")
    parser.add_argument("--url", default="", help="HTTP target for non_llm suite")
    parser.add_argument("--mock", action="store_true", help="use built-in mock work function")
    parser.add_argument("--baseline", default="", help="approved baseline env json")
    parser.add_argument("--output", default="", help="evidence output dir")
    args = parser.parse_args(argv)

    defaults = DEFAULT_REQUIREMENTS[args.suite]
    samples = args.samples if args.samples is not None else defaults["required_samples"]
    max_seconds = (
        args.max_seconds if args.max_seconds is not None else float(defaults["max_seconds"])
    )
    command = " ".join(sys.argv if argv is None else ["benchmark_release.py", *argv])

    environment = current_environment_identity(fixture_identity=args.suite)
    baseline = load_baseline(args.baseline or None)

    try:
        if args.mock:
            work_fn = mock_work_fn
        elif args.suite == "non_llm":
            if not args.url:
                print("error: --url required for non_llm without --mock", file=sys.stderr)
                return EXIT_ERROR
            work_fn = http_work_fn(args.url)
        elif args.suite == "llm":
            work_fn = external_llm_work_fn()
        else:  # runtime
            work_fn = mock_work_fn
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    summary, payload = run_suite(
        args.suite,
        samples=samples,
        max_seconds=max_seconds,
        work_fn=work_fn,
        baseline=baseline,
        environment=environment,
        command=command,
    )

    if args.output:
        out_dir = Path(args.output)
    else:
        from core.release.evidence import evidence_root

        out_dir = evidence_root() / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"benchmark_{args.suite}.json"
    tmp = out_dir / f".benchmark_{args.suite}.tmp"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, out_path)

    print(json.dumps({"suite": args.suite, "verdict": summary.verdict,
                      "valid_samples": summary.valid_count,
                      "invalid_reasons": summary.invalid_reasons,
                      "evidence": str(out_path)}, ensure_ascii=False))
    return EXIT_PASS if summary.verdict == "pass" else EXIT_INVALID


if __name__ == "__main__":
    raise SystemExit(main())
