"""Operation Ledger：幂等登记、状态机与资源回放。

契约（design.md §3 / OperationRecord）：

- ``operation_id`` 唯一；同一 ID + 同一 ``input_digest`` 返回 existing；
  同一 ID + 不同 digest 返回 409 ``operation_conflict``。
- ``commit_operation`` 使用数据库 CAS，只允许 ``accepted|running -> committed``
  一次，``commit_count <= 1``；committed 后资源身份与 result digest 不可变。
- ledger 不保存 raw prompt 或全文，只保存 digest 与身份。
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


OPERATION_SCHEMA_VERSION = 1

#: 终态（terminal）；committed 允许 terminal_type 为 complete/error/cancelled 之一
TERMINAL_STATUSES = {"committed", "failed", "cancelled"}
OPEN_STATUSES = {"accepted", "running"}


class OperationConflict(Exception):
    """同 Operation ID + 不同 input digest。"""

    def __init__(self, operation_id: str):
        super().__init__(f"operation conflict: {operation_id}")
        self.operation_id = operation_id


class OperationStateError(Exception):
    """非法状态迁移（如重复 commit、committed 后修改）。"""


@dataclass
class OperationRecord:
    operation_id: str
    kind: str
    input_digest: str
    status: str  # accepted|running|committed|failed|cancelled
    request_id_first: str = ""
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    result_digest: Optional[str] = None
    state_fingerprint_before: str = ""
    state_fingerprint_after: Optional[str] = None
    config_identity: Optional[str] = None
    llm_call_count: int = 0
    commit_count: int = 0
    terminal_type: Optional[str] = None
    error_code: Optional[str] = None
    retriable: bool = False
    accepted_at: str = ""
    updated_at: str = ""
    committed_at: Optional[str] = None


@dataclass
class BeginResult:
    outcome: str  # "accepted" | "existing" | "conflict"
    record: Optional[OperationRecord] = None


def canonical_digest(payload: Any) -> str:
    """规范化 JSON（稳定 key order、UTF-8、无无语义空白）的 SHA-256。"""
    normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def derive_operation_id(parent_operation_id: str, step_key: str) -> str:
    """后台子步骤的派生 Operation ID：父 ID + 稳定 step key。"""
    return f"{parent_operation_id}:{step_key}"


class OperationStore:
    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operations (
                  operation_id TEXT PRIMARY KEY,
                  kind TEXT NOT NULL,
                  input_digest TEXT NOT NULL,
                  status TEXT NOT NULL,
                  request_id_first TEXT NOT NULL DEFAULT '',
                  resource_type TEXT,
                  resource_id TEXT,
                  result_digest TEXT,
                  state_fingerprint_before TEXT NOT NULL DEFAULT '',
                  state_fingerprint_after TEXT,
                  config_identity TEXT,
                  llm_call_count INTEGER NOT NULL DEFAULT 0,
                  commit_count INTEGER NOT NULL DEFAULT 0,
                  terminal_type TEXT,
                  error_code TEXT,
                  retriable INTEGER NOT NULL DEFAULT 0,
                  accepted_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  committed_at TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_operations_resource "
                "ON operations(resource_type, resource_id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  store TEXT NOT NULL,
                  version INTEGER NOT NULL,
                  applied_at TEXT NOT NULL,
                  PRIMARY KEY (store, version)
                )
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(store, version, applied_at) VALUES(?, ?, ?)",
                ("operation_store", OPERATION_SCHEMA_VERSION, _utcnow_iso()),
            )

    # ------------------------------------------------------------------
    # 状态机
    # ------------------------------------------------------------------

    def begin_operation(
        self,
        operation_id: str,
        kind: str,
        input_digest: str,
        correlation: Optional[Dict[str, str]] = None,
        state_fingerprint_before: str = "",
    ) -> BeginResult:
        """登记一次逻辑操作。

        - 新 ID：插入 ``accepted``。
        - 已存在 + 同 digest：``existing``（回放资源/结果）。
        - 已存在 + 不同 digest：``conflict``（调用方映射 409）。
        """
        now = _utcnow_iso()
        correlation = correlation or {}
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM operations WHERE operation_id = ?", (operation_id,)
            ).fetchone()
            if row is not None:
                record = self._row_to_record(row)
                if record.input_digest != input_digest:
                    return BeginResult(outcome="conflict", record=record)
                return BeginResult(outcome="existing", record=record)
            conn.execute(
                """
                INSERT INTO operations(
                  operation_id, kind, input_digest, status, request_id_first,
                  state_fingerprint_before, accepted_at, updated_at
                ) VALUES(?, ?, ?, 'accepted', ?, ?, ?, ?)
                """,
                (
                    operation_id,
                    kind,
                    input_digest,
                    correlation.get("request_id", ""),
                    state_fingerprint_before,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM operations WHERE operation_id = ?", (operation_id,)
            ).fetchone()
            return BeginResult(outcome="accepted", record=self._row_to_record(row))

    def mark_running(self, operation_id: str, config_identity: Optional[str] = None) -> OperationRecord:
        with self._lock, self._connect() as conn:
            row = self._require_row(conn, operation_id)
            record = self._row_to_record(row)
            if record.status == "committed":
                return record  # 幂等：已提交操作不再变 running
            if record.status in {"failed", "cancelled"}:
                raise OperationStateError(f"operation {operation_id} is {record.status}")
            conn.execute(
                "UPDATE operations SET status='running', config_identity=COALESCE(?, config_identity), updated_at=? "
                "WHERE operation_id=?",
                (config_identity, _utcnow_iso(), operation_id),
            )
        return self.get(operation_id)

    def commit_operation(
        self,
        operation_id: str,
        resource_type: str,
        resource_id: str,
        result_digest: str,
        state_fingerprint: str,
        terminal_type: str = "complete",
    ) -> OperationRecord:
        """CAS 提交：只允许 accepted|running -> committed，且全局 commit 一次。"""
        if terminal_type not in {"complete", "error", "cancelled"}:
            raise ValueError(f"invalid terminal_type: {terminal_type}")
        now = _utcnow_iso()
        with self._lock, self._connect() as conn:
            row = self._require_row(conn, operation_id)
            record = self._row_to_record(row)
            if record.status == "committed":
                # 幂等回放：同资源同 digest 返回既有记录，不增加 commit_count
                if (
                    record.resource_type == resource_type
                    and record.resource_id == resource_id
                    and record.result_digest == result_digest
                ):
                    return record
                raise OperationStateError(
                    f"operation {operation_id} already committed with different result"
                )
            if record.status in {"failed", "cancelled"}:
                raise OperationStateError(f"operation {operation_id} is {record.status}")
            cursor = conn.execute(
                """
                UPDATE operations SET
                  status='committed',
                  resource_type=?,
                  resource_id=?,
                  result_digest=?,
                  state_fingerprint_after=?,
                  terminal_type=?,
                  commit_count=commit_count+1,
                  committed_at=?,
                  updated_at=?
                WHERE operation_id=? AND status IN ('accepted','running') AND commit_count=0
                """,
                (
                    resource_type,
                    resource_id,
                    result_digest,
                    state_fingerprint,
                    terminal_type,
                    now,
                    now,
                    operation_id,
                ),
            )
            if cursor.rowcount != 1:
                raise OperationStateError(f"operation {operation_id} lost commit race")
        return self.get(operation_id)

    def fail_operation(
        self,
        operation_id: str,
        error_code: str,
        retriable: bool = False,
    ) -> OperationRecord:
        with self._lock, self._connect() as conn:
            row = self._require_row(conn, operation_id)
            record = self._row_to_record(row)
            if record.status == "committed":
                return record  # committed 终态不可变
            conn.execute(
                """
                UPDATE operations SET
                  status='failed', terminal_type='error', error_code=?,
                  retriable=?, updated_at=?
                WHERE operation_id=? AND status IN ('accepted','running')
                """,
                (error_code, 1 if retriable else 0, _utcnow_iso(), operation_id),
            )
        return self.get(operation_id)

    def cancel_operation(self, operation_id: str, before_commit: bool = True) -> OperationRecord:
        """客户端断开：pre-commit 取消；post-commit 保留结果且禁止二次提交。"""
        with self._lock, self._connect() as conn:
            row = self._require_row(conn, operation_id)
            record = self._row_to_record(row)
            if record.status == "committed":
                return record  # 已提交：保留结果，commit_count 不变
            if record.status in {"failed", "cancelled"}:
                return record
            if before_commit:
                conn.execute(
                    """
                    UPDATE operations SET
                      status='cancelled', terminal_type='cancelled', updated_at=?
                    WHERE operation_id=? AND status IN ('accepted','running')
                    """,
                    (_utcnow_iso(), operation_id),
                )
        return self.get(operation_id)

    def record_llm_call(self, operation_id: str, count: int = 1) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE operations SET llm_call_count=llm_call_count+?, updated_at=? WHERE operation_id=?",
                (count, _utcnow_iso(), operation_id),
            )

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get(self, operation_id: str) -> Optional[OperationRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM operations WHERE operation_id = ?", (operation_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def count_resources(self, resource_type: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM operations WHERE resource_type = ? AND status='committed'",
                (resource_type,),
            ).fetchone()
        return int(row["n"])

    def list_by_status(self, status: str) -> List[OperationRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM operations WHERE status = ? ORDER BY updated_at", (status,)
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    # ------------------------------------------------------------------

    def _require_row(self, conn: sqlite3.Connection, operation_id: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM operations WHERE operation_id = ?", (operation_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown operation: {operation_id}")
        return row

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> OperationRecord:
        return OperationRecord(
            operation_id=row["operation_id"],
            kind=row["kind"],
            input_digest=row["input_digest"],
            status=row["status"],
            request_id_first=row["request_id_first"],
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            result_digest=row["result_digest"],
            state_fingerprint_before=row["state_fingerprint_before"],
            state_fingerprint_after=row["state_fingerprint_after"],
            config_identity=row["config_identity"],
            llm_call_count=row["llm_call_count"],
            commit_count=row["commit_count"],
            terminal_type=row["terminal_type"],
            error_code=row["error_code"],
            retriable=bool(row["retriable"]),
            accepted_at=row["accepted_at"],
            updated_at=row["updated_at"],
            committed_at=row["committed_at"],
        )
