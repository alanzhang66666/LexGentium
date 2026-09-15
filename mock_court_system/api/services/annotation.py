"""Field overlays and change history for research packs. Never writes pack.json."""
from __future__ import annotations

import copy
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from api.services import materials

REVIEW_STATES = ("pending", "tech_checked", "law_reviewed", "disputed")

LIST_FIELD_ID = {
    "procedural_facts": "item_id",
    "party_claims": "item_id",
    "court_findings": "item_id",
    "legal_bases": "item_id",
    "material_gaps": "gap_id",
    "source_anchors": "source_id",
    "rules": "rule_id",
    "documents": "document_id",
    "argument_records": "argument_id",
    "evidence_links": "link_id",
}

PRIMARY_VALUE_KEY = {
    "procedural_facts": "value",
    "party_claims": "claim_text",
    "court_findings": "finding",
    "legal_bases": "citation",
    "material_gaps": "description",
    "source_anchors": "quote",
    "rules": "text",
    "documents": "title",
    "argument_records": "claim",
    "evidence_links": "purpose",
    "task_labels.elements": "value",
}


class AnnotationError(Exception):
    pass


class FieldNotFoundError(AnnotationError):
    pass


class InvalidReviewStateError(AnnotationError):
    pass


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_annotation_db_path() -> Path:
    env = (os.getenv("RESEARCH_ANNOTATION_DB") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "data" / "research_annotations.sqlite3"


class AnnotationStore:
    """SQLite overlays + changelog. pack.json on disk is never opened for write."""

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
                CREATE TABLE IF NOT EXISTS annotation_overlays (
                  dataset_id TEXT NOT NULL,
                  cluster_id TEXT NOT NULL,
                  pack_version TEXT NOT NULL,
                  field_path TEXT NOT NULL,
                  item_id TEXT NOT NULL DEFAULT '',
                  overlay_json TEXT NOT NULL,
                  review_state TEXT,
                  updated_by TEXT NOT NULL DEFAULT '',
                  updated_at TEXT NOT NULL,
                  PRIMARY KEY (dataset_id, cluster_id, pack_version, field_path)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS annotation_changelog (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  dataset_id TEXT NOT NULL,
                  cluster_id TEXT NOT NULL,
                  pack_version TEXT NOT NULL,
                  field_path TEXT NOT NULL,
                  item_id TEXT NOT NULL DEFAULT '',
                  actor TEXT NOT NULL,
                  action TEXT NOT NULL,
                  from_value TEXT,
                  to_value TEXT,
                  review_state TEXT,
                  note TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ann_log_pack
                ON annotation_changelog(dataset_id, cluster_id, pack_version, created_at)
                """
            )

    def list_overlays(self, dataset_id: str, cluster_id: str, pack_version: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT dataset_id, cluster_id, pack_version, field_path, item_id,
                       overlay_json, review_state, updated_by, updated_at
                FROM annotation_overlays
                WHERE dataset_id = ? AND cluster_id = ? AND pack_version = ?
                ORDER BY field_path
                """,
                (dataset_id, cluster_id, pack_version),
            ).fetchall()
        return [_row_overlay(row) for row in rows]

    def get_overlay(
        self,
        dataset_id: str,
        cluster_id: str,
        pack_version: str,
        field_path: str,
    ) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT dataset_id, cluster_id, pack_version, field_path, item_id,
                       overlay_json, review_state, updated_by, updated_at
                FROM annotation_overlays
                WHERE dataset_id = ? AND cluster_id = ? AND pack_version = ? AND field_path = ?
                """,
                (dataset_id, cluster_id, pack_version, field_path),
            ).fetchone()
        return _row_overlay(row) if row else None

    def count_overlays(self, dataset_id: str, cluster_id: str, pack_version: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n FROM annotation_overlays
                WHERE dataset_id = ? AND cluster_id = ? AND pack_version = ?
                """,
                (dataset_id, cluster_id, pack_version),
            ).fetchone()
        return int(row["n"] if row else 0)

    def upsert_overlay(
        self,
        *,
        dataset_id: str,
        cluster_id: str,
        pack_version: str,
        field_path: str,
        item_id: str,
        overlay: dict[str, Any],
        review_state: Optional[str],
        actor: str,
    ) -> dict[str, Any]:
        now = _utcnow_iso()
        payload = json.dumps(overlay, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO annotation_overlays(
                  dataset_id, cluster_id, pack_version, field_path, item_id,
                  overlay_json, review_state, updated_by, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dataset_id, cluster_id, pack_version, field_path) DO UPDATE SET
                  item_id=excluded.item_id,
                  overlay_json=excluded.overlay_json,
                  review_state=excluded.review_state,
                  updated_by=excluded.updated_by,
                  updated_at=excluded.updated_at
                """,
                (
                    dataset_id,
                    cluster_id,
                    pack_version,
                    field_path,
                    item_id,
                    payload,
                    review_state,
                    actor,
                    now,
                ),
            )
        return {
            "dataset_id": dataset_id,
            "cluster_id": cluster_id,
            "pack_version": pack_version,
            "field_path": field_path,
            "item_id": item_id,
            "overlay": overlay,
            "review_state": review_state,
            "updated_by": actor,
            "updated_at": now,
        }

    def append_changelog(
        self,
        *,
        dataset_id: str,
        cluster_id: str,
        pack_version: str,
        field_path: str,
        item_id: str,
        actor: str,
        action: str,
        from_value: Any,
        to_value: Any,
        review_state: Optional[str],
        note: str,
    ) -> dict[str, Any]:
        now = _utcnow_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO annotation_changelog(
                  dataset_id, cluster_id, pack_version, field_path, item_id,
                  actor, action, from_value, to_value, review_state, note, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_id,
                    cluster_id,
                    pack_version,
                    field_path,
                    item_id,
                    actor,
                    action,
                    _json_dump(from_value),
                    _json_dump(to_value),
                    review_state,
                    note,
                    now,
                ),
            )
            entry_id = int(cursor.lastrowid)
        return {
            "id": entry_id,
            "dataset_id": dataset_id,
            "cluster_id": cluster_id,
            "pack_version": pack_version,
            "field_path": field_path,
            "item_id": item_id,
            "actor": actor,
            "action": action,
            "from_value": from_value,
            "to_value": to_value,
            "review_state": review_state,
            "note": note,
            "created_at": now,
        }

    def list_changelog(
        self,
        dataset_id: str,
        cluster_id: str,
        pack_version: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT id, dataset_id, cluster_id, pack_version, field_path, item_id,
                   actor, action, from_value, to_value, review_state, note, created_at
            FROM annotation_changelog
            WHERE dataset_id = ? AND cluster_id = ?
        """
        args: list[Any] = [dataset_id, cluster_id]
        if pack_version:
            sql += " AND pack_version = ?"
            args.append(pack_version)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(max(1, min(int(limit), 1000)))
        with self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [_row_changelog(row) for row in rows]


_STORE: Optional[AnnotationStore] = None
_STORE_PATH: Optional[str] = None


def get_annotation_store() -> AnnotationStore:
    global _STORE, _STORE_PATH
    path = str(default_annotation_db_path())
    if _STORE is None or _STORE_PATH != path:
        _STORE = AnnotationStore(path)
        _STORE_PATH = path
    return _STORE


def reset_annotation_store_cache() -> None:
    global _STORE, _STORE_PATH
    _STORE = None
    _STORE_PATH = None


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_load(raw: Optional[str]) -> Any:
    if raw is None or raw == "":
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _row_overlay(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "dataset_id": row["dataset_id"],
        "cluster_id": row["cluster_id"],
        "pack_version": row["pack_version"],
        "field_path": row["field_path"],
        "item_id": row["item_id"],
        "overlay": _json_load(row["overlay_json"]) or {},
        "review_state": row["review_state"],
        "updated_by": row["updated_by"],
        "updated_at": row["updated_at"],
    }


def _row_changelog(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "dataset_id": row["dataset_id"],
        "cluster_id": row["cluster_id"],
        "pack_version": row["pack_version"],
        "field_path": row["field_path"],
        "item_id": row["item_id"],
        "actor": row["actor"],
        "action": row["action"],
        "from_value": _json_load(row["from_value"]),
        "to_value": _json_load(row["to_value"]),
        "review_state": row["review_state"],
        "note": row["note"],
        "created_at": row["created_at"],
    }


def parse_field_path(field_path: str) -> dict[str, str]:
    path = (field_path or "").strip()
    if not path:
        raise FieldNotFoundError("field_path is required")
    if path in {"review_state", "notes"}:
        return {"kind": "pack", "key": path, "item_id": path}
    if path == "task_labels":
        return {"kind": "task_labels", "key": "", "item_id": "task_labels"}
    if path.startswith("task_labels.elements/"):
        element_id = path.split("/", 1)[1]
        if not element_id:
            raise FieldNotFoundError(path)
        return {"kind": "element", "key": element_id, "item_id": element_id}
    if path.startswith("task_labels/"):
        key = path.split("/", 1)[1]
        if not key:
            raise FieldNotFoundError(path)
        return {"kind": "task_label_field", "key": key, "item_id": key}
    column, sep, item_id = path.partition("/")
    if not sep or not item_id or column not in LIST_FIELD_ID:
        raise FieldNotFoundError(path)
    return {"kind": "list", "key": column, "item_id": item_id}


def locate_item(pack: dict[str, Any], field_path: str) -> tuple[Any, str]:
    parsed = parse_field_path(field_path)
    kind = parsed["kind"]
    if kind == "pack":
        return pack.get(parsed["key"]), parsed["key"]
    if kind == "task_labels":
        return pack.get("task_labels") or {}, "task_labels"
    if kind == "task_label_field":
        labels = pack.get("task_labels") or {}
        return labels.get(parsed["key"]), parsed["key"]
    if kind == "element":
        for element in (pack.get("task_labels") or {}).get("elements") or []:
            if element.get("element_id") == parsed["key"]:
                return element, PRIMARY_VALUE_KEY["task_labels.elements"]
        raise FieldNotFoundError(field_path)
    column = parsed["key"]
    item_id = parsed["item_id"]
    id_key = LIST_FIELD_ID[column]
    for item in pack.get(column) or []:
        if str(item.get(id_key)) == item_id:
            return item, PRIMARY_VALUE_KEY[column]
    raise FieldNotFoundError(field_path)


def apply_overlays(pack: dict[str, Any], overlays: list[dict[str, Any]]) -> dict[str, Any]:
    merged = copy.deepcopy(pack)
    for entry in overlays:
        overlay = entry.get("overlay") if "overlay" in entry else entry
        field_path = entry.get("field_path")
        if not field_path or not isinstance(overlay, dict):
            continue
        _apply_one(merged, field_path, overlay)
    return merged


def _apply_one(pack: dict[str, Any], field_path: str, overlay: dict[str, Any]) -> None:
    parsed = parse_field_path(field_path)
    kind = parsed["kind"]
    clean = {key: value for key, value in overlay.items() if not str(key).startswith("_")}
    if kind == "pack":
        key = parsed["key"]
        if key in clean:
            pack[key] = clean[key]
        elif "value" in clean:
            pack[key] = clean["value"]
        elif key == "review_state" and "review_state" in clean:
            pack["review_state"] = clean["review_state"]
        return
    if kind == "task_labels":
        labels = pack.setdefault("task_labels", {})
        if isinstance(labels, dict):
            labels.update(clean)
        return
    if kind == "task_label_field":
        labels = pack.setdefault("task_labels", {})
        if not isinstance(labels, dict):
            return
        key = parsed["key"]
        if "value" in clean:
            labels[key] = clean["value"]
        for field, value in clean.items():
            if field == "value":
                continue
            if field == key or field == "review_state":
                labels[field] = value
        return
    if kind == "element":
        for element in (pack.get("task_labels") or {}).get("elements") or []:
            if element.get("element_id") == parsed["key"]:
                element.update(clean)
                return
        return
    column = parsed["key"]
    id_key = LIST_FIELD_ID[column]
    for item in pack.get(column) or []:
        if str(item.get(id_key)) == parsed["item_id"]:
            item.update(clean)
            return


def _validate_review_state(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    if value not in REVIEW_STATES:
        raise InvalidReviewStateError(
            f"review_state must be one of {REVIEW_STATES}, got {value!r}"
        )
    return value


def _actor_name(actor: Optional[str]) -> str:
    name = (actor or "").strip() or "anonymous"
    return name[:80]


def _load_base_dict(dataset_id: str, cluster_id: str, pack_version: Optional[str] = None) -> dict[str, Any]:
    pack = materials.get_loader().get_pack(dataset_id, cluster_id, pack_version)
    return pack.model_dump(mode="json")


def _list_base_dicts(dataset_id: Optional[str] = None) -> list[dict[str, Any]]:
    return [row.model_dump(mode="json") for row in materials.get_loader().list_packs(dataset_id)]


def _document_text(dataset_id: str, cluster_id: str, document_id: str) -> str:
    return materials.get_loader().get_document_text(dataset_id, cluster_id, document_id)


def list_annotated_packs(dataset_id: Optional[str] = None) -> list[dict[str, Any]]:
    store = get_annotation_store()
    summaries = _list_base_dicts(dataset_id)
    result: list[dict[str, Any]] = []
    for summary in summaries:
        overlay = store.get_overlay(
            summary["dataset_id"],
            summary["cluster_id"],
            summary["pack_version"],
            "review_state",
        )
        if overlay:
            state = overlay["overlay"].get("review_state") or overlay["overlay"].get("value")
            if state in REVIEW_STATES:
                summary["review_state"] = state
        summary["overlay_count"] = store.count_overlays(
            summary["dataset_id"],
            summary["cluster_id"],
            summary["pack_version"],
        )
        result.append(summary)
    return result


def get_annotated_pack(
    dataset_id: str,
    cluster_id: str,
    pack_version: Optional[str] = None,
    include_reference: bool = True,
) -> dict[str, Any]:
    base = _load_base_dict(dataset_id, cluster_id, pack_version)
    store = get_annotation_store()
    overlays = store.list_overlays(base["dataset_id"], base["cluster_id"], base["pack_version"])
    merged = apply_overlays(base, overlays)
    if not include_reference:
        from core.research import strip_reference

        merged = strip_reference(merged)
    documents: list[dict[str, Any]] = []
    for doc in merged.get("documents") or []:
        document_id = str(doc.get("document_id") or "")
        try:
            text = _document_text(dataset_id, cluster_id, document_id)
        except materials.PackNotFoundError:
            text = ""
        documents.append({**doc, "text": text})
    return {
        "pack": merged,
        "documents": documents,
        "pack_version": base["pack_version"],
        "overlay_count": len(overlays),
        "pack_json_unmodified": True,
    }


def get_source_text(
    dataset_id: str,
    cluster_id: str,
    source_id: str,
    pack_version: Optional[str] = None,
) -> dict[str, Any]:
    bundle = get_annotated_pack(dataset_id, cluster_id, pack_version)
    anchor = materials.find_source_anchor(bundle["pack"], source_id)
    document_id = str(anchor.get("document_id") or "")
    document = next((doc for doc in bundle["documents"] if doc.get("document_id") == document_id), None)
    text = document.get("text") if document else _document_text(dataset_id, cluster_id, document_id)
    span = materials.extract_source_span(text or "", anchor)
    span["document_text"] = text or ""
    span["dataset_id"] = dataset_id
    span["cluster_id"] = cluster_id
    span["pack_version"] = bundle["pack_version"]
    return span


def patch_field(
    dataset_id: str,
    cluster_id: str,
    *,
    field_path: str,
    actor: Optional[str] = None,
    note: str = "",
    value: Any = None,
    review_state: Optional[str] = None,
    patch: Optional[dict[str, Any]] = None,
    pack_version: Optional[str] = None,
) -> dict[str, Any]:
    parsed = parse_field_path(field_path)
    state = _validate_review_state(review_state)
    who = _actor_name(actor)
    remark = (note or "")[:2000]

    base = _load_base_dict(dataset_id, cluster_id, pack_version)
    version = base["pack_version"]
    store = get_annotation_store()
    existing_overlays = store.list_overlays(dataset_id, cluster_id, version)
    current = apply_overlays(base, existing_overlays)
    located, primary_key = locate_item(current, field_path)

    overlay: dict[str, Any] = {}
    prior = store.get_overlay(dataset_id, cluster_id, version, field_path)
    if prior and isinstance(prior.get("overlay"), dict):
        overlay.update(prior["overlay"])
    if patch:
        overlay.update({key: val for key, val in patch.items() if not str(key).startswith("_")})
    if value is not None:
        overlay[primary_key] = value
    if state is not None:
        overlay["review_state"] = state

    if not overlay:
        raise AnnotationError("patch is empty: provide value, review_state, or patch")

    from_value = located.get(primary_key) if isinstance(located, dict) else located
    to_value = overlay.get(primary_key, overlay.get("review_state", overlay))
    overlay_state = overlay.get("review_state")
    if overlay_state is not None:
        _validate_review_state(str(overlay_state))

    has_value = value is not None or (patch and any(key != "review_state" for key in patch))
    has_state = state is not None or (patch and "review_state" in patch)
    if has_value and has_state:
        action = "update_field_and_review"
    elif has_state:
        action = "set_review_state"
    else:
        action = "update_field"

    store.upsert_overlay(
        dataset_id=dataset_id,
        cluster_id=cluster_id,
        pack_version=version,
        field_path=field_path,
        item_id=parsed["item_id"],
        overlay=overlay,
        review_state=str(overlay_state) if overlay_state is not None else None,
        actor=who,
    )
    entry = store.append_changelog(
        dataset_id=dataset_id,
        cluster_id=cluster_id,
        pack_version=version,
        field_path=field_path,
        item_id=parsed["item_id"],
        actor=who,
        action=action,
        from_value=from_value,
        to_value=to_value,
        review_state=str(overlay_state) if overlay_state is not None else None,
        note=remark,
    )
    bundle = get_annotated_pack(dataset_id, cluster_id, version)
    item, _ = locate_item(bundle["pack"], field_path)
    return {
        "pack": bundle["pack"],
        "documents": bundle["documents"],
        "pack_version": version,
        "overlay_count": bundle["overlay_count"],
        "pack_json_unmodified": True,
        "field_path": field_path,
        "item": item,
        "change": entry,
    }


def list_change_log(
    dataset_id: str,
    cluster_id: str,
    pack_version: Optional[str] = None,
    limit: int = 200,
) -> dict[str, Any]:
    if pack_version is None:
        base = _load_base_dict(dataset_id, cluster_id)
        pack_version = base["pack_version"]
    else:
        _load_base_dict(dataset_id, cluster_id, pack_version)
    entries = get_annotation_store().list_changelog(dataset_id, cluster_id, pack_version, limit=limit)
    return {
        "dataset_id": dataset_id,
        "cluster_id": cluster_id,
        "pack_version": pack_version,
        "entries": entries,
        "total": len(entries),
    }
