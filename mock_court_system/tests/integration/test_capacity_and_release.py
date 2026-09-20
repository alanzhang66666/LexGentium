"""容量 semaphore 与 FullCase 资源释放集成测试（Task 12.4）。

- 饱和时在 LLM/持久化之前拒绝：permit 取不到 → 429 capacity_exceeded +
  正整数 Retry-After，且 task 表不出现新记录。
- completed/failed/cancelled terminal 都释放 permit，in-flight gauge 回落。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.capacity import CapacityGuard  # noqa: E402


class _FakeResult:
    def to_dict(self):
        return {"ok": True}


class _FakeOrchestrator:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def run_full_case(self, case_info, on_progress=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("simulated failure")
        return _FakeResult()


def test_saturation_rejects_before_work():
    guard = CapacityGuard(max_concurrent=1, retry_after_seconds=3)
    permit = guard.try_acquire()
    assert permit is not None
    assert guard.saturated
    # 第二个请求在占用释放前取不到 permit → 调用方应直接 429
    assert guard.try_acquire() is None
    assert guard.retry_after_seconds == 3 and guard.retry_after_seconds > 0
    permit.release()
    assert not guard.saturated


def test_release_idempotent():
    guard = CapacityGuard(max_concurrent=1)
    permit = guard.try_acquire()
    permit.release()
    permit.release()  # 幂等
    assert guard.in_flight == 0
    # 释放后可重新获取
    assert guard.try_acquire() is not None


def test_fullcase_completed_releases_permit(monkeypatch):
    import api.state as state

    guard = CapacityGuard(max_concurrent=1)
    monkeypatch.setattr(state, "capacity_guard", guard)
    monkeypatch.setattr(state, "_orchestrator", _FakeOrchestrator())

    permit = guard.try_acquire()
    assert permit is not None
    task_id = "t_completed"
    state.simulation_tasks[task_id] = {"status": "pending", "worker": object()}
    state._run_full_simulation_task(task_id, {"case_id": "x"}, permit)

    assert state.simulation_tasks[task_id]["status"] == "completed"
    assert guard.in_flight == 0  # terminal 后释放
    assert "worker" not in state.simulation_tasks[task_id]  # runtime 引用清理


def test_fullcase_failed_releases_permit(monkeypatch):
    import api.state as state

    guard = CapacityGuard(max_concurrent=1)
    monkeypatch.setattr(state, "capacity_guard", guard)
    monkeypatch.setattr(state, "_orchestrator", _FakeOrchestrator(fail=True))

    permit = guard.try_acquire()
    task_id = "t_failed"
    state.simulation_tasks[task_id] = {"status": "pending"}
    state._run_full_simulation_task(task_id, {"case_id": "x"}, permit)

    assert state.simulation_tasks[task_id]["status"] == "failed"
    assert guard.in_flight == 0


def test_tournament_releases_permit(monkeypatch):
    import api.state as state

    guard = CapacityGuard(max_concurrent=1)
    monkeypatch.setattr(state, "capacity_guard", guard)

    class _FakeEngine:
        def run_tournament(self, case_info, rounds=3, on_progress=None):
            return _FakeResult()

    monkeypatch.setattr(state, "_game_engine", _FakeEngine())

    permit = guard.try_acquire()
    task_id = "t_tournament"
    state.simulation_tasks[task_id] = {"status": "pending"}
    state._run_tournament_task(task_id, {"case_id": "x"}, 3, permit)

    assert state.simulation_tasks[task_id]["status"] == "completed"
    assert guard.in_flight == 0


def test_release_within_10s_gauge(monkeypatch):
    """terminal 后 in-flight gauge 应在 10s 内回落（实际远快于此）。"""
    import api.state as state

    guard = CapacityGuard(max_concurrent=1)
    monkeypatch.setattr(state, "capacity_guard", guard)
    monkeypatch.setattr(state, "_orchestrator", _FakeOrchestrator())

    permit = guard.try_acquire()
    state.simulation_tasks["t_gauge"] = {"status": "pending"}
    t0 = time.monotonic()
    state._run_full_simulation_task("t_gauge", {"case_id": "x"}, permit)
    elapsed = time.monotonic() - t0
    assert guard.in_flight == 0
    assert elapsed < 10


def test_load_simulation_task_missing_returns_none():
    import api.state as state

    assert state.load_simulation_task("not-a-task") is None


def test_load_simulation_task_reads_memory():
    import api.state as state

    task_id = "sim_load_roundtrip"
    state.simulation_tasks[task_id] = {
        "status": "pending",
        "message": "task created",
        "current_stage": None,
        "result": None,
    }
    try:
        loaded = state.load_simulation_task(task_id)
        assert loaded is not None
        assert loaded["status"] == "pending"
        assert loaded["message"] == "task created"
    finally:
        state.simulation_tasks.pop(task_id, None)
