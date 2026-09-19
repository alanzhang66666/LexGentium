"""Runtime restart / CheckpointV2 / RuntimeUnitOfWork 集成测试（Task 5.2）。

验收：turn 的 checkpoint/session/operation/number/fingerprint 原子一致；
失败保留上一 fingerprint；重启后从最高 committed turn 恢复；v1 双读。
"""
from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

_PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(_PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PRODUCT_ROOT))

from core.graphs.checkpoint import SqliteCheckpointStore  # noqa: E402
from core.store.conversation_store import SqliteConversationStore  # noqa: E402
from core.store.operation_store import OperationStore, canonical_digest  # noqa: E402
from api.services.runtime_unit_of_work import (  # noqa: E402
    OperationStateError,
    RuntimeUnitOfWork,
)


@pytest.fixture
def stores(tmp_path):
    cp = SqliteCheckpointStore(str(tmp_path / "checkpoints.sqlite3"))
    ops = OperationStore(str(tmp_path / "operations.sqlite3"))
    conv = SqliteConversationStore(str(tmp_path / "conversations.sqlite3"))
    return cp, ops, conv


class TestCheckpointV2:
    def test_save_load_roundtrip_via_compat_api(self, tmp_path):
        store = SqliteCheckpointStore(str(tmp_path / "cp.sqlite3"))
        store.save("t1", {"stage": "CD", "turn": 0})
        store.save("t1", {"stage": "CD", "turn": 1})
        assert store.load("t1") == {"stage": "CD", "turn": 1}
        head = store.head_v2("t1")
        assert head.turn_number == 1
        # 双读：v1 表未被新写入触碰
        conn = sqlite3.connect(store.path)
        assert conn.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] == 0
        conn.close()

    def test_dual_read_v1_fallback(self, tmp_path):
        store = SqliteCheckpointStore(str(tmp_path / "cp.sqlite3"))
        # 手工写一行旧 v1 checkpoint
        conn = sqlite3.connect(store.path)
        conn.execute(
            "INSERT INTO checkpoints(thread_id, payload, updated_at) VALUES (?,?,0)",
            ("legacy", json.dumps({"old": True})),
        )
        conn.commit()
        conn.close()
        assert store.load("legacy") == {"old": True}
        # v2 head 优先于 v1
        store.save_v2("legacy", 0, {"new": True})
        assert store.load("legacy") == {"new": True}

    def test_v2_rows_carry_identity(self, tmp_path):
        store = SqliteCheckpointStore(str(tmp_path / "cp.sqlite3"))
        store.save_v2("t9", 3, {"x": 1}, state_fingerprint="fp-3", operation_id="op-9")
        head = store.head_v2("t9")
        assert head.state_fingerprint == "fp-3"
        assert head.operation_id == "op-9"
        assert head.turn_number == 3

    def test_restart_recovers_highest_committed_turn(self, tmp_path):
        path = str(tmp_path / "cp.sqlite3")
        store = SqliteCheckpointStore(path)
        store.save_v2("sess", 0, {"stage": "CD"}, state_fingerprint="fp0")
        store.save_v2("sess", 1, {"stage": "DD"}, state_fingerprint="fp1")
        # 重启 = 新实例同一文件
        reopened = SqliteCheckpointStore(path)
        head = reopened.head_v2("sess")
        assert head.turn_number == 1
        assert head.payload == {"stage": "DD"}
        assert head.state_fingerprint == "fp1"


class TestRuntimeUnitOfWork:
    def test_atomic_commit_all_three_stores(self, stores):
        cp, ops, conv = stores
        rec = conv.create(session_id="s1", scenario="CD", case_id="c1", input_json={})
        ops.begin_operation("op-1", "conversation.message", canonical_digest({"m": 1}), {})

        rec.dialog_history = [{"turn": 0, "role": "Client", "message": "hi"}]
        fp = canonical_digest(rec.dialog_history)
        with RuntimeUnitOfWork(cp, operation_store=ops, conversation_store=conv) as uow:
            uow.save_conversation(rec)
            uow.commit_operation("op-1", "conversation_message", "s1:1", "dig", fp)
            uow.save_checkpoint(
                "conversation:s1", 1, {"dialog_history": rec.dialog_history},
                state_fingerprint=fp, operation_id="op-1",
            )

        assert conv.get("s1").dialog_history[0]["message"] == "hi"
        op = ops.get("op-1")
        assert op.status == "committed"
        assert op.state_fingerprint_after == fp
        head = cp.head_v2("conversation:s1")
        assert head.turn_number == 1
        assert head.state_fingerprint == fp

    def test_failure_rolls_back_and_preserves_fingerprint(self, stores):
        cp, ops, conv = stores
        rec = conv.create(session_id="s2", scenario="CD", case_id="c1", input_json={})
        ops.begin_operation("op-2", "conversation.message", canonical_digest({"m": 1}), {})

        with RuntimeUnitOfWork(cp, operation_store=ops, conversation_store=conv) as uow:
            uow.save_checkpoint("conversation:s2", 0, {"v": 0}, state_fingerprint="fp-good")
            uow.save_conversation(rec)

        rec.dialog_history = [{"turn": 1, "role": "Client", "message": "bad turn"}]
        with pytest.raises(RuntimeError):
            with RuntimeUnitOfWork(cp, operation_store=ops, conversation_store=conv) as uow:
                uow.save_conversation(rec)
                uow.save_checkpoint("conversation:s2", 1, {"v": 1}, state_fingerprint="fp-bad")
                uow.commit_operation("op-2", "conversation_message", "s2:1", "dig", "fp-bad")
                raise RuntimeError("simulated mid-commit failure")

        # 回滚：checkpoint head 仍是 fp-good，会话未更新，operation 未提交
        assert cp.head_v2("conversation:s2").state_fingerprint == "fp-good"
        assert conv.get("s2").dialog_history == []
        assert ops.get("op-2").status == "accepted"

    def test_commit_rejects_non_active_operation(self, stores):
        cp, ops, conv = stores
        ops.begin_operation("op-3", "k", "d", {})
        ops.fail_operation("op-3", "x", retriable=True)
        with pytest.raises(OperationStateError):
            with RuntimeUnitOfWork(cp, operation_store=ops) as uow:
                uow.commit_operation("op-3", "r", "id", "d", "fp")

    def test_commit_idempotent_replay(self, stores):
        cp, ops, _ = stores
        ops.begin_operation("op-4", "k", "d", {})
        with RuntimeUnitOfWork(cp, operation_store=ops) as uow:
            uow.commit_operation("op-4", "r", "id", "dig", "fp")
        with RuntimeUnitOfWork(cp, operation_store=ops) as uow:
            uow.commit_operation("op-4", "r", "id", "dig", "fp")  # 同结果回放不报错
        assert ops.get("op-4").commit_count == 1


class TestRuntimeSessionIsolation:
    def test_distinct_sessions_isolated_checkpoints(self, tmp_path):
        store = SqliteCheckpointStore(str(tmp_path / "cp.sqlite3"))
        for i in range(10):
            store.save_v2(f"sess-{i}", 0, {"turn": 0, "session": i})
        for i in range(10):
            head = store.head_v2(f"sess-{i}")
            assert head.payload["session"] == i
