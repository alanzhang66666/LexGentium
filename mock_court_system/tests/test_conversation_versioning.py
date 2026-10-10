"""Regression checks for versioned conversation persistence."""
import sqlite3

import pytest

from core.store.conversation_store import (
    ConcurrentSessionUpdate,
    MemoryConversationStore,
    SqliteConversationStore,
)


@pytest.mark.parametrize("factory", [
    lambda tmp: MemoryConversationStore(),
    lambda tmp: SqliteConversationStore(str(tmp / "conversation.sqlite3")),
])
def test_stale_snapshot_cannot_overwrite_concurrent_message(tmp_path, factory):
    store = factory(tmp_path)
    store.create(session_id="sid", scenario="CI", case_id="case", input_json={})
    first = store.get("sid")
    stale = store.get("sid")
    first.dialog_history.append({"role": "Plaintiff", "message": "first"})
    store.save(first)
    stale.dialog_history.append({"role": "Defendant", "message": "stale"})
    with pytest.raises(ConcurrentSessionUpdate):
        store.save(stale)
    assert store.get("sid").dialog_history == [{"role": "Plaintiff", "message": "first"}]


def test_legacy_sqlite_table_is_migrated_without_data_loss(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE conversations (
            session_id TEXT PRIMARY KEY, scenario TEXT NOT NULL,
            case_id TEXT NOT NULL, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, dialog_history_json TEXT NOT NULL,
            input_json_json TEXT NOT NULL
        )""")
        conn.execute(
            "INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sid", "CI", "case", "2026-01-01Z", "2026-01-01Z", "[]", "{}"),
        )
    store = SqliteConversationStore(str(path))
    rec = store.get("sid")
    assert rec.version == 0
    rec.dialog_history.append({"role": "Judge", "message": "preserved"})
    store.save(rec)
    assert store.get("sid").version == 1
    assert store.get("sid").dialog_history[0]["message"] == "preserved"
