"""SQLite registry/migration/probe/backup/restore 集成测试。

Task 6.1 覆盖 registry/migration/probe；6.2 覆盖 backup/restore/digest。
"""
from __future__ import annotations

import sqlite3

import pytest

from core.store.migrations import (
    Migration,
    MigrationRequired,
    apply_migrations,
    current_version,
)
from core.store.registry import StoreDescriptor, StoreRegistry


def _registry(tmp_path, descriptors=None) -> StoreRegistry:
    return StoreRegistry(
        descriptors or (
            StoreDescriptor(
                logical_name="alpha_store",
                schema_version=1,
                path_config_key="ALPHA_DB_PATH",
                default_filename="alpha.sqlite3",
            ),
            StoreDescriptor(
                logical_name="beta_store",
                schema_version=1,
                path_config_key="BETA_DB_PATH",
                default_filename="beta.sqlite3",
            ),
        ),
        data_root=tmp_path,
    )


def test_registry_resolves_default_and_env_paths(tmp_path, monkeypatch):
    registry = _registry(tmp_path)
    assert registry.resolve_path("alpha_store") == tmp_path / "alpha.sqlite3"
    monkeypatch.setenv("ALPHA_DB_PATH", str(tmp_path / "custom.sqlite3"))
    assert registry.resolve_path("alpha_store") == tmp_path / "custom.sqlite3"


