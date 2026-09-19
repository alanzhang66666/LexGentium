"""SSE lifecycle: coordinator begin/commit/cancel/disconnect semantics."""
from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

_PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(_PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PRODUCT_ROOT))

from api.observability.metrics import MetricsRegistry
from api.services.operation_coordinator import (
    CommitCapabilityLost,
    OperationCoordinator,
    OperationCancelled,
)
from core.store.operation_store import OperationConflict, OperationStore


def _coordinator(tmp_path, **kw):
    store = OperationStore(str(tmp_path / f"ops-{uuid.uuid4().hex}.sqlite3"))
    metrics = MetricsRegistry()
    return OperationCoordinator(store, metrics=metrics, **kw), store, metrics


def _payload():
    return {"session_id": "s-1", "message": "hello"}


def test_first_event_is_start_and_immediate(tmp_path):
    coordinator, _, _ = _coordinator(tmp_path)
    before = time.monotonic()
    handle = coordinator.begin("op-1", "conversation_message", _payload(), "req-1")
    elapsed = time.monotonic() - before

    assert elapsed < 1.0
    assert len(handle.frames) == 1
    frame = handle.frames[0]
    assert 'event: start' in frame
    assert '"sequence": 0' in frame or '"sequence":0' in frame
    assert handle.record.status == "accepted"


def test_terminal_cas_and_duplicate_metric(tmp_path):
    coordinator, _, metrics = _coordinator(tmp_path)
    handle = coordinator.begin("op-2", "conversation_message", _payload(), "req-2")

    assert coordinator.emit(handle, "delta", text="a") is not None
    assert coordinator.emit(handle, "complete", text="done") is not None
    # Second terminal is ignored and counted.
    assert coordinator.emit(handle, "complete", text="again") is None
    assert coordinator.emit(handle, "error", error={"code": "x"}) is None
    assert handle.encoder.lifecycle.terminal_type == "complete"
    assert handle.encoder.lifecycle.duplicate_terminal_count == 2
    assert metrics.sse_duplicate_terminal.value({"type": "complete"}) == 1
    assert metrics.sse_duplicate_terminal.value({"type": "error"}) == 1
    # Non-terminal events are also rejected after terminal.
    assert coordinator.emit(handle, "delta", text="late") is None


def test_pre_commit_disconnect_cancels_within_grace(tmp_path):
    coordinator, store, _ = _coordinator(tmp_path)
    handle = coordinator.begin("op-3", "conversation_message", _payload(), "req-3",
                               state_fingerprint="fp-before")
    coordinator.mark_running(handle)

    stopped = threading.Event()

    def worker():
        try:
            while not handle.token.cancelled:
                handle.token.wait(0.05)
        finally:
            stopped.set()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    outcome = coordinator.disconnect("op-3")
    assert outcome == "cancelled_before_commit"
    assert stopped.wait(timeout=coordinator.cancel_grace_s)
    record = store.get("op-3")
    assert record.status == "cancelled"
    assert record.commit_count == 0
    assert record.state_fingerprint_after is None
    assert record.state_fingerprint_before == "fp-before"


def test_late_worker_loses_commit_capability(tmp_path):
    coordinator, store, _ = _coordinator(tmp_path)
    handle = coordinator.begin("op-4", "conversation_message", _payload(), "req-4")

    coordinator.disconnect("op-4")
    with pytest.raises(CommitCapabilityLost):
        coordinator.commit(handle, "session", "s-1", "digest", "fp-after")
    record = store.get("op-4")
    assert record.status == "cancelled"
    assert record.commit_count == 0


def test_post_commit_disconnect_retains_result(tmp_path):
    coordinator, store, _ = _coordinator(tmp_path)
    handle = coordinator.begin("op-5", "conversation_message", _payload(), "req-5")
    coordinator.commit(handle, "session", "s-1", "result-digest", "fp-after")

    outcome = coordinator.disconnect("op-5")
    assert outcome == "detached_after_commit"
    record = store.get("op-5")
    assert record.status == "committed"
    assert record.commit_count == 1
    assert record.result_digest == "result-digest"
    assert record.state_fingerprint_after == "fp-after"


def test_retry_after_commit_replays_without_duplicate(tmp_path):
    coordinator, store, metrics = _coordinator(tmp_path)
    handle = coordinator.begin("op-6", "conversation_message", _payload(), "req-6")
    coordinator.commit(handle, "session", "s-1", "result-digest", "fp-after")

    replayed = coordinator.replay("op-6")
    assert replayed is not None
    assert replayed.resource_id == "s-1"
    assert replayed.result_digest == "result-digest"

    # Retried begin returns the same committed handle — no second LLM/final.
    again = coordinator.begin("op-6", "conversation_message", _payload(), "req-6b")
    assert again.replayed is True
    assert again.record.commit_count == 1
    assert again.record.llm_call_count == 0
    assert len(again.frames) == 0  # no new start frame for replay


def test_conflicting_input_digest_rejected(tmp_path):
    coordinator, _, _ = _coordinator(tmp_path)
    coordinator.begin("op-7", "conversation_message", _payload(), "req-7")
    with pytest.raises(OperationConflict):
        coordinator.begin("op-7", "conversation_message", {"different": True}, "req-7b")


def test_unknown_disconnect_is_harmless(tmp_path):
    coordinator, _, _ = _coordinator(tmp_path)
    assert coordinator.disconnect("op-missing") == "unknown_operation"


def test_cancelled_token_raises_inside_worker(tmp_path):
    coordinator, _, _ = _coordinator(tmp_path)
    handle = coordinator.begin("op-8", "conversation_message", _payload(), "req-8")
    coordinator.disconnect("op-8")
    with pytest.raises(OperationCancelled):
        handle.token.throw_if_cancelled()
