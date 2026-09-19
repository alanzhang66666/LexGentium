"""Release gate CLI（Task 14.1）。

Subcommands
-----------
scan-source --root PATH        Scope + sensitive-artifact scan (task 10.3).
test [--critical-runs N] [--dry-run]
                               unit_tests_critical ×N，同 commit 三连跑。
build|contract|security|recovery|e2e|performance|deploy|boundary|scan
                               执行对应 check 并写 content-addressed evidence。
verify --version V --commit SHA [--approver NAME]
                               聚合 evidence → manifest → 确定性 gate →
                               append-only decision chain；GO 退 0，NO-GO 退 1。

所有命令固定 cwd = product root、sanitized env、Version/Commit 绑定；
任何失败/timeout/样本不足/关联缺失立即 no-go，不启动任何 watch 进程。
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

_PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(_PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PRODUCT_ROOT))
_CORE_DIR = _PRODUCT_ROOT / "core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from core.fingerprint import canonical_digest  # noqa: E402
from core.release.checks import (  # noqa: E402
    CheckSpec,
    environment_identity,
    git_commit_id,
    load_check_catalog,
    load_evidence,
    new_run_id,
    persist_evidence,
    run_check,
)
from core.release.evidence import (  # noqa: E402
    EvidenceRecord,
    EvidenceResult,
    GapRecord,
    InventoryDisclosure,
    ReleaseManifest,
    evidence_root,
)
from core.release.gate import (  # noqa: E402
    DecisionLog,
    GateCriterion,
    ReleaseDecision,
    evaluate_gate,
    validate_chain,
)
from core.release.version import VERSION_ID  # noqa: E402

# CLI 子命令 → catalog check_id
_COMMAND_CHECKS: Dict[str, List[str]] = {
    "test": ["unit_tests_critical"],
    "typecheck": ["typecheck"],
    "build": ["build"],
    "contract": ["contract"],
    "security": ["security", "source_scan"],
    "recovery": ["recovery"],
    "e2e": ["e2e"],
    "performance": ["performance"],
    "deploy": ["deploy_docs"],
    "boundary": ["boundary"],
    "scan": ["source_scan"],
}

_GAPS_PATH = _PRODUCT_ROOT / "release" / "gaps.yaml"
_DECISIONS_FILE = "decisions.jsonl"


def _sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    if not path.is_file():
        return ""
    return _sha(path.read_bytes().hex())


def _resolve_commit(value: str) -> str:
    if value.upper() == "HEAD":
        return git_commit_id()
    return value


def _run_scan_source_in_process(root: Path) -> Dict[str, Any]:
    from release.source_scan import scan_source

    report = scan_source(root)
    return {"exit_code": 0 if report.ok else 1, "artifact": report.to_dict()}


def _execute_check(
    spec: CheckSpec,
    *,
    commit_id: str,
    run_id: str,
    run_index: int,
    root: Path,
    dry_run: bool,
) -> Optional[EvidenceRecord]:
    if dry_run:
        rendered = " ".join(
            c.replace("{python}", sys.executable).replace(
                "{evidence_dir}", str(evidence_root())
            )
            for c in spec.command
        ) or f"in_process:{spec.check_id}"
        print(f"[dry-run] {spec.check_id}: {rendered} (timeout {spec.timeout_seconds}s)")
        return None

    in_process = None
    if spec.kind == "in_process":
        in_process = _run_scan_source_in_process(root)

    record, stdout_tail = run_check(
        spec,
        commit_id=commit_id,
        run_id=run_id,
        run_index=run_index,
        root=root,
        in_process_result=in_process,
    )
    artifact = (in_process or {}).get("artifact") or {"stdout_tail": stdout_tail}
    path = persist_evidence(record, artifact)
    summary = {
        "check_id": record.check_id,
        "result": record.result,
        "exit_code": record.exit_code,
        "duration_ms": record.duration_ms,
        "sample_count": record.sample_count,
        "evidence_id": record.evidence_id,
        "evidence_file": path.name,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return record


def _cmd_scan_source(root: str) -> int:
    from release.source_scan import scan_source

    report = scan_source(Path(root))
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


def _cmd_run_checks(args: argparse.Namespace) -> int:
    catalog = {s.check_id: s for s in load_check_catalog()}
    check_ids = _COMMAND_CHECKS[args.command]
    commit = git_commit_id()
    if not commit:
        print(json.dumps({"error": "cannot resolve full commit id"}, ensure_ascii=False))
        return 2
    run_id = new_run_id()
    root = Path(args.root).resolve()
    runs = getattr(args, "critical_runs", 1) or 1
    dry_run = getattr(args, "dry_run", False)

    if dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "version_id": VERSION_ID,
                    "commit_id": commit,
                    "cwd": str(_PRODUCT_ROOT),
                    "environment_identity": environment_identity(),
                    "planned_runs": runs,
                },
                ensure_ascii=False,
            )
        )

    records: List[EvidenceRecord] = []
    worst = 0
    for check_id in check_ids:
        spec = catalog.get(check_id)
        if spec is None:
            print(json.dumps({"error": f"unknown check_id {check_id}"}, ensure_ascii=False))
            return 2
        iterations = runs if check_id == "unit_tests_critical" else 1
        for i in range(iterations):
            record = _execute_check(
                spec,
                commit_id=commit,
                run_id=run_id,
                run_index=i,
                root=root,
                dry_run=dry_run,
            )
            if record is None:
                continue
            records.append(record)
            if record.result != EvidenceResult.PASS.value:
                worst = 1
                break  # 任一失败立即短路，不再跑后续迭代/check
        if worst:
            break

    if dry_run:
        return 0
    return worst


def _load_gaps() -> List[GapRecord]:
    import yaml

    if not _GAPS_PATH.is_file():
        return []
    raw = yaml.safe_load(_GAPS_PATH.read_text(encoding="utf-8")) or {}
    return [GapRecord(**item) for item in (raw.get("gaps") or [])]


def _build_manifest(commit: str, evidence: List[EvidenceRecord], gaps: List[GapRecord]) -> ReleaseManifest:
    import yaml

    inventory_raw = yaml.safe_load(
        (_PRODUCT_ROOT / "release" / "inventory.yaml").read_text(encoding="utf-8")
    ) or {}
    disclosure = InventoryDisclosure.from_inventory(inventory_raw)
    known_limitations = tuple(
        f"{g.gap_id}: {g.actual}" for g in gaps if g.status == "open"
    )
    locks = {}
    for name in ("requirements.lock", "requirements.txt", "package-lock.json"):
        digest = _file_digest(_PRODUCT_ROOT / name)
        if digest:
            locks[name] = digest
    from datetime import datetime

    return ReleaseManifest(
        version_id=VERSION_ID,
        commit_id=commit,
        generated_at=datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        package_metadata_digest=_file_digest(_PRODUCT_ROOT / "package.json"),
        route_catalog_digest=_file_digest(_PRODUCT_ROOT / "release" / "routes.yaml"),
        configuration_digest=_file_digest(_PRODUCT_ROOT / "release" / "configuration.yaml"),
        authoritative_status_digest=_file_digest(_PRODUCT_ROOT / "docs" / "SYSTEM_STATUS.md"),
        lock_digests=locks,
        disclosure=disclosure,
        known_limitations=known_limitations,
        evidence_index=tuple(ev.evidence_id for ev in evidence),
        gap_index=tuple(g.gap_id for g in gaps),
    )


def _load_decision_log(root: Path) -> DecisionLog:
    path = root / _DECISIONS_FILE
    records: List[ReleaseDecision] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            records.append(ReleaseDecision(**json.loads(line)))
    return DecisionLog(records)


def _persist_decision(root: Path, record: ReleaseDecision) -> Path:
    path = root / _DECISIONS_FILE
    root.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(record), ensure_ascii=False, sort_keys=True) + "\n")
    return path


def _cmd_verify(args: argparse.Namespace) -> int:
    commit = _resolve_commit(args.commit)
    if not commit or len(commit) != 40:
        print(json.dumps({"error": "verify requires a full 40-hex commit id"}, ensure_ascii=False))
        return 2
    if args.version != VERSION_ID:
        print(
            json.dumps(
                {"error": f"version mismatch: {args.version} != {VERSION_ID}"},
                ensure_ascii=False,
            )
        )
        return 2

    root = Path(args.evidence_root).resolve() if args.evidence_root else evidence_root()
    all_evidence = load_evidence(root)
    # 只采纳绑定本候选 commit 的证据；缺失 mandatory check 会在 gate 里 fail closed
    candidate_evidence = [ev for ev in all_evidence if ev.commit_id == commit]
    gaps = _load_gaps()
    manifest = _build_manifest(commit, candidate_evidence, gaps)

    catalog = load_check_catalog()
    criteria = [
        GateCriterion(
            check_id=s.check_id,
            mandatory=s.mandatory,
            min_samples=s.min_samples,
            owner=s.owner,
            closure_action=s.closure_action,
        )
        for s in catalog
    ]
    evaluation = evaluate_gate(criteria, candidate_evidence, gaps, manifest)

    log = _load_decision_log(root)
    record = log.append(
        evaluation,
        approver=args.approver,
        manifest=manifest,
        evidence=candidate_evidence,
    )
    _persist_decision(root, record)

    chain_ok, chain_reason = validate_chain(list(log.records))
    out = {
        "decision": evaluation.decision,
        "decision_id": record.decision_id,
        "version_id": VERSION_ID,
        "commit_id": commit,
        "manifest_digest": manifest.digest(),
        "record_digest": record.record_digest,
        "chain_valid": chain_ok,
        "chain_error": chain_reason,
        "failed_criteria": [asdict(f) for f in evaluation.failed_criteria],
        "disclosure": manifest.disclosure.to_dict(),
        "open_gaps": [g.gap_id for g in gaps if g.status == "open"],
        "evidence_records": len(candidate_evidence),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if evaluation.decision == "go" and chain_ok else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="release_gate")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan-source", help="scope + sensitive-artifact scan")
    scan.add_argument("--root", default=".", help="repository/product root")

    for name in sorted(_COMMAND_CHECKS):
        p = sub.add_parser(name, help=f"run check(s): {', '.join(_COMMAND_CHECKS[name])}")
        p.add_argument("--root", default=str(_PRODUCT_ROOT), help="product root (cwd)")
        if name == "test":
            p.add_argument("--critical-runs", type=int, default=1)
        p.add_argument("--dry-run", action="store_true")

    verify = sub.add_parser("verify", help="evaluate gate + append decision")
    verify.add_argument("--version", required=True)
    verify.add_argument("--commit", required=True, help="full 40-hex sha or HEAD")
    verify.add_argument("--approver", default="release-gate-cli")
    verify.add_argument("--evidence-root", default="")

    args = parser.parse_args(argv)
    if args.command == "scan-source":
        return _cmd_scan_source(args.root)
    if args.command == "verify":
        return _cmd_verify(args)
    return _cmd_run_checks(args)


if __name__ == "__main__":
    raise SystemExit(main())
