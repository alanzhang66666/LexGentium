"""Operation ledger 属性测试。

覆盖 Properties 7, 19, 23。
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.store.operation_store import (  # noqa: E402
    OperationStateError,
    OperationStore,
)


def _store(tmp_path_factory) -> OperationStore:
    # Hypothesis 示例共享 function-scope fixture → 每例独立 DB 目录
    return OperationStore(str(Path(tmp_path_factory.mktemp("ops")) / "ops.sqlite3"))


# ---------- Property 7: Operation ID 幂等 ----------


@given(digest_a=st.text(min_size=1, max_size=32), digest_b=st.text(min_size=1, max_size=32))
@settings(max_examples=15)
def test_property_7_operation_id_idempotent_replay(tmp_path_factory, digest_a, digest_b):
    store = _store(tmp_path_factory)
    r1 = store.begin_operation("op1", "conversation_stream", digest_a)
    assert r1.outcome == "accepted"
    # 同 ID + 同 digest → 回放，不产生第二条记录
    r2 = store.begin_operation("op1", "conversation_stream", digest_a)
    assert r2.outcome == "existing"
    assert r2.record.operation_id == r1.record.operation_id
    # 同 ID + 异 digest → conflict（调用方映射 409）
    if digest_b != digest_a:
        r3 = store.begin_operation("op1", "conversation_stream", digest_b)
        assert r3.outcome == "conflict"


# ---------- Property 19: commit 边界恰一次 ----------


@given(n_commits=st.integers(min_value=1, max_value=5))
@settings(max_examples=10)
def test_property_19_commit_exactly_once(tmp_path_factory, n_commits):
    store = _store(tmp_path_factory)
    store.begin_operation("op1", "conversation_stream", "d")
    store.mark_running("op1")
    rec = store.commit_operation("op1", "session", "s1", "digest", "fp")
    assert rec.commit_count == 1
    for _ in range(n_commits - 1):
        # 同资源同 digest → 幂等回放，commit_count 不增
        again = store.commit_operation("op1", "session", "s1", "digest", "fp")
        assert again.commit_count == 1
    # 不同结果 → 拒绝
    with pytest.raises(OperationStateError):
        store.commit_operation("op1", "session", "s1", "other", "fp")


def test_property_19_concurrent_commits_single_winner(tmp_path):
    store = OperationStore(str(tmp_path / "ops.sqlite3"))
    store.begin_operation("op1", "conversation_stream", "d")
    winners, errors = [], []

    def commit(i):
        try:
            winners.append(store.commit_operation("op1", "s", f"r{i}", "dg", "fp"))
        except OperationStateError as e:
            errors.append(e)

    threads = [threading.Thread(target=commit, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    final = store.get("op1")
    assert final.commit_count == 1
    assert final.status == "committed"
    assert len(errors) >= 1 or len({w.resource_id for w in winners}) == 1


# ---------- Property 23: 持久化失败不改已提交状态 ----------


def test_property_23_committed_state_immutable_under_failure(tmp_path):
    store = OperationStore(str(tmp_path / "ops.sqlite3"))
    store.begin_operation("op1", "k", "d")
    store.commit_operation("op1", "s", "r", "dg", "fp")
    committed = store.get("op1")
    # committed 后 fail/cancel/重新 mark_running 均不改变终态
    assert store.fail_operation("op1", "late_error").status == "committed"
    assert store.cancel_operation("op1").status == "committed"
    assert store.mark_running("op1").status == "committed"
    after = store.get("op1")
    assert after == committed
    assert after.commit_count == 1
