"""高成本 operation 容量 semaphore 与资源释放（Task 12.4）。

- bounded semaphore 控制并发；饱和时在开始任何 LLM 调用/持久化之前
  返回 429 ``capacity_exceeded`` 与正整数 ``Retry-After``。
- permit release 幂等；terminal（completed/failed/cancelled）后必须释放，
  并以 in-flight gauge 验证 10 秒内回落。
"""
from __future__ import annotations

import os
import threading
from typing import Optional


class CapacityPermit:
    """一次高成本 operation 的占用凭证；release 幂等。"""

    def __init__(self, guard: "CapacityGuard"):
        self._guard = guard
        self._released = False
        self._lock = threading.Lock()

    def release(self) -> None:
        with self._lock:
            if self._released:
                return
            self._released = True
        self._guard._release()

    def __enter__(self) -> "CapacityPermit":
        return self

    def __exit__(self, *_exc) -> None:
        self.release()


class CapacityGuard:
    """有界并发守卫；饱和时 try_acquire 返回 None（调用方据此拒绝）。"""

    def __init__(self, max_concurrent: int, retry_after_seconds: int = 5):
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        if retry_after_seconds < 1:
            raise ValueError("retry_after_seconds must be a positive integer")
        self._max = max_concurrent
        self._retry_after = retry_after_seconds
        self._sem = threading.BoundedSemaphore(max_concurrent)
        self._in_flight = 0
        self._lock = threading.Lock()

    @property
    def max_concurrent(self) -> int:
        return self._max

    @property
    def retry_after_seconds(self) -> int:
        return self._retry_after

    @property
    def in_flight(self) -> int:
        with self._lock:
            return self._in_flight

    @property
    def saturated(self) -> bool:
        return self.in_flight >= self._max

    def try_acquire(self) -> Optional[CapacityPermit]:
        if not self._sem.acquire(blocking=False):
            return None
        with self._lock:
            self._in_flight += 1
        return CapacityPermit(self)

    def _release(self) -> None:
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
        self._sem.release()

    @classmethod
    def from_env(cls) -> "CapacityGuard":
        max_concurrent = int(os.getenv("CAPACITY_MAX_CONCURRENT", "4") or "4")
        retry_after = int(os.getenv("CAPACITY_RETRY_AFTER_SECONDS", "5") or "5")
        return cls(max_concurrent=max_concurrent, retry_after_seconds=retry_after)
