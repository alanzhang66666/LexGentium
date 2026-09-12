"""Append-only research claim events. Resume of the same run_id never overwrites."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

from core.research.runtime import (
    CLAIM_ACTIONS,
    POST_REBUTTAL_ACTIONS,
    TRIAD_REQUIRED_ACTIONS,
    canonical_research_role,
    compact_research_meta,
    get_task_config,
    session_stop_reason,
    has_research,
    research_block,
)


class ClaimError(Exception):
    pass


class ClaimIncompleteError(ClaimError):
    pass


class ClaimActionError(ClaimError):
    pass


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_claims_db_path() -> Path:
    env = (os.getenv("RESEARCH_CLAIMS_DB") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "data" / "research_claims.sqlite3"


class ClaimStore:
    def __init__(self, db_path: str | Path) -> None:
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
                CREATE TABLE IF NOT EXISTS claim_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    session_id TEXT,
                    seq INTEGER NOT NULL,
                    claim_id TEXT NOT NULL,
                    at TEXT NOT NULL,
                    role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    fact TEXT NOT NULL DEFAULT '',
                    norm TEXT NOT NULL DEFAULT '',
                    reasoning TEXT NOT NULL DEFAULT '',
                    target_claim_id TEXT,
                    source_ids_json TEXT NOT NULL DEFAULT '[]',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE (run_id, seq)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_claim_events_run ON claim_events(run_id, seq)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS research_runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    derived_from TEXT,
                    dataset_id TEXT,
                    cluster_id TEXT,
                    pack_version TEXT,
                    task_type TEXT,
                    materials_hash TEXT,
                    conditions_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_research_runs_cluster ON research_runs(dataset_id, cluster_id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS research_reviews (
                    review_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    report_id TEXT,
                    reviewer TEXT NOT NULL DEFAULT '',
                    review_state TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS research_evals (
                    report_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    session_id TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def next_seq(self, run_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) AS max_seq FROM claim_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return int(row["max_seq"]) + 1 if row else 1

    def insert_event(self, event: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO claim_events (
                    event_id, run_id, session_id, seq, claim_id, at, role, action,
                    fact, norm, reasoning, target_claim_id, source_ids_json, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"],
                    event["run_id"],
                    event.get("session_id"),
                    event["seq"],
                    event["claim_id"],
                    event["at"],
                    event["role"],
                    event["action"],
                    event.get("fact") or "",
                    event.get("norm") or "",
                    event.get("reasoning") or "",
                    event.get("target_claim_id"),
                    json.dumps(event.get("source_ids") or [], ensure_ascii=False),
                    json.dumps(event.get("payload") or {}, ensure_ascii=False),
                ),
            )
            conn.commit()
        return event

    def list_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM claim_events WHERE run_id = ? ORDER BY seq ASC",
                (run_id,),
            ).fetchall()
        return [_row_to_event(row) for row in rows]

    def upsert_run(self, record: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO research_runs (
                    run_id, session_id, derived_from, dataset_id, cluster_id,
                    pack_version, task_type, materials_hash, conditions_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    session_id = excluded.session_id,
                    materials_hash = excluded.materials_hash,
                    conditions_json = excluded.conditions_json
                """,
                (
                    record["run_id"],
                    record.get("session_id"),
                    record.get("derived_from"),
                    record.get("dataset_id"),
                    record.get("cluster_id"),
                    record.get("pack_version"),
                    record.get("task_type"),
                    record.get("materials_hash"),
                    json.dumps(record.get("conditions") or {}, ensure_ascii=False),
                    record.get("created_at") or _utcnow_iso(),
                ),
            )
            conn.commit()

    def get_run(self, run_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM research_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "run_id": row["run_id"],
            "session_id": row["session_id"],
            "derived_from": row["derived_from"],
            "dataset_id": row["dataset_id"],
            "cluster_id": row["cluster_id"],
            "pack_version": row["pack_version"],
            "task_type": row["task_type"],
            "materials_hash": row["materials_hash"],
            "conditions": json.loads(row["conditions_json"] or "{}"),
            "created_at": row["created_at"],
        }

    def list_runs(
        self,
        *,
        dataset_id: Optional[str] = None,
        cluster_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM research_runs"
        params: list[Any] = []
        clauses: list[str] = []
        if dataset_id:
            clauses.append("dataset_id = ?")
            params.append(dataset_id)
        if cluster_id:
            clauses.append("cluster_id = ?")
            params.append(cluster_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "run_id": row["run_id"],
                "session_id": row["session_id"],
                "derived_from": row["derived_from"],
                "dataset_id": row["dataset_id"],
                "cluster_id": row["cluster_id"],
                "pack_version": row["pack_version"],
                "task_type": row["task_type"],
                "materials_hash": row["materials_hash"],
                "conditions": json.loads(row["conditions_json"] or "{}"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def add_review(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO research_reviews (
                    review_id, run_id, report_id, reviewer, review_state, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["review_id"],
                    record["run_id"],
                    record.get("report_id"),
                    record.get("reviewer") or "",
                    record["review_state"],
                    record.get("note") or "",
                    record["created_at"],
                ),
            )
            conn.commit()
        return record

    def list_reviews(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM research_reviews WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_eval(self, record: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO research_evals (report_id, run_id, session_id, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(report_id) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (
                    record["report_id"],
                    record["run_id"],
                    record.get("session_id"),
                    json.dumps(record.get("payload") or {}, ensure_ascii=False),
                    record.get("created_at") or _utcnow_iso(),
                ),
            )
            conn.commit()

    def latest_eval(self, run_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM research_evals WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "report_id": row["report_id"],
            "run_id": row["run_id"],
            "session_id": row["session_id"],
            "payload": json.loads(row["payload_json"] or "{}"),
            "created_at": row["created_at"],
        }


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "event_id": row["event_id"],
        "run_id": row["run_id"],
        "session_id": row["session_id"],
        "seq": row["seq"],
        "claim_id": row["claim_id"],
        "at": row["at"],
        "role": row["role"],
        "action": row["action"],
        "fact": row["fact"],
        "norm": row["norm"],
        "reasoning": row["reasoning"],
        "target_claim_id": row["target_claim_id"],
        "source_ids": json.loads(row["source_ids_json"] or "[]"),
        "payload": json.loads(row["payload_json"] or "{}"),
    }


_STORE: Optional[ClaimStore] = None


def get_store() -> ClaimStore:
    global _STORE
    if _STORE is None:
        _STORE = ClaimStore(default_claims_db_path())
    return _STORE


def reset_store_for_tests(db_path: str | Path) -> ClaimStore:
    global _STORE
    _STORE = ClaimStore(db_path)
    return _STORE


def register_run_from_session(session_id: str, input_json: Optional[dict[str, Any]]) -> None:
    research = research_block(input_json)
    run_id = research.get("run_id")
    if not run_id:
        return
    get_store().upsert_run(
        {
            "run_id": run_id,
            "session_id": session_id,
            "derived_from": research.get("derived_from"),
            "dataset_id": research.get("dataset_id"),
            "cluster_id": research.get("cluster_id"),
            "pack_version": research.get("pack_version"),
            "task_type": research.get("task_type"),
            "materials_hash": research.get("materials_hash"),
            "conditions": {
                "visible_materials": research.get("visible_materials"),
                "experiment_conditions": research.get("experiment_conditions"),
                "model_config": research.get("model_config") or research.get("model_config_snapshot"),
            },
            "created_at": _utcnow_iso(),
        }
    )


def _require_triad(action: str, fact: str, norm: str, reasoning: str) -> None:
    if action in TRIAD_REQUIRED_ACTIONS:
        missing = [
            name
            for name, value in (("fact", fact), ("norm", norm), ("reasoning", reasoning))
            if not str(value or "").strip()
        ]
        if missing:
            raise ClaimIncompleteError(
                f"action {action!r} requires fact, norm, and reasoning; missing {missing}"
            )
    if action in ("rebut", "withdraw", "admit_insufficient") and not str(reasoning or "").strip():
        raise ClaimIncompleteError(f"action {action!r} requires reasoning")


def _validate_action_sequence(events: list[dict[str, Any]], action: str, claim_id: str) -> None:
    if action not in CLAIM_ACTIONS:
        raise ClaimActionError(f"unknown claim action: {action}")
    claim_events = [item for item in events if item.get("claim_id") == claim_id]
    if not claim_events:
        if action not in ("assert", "ground"):
            raise ClaimActionError("first event on a claim must be assert or ground")
        return
    last = claim_events[-1]
    if last.get("action") == "rebut" and action not in POST_REBUTTAL_ACTIONS:
        raise ClaimActionError(
            "after rebuttal the next action must be supplement, revise, withdraw, or admit_insufficient"
        )
    if last.get("action") in ("withdraw", "admit_insufficient") and action not in (
        "assert",
        "ground",
    ):
        raise ClaimActionError("closed claim cannot take a further revision")


def append_claim_event(
    *,
    run_id: str,
    session_id: Optional[str],
    role: str,
    action: str,
    fact: str = "",
    norm: str = "",
    reasoning: str = "",
    claim_id: Optional[str] = None,
    target_claim_id: Optional[str] = None,
    source_ids: Optional[list[str]] = None,
    task_type: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    store = get_store()
    existing = store.list_events(run_id)
    action = str(action or "").strip()
    resolved_claim = (claim_id or target_claim_id or "").strip() or f"claim_{uuid.uuid4().hex[:12]}"
    if action == "rebut" and not (target_claim_id or claim_id):
        raise ClaimActionError("rebut requires target_claim_id")
    if action == "rebut":
        resolved_claim = str(target_claim_id or claim_id)
    _require_triad(action, fact, norm, reasoning)
    _validate_action_sequence(existing, action, resolved_claim)
    event = {
        "event_id": f"cevt_{uuid.uuid4().hex}",
        "run_id": run_id,
        "session_id": session_id,
        "seq": store.next_seq(run_id),
        "claim_id": resolved_claim,
        "at": _utcnow_iso(),
        "role": canonical_research_role(role, task_type),
        "action": action,
        "fact": fact or "",
        "norm": norm or "",
        "reasoning": reasoning or "",
        "target_claim_id": target_claim_id,
        "source_ids": list(source_ids or []),
        "payload": payload or {},
    }
    return store.insert_event(event)


def list_claim_events(run_id: str) -> list[dict[str, Any]]:
    return get_store().list_events(run_id)


def claim_chain(run_id: str) -> list[dict[str, Any]]:
    """Group append-only events into assert → ground → rebut → revise/withdraw."""
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for event in list_claim_events(run_id):
        claim_id = event["claim_id"]
        if claim_id not in grouped:
            grouped[claim_id] = {
                "claim_id": claim_id,
                "role": event["role"],
                "status": event["action"],
                "fact": event.get("fact") or "",
                "norm": event.get("norm") or "",
                "reasoning": event.get("reasoning") or "",
                "source_ids": list(event.get("source_ids") or []),
                "events": [],
            }
            order.append(claim_id)
        bucket = grouped[claim_id]
        bucket["events"].append(event)
        bucket["status"] = event["action"]
        if event.get("fact"):
            bucket["fact"] = event["fact"]
        if event.get("norm"):
            bucket["norm"] = event["norm"]
        if event.get("reasoning"):
            bucket["reasoning"] = event["reasoning"]
        if event.get("source_ids"):
            bucket["source_ids"] = list(event["source_ids"])
    return [grouped[key] for key in order]


def session_claim_bundle(record) -> dict[str, Any]:
    research = compact_research_meta(record.input_json)
    if not research:
        return {"research": None, "claim_chain": [], "task_protocol": None, "stop_reason": None}
    run_id = research.get("run_id")
    events = list_claim_events(str(run_id)) if run_id else []
    protocol = get_task_config(research.get("task_type"))
    return {
        "research": research,
        "claim_chain": claim_chain(str(run_id)) if run_id else [],
        "task_protocol": protocol.as_dict() if protocol else None,
        "stop_reason": session_stop_reason(
            task_type=research.get("task_type"),
            dialog_history=list(getattr(record, "dialog_history", None) or []),
            claim_actions=[item["action"] for item in events],
            finished=False,
        ),
    }


def append_session_claim(record, body: dict[str, Any]) -> dict[str, Any]:
    if not has_research(record.input_json):
        raise HTTPException(status_code=400, detail="civil session has no research run")
    research = research_block(record.input_json)
    try:
        event = append_claim_event(
            run_id=str(research["run_id"]),
            session_id=record.session_id,
            role=str(body.get("role") or ""),
            action=str(body.get("action") or ""),
            fact=str(body.get("fact") or ""),
            norm=str(body.get("norm") or ""),
            reasoning=str(body.get("reasoning") or ""),
            claim_id=body.get("claim_id"),
            target_claim_id=body.get("target_claim_id"),
            source_ids=list(body.get("source_ids") or []),
            task_type=research.get("task_type"),
            payload=body.get("payload") if isinstance(body.get("payload"), dict) else {},
        )
    except ClaimError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"event": event, **session_claim_bundle(record)}
