"""OperationCoordinator: operation ledger + stream lifecycle + cancellation.

Design contract (release-readiness design §3-4):

- ``begin`` registers the operation and emits the ``start`` event
  synchronously, so the first stream event is always well under 1s.
- A client disconnect triggers the operation's cancellation token. If no
  domain commit has happened, the worker must observe the token and stop
  within ``cancel_grace_s`` (5s) and the record becomes
  ``cancelled_before_commit`` with the state fingerprint unchanged. If the
  commit already happened the result is retained and only delivery stops.
- A worker that finishes after a pre-commit cancel has lost commit
  capability: ``commit`` raises ``CommitCapabilityLost`` and writes nothing.
- Committed operations replay their resource/result on retry without
  repeating the LLM work or the final event.
- Terminal events are compare-and-set through ``StreamLifecycle``; each
  ignored duplicate terminal increments
  ``lexgentium_sse_duplicate_terminal_total{type}``.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from api.observability.metrics import MetricsRegistry
from api.services.sse import SseEncoder
from core.store.operation_store import (
    BeginResult,
    OperationConflict,
    OperationRecord,
    OperationStore,
    canonical_digest,
)

DEFAULT_CANCEL_GRACE_S = 5.0


class OperationCancelled(Exception):
    """Raised inside cooperative workers when the token is cancelled."""


class CommitCapabilityLost(Exception):
    """Raised when a late worker tries to commit after pre-commit cancel."""


class CancellationToken:
    """Cooperative cancellation for workers running third-party sync SDKs."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float) -> bool:
        """Sleep up to ``timeout``; returns True when cancelled early."""
        return self._event.wait(timeout)

    def throw_if_cancelled(self) -> None:
        if self.cancelled:
            raise OperationCancelled()


@dataclass
class OperationHandle:
    """Per-operation stream surface handed to the route/worker pair."""

    operation_id: str
    request_id: str
    record: OperationRecord
    replayed: bool
    encoder: SseEncoder
    token: CancellationToken
    frames: List[str] = field(default_factory=list)

    @property
    def terminal_type(self) -> Optional[str]:
        return self.encoder.lifecycle.terminal_type


class OperationCoordinator:
    def __init__(
        self,
        store: OperationStore,
        *,
        metrics: Optional[MetricsRegistry] = None,
        cancel_grace_s: float = DEFAULT_CANCEL_GRACE_S,
        clock=time.monotonic,
    ) -> None:
        self.store = store
        self.metrics = metrics or MetricsRegistry()
        self.cancel_grace_s = float(cancel_grace_s)
        self._clock = clock
        self._lock = threading.Lock()
        self._handles: Dict[str, OperationHandle] = {}

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def begin(
        self,
        operation_id: str,
        kind: str,
        payload: Any,
        request_id: str,
        *,
        state_fingerprint: str = "",
    ) -> OperationHandle:
        """Register the operation; emits the ``start`` frame immediately.

        The store arbitrates first so a retry with a different input digest
        is rejected even when a live handle is cached. A committed operation
        yields a replayed handle with no frames — the caller serves the
        stored result instead of running work again.
        """
        result: BeginResult = self.store.begin_operation(
            operation_id,
            kind,
            canonical_digest(payload),
            {"request_id": request_id},
            state_fingerprint_before=state_fingerprint,
        )
        if result.outcome == "conflict":
            raise OperationConflict(operation_id)
        record = result.record

        if result.outcome == "existing" and record.status == "committed":
            return OperationHandle(
                operation_id=operation_id,
                request_id=request_id,
                record=record,
                replayed=True,
                encoder=SseEncoder(operation_id=operation_id, request_id=request_id),
                token=CancellationToken(),
            )

        with self._lock:
            existing = self._handles.get(operation_id)
            if existing is not None:
                return existing
            encoder = SseEncoder(operation_id=operation_id, request_id=request_id)
            handle = OperationHandle(
                operation_id=operation_id,
                request_id=request_id,
                record=record,
                replayed=False,
                encoder=encoder,
                token=CancellationToken(),
            )
            self._handles[operation_id] = handle

        # First event goes out synchronously at accept time (<=1s budget).
        frame = encoder.emit("start", resource=None)
        if frame is not None:
            handle.frames.append(frame)
        return handle

    def mark_running(self, handle: OperationHandle, config_identity: Optional[str] = None) -> None:
        handle.record = self.store.mark_running(handle.operation_id, config_identity)

    def emit(self, handle: OperationHandle, type: str, **fields: Any) -> Optional[str]:
        """Encode one event; ignored duplicate terminals bump the metric."""
        was_terminal_candidate = type in ("complete", "error", "cancelled")
        frame = handle.encoder.emit(type, **fields)
        if frame is None:
            if was_terminal_candidate:
                self.metrics.sse_duplicate_terminal.inc(labels={"type": type})
            return None
        handle.frames.append(frame)
        return frame

    def emit_domain(self, handle: OperationHandle, type: str, data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """域事件 → envelope；被忽略的重复 terminal 计入 metric。"""
        terminal_candidate = type in ("final", "simulation_complete", "round_complete", "error", "cancelled")
        frame = handle.encoder.emit_domain(type, data)
        if frame is None:
            if terminal_candidate:
                self.metrics.sse_duplicate_terminal.inc(labels={"type": type})
            return None
        handle.frames.append(frame)
        return frame

    def commit(
        self,
        handle: OperationHandle,
        resource_type: str,
        resource_id: str,
        result_digest: str,
        state_fingerprint_after: str,
    ) -> OperationRecord:
        """Commit exactly once; late workers after cancel are rejected."""
        if handle.token.cancelled:
            raise CommitCapabilityLost(handle.operation_id)
        record = self.store.commit_operation(
            handle.operation_id,
            resource_type=resource_type,
            resource_id=resource_id,
            result_digest=result_digest,
            state_fingerprint=state_fingerprint_after,
        )
        handle.record = record
        return record

    def fail(self, handle: OperationHandle, error_code: str, retriable: bool) -> OperationRecord:
        record = self.store.fail_operation(handle.operation_id, error_code, retriable)
        handle.record = record
        return record

    def disconnect(self, operation_id: str) -> str:
        """Client disconnect: cancel the token, split on the commit boundary.

        Returns ``cancelled_before_commit`` when the operation never reached
        a domain commit (fingerprint unchanged, worker must stop within
        ``cancel_grace_s``) or ``detached_after_commit`` when the result is
        already durable and only delivery stops.
        """
        with self._lock:
            handle = self._handles.get(operation_id)
        if handle is None:
            record = self.store.get(operation_id)
            if record is None:
                return "unknown_operation"
            if record.status == "committed":
                return "detached_after_commit"
            if record.status in ("accepted", "running"):
                self.store.cancel_operation(operation_id, before_commit=True)
                return "cancelled_before_commit"
            return f"already_{record.status}"

        handle.token.cancel()
        record = self.store.get(operation_id)
        if record is not None and record.status == "committed":
            return "detached_after_commit"
        try:
            self.store.cancel_operation(operation_id, before_commit=True)
        except Exception:
            pass
        return "cancelled_before_commit"

    def replay(self, operation_id: str) -> Optional[OperationRecord]:
        """Committed operations replay resource/result without re-running."""
        record = self.store.get(operation_id)
        if record is not None and record.status == "committed":
            return record
        return None

    def get(self, operation_id: str) -> Optional[OperationRecord]:
        return self.store.get(operation_id)
