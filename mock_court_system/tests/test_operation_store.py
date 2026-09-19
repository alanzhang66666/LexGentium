"""OperationStore 状态机与幂等测试（Task 4.1）。"""
from __future__ import annotations

import threading

import pytest

from core.store.operation_store import (
    OperationConflict,
    OperationStateError,
    OperationStore,
    canonical_digest,
    derive_operation_id,
)


@pytest.fixture()
def store(tmp_path):
    return OperationStore(str(tmp_path / "ops.sqlite3"))


def _digest(n: int) -> str:
    return canonical_digest({"input": n})


def test_begin_accepts_and_replays_same_digest(store):
    first = store.begin_operation("op-1", "conversation.start", _digest(1))
    assert first.outcome == "accepted"
    replay = store.begin_operation("op-1", "conversation.start", _digest(1))
    assert replay.outcome == "existing"
    assert replay.record.operation_id == "op-1"


def test_begin_conflict_on_different_digest(store):
    store.begin_operation("op-1", "conversation.start", _digest(1))
    conflict = store.begin_operation("op-1", "conversation.start", _digest(2))
    assert conflict.outcome == "conflict"


def test_commit_exactly_once_and_replay(store):
    store.begin_operation("op-1", "conversation.message", _digest(1))
    store.mark_running("op-1", config_identity="cfg-1")
    committed = store.commit_operation(
        "op-1", "conversation", "sess-1", "result-digest", "fp-after"
    )
    assert committed.status == "committed"
    assert committed.commit_count == 1
    # 相同资源/结果重试 -> 回放，commit_count 不变
    replay = store.commit_operation(
        "op-1", "conversation", "sess-1", "result-digest", "fp-after"
    )
    assert replay.commit_count == 1
    # 不同结果重试 -> 状态错误
    with pytest.raises(OperationStateError):
        store.commit_operation("op-1", "conversation", "sess-2", "other", "fp-x")


def test_committed_operation_is_immutable(store):
    store.begin_operation("op-1", "conversation.message", _digest(1))
    store.commit_operation("op-1", "conversation", "sess-1", "d", "fp")
    # fail/cancel 不得改变 committed 状态
    rec = store.fail_operation("op-1", "internal_error")
    assert rec.status == "committed"
    rec = store.cancel_operation("op-1")
    assert rec.status == "committed"
    rec = store.mark_running("op-1")
    assert rec.status == "committed"


def test_fail_and_cancel_terminal_states(store):
    store.begin_operation("op-f", "evaluate", _digest(1))
    rec = store.fail_operation("op-f", "llm_timeout", retriable=True)
    assert rec.status == "failed"
    assert rec.terminal_type == "error"
    assert rec.retriable is True
    # 失败后不能再 commit
    with pytest.raises(OperationStateError):
        store.commit_operation("op-f", "report", "r1", "d", "fp")

    store.begin_operation("op-c", "conversation.message", _digest(2))
    store.mark_running("op-c")
    rec = store.cancel_operation("op-c", before_commit=True)
    assert rec.status == "cancelled"
    assert rec.terminal_type == "cancelled"
    assert rec.commit_count == 0


def test_concurrent_commit_single_winner(store):
    store.begin_operation("op-race", "evaluate", _digest(1))
    store.mark_running("op-race")
    results = []
    errors = []

    def attempt(i):
        try:
            results.append(
                store.commit_operation("op-race", "report", "r1", "d", f"fp-{i}")
            )
        except OperationStateError as e:
            errors.append(e)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rec = store.get("op-race")
    assert rec.commit_count == 1
    assert rec.status == "committed"
    # 只有一个不同 fingerprint 可以胜出；相同 fingerprint 的调用按回放成功
    assert len(results) + len(errors) == 8


def test_derived_operation_ids_are_stable(store):
    assert derive_operation_id("op-parent", "step-3") == "op-parent:step-3"
    assert derive_operation_id("op-parent", "step-3") == derive_operation_id("op-parent", "step-3")


def test_llm_call_counter(store):
    store.begin_operation("op-llm", "ci.turn", _digest(1))
    store.record_llm_call("op-llm")
    store.record_llm_call("op-llm", 2)
    assert store.get("op-llm").llm_call_count == 3


def test_canonical_digest_stable_and_order_insensitive():
    a = canonical_digest({"b": 2, "a": {"d": 1, "c": [1, 2]}})
    b = canonical_digest({"a": {"c": [1, 2], "d": 1}, "b": 2})
    assert a == b
    assert canonical_digest({"a": 1}) != canonical_digest({"a": 2})