def test_registry_probe_insert_select_delete_leaves_no_business_changes(tmp_path):
    registry = _registry(tmp_path)
    path = registry.resolve_path("alpha_store")
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE business (id TEXT PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO business VALUES('b1', 'v1')")
    conn.commit()
    conn.close()

    result = registry.probe("alpha_store")
    assert result.ok is True
    assert result.reason is None

    conn = sqlite3.connect(str(path))
    assert conn.execute("SELECT COUNT(*) FROM business").fetchone()[0] == 1
    # 探针表允许存在但必须是空的
    assert conn.execute("SELECT COUNT(*) FROM _readiness_probe").fetchone()[0] == 0
    conn.close()


def test_registry_probe_all_reports_each_store(tmp_path):
    registry = _registry(tmp_path)
    results = registry.probe_all()
    assert {r.logical_name for r in results} == {"alpha_store", "beta_store"}
    assert all(r.ok for r in results)
    assert all(r.to_public()["reason"] is None for r in results)


def test_migration_applies_additively_and_records_versions(tmp_path):
    path = tmp_path / "mig.sqlite3"
    conn = sqlite3.connect(str(path))

    def v1(c):
        c.execute("CREATE TABLE t (id TEXT PRIMARY KEY)")

    def v2(c):
        c.execute("ALTER TABLE t ADD COLUMN extra TEXT")

    assert apply_migrations(conn, "demo", [Migration(1, v1), Migration(2, v2)], 2) == 2
    assert current_version(conn, "demo") == 2
    # 幂等：再次应用不重复执行
    assert apply_migrations(conn, "demo", [Migration(1, v1), Migration(2, v2)], 2) == 2


def test_migration_required_on_higher_unknown_version(tmp_path):
    path = tmp_path / "future.sqlite3"
    conn = sqlite3.connect(str(path))
    apply_migrations(conn, "demo", [Migration(5, lambda c: c.execute("CREATE TABLE x (id TEXT)"))], 5)
    conn.commit()
    conn.close()

    descriptors = (
        StoreDescriptor(
            logical_name="demo",
            schema_version=2,
            path_config_key="DEMO_DB_PATH",
            default_filename="future.sqlite3",
        ),
    )
    registry = _registry(tmp_path, descriptors)
    result = registry.probe("demo")
    assert result.ok is False
    assert result.reason == "migration_required"
    assert result.schema_version == 5

    # business readiness 必须被拒绝：更高版本不得进入业务流程
    conn = sqlite3.connect(str(path))
    with pytest.raises(MigrationRequired):
        apply_migrations(conn, "demo", [], 2)
    conn.close()


def test_probe_failure_is_reported_not_raised(tmp_path):
    descriptors = (
        StoreDescriptor(
            logical_name="blocked",
            schema_version=1,
            path_config_key="BLOCKED_DB_PATH",
            default_filename="blocked.sqlite3",
        ),
    )
    registry = _registry(tmp_path, descriptors)
    # 目录路径当 DB 文件 -> open_failed/probe_failed，不抛异常
    blocked = tmp_path / "blocked.sqlite3"
    blocked.mkdir()
    result = registry.probe("blocked")
    assert result.ok is False
    assert result.reason in {"open_failed", "probe_failed"}


# ---------- Task 6.2: backup / verify / clean restore ----------


def _seeded_registry(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    registry = StoreRegistry(data_root=data_root)
    for desc in registry.descriptors():
        if not desc.required_in_production:
            continue
        path = registry.resolve_path(desc.logical_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        conn.execute("CREATE TABLE IF NOT EXISTS business (id TEXT PRIMARY KEY, v TEXT, updated_at TEXT)")
        conn.execute(
            "INSERT OR REPLACE INTO business VALUES(?, ?, ?)",
            (desc.logical_name, "seed", "2026-01-01T00:00:00Z"),
        )
        conn.commit()
        conn.close()
    return registry, data_root


def test_backup_creates_snapshots_and_atomic_manifest(tmp_path, monkeypatch):
    for var in (
        "CONVERSATION_DB_PATH",
        "EVALUATION_DB_PATH",
        "OPERATION_DB_PATH",
        "HEARING_CHECKPOINT_PATH",
        "RESEARCH_CLAIMS_DB",
    ):
        monkeypatch.delenv(var, raising=False)
    registry, _ = _seeded_registry(tmp_path)
    dest = tmp_path / "backup"

    from core.store.backup import MANIFEST_FILENAME, create_backup

    manifest = create_backup(dest, "test", registry=registry, project_root=tmp_path)
    assert manifest.backup_id.startswith("bak_")
    assert manifest.version_id == "1.0.0"
    names = {e.logical_name for e in manifest.store_entries}
    assert "conversation_store" in names and "evaluation_store" in names
    assert (dest / MANIFEST_FILENAME).exists()
    for e in manifest.store_entries:
        assert (dest / e.filename).exists()
        assert len(e.sha256) == 64
        assert e.size_bytes > 0


def test_verify_backup_detects_tamper(tmp_path, monkeypatch):
    for var in (
        "CONVERSATION_DB_PATH",
        "EVALUATION_DB_PATH",
        "OPERATION_DB_PATH",
        "HEARING_CHECKPOINT_PATH",
        "RESEARCH_CLAIMS_DB",
    ):
        monkeypatch.delenv(var, raising=False)
    registry, _ = _seeded_registry(tmp_path)
    dest = tmp_path / "backup"

    from core.store.backup import create_backup, verify_backup

    manifest = create_backup(dest, "test", registry=registry, project_root=tmp_path)
    assert verify_backup(dest).ok

    victim = dest / manifest.store_entries[0].filename
    victim.write_bytes(victim.read_bytes() + b"tamper")
    result = verify_backup(dest)
    assert not result.ok
    assert any(m.endswith("sha256") for m in result.mismatches)


def test_restore_only_into_empty_root_and_recovers_fingerprint(tmp_path, monkeypatch):
    for var in (
        "CONVERSATION_DB_PATH",
        "EVALUATION_DB_PATH",
        "OPERATION_DB_PATH",
        "HEARING_CHECKPOINT_PATH",
        "RESEARCH_CLAIMS_DB",
    ):
        monkeypatch.delenv(var, raising=False)
    registry, data_root = _seeded_registry(tmp_path)
    dest = tmp_path / "backup"

    from core.fingerprint import tables_fingerprint
    from core.store.backup import create_backup, restore_backup

    create_backup(dest, "test", registry=registry, project_root=tmp_path)

    # 非空 root 拒绝，不覆盖
    dirty = tmp_path / "dirty"
    dirty.mkdir()
    (dirty / "keep.txt").write_text("do-not-touch")
    refused = restore_backup(dest, dirty)
    assert not refused.ok
    assert "data_root_not_empty" in refused.failures
    assert (dirty / "keep.txt").read_text() == "do-not-touch"

    clean = tmp_path / "clean"
    result = restore_backup(dest, clean)
    assert result.ok, result.failures
    assert "conversation_store" in result.restored_stores
    assert result.rto_ms >= 0

    # 抽样 fingerprint：恢复库与源库业务表一致
    src_conn = sqlite3.connect(str(data_root / "conversations.sqlite3"))
    dst_conn = sqlite3.connect(str(clean / "conversations.sqlite3"))
    assert tables_fingerprint(src_conn, ["business"]) == tables_fingerprint(
        dst_conn, ["business"]
    )
    src_conn.close()
    dst_conn.close()


def test_restore_fails_closed_on_bad_digest(tmp_path, monkeypatch):
    for var in (
        "CONVERSATION_DB_PATH",
        "EVALUATION_DB_PATH",
        "OPERATION_DB_PATH",
        "HEARING_CHECKPOINT_PATH",
        "RESEARCH_CLAIMS_DB",
    ):
        monkeypatch.delenv(var, raising=False)
    registry, _ = _seeded_registry(tmp_path)
    dest = tmp_path / "backup"

    from core.store.backup import MANIFEST_FILENAME, create_backup, restore_backup
    import json

    manifest = create_backup(dest, "test", registry=registry, project_root=tmp_path)
    victim = dest / manifest.store_entries[0].filename
    victim.write_bytes(victim.read_bytes() + b"x")

    clean = tmp_path / "clean"
    result = restore_backup(dest, clean)
    assert not result.ok
    # 失败不留下部分恢复的 data root
    assert not clean.exists() or not any(clean.iterdir())


def test_rpo_age_from_max_commit_time(tmp_path, monkeypatch):
    registry, _ = _seeded_registry(tmp_path)
    dest = tmp_path / "backup"

    from core.store.backup import create_backup, rpo_age_seconds

    manifest = create_backup(dest, "test", registry=registry, project_root=tmp_path)
    # max_commit_time 为 2026-01-01；now 一小时后 → RPO 3600s
    age = rpo_age_seconds(manifest, now_iso="2026-01-01T01:00:00Z")
    assert 0 < age <= 3600
