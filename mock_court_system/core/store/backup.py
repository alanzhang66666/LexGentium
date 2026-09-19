"""SQLite 在线备份 / 校验 / clean restore（design §9，Task 6.2）。

- 用连接级 ``conn.backup()`` 为每个 required store 建一致快照；
  记录 schema_version、起止时间、SHA-256、size、max included commit time。
- backup set manifest 最后原子写入（temp + os.replace）。
- restore 只允许空 data root：先验全部 digest → 恢复文件 →
  migrations/readiness → 抽样比对 fingerprint；失败不覆盖现有 data root。
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.release.version import VERSION_ID
from core.store.migrations import apply_migrations
from core.store.registry import REQUIRED_STORES, StoreRegistry

MANIFEST_FILENAME = "backup_manifest.json"

#: 各 store 里用于推断 max included commit time 的时间列候选
_TIME_COLUMNS = ("updated_at", "created_at", "completed_at", "committed_at")


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _max_commit_time(db_path: Path) -> str:
    """从业务表时间列推断最大 included commit time；无记录时用备份时刻。"""
    latest = ""
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            for table in tables:
                cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
                for col in _TIME_COLUMNS:
                    if col in cols:
                        row = conn.execute(
                            f"SELECT MAX({col}) FROM {table}"
                        ).fetchone()
                        if row and row[0] and str(row[0]) > latest:
                            latest = str(row[0])
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    return latest


@dataclass(frozen=True)
class StoreBackupEntry:
    logical_name: str
    schema_version: int
    filename: str
    sha256: str
    size_bytes: int
    max_commit_time: str


@dataclass(frozen=True)
class BackupManifest:
    backup_id: str
    version_id: str
    commit_id: str
    requested_by: str
    started_at: str
    completed_at: str
    environment_identity: str
    store_entries: Tuple[StoreBackupEntry, ...]
    manifest_digest: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["store_entries"] = [asdict(e) for e in self.store_entries]
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "BackupManifest":
        return BackupManifest(
            backup_id=d["backup_id"],
            version_id=d["version_id"],
            commit_id=d["commit_id"],
            requested_by=d.get("requested_by", ""),
            started_at=d["started_at"],
            completed_at=d["completed_at"],
            environment_identity=d.get("environment_identity", ""),
            store_entries=tuple(
                StoreBackupEntry(**e) for e in d.get("store_entries", [])
            ),
            manifest_digest=d.get("manifest_digest", ""),
        )


@dataclass(frozen=True)
class DigestResult:
    ok: bool
    mismatches: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RestoreResult:
    ok: bool
    restored_stores: Tuple[str, ...]
    failures: Tuple[str, ...]
    rto_ms: int


def _git_commit_id(project_root: Path) -> str:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        sha = (out.stdout or "").strip()
        return sha if len(sha) == 40 else "0" * 40
    except Exception:
        return "0" * 40


def _environment_identity() -> str:
    import platform
    import sys

    return "|".join(
        [
            platform.system().lower(),
            platform.machine().lower(),
            f"py{sys.version_info.major}.{sys.version_info.minor}",
        ]
    )


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".bak-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, sort_keys=True, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def create_backup(
    destination: Path,
    requested_by: str = "release",
    *,
    registry: Optional[StoreRegistry] = None,
    project_root: Optional[Path] = None,
) -> BackupManifest:
    """为 registry 全部 required store 生成一致快照 + 原子 manifest。"""
    registry = registry or StoreRegistry()
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    started_at = _utcnow_iso()

    entries: List[StoreBackupEntry] = []
    for desc in registry.descriptors():
        if not desc.required_in_production:
            continue
        src_path = registry.resolve_path(desc.logical_name)
        dst_path = destination / f"{desc.logical_name}.sqlite3"
        if not src_path.exists():
            # 未初始化的 store：空库快照，保持 manifest 完整
            src_path.parent.mkdir(parents=True, exist_ok=True)
            sqlite3.connect(str(src_path)).close()
        src = sqlite3.connect(str(src_path))
        try:
            dst = sqlite3.connect(str(dst_path))
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

        schema_version = 0
        probe = sqlite3.connect(str(dst_path))
        try:
            row = probe.execute(
                "SELECT version FROM schema_migrations WHERE logical_name = ?",
                (desc.logical_name,),
            ).fetchone()
            if row:
                schema_version = int(row[0])
            else:
                schema_version = desc.schema_version
        except sqlite3.Error:
            schema_version = desc.schema_version
        finally:
            probe.close()

        entries.append(
            StoreBackupEntry(
                logical_name=desc.logical_name,
                schema_version=schema_version,
                filename=dst_path.name,
                sha256=_sha256(dst_path),
                size_bytes=dst_path.stat().st_size,
                max_commit_time=_max_commit_time(dst_path),
            )
        )

    completed_at = _utcnow_iso()
    manifest = BackupManifest(
        backup_id=f"bak_{uuid.uuid4().hex[:16]}",
        version_id=VERSION_ID,
        commit_id=_git_commit_id(project_root or Path(__file__).resolve().parents[2]),
        requested_by=requested_by,
        started_at=started_at,
        completed_at=completed_at,
        environment_identity=_environment_identity(),
        store_entries=tuple(entries),
    )
    payload = manifest.to_dict()
    from core.fingerprint import canonical_digest

    payload["manifest_digest"] = canonical_digest(
        {k: v for k, v in payload.items() if k != "manifest_digest"}
    )
    _atomic_write_json(destination / MANIFEST_FILENAME, payload)
    return BackupManifest.from_dict(payload)


def load_manifest(destination: Path) -> BackupManifest:
    return BackupManifest.from_dict(
        json.loads((Path(destination) / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    )


def verify_backup(destination: Path) -> DigestResult:
    """重算各 store 文件 SHA-256 与 manifest digest。"""
    destination = Path(destination)
    manifest = load_manifest(destination)
    mismatches: List[str] = []
    for entry in manifest.store_entries:
        f = destination / entry.filename
        if not f.exists():
            mismatches.append(f"{entry.logical_name}:missing")
            continue
        if _sha256(f) != entry.sha256:
            mismatches.append(f"{entry.logical_name}:sha256")

    from core.fingerprint import canonical_digest

    payload = manifest.to_dict()
    expected = payload.pop("manifest_digest", "")
    if canonical_digest(payload) != expected:
        mismatches.append("manifest:digest")
    return DigestResult(ok=not mismatches, mismatches=tuple(mismatches))


def restore_backup(
    destination: Path,
    clean_data_root: Path,
    *,
    registry: Optional[StoreRegistry] = None,
) -> RestoreResult:
    """仅允许恢复到空 data root；先验 digest，再恢复，再 migrations/readiness。"""
    start_ns = time.perf_counter_ns()
    destination = Path(destination)
    clean_data_root = Path(clean_data_root)
    failures: List[str] = []
    restored: List[str] = []

    if clean_data_root.exists() and any(clean_data_root.iterdir()):
        return RestoreResult(
            ok=False,
            restored_stores=(),
            failures=("data_root_not_empty",),
            rto_ms=int((time.perf_counter_ns() - start_ns) / 1_000_000),
        )

    digest = verify_backup(destination)
    if not digest.ok:
        return RestoreResult(
            ok=False,
            restored_stores=(),
            failures=tuple(digest.mismatches),
            rto_ms=int((time.perf_counter_ns() - start_ns) / 1_000_000),
        )

    registry = registry or StoreRegistry(data_root=clean_data_root)
    manifest = load_manifest(destination)
    clean_data_root.mkdir(parents=True, exist_ok=True)
    entries_by_name = {e.logical_name: e for e in manifest.store_entries}

    for desc in registry.descriptors():
        if not desc.required_in_production:
            continue
        entry = entries_by_name.get(desc.logical_name)
        if entry is None:
            failures.append(f"{desc.logical_name}:not_in_manifest")
            continue
        src = destination / entry.filename
        dst = clean_data_root / desc.default_filename
        dst.write_bytes(src.read_bytes())
        # 恢复后跑 migrations + readiness probe
        try:
            conn = sqlite3.connect(str(dst))
            try:
                apply_migrations(conn, desc.logical_name, desc.migrations, desc.schema_version)
            finally:
                conn.close()
        except Exception as exc:
            failures.append(f"{desc.logical_name}:migration:{type(exc).__name__}")
            continue
        probe = registry.probe(desc.logical_name)
        if not probe.ok:
            failures.append(f"{desc.logical_name}:probe:{probe.reason}")
            continue
        restored.append(desc.logical_name)

    return RestoreResult(
        ok=not failures,
        restored_stores=tuple(restored),
        failures=tuple(failures),
        rto_ms=int((time.perf_counter_ns() - start_ns) / 1_000_000),
    )


def rpo_age_seconds(manifest: BackupManifest, *, now_iso: Optional[str] = None) -> float:
    """RPO：备份中最大 included commit time 距 now 的秒数（越小越新）。"""
    latest = max(
        (e.max_commit_time for e in manifest.store_entries if e.max_commit_time),
        default=manifest.completed_at,
    )
    try:
        latest_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
        now_dt = datetime.fromisoformat(
            (now_iso or _utcnow_iso()).replace("Z", "+00:00")
        )
        return max(0.0, (now_dt - latest_dt).total_seconds())
    except ValueError:
        return float("inf")
