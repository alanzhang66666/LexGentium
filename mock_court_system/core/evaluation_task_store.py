from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class EvaluationTaskRecord:
    report_id: str
    status: str  # running|completed|failed
    message: str
    created_at: str
    updated_at: str
    results_json: Optional[str] = None
    report_path: Optional[str] = None

    def results(self) -> Optional[Dict[str, Any]]:
        if not self.results_json:
            return None
        try:
            return json.loads(self.results_json)
        except Exception:
            return None


class EvaluationTaskStore:
    def upsert(self, record: EvaluationTaskRecord) -> None:
        raise NotImplementedError

    def get(self, report_id: str) -> Optional[EvaluationTaskRecord]:
        raise NotImplementedError

    def list_recent(self, limit: int = 50) -> List[EvaluationTaskRecord]:
        raise NotImplementedError


class SqliteEvaluationTaskStore(EvaluationTaskStore):
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
                CREATE TABLE IF NOT EXISTS evaluation_tasks (
                  report_id TEXT PRIMARY KEY,
                  status TEXT NOT NULL,
                  message TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  results_json TEXT,
                  report_path TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_updated_at ON evaluation_tasks(updated_at)")

    def upsert(self, record: EvaluationTaskRecord) -> None:
        record.updated_at = _utcnow_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO evaluation_tasks(report_id, status, message, created_at, updated_at, results_json, report_path)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_id) DO UPDATE SET
                  status=excluded.status,
                  message=excluded.message,
                  updated_at=excluded.updated_at,
                  results_json=excluded.results_json,
                  report_path=excluded.report_path
                """,
                (
                    record.report_id,
                    record.status,
                    record.message,
                    record.created_at,
                    record.updated_at,
                    record.results_json,
                    record.report_path,
                ),
            )

    def get(self, report_id: str) -> Optional[EvaluationTaskRecord]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM evaluation_tasks WHERE report_id = ?", (report_id,)).fetchone()
        if not row:
            return None
        return EvaluationTaskRecord(
            report_id=row["report_id"],
            status=row["status"],
            message=row["message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            results_json=row["results_json"],
            report_path=row["report_path"],
        )

    def list_recent(self, limit: int = 50) -> List[EvaluationTaskRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM evaluation_tasks ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            EvaluationTaskRecord(
                report_id=r["report_id"],
                status=r["status"],
                message=r["message"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                results_json=r["results_json"],
                report_path=r["report_path"],
            )
            for r in rows
        ]


def build_evaluation_task_store(project_root: Path) -> EvaluationTaskStore:
    # Reuse the same sqlite file as conversation store by default for simplicity.
    # It keeps all “app runtime state” in ./data/app_state.sqlite3 unless overridden later.
    db_path = str(project_root / "data" / "app_state.sqlite3")
    return SqliteEvaluationTaskStore(db_path=db_path)

