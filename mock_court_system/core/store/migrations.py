"""Additive schema migrations 与 schema_migrations 账本（design.md §9）。

- 所有 required store 都有 ``schema_migrations`` 表记录 (store, version, applied_at)。
- 只做 additive/expand-contract 迁移；未知更高版本返回 ``migration_required``。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, Optional

MIGRATIONS_TABLE = "schema_migrations"


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class MigrationRequired(Exception):
    """数据文件 schema 版本高于本代码支持的版本。"""

    def __init__(self, store: str, found_version: int, supported_version: int):
        super().__init__(
            f"{store} schema version {found_version} > supported {supported_version}"
        )
        self.store = store
        self.found_version = found_version
        self.supported_version = supported_version


@dataclass(frozen=True)
class Migration:
    """一次 additive 迁移：版本号 + 执行函数（必须可重复安全）。"""

    version: int
    apply: Callable[[sqlite3.Connection], None]
    description: str = ""


def ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
          store TEXT NOT NULL,
          version INTEGER NOT NULL,
          applied_at TEXT NOT NULL,
          PRIMARY KEY (store, version)
        )
        """
    )


def current_version(conn: sqlite3.Connection, store: str) -> int:
    ensure_migrations_table(conn)
    row = conn.execute(
        f"SELECT MAX(version) AS v FROM {MIGRATIONS_TABLE} WHERE store = ?", (store,)
    ).fetchone()
    value = row["v"] if isinstance(row, sqlite3.Row) else row[0]
    return int(value or 0)


def check_compatible(conn: sqlite3.Connection, store: str, supported_version: int) -> None:
    found = current_version(conn, store)
    if found > supported_version:
        raise MigrationRequired(store, found, supported_version)


def apply_migrations(
    conn: sqlite3.Connection,
    store: str,
    migrations: Iterable[Migration],
    target_version: int,
) -> int:
    """按版本升序应用未执行的迁移；返回最终版本。

    发现更高版本立即抛 ``MigrationRequired``；不执行任何 destructive
    down-migration。
    """
    ensure_migrations_table(conn)
    found = current_version(conn, store)
    if found > target_version:
        raise MigrationRequired(store, found, target_version)

    for migration in sorted(migrations, key=lambda m: m.version):
        if migration.version <= found:
            continue
        if migration.version > target_version:
            raise MigrationRequired(store, migration.version, target_version)
        migration.apply(conn)
        conn.execute(
            f"INSERT OR REPLACE INTO {MIGRATIONS_TABLE}(store, version, applied_at) VALUES(?, ?, ?)",
            (store, migration.version, _utcnow_iso()),
        )

    final = current_version(conn, store)
    if final == 0 and target_version > 0:
        conn.execute(
            f"INSERT OR IGNORE INTO {MIGRATIONS_TABLE}(store, version, applied_at) VALUES(?, ?, ?)",
            (store, target_version, _utcnow_iso()),
        )
        final = target_version
    return final
