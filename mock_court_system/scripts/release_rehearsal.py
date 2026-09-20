"""Release rehearsal：备份/恢复/升级/回滚演练（Task 13.2）。

所有子命令有限执行、不产生 watch 进程，使用 clean data root 与
immutable artifact；transcript 记录身份、权限、duration、fingerprint。

Subcommands
-----------
backup   --data-root DIR --dest DIR
restore  --backup DIR --data-root DIR
rollback --production DIR --backup DIR [--simulate-failure]
full     --workdir DIR          # 全链路演练：fixture → backup → restore → rollback

验收阈值：恢复/回滚 <=4h，RPO age <=24h；失败不切换生产 root。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

_PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(_PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PRODUCT_ROOT))
_CORE_DIR = _PRODUCT_ROOT / "core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from core.release.version import VERSION_ID  # noqa: E402
from core.store.backup import (  # noqa: E402
    create_backup,
    load_manifest,
    restore_backup,
    rpo_age_seconds,
    verify_backup,
)
from core.store.registry import StoreRegistry  # noqa: E402

RTO_LIMIT_SECONDS = 4 * 3600
RPO_LIMIT_SECONDS = 24 * 3600

_STORE_PATH_ENV = (
    "CONVERSATION_DB_PATH",
    "EVALUATION_DB_PATH",
    "OPERATION_DB_PATH",
    "HEARING_CHECKPOINT_PATH",
    "RESEARCH_CLAIMS_DB",
    "GAME_DB_PATH",
    "MEDIATION_DB_PATH",
)


@contextmanager
def _isolated_store_paths() -> Iterator[None]:
    """演练用显式 data_root 时，不要读到进程里残留的生产路径 env。"""
    saved = {key: os.environ.pop(key, None) for key in _STORE_PATH_ENV}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _identity() -> Dict[str, Any]:
    from core.store.backup import _environment_identity, _git_commit_id

    return {
        "version_id": VERSION_ID,
        "commit_id": _git_commit_id(_PRODUCT_ROOT),
        "environment_identity": _environment_identity(),
        "non_root": (os.getuid() != 0) if hasattr(os, "getuid") else True,
        "platform": sys.platform,
    }


def _transcript(drill: str, steps: List[Dict[str, Any]], verdict: str, reasons: List[str]) -> Dict[str, Any]:
    return {
        "schema": "release-rehearsal-v1",
        "drill": drill,
        "identity": _identity(),
        "started_steps": len(steps),
        "steps": steps,
        "verdict": verdict,
        "failure_reasons": reasons,
        "finished_at": _utcnow(),
    }


def _emit(transcript: Dict[str, Any], out: Optional[str]) -> int:
    text = json.dumps(transcript, ensure_ascii=False, indent=2)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if transcript["verdict"] == "pass" else 1


def _cmd_backup(args: argparse.Namespace) -> int:
    with _isolated_store_paths():
        return _cmd_backup_body(args)


def _cmd_backup_body(args: argparse.Namespace) -> int:
    steps: List[Dict[str, Any]] = []
    reasons: List[str] = []
    data_root = Path(args.data_root)
    registry = StoreRegistry(data_root=data_root)
    t0 = time.monotonic()
    manifest = create_backup(Path(args.dest), requested_by="release_rehearsal", registry=registry)
    duration = time.monotonic() - t0
    steps.append(
        {
            "step": "create_backup",
            "duration_ms": int(duration * 1000),
            "backup_id": manifest.backup_id,
            "manifest_digest": manifest.to_dict().get("manifest_digest", ""),
            "stores": [e.logical_name for e in manifest.store_entries],
        }
    )
    rpo = rpo_age_seconds(manifest)
    steps.append({"step": "rpo_check", "rpo_age_seconds": rpo, "limit_seconds": RPO_LIMIT_SECONDS})
    if rpo > RPO_LIMIT_SECONDS:
        reasons.append(f"rpo_age {rpo:.0f}s exceeds {RPO_LIMIT_SECONDS}s")
    digest = verify_backup(Path(args.dest))
    steps.append({"step": "verify_digest", "ok": digest.ok, "mismatches": list(digest.mismatches)})
    if not digest.ok:
        reasons.extend(digest.mismatches)
    verdict = "pass" if not reasons else "fail"
    return _emit(_transcript("backup", steps, verdict, reasons), args.out)


def _cmd_restore(args: argparse.Namespace) -> int:
    with _isolated_store_paths():
        return _cmd_restore_body(args)


def _cmd_restore_body(args: argparse.Namespace) -> int:
    steps: List[Dict[str, Any]] = []
    reasons: List[str] = []
    data_root = Path(args.data_root)
    registry = StoreRegistry(data_root=data_root)
    result = restore_backup(Path(args.backup), data_root, registry=registry)
    rto_s = result.rto_ms / 1000
    steps.append(
        {
            "step": "restore_backup",
            "rto_ms": result.rto_ms,
            "rto_limit_seconds": RTO_LIMIT_SECONDS,
            "restored": list(result.restored_stores),
            "failures": list(result.failures),
        }
    )
    if not result.ok:
        reasons.extend(result.failures)
    if rto_s > RTO_LIMIT_SECONDS:
        reasons.append(f"rto {rto_s:.0f}s exceeds {RTO_LIMIT_SECONDS}s")
    # 恢复后 readiness 轮询（事务性 probe）
    probes = {}
    for desc in registry.descriptors():
        if not desc.required_in_production:
            continue
        probe = registry.probe(desc.logical_name)
        probes[desc.logical_name] = {"ok": probe.ok, "reason": probe.reason}
        if not probe.ok:
            reasons.append(f"probe {desc.logical_name}: {probe.reason}")
    steps.append({"step": "readiness_probe", "probes": probes})
    verdict = "pass" if not reasons else "fail"
    return _emit(_transcript("restore", steps, verdict, reasons), args.out)


def _cmd_rollback(args: argparse.Namespace) -> int:
    with _isolated_store_paths():
        return _cmd_rollback_body(args)


def _cmd_rollback_body(args: argparse.Namespace) -> int:
    """升级失败回滚演练：生产 root 在失败时不得被切换/破坏。

    顺序：先升级前备份（备份会合法初始化 store），再快照业务内容；
    模拟失败损坏 root 后，quarantine + restore，恢复内容必须与备份一致。
    """
    steps: List[Dict[str, Any]] = []
    reasons: List[str] = []
    production = Path(args.production)
    backup_dir = Path(args.backup)

    # 1) 升级前备份（允许初始化 store）
    registry = StoreRegistry(data_root=production)
    manifest = create_backup(backup_dir, requested_by="release_rehearsal_rollback", registry=registry)
    steps.append({"step": "pre_upgrade_backup", "backup_id": manifest.backup_id})

    # 2) 快照生产 root 业务内容（备份完成后，snapshot 基线）
    before = _db_content_fingerprint(production)
    steps.append({"step": "snapshot_before", "fingerprints": before})

    # 3) 模拟升级失败：staging marker + 损坏业务库内容
    if args.simulate_failure:
        marker = production / ".upgrade_in_progress"
        production.mkdir(parents=True, exist_ok=True)
        marker.write_text("upgrade failed mid-flight", encoding="utf-8")
        damaged = []
        for f in sorted(production.glob("*.sqlite3")):
            with open(f, "r+b") as fh:
                fh.seek(0)
                fh.write(b"CORRUPTED-BY-REHEARSAL\x00" * 8)
            damaged.append(f.name)
        steps.append({"step": "simulate_upgrade_failure", "marker": marker.name, "damaged": damaged})
    steps.append({"step": "rollback", "action": "preserve production root; restore from backup if damaged"})

    # 4) 校验业务内容未被改变
    after = _db_content_fingerprint(production)
    steps.append({"step": "snapshot_after", "fingerprints": after})
    if before != after:
        steps.append({"step": "detect_damage", "changed": sorted(set(before) ^ set(after) | {k for k in before if before[k] != after.get(k)})})
        # 受损 root 移入 quarantine，从备份恢复
        quarantine = production.parent / f"{production.name}.quarantine-{uuid.uuid4().hex[:8]}"
        production.rename(quarantine)
        restore = restore_backup(backup_dir, production, registry=StoreRegistry(data_root=production))
        steps.append({"step": "restore_production", "ok": restore.ok, "failures": list(restore.failures)})
        steps.append({"step": "quarantine_damaged_root", "path": str(quarantine)})
        if not restore.ok:
            reasons.extend(restore.failures)
        else:
            restored_fp = _db_content_fingerprint(production)
            match = restored_fp == before
            steps.append({"step": "restored_content_compare", "match": match})
            if not match:
                reasons.append("restored_production_content_mismatch")
    # 生产 root 不允许残留升级 marker（无论是否触发恢复）
    if (production / ".upgrade_in_progress").exists():
        reasons.append("upgrade_marker_left_in_production_root")

    rpo = rpo_age_seconds(load_manifest(backup_dir))
    steps.append({"step": "rpo_check", "rpo_age_seconds": rpo, "limit_seconds": RPO_LIMIT_SECONDS})
    if rpo > RPO_LIMIT_SECONDS:
        reasons.append(f"rpo_age {rpo:.0f}s exceeds {RPO_LIMIT_SECONDS}s")

    verdict = "pass" if not reasons else "fail"
    return _emit(_transcript("rollback", steps, verdict, reasons), args.out)


def _db_content_fingerprint(data_root: Path) -> Dict[str, str]:
    """每库业务内容指纹：用户表全量行（按 rowid）的 sha256。

    排除 sqlite_* / schema_migrations / probe 元数据 — migration 是恢复
    的合法副作用，不算内容差异。
    """
    import hashlib

    fp: Dict[str, str] = {}
    for db in sorted(data_root.glob("*.sqlite3")):
        h = hashlib.sha256()
        try:
            conn = sqlite3.connect(str(db))
            try:
                tables = [
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name NOT LIKE 'sqlite_%' "
                        "AND name NOT IN ('schema_migrations', '_readiness_probe', 'probe') "
                        "ORDER BY name"
                    )
                ]
                for table in tables:
                    h.update(table.encode())
                    for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid'):
                        h.update(repr(row).encode())
            finally:
                conn.close()
        except sqlite3.Error:
            fp[db.name] = "unreadable"
            continue
        fp[db.name] = h.hexdigest()
    return fp


def _seed_fixture_store(data_root: Path) -> None:
    """最小 fixture：一个 required store 文件带业务行。"""
    data_root.mkdir(parents=True, exist_ok=True)
    db = data_root / "conversations.sqlite3"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, payload TEXT)")
        conn.execute("INSERT OR REPLACE INTO sessions VALUES ('rehearsal-fixture', '{}')")
        conn.commit()
    finally:
        conn.close()


def _cmd_full(args: argparse.Namespace) -> int:
    with _isolated_store_paths():
        return _cmd_full_body(args)


def _cmd_full_body(args: argparse.Namespace) -> int:
    """全链路演练：fixture data root → backup → 新 root restore → 指纹一致 → 回滚。"""
    steps: List[Dict[str, Any]] = []
    reasons: List[str] = []
    workdir = Path(args.workdir)
    run_id = uuid.uuid4().hex[:8]
    source_root = workdir / f"{run_id}_source"
    restore_root = workdir / f"{run_id}_restored"
    backup_dir = workdir / f"{run_id}_backup"

    _seed_fixture_store(source_root)
    steps.append({"step": "seed_fixture", "root": source_root.name})

    # backup
    registry = StoreRegistry(data_root=source_root)
    manifest = create_backup(backup_dir, requested_by="release_rehearsal_full", registry=registry)
    steps.append({"step": "backup", "backup_id": manifest.backup_id})

    # restore to fresh root
    result = restore_backup(backup_dir, restore_root, registry=StoreRegistry(data_root=restore_root))
    rto_s = result.rto_ms / 1000
    steps.append({"step": "restore", "rto_ms": result.rto_ms, "ok": result.ok, "failures": list(result.failures)})
    if not result.ok:
        reasons.extend(result.failures)
    if rto_s > RTO_LIMIT_SECONDS:
        reasons.append(f"rto {rto_s}s exceeds {RTO_LIMIT_SECONDS}s")

    # 指纹一致性：恢复后业务内容与源一致（migration/probe 元数据不计）
    src_fp = _db_content_fingerprint(source_root)
    dst_fp = _db_content_fingerprint(restore_root)
    match = src_fp == dst_fp
    steps.append({"step": "fingerprint_compare", "match": match, "source": src_fp, "restored": dst_fp})
    if not match:
        reasons.append("restored_content_mismatch")

    rpo = rpo_age_seconds(manifest)
    steps.append({"step": "rpo_check", "rpo_age_seconds": rpo, "limit_seconds": RPO_LIMIT_SECONDS})
    if rpo > RPO_LIMIT_SECONDS:
        reasons.append(f"rpo_age {rpo:.0f}s exceeds {RPO_LIMIT_SECONDS}s")

    verdict = "pass" if not reasons else "fail"
    transcript = _transcript("full", steps, verdict, reasons)
    transcript["run_id"] = run_id
    return _emit(transcript, args.out)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="release_rehearsal")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("backup", help="backup drill")
    b.add_argument("--data-root", required=True)
    b.add_argument("--dest", required=True)
    b.add_argument("--out", default="")

    r = sub.add_parser("restore", help="restore drill to a clean data root")
    r.add_argument("--backup", required=True)
    r.add_argument("--data-root", required=True)
    r.add_argument("--out", default="")

    rb = sub.add_parser("rollback", help="failed-upgrade rollback drill")
    rb.add_argument("--production", required=True)
    rb.add_argument("--backup", required=True)
    rb.add_argument("--simulate-failure", action="store_true")
    rb.add_argument("--out", default="")

    f = sub.add_parser("full", help="end-to-end rehearsal in a workdir")
    f.add_argument("--workdir", required=True)
    f.add_argument("--out", default="")

    args = parser.parse_args(argv)
    return {
        "backup": _cmd_backup,
        "restore": _cmd_restore,
        "rollback": _cmd_rollback,
        "full": _cmd_full,
    }[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
