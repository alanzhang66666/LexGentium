from __future__ import annotations

import json
import copy
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _parse_iso(ts: str) -> datetime:
    # Accept both "...Z" and naive isoformat
    if ts.endswith("Z"):
        ts = ts[:-1]
    return datetime.fromisoformat(ts)


@dataclass
class ConversationRecord:
    session_id: str
    scenario: str
    case_id: str
    created_at: str
    updated_at: str
    dialog_history: List[Dict[str, Any]]
    input_json: Dict[str, Any]
    version: int = 0

    @property
    def message_count(self) -> int:
        return len(self.dialog_history)


class ConcurrentSessionUpdate(RuntimeError):
    """A session was changed after this snapshot was loaded."""


class ConversationStore:
    def create(self, *, session_id: str, scenario: str, case_id: str, input_json: Dict[str, Any]) -> ConversationRecord:
        raise NotImplementedError

    def get(self, session_id: str) -> Optional[ConversationRecord]:
        raise NotImplementedError

    def save(self, record: ConversationRecord) -> None:
        raise NotImplementedError

    def delete(self, session_id: str) -> bool:
        raise NotImplementedError

    def list(self, *, limit: int, offset: int) -> Tuple[List[Dict[str, Any]], int]:
        raise NotImplementedError

    def cleanup(self, *, max_age_hours: int) -> int:
        raise NotImplementedError


class MemoryConversationStore(ConversationStore):
    def __init__(self):
        self._sessions: Dict[str, ConversationRecord] = {}

    def create(self, *, session_id: str, scenario: str, case_id: str, input_json: Dict[str, Any]) -> ConversationRecord:
        now = _utcnow_iso()
        rec = ConversationRecord(
            session_id=session_id,
            scenario=scenario,
            case_id=case_id,
            created_at=now,
            updated_at=now,
            dialog_history=[],
            input_json=input_json or {},
        )
        self._sessions[session_id] = copy.deepcopy(rec)
        return rec

    def get(self, session_id: str) -> Optional[ConversationRecord]:
        record = self._sessions.get(session_id)
        return copy.deepcopy(record) if record is not None else None

    def save(self, record: ConversationRecord) -> None:
        existing = self._sessions.get(record.session_id)
        if existing is None or existing.version != record.version:
            raise ConcurrentSessionUpdate(record.session_id)
        record.version += 1
        record.updated_at = _utcnow_iso()
        self._sessions[record.session_id] = copy.deepcopy(record)

    def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def list(self, *, limit: int, offset: int) -> Tuple[List[Dict[str, Any]], int]:
        sessions = sorted(self._sessions.values(), key=lambda r: r.updated_at, reverse=True)
        total = len(sessions)
        page = sessions[offset : offset + limit]
        result = [
            {
                "session_id": r.session_id,
                "scenario": r.scenario,
                "case_id": r.case_id,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "message_count": r.message_count,
                "is_finished": bool(r.dialog_history and r.dialog_history[-1].get("role") == "Final"),
                "links": (r.input_json or {}).get("links") or {},
            }
            for r in page
        ]
        return result, total

    def cleanup(self, *, max_age_hours: int) -> int:
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        to_delete = []
        for sid, rec in self._sessions.items():
            try:
                if _parse_iso(rec.updated_at) < cutoff:
                    to_delete.append(sid)
            except Exception:
                continue
        for sid in to_delete:
            self._sessions.pop(sid, None)
        return len(to_delete)


class SqliteConversationStore(ConversationStore):
    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                  session_id TEXT PRIMARY KEY,
                  scenario TEXT NOT NULL,
                  case_id TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  dialog_history_json TEXT NOT NULL,
                  input_json_json TEXT NOT NULL,
                  version INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(conversations)")}
            if "version" not in columns:
                conn.execute("ALTER TABLE conversations ADD COLUMN version INTEGER NOT NULL DEFAULT 0")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at)")

    def create(self, *, session_id: str, scenario: str, case_id: str, input_json: Dict[str, Any]) -> ConversationRecord:
        now = _utcnow_iso()
        rec = ConversationRecord(
            session_id=session_id,
            scenario=scenario,
            case_id=case_id,
            created_at=now,
            updated_at=now,
            dialog_history=[],
            input_json=input_json or {},
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversations(session_id, scenario, case_id, created_at, updated_at, dialog_history_json, input_json_json)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.session_id,
                    rec.scenario,
                    rec.case_id,
                    rec.created_at,
                    rec.updated_at,
                    json.dumps(rec.dialog_history, ensure_ascii=False),
                    json.dumps(rec.input_json, ensure_ascii=False),
                ),
            )
        return rec

    def get(self, session_id: str) -> Optional[ConversationRecord]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM conversations WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            return None
        return ConversationRecord(
            session_id=row["session_id"],
            scenario=row["scenario"],
            case_id=row["case_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            dialog_history=json.loads(row["dialog_history_json"]) if row["dialog_history_json"] else [],
            input_json=json.loads(row["input_json_json"]) if row["input_json_json"] else {},
            version=row["version"],
        )

    def save(self, record: ConversationRecord) -> None:
        now = _utcnow_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE conversations
                SET scenario = ?, case_id = ?, updated_at = ?,
                    dialog_history_json = ?, input_json_json = ?, version = version + 1
                WHERE session_id = ? AND version = ?
                """,
                (
                    record.scenario,
                    record.case_id,
                    now,
                    json.dumps(record.dialog_history, ensure_ascii=False),
                    json.dumps(record.input_json, ensure_ascii=False),
                    record.session_id,
                    record.version,
                ),
            )
            if cursor.rowcount != 1:
                raise ConcurrentSessionUpdate(record.session_id)
        record.updated_at = now
        record.version += 1

    def delete(self, session_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
            return cur.rowcount > 0

    def list(self, *, limit: int, offset: int) -> Tuple[List[Dict[str, Any]], int]:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM conversations").fetchone()["c"]
            rows = conn.execute(
                """
                SELECT session_id, scenario, case_id, created_at, updated_at, dialog_history_json, input_json_json
                FROM conversations
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        result = []
        for r in rows:
            try:
                hist = json.loads(r["dialog_history_json"]) if r["dialog_history_json"] else []
            except Exception:
                hist = []
            try:
                extra = json.loads(r["input_json_json"]) if r["input_json_json"] else {}
            except Exception:
                extra = {}
            links = extra.get("links") if isinstance(extra, dict) else {}
            result.append(
                {
                    "session_id": r["session_id"],
                    "scenario": r["scenario"],
                    "case_id": r["case_id"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "message_count": len(hist),
                    "is_finished": bool(hist and isinstance(hist, list) and hist[-1].get("role") == "Final"),
                    "links": links if isinstance(links, dict) else {},
                }
            )
        return result, int(total)

    def cleanup(self, *, max_age_hours: int) -> int:
        cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).replace(microsecond=0).isoformat()
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM conversations WHERE REPLACE(updated_at, 'Z', '') < ?", (cutoff,))
            return cur.rowcount


def build_conversation_store(project_root: Path) -> ConversationStore:
    kind = os.getenv("CONVERSATION_STORE", "").strip().lower() or "sqlite"
    if kind == "memory":
        return MemoryConversationStore()
    # default sqlite
    db_path = os.getenv("CONVERSATION_DB_PATH", "").strip()
    if not db_path:
        db_path = str(project_root / "data" / "conversations.sqlite3")
    return SqliteConversationStore(db_path=db_path)

