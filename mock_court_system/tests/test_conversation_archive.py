"""Conversation Archive Codec：parse-all-errors、pretty print 往返、
preserve/remap 身份策略、事务导入与 invalid 不改指纹。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.archive.conversation import (
    ArchiveImportError,
    ArchiveValidationError,
    ConversationArchiveCodec,
    ConversationArchiveImporter,
)
from core.fingerprint import canonical_digest, tables_fingerprint
from core.store.conversation_store import MemoryConversationStore, SqliteConversationStore


@pytest.fixture
def codec() -> ConversationArchiveCodec:
    return ConversationArchiveCodec()


def _doc(**overrides):
    doc = {
        "schema_version": "1",
        "session_id": "sess-old-1",
        "session_policy": "remap",
        "scenario": "CI",
        "case_id": "case-1",
        "stage": "hearing",
        "dialog": [
            {"turn": 0, "role": "Judge", "message": "现在开庭。"},
            {"turn": 1, "role": "Plaintiff", "message": "到庭。"},
        ],
        "links": {"derived_from": "sess-old-1"},
        "input_json": {"research": {"run_id": "sess-old-1"}},
        "reasoning": {"state_machine": {"state": "OPENING"}},
        "operations": [
            {"operation_id": "op-1", "resource_type": "session", "resource_id": "sess-old-1"}
        ],
    }
    doc.update(overrides)
    return doc


class TestParseAllErrors:
    def test_valid_document_round_trips(self, codec):
        archive = codec.parse(_doc())
        assert archive.scenario == "CI"
        assert len(archive.dialog) == 2
        assert archive.operations[0]["operation_id"] == "op-1"

    def test_collects_all_errors_not_first(self, codec):
        doc = _doc()
        doc["scenario"] = ""
        doc["session_policy"] = "bogus"
        doc["dialog"] = [{"turn": "x", "role": "", "message": 1}]
        doc["extra_field"] = 1
        with pytest.raises(ArchiveValidationError) as ei:
            codec.parse(doc)
        paths = {e["path"] for e in ei.value.errors}
        assert "/scenario" in paths
        assert "/session_policy" in paths
        assert "/extra_field" in paths
        assert any(p.startswith("/dialog/0") for p in paths)
        assert len(ei.value.errors) >= 5

    def test_rejects_non_json_and_non_object(self, codec):
        with pytest.raises(ArchiveValidationError):
            codec.parse("{not json")
        with pytest.raises(ArchiveValidationError):
            codec.parse([1, 2, 3])

    def test_rejects_wrong_schema_version(self, codec):
        with pytest.raises(ArchiveValidationError) as ei:
            codec.parse(_doc(schema_version="2"))
        assert ei.value.errors[0]["path"] == "/schema_version"


class TestPrettyPrintRoundTrip:
    def test_export_import_export_semantic_digest_equal(self, codec):
        archive = codec.parse(_doc())
        printed = codec.dumps(archive)
        reparsed = codec.parse(printed)
        assert codec.semantic_digest(reparsed) == codec.semantic_digest(archive)
        assert codec.dumps(reparsed) == printed

    def test_whitespace_does_not_change_digest(self, codec):
        compact = '{"schema_version":"1","scenario":"CI","case_id":"c","dialog":[],"session_policy":"remap"}'
        pretty = codec.dumps(codec.parse(compact))
        assert codec.semantic_digest(codec.parse(compact)) == codec.semantic_digest(codec.parse(pretty))


class TestImport:
    def test_remap_mints_new_id_and_rewrites_references(self, codec):
        store = MemoryConversationStore()
        archive = codec.parse(_doc(session_policy="remap"))
        result = ConversationArchiveImporter(store).import_archive(
            archive, session_id_generator=lambda: "sess-new-9"
        )
        assert result["session_id"] == "sess-new-9"
        assert result["id_map"] == {"sess-old-1": "sess-new-9"}
        record = store.get("sess-new-9")
        assert record is not None
        assert record.input_json["links"]["derived_from"] == "sess-new-9"
        assert record.input_json["research"]["run_id"] == "sess-new-9"
        assert record.input_json["operations"][0]["resource_id"] == "sess-new-9"

    def test_preserve_keeps_id_when_no_conflict(self, codec):
        store = MemoryConversationStore()
        archive = codec.parse(_doc(session_policy="preserve"))
        result = ConversationArchiveImporter(store).import_archive(archive)
        assert result["session_id"] == "sess-old-1"
        assert result["id_map"] == {}
        record = store.get("sess-old-1")
        assert record.input_json["links"]["derived_from"] == "sess-old-1"

    def test_preserve_conflict_raises_without_write(self, codec):
        store = MemoryConversationStore()
        archive = codec.parse(_doc(session_policy="preserve"))
        importer = ConversationArchiveImporter(store)
        importer.import_archive(archive)
        with pytest.raises(ArchiveImportError) as ei:
            importer.import_archive(archive)
        assert ei.value.code == "session_id_conflict"
        assert store.get("sess-old-1") is not None

    def test_invalid_archive_does_not_change_record_count_or_fingerprint(self, codec, tmp_path):
        store = SqliteConversationStore(str(tmp_path / "conv.sqlite3"))
        importer = ConversationArchiveImporter(store)
        before_count = store.list(limit=100, offset=0)[1]

        conn = store._connect()
        before_fp = tables_fingerprint(conn, ["conversations"])
        conn.close()

        with pytest.raises(ArchiveValidationError):
            codec.parse(_doc(scenario="", dialog="nope"))
        with pytest.raises(ArchiveImportError):
            good = codec.parse(_doc(session_policy="preserve"))
            importer.import_archive(good)
            importer.import_archive(good)

        conn = store._connect()
        after_fp = tables_fingerprint(conn, ["conversations"])
        conn.close()
        # 一次成功导入 + 一次失败冲突导入 → 恰一行变化，失败那次无部分写入
        after_count = store.list(limit=100, offset=0)[1]
        assert before_count == 0
        assert after_count == 1
        assert before_fp != after_fp

    def test_dialog_and_unknown_fields_preserved(self, codec):
        store = MemoryConversationStore()
        doc = _doc(input_json={"research": {"dataset_id": "d", "unknown_fact": None}, "links": {}})
        archive = codec.parse(doc)
        ConversationArchiveImporter(store).import_archive(
            archive, session_id_generator=lambda: "s1"
        )
        record = store.get("s1")
        assert record.dialog_history[0]["role"] == "Judge"
        assert record.input_json["research"]["unknown_fact"] is None
        assert record.input_json["reasoning_meta"]["state_machine"]["state"] == "OPENING"

    def test_export_from_record_round_trip(self, codec):
        store = MemoryConversationStore()
        archive = codec.parse(_doc())
        ConversationArchiveImporter(store).import_archive(
            archive, session_id_generator=lambda: "s-exp"
        )
        record = store.get("s-exp")
        exported = codec.from_record(record, session_policy="preserve")
        assert exported.scenario == "CI"
        assert exported.dialog[1]["message"] == "到庭。"
        reprinted = codec.parse(codec.dumps(exported))
        assert codec.semantic_digest(reprinted) == codec.semantic_digest(exported)
