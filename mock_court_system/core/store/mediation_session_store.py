"""调解会话 SQLite 存档，供引擎重启后按 session_id 恢复。"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


_DDL = """
CREATE TABLE IF NOT EXISTS mediation_sessions (
    session_id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class MediationSessionStore:
    def __init__(self, db_path: str):
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript(_DDL)

    def save(self, session_id: str, payload: Dict[str, Any]) -> None:
        blob = json.dumps(payload, ensure_ascii=False, default=str)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO mediation_sessions(session_id, payload_json, updated_at)
                   VALUES (?, ?, datetime('now'))
                   ON CONFLICT(session_id) DO UPDATE SET
                     payload_json=excluded.payload_json,
                     updated_at=excluded.updated_at""",
                (session_id, blob),
            )

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT payload_json FROM mediation_sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        return data if isinstance(data, dict) else None

    def delete(self, session_id: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "DELETE FROM mediation_sessions WHERE session_id=?",
                (session_id,),
            )
            return cur.rowcount > 0
