"""Conversation Archive Codec：parse-all-errors → normalized model →
stable pretty print；export-import-export 以 semantic digest 比较。

设计契约（design.md §Conversation Archive Codec）：
- 纯逻辑层，不直接写 DB：parse → validate all → normalized model。
- 错误收集全部可判定 schema violations，每项含 ``path``/``reason``。
- 只有完整验证成功后 importer 才写库；sqlite 导入在单个事务中完成。
- Session ID 策略由 archive 声明：``preserve`` 仅在无冲突时保留；
  ``remap`` 产生映射并同步更新 links / operation references。
- Pretty Printer 使用稳定 key order、UTF-8 与 schema version；
  round trip 比较 normalized semantic digest，不比较无语义空白。
"""
from __future__ import annotations

import copy
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from core.fingerprint import canonical_digest
from core.store.conversation_store import (
    ConversationRecord,
    ConversationStore,
    MemoryConversationStore,
    SqliteConversationStore,
)

SCHEMA_VERSION = "1"
SESSION_POLICIES = ("preserve", "remap")
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class ArchiveValidationError(ValueError):
    """归档解析失败：携带全部 field errors（path + reason）。"""

    def __init__(self, errors: List[Dict[str, str]]):
        self.errors = errors
        super().__init__(f"conversation archive invalid: {len(errors)} error(s)")


class ArchiveImportError(RuntimeError):
    """导入期冲突（如 preserve 撞已有 session）。"""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class ConversationArchive:
    """规范化归档模型；未知字段一律拒绝（extra=forbid 语义）。"""

    session_id: Optional[str] = None
    session_policy: str = "remap"
    scenario: str = ""
    case_id: str = ""
    stage: Optional[str] = None
    created_at: Optional[str] = None
    dialog: List[Dict[str, Any]] = field(default_factory=list)
    links: Dict[str, Any] = field(default_factory=dict)
    input_json: Dict[str, Any] = field(default_factory=dict)
    reasoning: Optional[Dict[str, Any]] = None
    operations: List[Dict[str, str]] = field(default_factory=list)

    def to_normalized_dict(self) -> Dict[str, Any]:
        """稳定形状的规范化 dict（semantic digest 与 pretty print 共用）。"""
        out: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "session_policy": self.session_policy,
            "scenario": self.scenario,
            "case_id": self.case_id,
            "dialog": [
                {"turn": int(m["turn"]), "role": m["role"], "message": m["message"]}
                for m in self.dialog
            ],
            "links": self.links,
            "input_json": self.input_json,
            "operations": [
                {
                    "operation_id": op["operation_id"],
                    "resource_type": op["resource_type"],
                    "resource_id": op["resource_id"],
                }
                for op in self.operations
            ],
        }
        if self.session_id is not None:
            out["session_id"] = self.session_id
        if self.stage is not None:
            out["stage"] = self.stage
        if self.created_at is not None:
            out["created_at"] = self.created_at
        if self.reasoning is not None:
            out["reasoning"] = self.reasoning
        return out


_KNOWN_KEYS = {
    "schema_version",
    "session_id",
    "session_policy",
    "scenario",
    "case_id",
    "stage",
    "created_at",
    "dialog",
    "links",
    "input_json",
    "reasoning",
    "operations",
}
_OP_KEYS = {"operation_id", "resource_type", "resource_id"}
_MSG_KEYS = {"turn", "role", "message"}


