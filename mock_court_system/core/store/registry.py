"""StoreRegistry：required SQLite store 的登记、schema 校验与 readiness 探针。

- 每个 required store 声明 logical_name、path env、schema_version、
  migrations 与 probe 版本。
- readiness probe 在专用 ``_readiness_probe`` 表的同一事务内做
  insert/select/delete，不触碰任何业务记录。
- 数据文件 schema 版本高于支持版本时报 ``migration_required``。
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Tuple

from core.store.migrations import (
    Migration,
    MigrationRequired,
    apply_migrations,
    check_compatible,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"

PROBE_TABLE = "_readiness_probe"


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass(frozen=True)
class StoreDescriptor:
    logical_name: str
    schema_version: int
    path_config_key: str
    default_filename: str
    required_in_production: bool = True
    migrations: Tuple[Migration, ...] = ()
    probe_version: int = 1


@dataclass
class ProbeResult:
    logical_name: str
    ok: bool
    schema_version: int
    reason: Optional[str] = None  # migration_required | open_failed | probe_failed
    detail: str = ""

    def to_public(self) -> dict:
        """面向 readiness 响应的安全视图：不含路径/文件名。"""
        return {
            "component": self.logical_name,
            "ok": self.ok,
            "reason": self.reason,
        }


#: 现役 required stores。schema_version 为本代码支持的最高版本。
REQUIRED_STORES: Tuple[StoreDescriptor, ...] = (
    StoreDescriptor(
        logical_name="conversation_store",
        schema_version=1,
        path_config_key="CONVERSATION_DB_PATH",
        default_filename="conversations.sqlite3",
    ),
    StoreDescriptor(
        logical_name="evaluation_store",
        schema_version=1,
        path_config_key="EVALUATION_DB_PATH",
        default_filename="app_state.sqlite3",
    ),
    StoreDescriptor(
        logical_name="operation_store",
        schema_version=1,
        path_config_key="OPERATION_DB_PATH",
        default_filename="operations.sqlite3",
    ),
    StoreDescriptor(
        logical_name="runtime_store",
        schema_version=1,
        path_config_key="HEARING_CHECKPOINT_PATH",
        default_filename="checkpoints.sqlite3",
    ),
    StoreDescriptor(
        logical_name="research_store",
        schema_version=1,
        path_config_key="RESEARCH_CLAIMS_DB",
        default_filename="research_claims.sqlite3",
    ),
    StoreDescriptor(
        logical_name="game_store",
        schema_version=1,
        path_config_key="GAME_DB_PATH",
        default_filename="game_sessions.sqlite3",
        required_in_production=False,
    ),
    StoreDescriptor(
        logical_name="mediation_store",
        schema_version=1,
        path_config_key="MEDIATION_DB_PATH",
        default_filename="mediation_sessions.sqlite3",
        required_in_production=False,
    ),
)


def runtime_data_root() -> Path:
    """运行数据根：可用 RUNTIME_DATA_ROOT 覆盖（测试/evidence 应放源码树外）。"""
    env = os.getenv("RUNTIME_DATA_ROOT", "").strip()
    return Path(env) if env else DEFAULT_DATA_ROOT


class StoreRegistry:
    def __init__(
        self,
        descriptors: Iterable[StoreDescriptor] = REQUIRED_STORES,
        data_root: Optional[Path] = None,
    ):
        self._descriptors = {d.logical_name: d for d in descriptors}
        self.data_root = Path(data_root) if data_root else runtime_data_root()

    def descriptors(self) -> Tuple[StoreDescriptor, ...]:
        return tuple(self._descriptors.values())

    def descriptor(self, logical_name: str) -> StoreDescriptor:
        return self._descriptors[logical_name]

    def resolve_path(self, logical_name: str) -> Path:
        desc = self.descriptor(logical_name)
        override = os.getenv(desc.path_config_key, "").strip()
        if override:
            return Path(override)
        return self.data_root / desc.default_filename

    def ensure_schema(self, logical_name: str, conn: sqlite3.Connection) -> int:
        """校验并应用 additive migrations；返回当前 schema 版本。"""
        desc = self.descriptor(logical_name)
        return apply_migrations(conn, logical_name, desc.migrations, desc.schema_version)

    def probe(self, logical_name: str) -> ProbeResult:
        """对单个 store 做事务性 read-write-delete 探针。"""
        desc = self.descriptor(logical_name)
        path = self.resolve_path(logical_name)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # autocommit 模式：事务边界完全由探针显式控制
            conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        except (OSError, sqlite3.Error) as exc:
            return ProbeResult(logical_name, False, 0, "open_failed", str(exc))

        try:
            conn.execute("PRAGMA journal_mode=WAL")
            check_compatible(conn, logical_name, desc.schema_version)
            self.ensure_schema(logical_name, conn)
            # 事务内 insert/select/delete：净效果为零，不改业务记录
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {PROBE_TABLE} ("
                "probe_id TEXT PRIMARY KEY, probe_version INTEGER, probed_at TEXT)"
            )
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                f"INSERT INTO {PROBE_TABLE}(probe_id, probe_version, probed_at) VALUES(?, ?, ?)",
                (f"probe-{logical_name}", desc.probe_version, _utcnow_iso()),
            )
            row = conn.execute(
                f"SELECT probe_version FROM {PROBE_TABLE} WHERE probe_id = ?",
                (f"probe-{logical_name}",),
            ).fetchone()
            value = row[0] if row else None
            conn.execute(
                f"DELETE FROM {PROBE_TABLE} WHERE probe_id = ?",
                (f"probe-{logical_name}",),
            )
            conn.commit()
            if value != desc.probe_version:
                return ProbeResult(logical_name, False, desc.schema_version, "probe_failed")
            return ProbeResult(logical_name, True, desc.schema_version)
        except MigrationRequired as exc:
            conn.rollback()
            return ProbeResult(
                logical_name, False, exc.found_version, "migration_required", str(exc)
            )
        except sqlite3.Error as exc:
            conn.rollback()
            return ProbeResult(logical_name, False, desc.schema_version, "probe_failed", str(exc))
        finally:
            conn.close()

    def probe_all(self, *, production: bool = False) -> list:
        results = []
        for desc in self._descriptors.values():
            if production and not desc.required_in_production:
                continue
            results.append(self.probe(desc.logical_name))
        return results

    def schema_versions(self) -> dict:
        versions = {}
        for desc in self._descriptors.values():
            path = self.resolve_path(desc.logical_name)
            if not path.exists():
                versions[desc.logical_name] = 0
                continue
            try:
                conn = sqlite3.connect(str(path))
                from core.store.migrations import current_version

                versions[desc.logical_name] = current_version(conn, desc.logical_name)
                conn.close()
            except sqlite3.Error:
                versions[desc.logical_name] = -1
        return versions
