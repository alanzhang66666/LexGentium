"""Release gate check catalog 与 bounded runner（Task 14.1）。

- ``release/checks.yaml`` 声明每条 mandatory/optional check 的命令、
  timeout、min_samples 与 owner。
- 每次执行产出一条 ``EvidenceRecord``，绑定完整 Version/Commit identity、
  固定 cwd（product root）、sanitized env、环境身份与 correlation context。
- evidence 以 content-addressed 文件名写入 ``evidence_root()/records/``，
  digest 相同则复写同一文件（确定性），不会互相覆盖不同证据。
- 任何失败/timeout/样本不足/字段缺失都 fail closed。
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from core.fingerprint import canonical_digest
from core.release.evidence import EvidenceRecord, EvidenceResult, evidence_root
from core.release.version import VERSION_ID

_PRODUCT_ROOT = Path(__file__).resolve().parents[2]
_CHECKS_PATH = _PRODUCT_ROOT / "release" / "checks.yaml"
_STDOUT_TAIL_LIMIT = 4000


@dataclass(frozen=True)
class CheckSpec:
    check_id: str
    kind: str  # subprocess | in_process
    mandatory: bool = True
    command: Tuple[str, ...] = ()
    timeout_seconds: int = 600
    min_samples: int = 0
    owner: str = "release"
    closure_action: str = ""


def load_check_catalog(path: Optional[Path] = None) -> List[CheckSpec]:
    raw = yaml.safe_load((path or _CHECKS_PATH).read_text(encoding="utf-8")) or {}
    specs: List[CheckSpec] = []
    for item in raw.get("checks") or []:
        specs.append(
            CheckSpec(
                check_id=str(item["check_id"]),
                kind=str(item.get("kind", "subprocess")),
                mandatory=bool(item.get("mandatory", True)),
                command=tuple(str(c) for c in (item.get("command") or ())),
                timeout_seconds=int(item.get("timeout_seconds", 600)),
                min_samples=int(item.get("min_samples", 0)),
                owner=str(item.get("owner", "release")),
                closure_action=str(item.get("closure_action", "")),
            )
        )
    return specs


def product_root() -> Path:
    return _PRODUCT_ROOT


def git_commit_id(cwd: Optional[Path] = None) -> str:
    """完整 40-hex HEAD；取不到返回 ''（fail closed）。"""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd or _PRODUCT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        sha = out.stdout.strip()
        return sha if len(sha) == 40 else ""
    except Exception:
        return ""


def environment_identity() -> str:
    """环境身份 digest：解释器/平台/Node 版本。"""
    node = ""
    try:
        out = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=10
        )
        node = out.stdout.strip()
    except Exception:
        node = "unavailable"
    payload = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "node": node,
        "cwd": str(_PRODUCT_ROOT),
    }
    return canonical_digest(payload)


def _render_command(spec: CheckSpec, evidence_dir: Path) -> List[str]:
    rendered = [
        c.replace("{python}", sys.executable).replace(
            "{evidence_dir}", str(evidence_dir)
        )
        for c in spec.command
    ]
    if rendered and not Path(rendered[0]).is_file():
        from shutil import which

        resolved = which(rendered[0])
        if resolved:
            rendered[0] = resolved
    return rendered


def _sanitized_env() -> Dict[str, str]:
    env = dict(os.environ)
    # 固定：不进入 watch / reload，不继承交互式调试变量
    for key in ("PYTHONBREAKPOINT", "PYTHONINSPECT", "WATCHFILES_FORCE_POLLING"):
        env.pop(key, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CI"] = "1"
    return env


def _parse_sample_count(spec: CheckSpec, stdout_tail: str) -> int:
    """从 stdout 回填样本数：pytest/playwright 'N passed' 或 JSON sample 字段。"""
    import re

    m = re.findall(r"(\d+) passed", stdout_tail)
    if m:
        return max(int(x) for x in m)
    m = re.search(r'"(?:sample_count|samples|valid_samples)"\s*:\s*(\d+)', stdout_tail)
    if m:
        return int(m.group(1))
    return 0


def run_check(
    spec: CheckSpec,
    *,
    commit_id: str,
    run_id: str,
    run_index: int = 0,
    root: Optional[Path] = None,
    extra_correlation: Optional[Dict[str, str]] = None,
    in_process_result: Optional[Dict[str, Any]] = None,
) -> Tuple[EvidenceRecord, str]:
    """执行一条 check；返回 (evidence, stdout_tail)。

    ``in_process_result`` 由调用方执行 in_process 检查后传入
    {"exit_code": int, "artifact": dict}。
    """
    started = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    t0 = time.monotonic()
    root = root or _PRODUCT_ROOT
    correlation = {"run_id": run_id, "run_index": str(run_index)}
    if extra_correlation:
        correlation.update(extra_correlation)

    exit_code = 1
    result = EvidenceResult.FAIL.value
    artifact: Dict[str, Any] = {}
    stdout_tail = ""

    if spec.kind == "in_process":
        payload = in_process_result or {}
        exit_code = int(payload.get("exit_code", 1))
        artifact = payload.get("artifact") or {}
        result = EvidenceResult.PASS.value if exit_code == 0 else EvidenceResult.FAIL.value
    else:
        cmd = _render_command(spec, evidence_root())
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(root),
                env=_sanitized_env(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=spec.timeout_seconds,
            )
            exit_code = proc.returncode
            stdout_tail = (proc.stdout or "")[-_STDOUT_TAIL_LIMIT:] + (
                proc.stderr or ""
            )[-_STDOUT_TAIL_LIMIT:]
            artifact = {"stdout_tail": stdout_tail}
            result = EvidenceResult.PASS.value if exit_code == 0 else EvidenceResult.FAIL.value
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout_tail = (exc.stdout or "")[-_STDOUT_TAIL_LIMIT:] if isinstance(exc.stdout, str) else ""
            artifact = {"stdout_tail": stdout_tail, "timeout_seconds": spec.timeout_seconds}
            result = EvidenceResult.TIMEOUT.value
        except Exception as exc:  # noqa: BLE001 - evidence 记录原因
            exit_code = 1
            artifact = {"runner_error": f"{type(exc).__name__}: {exc}"}
            result = EvidenceResult.INVALID.value

    duration_ms = int((time.monotonic() - t0) * 1000)
    record = EvidenceRecord(
        evidence_id=f"ev_{spec.check_id}_{run_id}_{run_index}",
        check_id=spec.check_id,
        version_id=VERSION_ID,
        commit_id=commit_id,
        command=" ".join(_render_command(spec, evidence_root()))
        if spec.command
        else f"in_process:{spec.check_id}",
        environment_identity=environment_identity(),
        started_at=started,
        duration_ms=duration_ms,
        exit_code=exit_code,
        result=result,
        sample_count=_parse_sample_count(spec, stdout_tail),
        artifact_digest=canonical_digest(artifact),
        correlation_context=correlation,
    )
    return record, stdout_tail


def persist_evidence(
    record: EvidenceRecord,
    artifact: Optional[Dict[str, Any]] = None,
    *,
    root: Optional[Path] = None,
) -> Path:
    """content-addressed 写入：文件名 = evidence digest。"""
    ev_root = (root or evidence_root()) / "records"
    ev_root.mkdir(parents=True, exist_ok=True)
    path = ev_root / f"{record.digest()}.json"
    payload = {"record": _record_to_dict(record), "artifact": artifact or {}}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _record_to_dict(record: EvidenceRecord) -> Dict[str, Any]:
    from dataclasses import asdict

    return asdict(record)


def load_evidence(root: Optional[Path] = None) -> List[EvidenceRecord]:
    ev_root = (root or evidence_root()) / "records"
    if not ev_root.is_dir():
        return []
    records: List[EvidenceRecord] = []
    for path in sorted(ev_root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(EvidenceRecord(**payload["record"]))
        except Exception:
            continue
    return records


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]