class ConversationArchiveCodec:
    """parse-all-errors → normalized ConversationArchive → stable print。"""

    def parse(self, payload: Any) -> ConversationArchive:
        errors: List[Dict[str, str]] = []

        def err(path: str, reason: str) -> None:
            errors.append({"path": path, "reason": reason})

        if isinstance(payload, (str, bytes)):
            try:
                payload = json.loads(payload)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ArchiveValidationError([{"path": "/", "reason": f"invalid json: {exc}"}])

        if not isinstance(payload, dict):
            raise ArchiveValidationError([{"path": "/", "reason": "archive must be an object"}])

        for key in payload:
            if key not in _KNOWN_KEYS:
                err(f"/{key}", "extra")

        version = payload.get("schema_version")
        if version != SCHEMA_VERSION:
            err("/schema_version", "format")

        policy = payload.get("session_policy", "remap")
        if policy not in SESSION_POLICIES:
            err("/session_policy", "format")

        session_id = payload.get("session_id")
        if session_id is not None and not (
            isinstance(session_id, str) and _SESSION_ID_RE.match(session_id)
        ):
            err("/session_id", "format")

        scenario = payload.get("scenario")
        if not isinstance(scenario, str) or not scenario:
            err("/scenario", "required")

        case_id = payload.get("case_id")
        if not isinstance(case_id, str):
            err("/case_id", "type")

        stage = payload.get("stage")
        if stage is not None and not isinstance(stage, str):
            err("/stage", "type")

        created_at = payload.get("created_at")
        if created_at is not None and not isinstance(created_at, str):
            err("/created_at", "type")

        dialog_raw = payload.get("dialog", [])
        dialog: List[Dict[str, Any]] = []
        if not isinstance(dialog_raw, list):
            err("/dialog", "type")
        else:
            for idx, item in enumerate(dialog_raw):
                path = f"/dialog/{idx}"
                if not isinstance(item, dict):
                    err(path, "type")
                    continue
                for key in item:
                    if key not in _MSG_KEYS:
                        err(f"{path}/{key}", "extra")
                turn = item.get("turn")
                if not isinstance(turn, int) or isinstance(turn, bool) or turn < 0:
                    err(f"{path}/turn", "type")
                role = item.get("role")
                if not isinstance(role, str) or not role:
                    err(f"{path}/role", "required")
                message = item.get("message")
                if not isinstance(message, str):
                    err(f"{path}/message", "type")
                if isinstance(turn, int) and not isinstance(turn, bool) and isinstance(role, str) and isinstance(message, str):
                    dialog.append({"turn": turn, "role": role, "message": message})

        links = payload.get("links", {})
        if not isinstance(links, dict):
            err("/links", "type")
            links = {}

        input_json = payload.get("input_json", {})
        if not isinstance(input_json, dict):
            err("/input_json", "type")
            input_json = {}

        reasoning = payload.get("reasoning")
        if reasoning is not None and not isinstance(reasoning, dict):
            err("/reasoning", "type")
            reasoning = None

        operations_raw = payload.get("operations", [])
        operations: List[Dict[str, str]] = []
        if not isinstance(operations_raw, list):
            err("/operations", "type")
        else:
            for idx, op in enumerate(operations_raw):
                path = f"/operations/{idx}"
                if not isinstance(op, dict):
                    err(path, "type")
                    continue
                for key in op:
                    if key not in _OP_KEYS:
                        err(f"{path}/{key}", "extra")
                fixed: Dict[str, str] = {}
                for key in ("operation_id", "resource_type", "resource_id"):
                    value = op.get(key)
                    if not isinstance(value, str) or not value:
                        err(f"{path}/{key}", "required")
                    else:
                        fixed[key] = value
                if len(fixed) == 3:
                    operations.append(fixed)

        if errors:
            raise ArchiveValidationError(errors)

        return ConversationArchive(
            session_id=session_id,
            session_policy=policy,
            scenario=scenario,
            case_id=case_id,
            stage=stage,
            created_at=created_at,
            dialog=dialog,
            links=dict(links),
            input_json=dict(input_json),
            reasoning=reasoning,
            operations=operations,
        )

    def dumps(self, archive: ConversationArchive) -> str:
        """稳定 pretty print：key 排序、UTF-8、schema version 固定。"""
        return json.dumps(
            archive.to_normalized_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

    def semantic_digest(self, archive: ConversationArchive) -> str:
        """normalized semantic digest：export-import-export 比较依据。"""
        return canonical_digest(archive.to_normalized_dict())

    def from_record(self, record: ConversationRecord, *, session_policy: str = "preserve") -> ConversationArchive:
        """从持久化记录导出归档（export 方向）。"""
        input_json = copy.deepcopy(record.input_json or {})
        links = input_json.pop("links", {}) if isinstance(input_json.get("links"), dict) else {}
        reasoning = input_json.pop("reasoning_meta", None) if isinstance(input_json.get("reasoning_meta"), dict) else None
        return ConversationArchive(
            session_id=record.session_id,
            session_policy=session_policy,
            scenario=record.scenario,
            case_id=record.case_id,
            created_at=record.created_at,
            dialog=[
                {
                    "turn": int(m.get("turn", idx)),
                    "role": m.get("role", ""),
                    "message": m.get("message", ""),
                }
                for idx, m in enumerate(record.dialog_history or [])
            ],
            links=links,
            input_json=input_json,
            reasoning=reasoning,
        )


def _remap_string_refs(value: Any, id_map: Dict[str, str]) -> Any:
    """递归重写结构中引用旧 session_id 的字符串值。"""
    if not id_map:
        return value
    if isinstance(value, str):
        return id_map.get(value, value)
    if isinstance(value, list):
        return [_remap_string_refs(v, id_map) for v in value]
    if isinstance(value, dict):
        return {k: _remap_string_refs(v, id_map) for k, v in value.items()}
    return value


def default_session_id_generator() -> str:
    return str(uuid.uuid4())


class ConversationArchiveImporter:
    """验证成功后的事务导入器；自身不重复 schema 校验。"""

    def __init__(self, store: ConversationStore):
        self.store = store

    def import_archive(
        self,
        archive: ConversationArchive,
        *,
        session_id_generator: Callable[[], str] = default_session_id_generator,
    ) -> Dict[str, Any]:
        id_map: Dict[str, str] = {}
        if archive.session_policy == "preserve" and archive.session_id:
            if self.store.get(archive.session_id) is not None:
                raise ArchiveImportError(
                    "session_id_conflict",
                    f"session {archive.session_id} already exists; use remap policy",
                )
            session_id = archive.session_id
        else:
            session_id = session_id_generator()
            if archive.session_id:
                id_map[archive.session_id] = session_id

        input_json = _remap_string_refs(copy.deepcopy(archive.input_json), id_map)
        links = _remap_string_refs(copy.deepcopy(archive.links), id_map)
        if links:
            input_json["links"] = links
        if archive.reasoning is not None:
            input_json["reasoning_meta"] = _remap_string_refs(copy.deepcopy(archive.reasoning), id_map)

        dialog = _remap_string_refs(copy.deepcopy(archive.dialog), id_map)
        operations = _remap_string_refs(copy.deepcopy(archive.operations), id_map)
        if operations:
            input_json["operations"] = operations

        record = ConversationRecord(
            session_id=session_id,
            scenario=archive.scenario,
            case_id=archive.case_id,
            created_at=archive.created_at or "",
            updated_at=archive.created_at or "",
            dialog_history=dialog,
            input_json=input_json,
        )

        if isinstance(self.store, SqliteConversationStore):
            self._import_sqlite(record)
        elif isinstance(self.store, MemoryConversationStore):
            self._import_memory(record)
        else:
            rec = self.store.create(
                session_id=session_id,
                scenario=archive.scenario,
                case_id=archive.case_id,
                input_json=input_json,
            )
            rec.dialog_history = dialog
            self.store.save(rec)

        return {"session_id": session_id, "id_map": id_map}

    def _import_sqlite(self, record: ConversationRecord) -> None:
        """单事务写入：校验已通过，INSERT 失败整体回滚。"""
        created = record.created_at or _now_iso()
        with self.store._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO conversations(session_id, scenario, case_id, created_at, updated_at, dialog_history_json, input_json_json)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.session_id,
                    record.scenario,
                    record.case_id,
                    created,
                    created,
                    json.dumps(record.dialog_history, ensure_ascii=False),
                    json.dumps(record.input_json, ensure_ascii=False),
                ),
            )

    def _import_memory(self, record: ConversationRecord) -> None:
        now = _now_iso()
        record.created_at = record.created_at or now
        record.updated_at = record.updated_at or now
        self.store._sessions[record.session_id] = record


def _now_iso() -> str:
    from datetime import datetime

    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
