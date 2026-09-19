"""Evaluation Provenance — 评分前先落不可变溯源，报告一对一不可变（design §12）。

接受评测时在同一事务里写入 ``EvaluationProvenance`` + ``EvaluationReport``；
完成后 ``report_id``/``provenance_id``/``result_digest``/``immutable_results``
不可更新（状态消息可更新，结果内容 append-only）。同一 ``operation_id``
重试回放既有 provenance/report identity，不产生第二条记录。
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.fingerprint import canonical_digest
from core.store.evaluation_task_store import _utcnow_iso


class ImmutableReportError(Exception):
    """已完成 report 的结果字段不可变。"""


class ProvenanceRequiredError(Exception):
    """报告必须挂在既有 provenance 上。"""


@dataclass(frozen=True)
class EvaluationProvenance:
    provenance_id: str
    input_digest: str
    prediction_identity: str
    evaluator_version: str
    rubric_namespace: str
    rubric_version: str
    configuration_identity: str
    model_identity: str
    operation_id: str
    created_at: str
    session_id: Optional[str] = None
    run_id: Optional[str] = None
    degraded: bool = False
    affected_metrics: tuple = ()


@dataclass(frozen=True)
class EvaluationReport:
    report_id: str
    provenance_id: str
    namespace: str
    status: str  # running|completed|failed
    created_at: str
    completed_at: Optional[str] = None
    result_digest: Optional[str] = None
    immutable_results: Optional[Dict[str, Any]] = None
    message: str = ""


def _provenance_row(row: sqlite3.Row) -> EvaluationProvenance:
    return EvaluationProvenance(
        provenance_id=row["provenance_id"],
        input_digest=row["input_digest"],
        prediction_identity=row["prediction_identity"],
        evaluator_version=row["evaluator_version"],
        rubric_namespace=row["rubric_namespace"],
        rubric_version=row["rubric_version"],
        configuration_identity=row["configuration_identity"],
        model_identity=row["model_identity"],
        operation_id=row["operation_id"],
        created_at=row["created_at"],
        session_id=row["session_id"],
        run_id=row["run_id"],
        degraded=bool(row["degraded"]),
        affected_metrics=tuple(json.loads(row["affected_metrics"] or "[]")),
    )


def _report_row(row: sqlite3.Row) -> EvaluationReport:
    return EvaluationReport(
        report_id=row["report_id"],
        provenance_id=row["provenance_id"],
        namespace=row["namespace"],
        status=row["status"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        result_digest=row["result_digest"],
        immutable_results=json.loads(row["immutable_results"]) if row["immutable_results"] else None,
        message=row["message"] or "",
    )


class EvaluationProvenanceStore:
    """SQLite 落地；一个 operation 恰一个 provenance + 一个 report。"""

    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS evaluation_provenance (
                  provenance_id TEXT PRIMARY KEY,
                  input_digest TEXT NOT NULL,
                  prediction_identity TEXT NOT NULL,
                  evaluator_version TEXT NOT NULL,
                  rubric_namespace TEXT NOT NULL,
                  rubric_version TEXT NOT NULL,
                  configuration_identity TEXT NOT NULL,
                  model_identity TEXT NOT NULL,
                  operation_id TEXT NOT NULL UNIQUE,
                  session_id TEXT,
                  run_id TEXT,
                  degraded INTEGER NOT NULL DEFAULT 0,
                  affected_metrics TEXT NOT NULL DEFAULT '[]',
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_reports (
                  report_id TEXT PRIMARY KEY,
                  provenance_id TEXT NOT NULL UNIQUE
                    REFERENCES evaluation_provenance(provenance_id),
                  namespace TEXT NOT NULL,
                  status TEXT NOT NULL,
                  message TEXT NOT NULL DEFAULT '',
                  result_digest TEXT,
                  immutable_results TEXT,
                  created_at TEXT NOT NULL,
                  completed_at TEXT
                );
                """
            )

    def begin_evaluation(
        self,
        *,
        operation_id: str,
        input_payload: Dict[str, Any],
        prediction_identity: str,
        evaluator_version: str,
        rubric_namespace: str,
        rubric_version: str,
        configuration_identity: str,
        model_identity: str,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
        degraded: bool = False,
        affected_metrics: Optional[List[str]] = None,
        report_id: Optional[str] = None,
    ) -> tuple:
        """评分前事务性写入 provenance + running report；重试返回既有 identity。"""
        try:
            return self._insert_provenance(
                operation_id=operation_id,
                input_payload=input_payload,
                prediction_identity=prediction_identity,
                evaluator_version=evaluator_version,
                rubric_namespace=rubric_namespace,
                rubric_version=rubric_version,
                configuration_identity=configuration_identity,
                model_identity=model_identity,
                session_id=session_id,
                run_id=run_id,
                degraded=degraded,
                affected_metrics=affected_metrics,
                report_id=report_id,
            )
        except sqlite3.IntegrityError:
            # operation_id UNIQUE：并发重试撞约束，回放既有记录
            existing = self.get_by_operation(operation_id)
            if existing:
                return existing
            raise

    def _insert_provenance(self, **kw) -> tuple:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT provenance_id FROM evaluation_provenance WHERE operation_id = ?",
                (kw["operation_id"],),
            ).fetchone()
            if row:
                return self.get_provenance(row["provenance_id"]), self.get_report_by_provenance(
                    row["provenance_id"]
                )

            provenance_id = f"prov_{uuid.uuid4().hex[:24]}"
            report_id = kw.get("report_id") or f"eval_{uuid.uuid4().hex[:24]}"
            now = _utcnow_iso()
            conn.execute(
                """
                INSERT INTO evaluation_provenance(
                  provenance_id, input_digest, prediction_identity, evaluator_version,
                  rubric_namespace, rubric_version, configuration_identity,
                  model_identity, operation_id, session_id, run_id,
                  degraded, affected_metrics, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provenance_id,
                    canonical_digest(kw["input_payload"]),
                    kw["prediction_identity"],
                    kw["evaluator_version"],
                    kw["rubric_namespace"],
                    kw["rubric_version"],
                    kw["configuration_identity"],
                    kw["model_identity"],
                    kw["operation_id"],
                    kw["session_id"],
                    kw["run_id"],
                    int(kw["degraded"]),
                    json.dumps(list(kw["affected_metrics"] or []), ensure_ascii=False),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO evaluation_reports(
                  report_id, provenance_id, namespace, status, message, created_at
                ) VALUES(?, ?, ?, 'running', '', ?)
                """,
                (report_id, provenance_id, kw["rubric_namespace"], now),
            )
        return self.get_provenance(provenance_id), self.get_report(report_id)

    def complete_report(
        self, report_id: str, *, results: Dict[str, Any], message: str = ""
    ) -> EvaluationReport:
        """写入 immutable_results + result_digest；重复完成返回既有报告（幂等）。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM evaluation_reports WHERE report_id = ?", (report_id,)
            ).fetchone()
            if not row:
                raise ProvenanceRequiredError(f"unknown report_id: {report_id}")
            report = _report_row(row)
            if report.status == "completed":
                if report.immutable_results == results:
                    return report
                raise ImmutableReportError(
                    f"report {report_id} already completed; results are immutable"
                )
            digest = canonical_digest(results)
            conn.execute(
                """
                UPDATE evaluation_reports
                SET status = 'completed', result_digest = ?, immutable_results = ?,
                    message = ?, completed_at = ?
                WHERE report_id = ?
                """,
                (
                    digest,
                    json.dumps(results, ensure_ascii=False, sort_keys=True),
                    message,
                    _utcnow_iso(),
                    report_id,
                ),
            )
        return self.get_report(report_id)

    def fail_report(self, report_id: str, *, message: str) -> EvaluationReport:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM evaluation_reports WHERE report_id = ?", (report_id,)
            ).fetchone()
            if not row:
                raise ProvenanceRequiredError(f"unknown report_id: {report_id}")
            if row["status"] == "completed":
                raise ImmutableReportError(f"report {report_id} is completed and immutable")
            conn.execute(
                "UPDATE evaluation_reports SET status = 'failed', message = ? WHERE report_id = ?",
                (message, report_id),
            )
        return self.get_report(report_id)

    def update_message(self, report_id: str, message: str) -> EvaluationReport:
        """状态消息可变；不改结果内容。"""
        with self._connect() as conn:
            conn.execute(
                "UPDATE evaluation_reports SET message = ? WHERE report_id = ?",
                (message, report_id),
            )
        return self.get_report(report_id)

    def get_provenance(self, provenance_id: str) -> Optional[EvaluationProvenance]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM evaluation_provenance WHERE provenance_id = ?", (provenance_id,)
            ).fetchone()
        return _provenance_row(row) if row else None

    def get_report(self, report_id: str) -> Optional[EvaluationReport]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM evaluation_reports WHERE report_id = ?", (report_id,)
            ).fetchone()
        return _report_row(row) if row else None

    def get_report_by_provenance(self, provenance_id: str) -> Optional[EvaluationReport]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM evaluation_reports WHERE provenance_id = ?", (provenance_id,)
            ).fetchone()
        return _report_row(row) if row else None

    def get_by_operation(self, operation_id: str) -> Optional[tuple]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT provenance_id FROM evaluation_provenance WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
        if not row:
            return None
        return self.get_provenance(row["provenance_id"]), self.get_report_by_provenance(
            row["provenance_id"]
        )

    def report_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM evaluation_reports").fetchone()[0]
