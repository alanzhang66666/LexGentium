"""SQLite checkpoint：thread_id = session_id / task_id。"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, Optional


DEFAULT_CHECKPOINT_PATH = os.path.join("data", "checkpoints.sqlite3")


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
            conn.commit()
            conn.close()

    def save(self, thread_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            conn = sqlite3.connect(self.path)
            conn.execute(
                "INSERT OR REPLACE INTO checkpoints(thread_id, payload, updated_at) VALUES (?,?,strftime('%s','now'))",
                (thread_id, json.dumps(payload, ensure_ascii=False)),
            )
            conn.commit()
            conn.close()

    def load(self, thread_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = sqlite3.connect(self.path)
            row = conn.execute(
                "SELECT payload FROM checkpoints WHERE thread_id=?",
                (thread_id,),
            ).fetchone()
            conn.close()
        if not row:
            return None
        return json.loads(row[0])

    def delete(self, thread_id: str) -> None:
        with self._lock:
            conn = sqlite3.connect(self.path)
            conn.execute("DELETE FROM checkpoints WHERE thread_id=?", (thread_id,))
            conn.commit()
            conn.close()
