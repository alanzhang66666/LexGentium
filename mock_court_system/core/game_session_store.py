"""
博弈会话持久化存储
将 game_sessions 从内存字典迁移到 SQLite，支持服务重启后恢复。
仅存储配置和元数据（引擎状态不序列化，重启后从历史重建）。
"""
from __future__ import annotations

import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("game_session_store")

_DDL = """
CREATE TABLE IF NOT EXISTS game_sessions (
    game_id TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,
    case_info_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    rounds_completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    result_json TEXT
);
"""


class GameSessionStore:
    """SQLite 持久化的博弈会话存储。"""

    def __init__(self, db_path: str):
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript(_DDL)

    def _now(self) -> str:
        return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    def save(
        self,
        game_id: str,
        config: Dict[str, Any],
        case_info: Dict[str, Any],
        status: str = "created",
        rounds_completed: int = 0,
        result: Optional[Dict[str, Any]] = None,
    ):
        """保存或更新博弈会话。"""
        now = self._now()
        config_json = json.dumps(config, ensure_ascii=False, default=str)
        case_json = json.dumps(case_info, ensure_ascii=False, default=str)
        result_json = json.dumps(result, ensure_ascii=False, default=str) if result else None

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO game_sessions
                   (game_id, config_json, case_info_json, status, rounds_completed,
                    created_at, updated_at, result_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(game_id) DO UPDATE SET
                     status=excluded.status,
                     rounds_completed=excluded.rounds_completed,
                     updated_at=excluded.updated_at,
                     result_json=excluded.result_json
                """,
                (game_id, config_json, case_json, status, rounds_completed,
                 now, now, result_json),
            )

    def update_status(self, game_id: str, status: str, rounds_completed: int,
                      result: Optional[Dict[str, Any]] = None):
        """仅更新状态和轮次。"""
        now = self._now()
        result_json = json.dumps(result, ensure_ascii=False, default=str) if result else None
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """UPDATE game_sessions
                   SET status=?, rounds_completed=?, updated_at=?, result_json=?
                   WHERE game_id=?""",
                (status, rounds_completed, now, result_json, game_id),
            )

    def get(self, game_id: str) -> Optional[Dict[str, Any]]:
        """获取博弈会话。"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM game_sessions WHERE game_id=?", (game_id,),
            ).fetchone()

        if not row:
            return None

        return {
            "game_id": row["game_id"],
            "config": json.loads(row["config_json"]),
            "case_info": json.loads(row["case_info_json"]),
            "status": row["status"],
            "rounds_completed": row["rounds_completed"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
        }

    def list_all(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """列出所有博弈会话（按创建时间倒序）。"""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT game_id, status, rounds_completed, created_at, updated_at
                   FROM game_sessions
                   ORDER BY created_at DESC
                   LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()

        return [dict(r) for r in rows]

    def delete(self, game_id: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM game_sessions WHERE game_id=?", (game_id,),
            )
            return cursor.rowcount > 0

    def count(self) -> int:
        with sqlite3.connect(self._db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM game_sessions").fetchone()[0]
