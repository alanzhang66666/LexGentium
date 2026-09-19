"""SQLite checkpoint：thread_id = session_id / task_id。

CheckpointV2（Task 5.2）：
- ``checkpoints_v2`` 按 (thread_id, turn_number) 版本化，单写 v2；
- ``load`` 双读：先读 v2 head，miss 回退旧 ``checkpoints``(v1) 表；
- ``save``（旧接口）转发到 v2，turn_number 自增，不再写 v1；
- 每行携带 state_fingerprint 与 operation_id，供 RuntimeUnitOfWork
  在同一事务内与 session/operation 提交对齐。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


DEFAULT_CHECKPOINT_PATH = os.path.join("data", "checkpoints.sqlite3")


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass(frozen=True)
class CheckpointV2:
    thread_id: str
    turn_number: int
    payload: Dict[str, Any]
    state_fingerprint: str
    operation_id: str
    committed_at: str


class SqliteCheckpointStore:
    def __init__(self, path: Optional[str] = None):
        self.path = path or os.getenv("HEARING_CHECKPOINT_PATH", DEFAULT_CHECKPOINT_PATH)
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._lock = threading.Lock()
        self._init()

    def _init(self) -> None:
        with self._lock:
            conn = sqlite3.connect(self.path)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints_v2 (
                    thread_id TEXT NOT NULL,
                    turn_number INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    state_fingerprint TEXT NOT NULL DEFAULT '',
                    operation_id TEXT NOT NULL DEFAULT '',
                    committed_at TEXT NOT NULL,
                    PRIMARY KEY (thread_id, turn_number)
                )
                """
            )
            conn.commit()
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # v2 API
    # ------------------------------------------------------------------

    def save_v2(
        self,
        thread_id: str,
        turn_number: int,
        payload: Dict[str, Any],
        *,
        state_fingerprint: str = "",
        operation_id: str = "",
        conn: Optional[sqlite3.Connection] = None,
    ) -> CheckpointV2:
        """单写 v2；传入 conn 时参与调用方事务（RuntimeUnitOfWork）。"""
        row = CheckpointV2(
            thread_id=thread_id,
            turn_number=int(turn_number),
            payload=payload,
            state_fingerprint=state_fingerprint,
            operation_id=operation_id,
            committed_at=_utcnow_iso(),
        )
        sql = (
            "INSERT OR REPLACE INTO checkpoints_v2"
            "(thread_id, turn_number, payload, state_fingerprint, operation_id, committed_at)"
            " VALUES (?,?,?,?,?,?)"
        )
        args = (
            row.thread_id,
            row.turn_number,
            json.dumps(row.payload, ensure_ascii=False),
            row.state_fingerprint,
            row.operation_id,
            row.committed_at,
        )
        if conn is not None:
            conn.execute(sql, args)
            return row
        with self._lock:
            c = self._connect()
            try:
                c.execute(sql, args)
                c.commit()
            finally:
                c.close()
        return row

    def head_v2(self, thread_id: str) -> Optional[CheckpointV2]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM checkpoints_v2 WHERE thread_id=? "
                    "ORDER BY turn_number DESC LIMIT 1",
                    (thread_id,),
                ).fetchone()
            finally:
                conn.close()
        if not row:
            return None
        return CheckpointV2(
            thread_id=row["thread_id"],
            turn_number=row["turn_number"],
            payload=json.loads(row["payload"]),
            state_fingerprint=row["state_fingerprint"],
            operation_id=row["operation_id"],
            committed_at=row["committed_at"],
        )

    def latest_turn_number(self, thread_id: str) -> int:
        head = self.head_v2(thread_id)
        return head.turn_number if head else -1

    # ------------------------------------------------------------------
    # 兼容 API：save → v2（turn 自增）；load 双读 v2 → v1
    # ------------------------------------------------------------------

    def save(self, thread_id: str, payload: Dict[str, Any]) -> None:
        self.save_v2(thread_id, self.latest_turn_number(thread_id) + 1, payload)

    def load(self, thread_id: str) -> Optional[Dict[str, Any]]:
        head = self.head_v2(thread_id)
        if head is not None:
            return head.payload
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT payload FROM checkpoints WHERE thread_id=?",
                    (thread_id,),
                ).fetchone()
            finally:
                conn.close()
        if not row:
            return None
        return json.loads(row[0])

    def delete(self, thread_id: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM checkpoints WHERE thread_id=?", (thread_id,))
                conn.execute("DELETE FROM checkpoints_v2 WHERE thread_id=?", (thread_id,))
                conn.commit()
            finally:
                conn.close()
