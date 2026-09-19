"""RuntimeUnitOfWork（Task 5.2）：单 turn 的原子提交单元。

把 checkpoint（runtime state DB，主连接）、conversation、operation
三个 SQLite 库 ATTACH 到同一连接，``BEGIN IMMEDIATE`` 后所有写入
在同一事务提交或整体回滚 —— 保证 turn 的 checkpoint / session /
operation / turn_number / state_fingerprint 原子一致；失败保留上一
fingerprint。

用法::

    with RuntimeUnitOfWork(checkpoint_store, operation_store=ops,
                           conversation_store=conv) as uow:
        uow.save_checkpoint(thread_id, turn, payload, fingerprint, op_id)
        uow.save_conversation(record)
        uow.commit_operation(op_id, resource_type, resource_id, digest, fingerprint)

非 sqlite 的 conversation store（内存实现）在 COMMIT 后 best-effort
落库，不参与原子事务。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class UnitOfWorkError(Exception):
    pass


class OperationStateError(UnitOfWorkError):
    pass


class RuntimeUnitOfWork:
    def __init__(
        self,
        checkpoint_store,
        *,
        operation_store=None,
        conversation_store=None,
    ) -> None:
        self._cp = checkpoint_store
        self._ops = operation_store
        self._conv = conversation_store
        self._conn: Optional[sqlite3.Connection] = None
        self._alias: Dict[str, str] = {}
        self._pending_conv = []  # 非 sqlite store 的 post-commit 回放

    # ------------------------------------------------------------------
    # transaction lifecycle
    # ------------------------------------------------------------------

    def __enter__(self) -> "RuntimeUnitOfWork":
        conn = self._cp._connect()
        conn.isolation_level = None  # autocommit → 手动 BEGIN
        for label, path in self._attach_paths():
            alias = f"uow_{label}"
            conn.execute(f"ATTACH DATABASE ? AS {alias}", (str(path),))
            self._alias[label] = alias
        conn.execute("BEGIN IMMEDIATE")
        self._conn = conn
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        conn = self._conn
        self._conn = None
        try:
            if exc_type is None:
                conn.execute("COMMIT")
                for rec in self._pending_conv:
                    self._conv.save(rec)
            else:
                conn.execute("ROLLBACK")
        finally:
            for alias in self._alias.values():
                try:
                    conn.execute(f"DETACH DATABASE {alias}")
                except sqlite3.Error:
                    pass
            conn.close()
        return False

    def _attach_paths(self):
        main_path = getattr(self._cp, "path", None)
        for label, store in (("ops", self._ops), ("conv", self._conv)):
            if store is None:
                continue
            path = getattr(store, "db_path", None) or getattr(store, "path", None)
            if path and str(path) != str(main_path):
                yield label, path

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise UnitOfWorkError("unit of work not entered")
        return self._conn

    # ------------------------------------------------------------------
    # writes（同一事务）
    # ------------------------------------------------------------------

    def save_checkpoint(
        self,
        thread_id: str,
        turn_number: int,
        payload: Dict[str, Any],
        *,
        state_fingerprint: str = "",
        operation_id: str = "",
    ) -> None:
        self._cp.save_v2(
            thread_id,
            turn_number,
            payload,
            state_fingerprint=state_fingerprint,
            operation_id=operation_id,
            conn=self._require_conn(),
        )

    def save_conversation(self, record) -> None:
        """UPDATE conversations；内存 store 记为 post-commit best-effort。"""
        if self._conv is None:
            raise UnitOfWorkError("no conversation store bound")
        alias = self._alias.get("conv")
        record.updated_at = _utcnow_iso()
        if alias is None:
            self._pending_conv.append(record)
            return
        self._require_conn().execute(
            f"""
            UPDATE {alias}.conversations
            SET scenario = ?, case_id = ?, updated_at = ?, dialog_history_json = ?, input_json_json = ?
            WHERE session_id = ?
            """,
            (
                record.scenario,
                record.case_id,
                record.updated_at,
                json.dumps(record.dialog_history, ensure_ascii=False),
                json.dumps(record.input_json, ensure_ascii=False),
                record.session_id,
            ),
        )

    def commit_operation(
        self,
        operation_id: str,
        resource_type: str,
        resource_id: str,
        result_digest: str,
        state_fingerprint: str,
        *,
        terminal_type: str = "complete",
    ) -> None:
        """CAS commit：只允许 accepted|running → committed；已提交同结果幂等回放。"""
        if self._ops is None:
            raise UnitOfWorkError("no operation store bound")
        alias = self._alias.get("ops")
        if alias is None:
            raise UnitOfWorkError("operation store is not sqlite-backed")
        conn = self._require_conn()
        row = conn.execute(
            f"SELECT status, resource_type, resource_id, result_digest "
            f"FROM {alias}.operations WHERE operation_id=?",
            (operation_id,),
        ).fetchone()
        if row is None:
            raise OperationStateError(f"operation {operation_id} not found")
        status = row[0]
        if status == "committed":
            if (row[1], row[2], row[3]) == (resource_type, resource_id, result_digest):
                return  # 幂等回放
            raise OperationStateError(
                f"operation {operation_id} already committed with different result"
            )
        if status in ("failed", "cancelled"):
            raise OperationStateError(f"operation {operation_id} is {status}")
        now = _utcnow_iso()
        conn.execute(
            f"""
            UPDATE {alias}.operations SET
              status='committed',
              resource_type=?, resource_id=?, result_digest=?,
              state_fingerprint_after=?, terminal_type=?,
              commit_count=commit_count+1, committed_at=?, updated_at=?
            WHERE operation_id=?
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
