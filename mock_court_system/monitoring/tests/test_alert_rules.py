"""Alert state machine tests: thresholds, windows, recovery semantics."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_MONITORING_DIR = Path(__file__).resolve().parents[1]
if str(_MONITORING_DIR) not in sys.path:
    sys.path.insert(0, str(_MONITORING_DIR.parent))

from monitoring.alerts import (  # noqa: E402
    AlertStateMachine,
    ErrorRatioRule,
    ReadinessRule,
    load_rules,
)


def _requests(count: int, errors: int, start: float, step: float = 1.0):
    return [
        {"kind": "request", "ts": start + i * step, "error": i < errors}
        for i in range(count)
    ]


def _rule():
    return ErrorRatioRule(
        "stable_route_error_rate",
        window_s=300,
        min_requests=20,
        error_ratio=0.05,
        evaluation_interval_s=60,
        operator_link="docs/RUNBOOK.md#stable-route-error-rate",
    )


def test_insufficient_volume_never_fires():
    machine = AlertStateMachine(_rule())
    machine.feed_all(_requests(count=19, errors=19, start=0))
    assert machine.evaluate(60) is None
    assert machine.state == "ok"


def test_threshold_crossing_fires_at_evaluation():
    machine = AlertStateMachine(_rule())
    machine.feed_all(_requests(count=20, errors=2, start=0))  # 10% > 5%
    event = machine.evaluate(60)
    assert event is not None and event.state == "firing"
    assert event.rule == "stable_route_error_rate"
    assert event.operator_link.endswith("stable-route-error-rate")
    assert machine.fired_at == 60


def test_ratio_at_threshold_does_not_fire():
    machine = AlertStateMachine(_rule())
    machine.feed_all(_requests(count=20, errors=1, start=0))  # exactly 5%
    assert machine.evaluate(60) is None
    assert machine.state == "ok"


def test_stale_samples_leave_window():
    machine = AlertStateMachine(_rule())
    # Errors at t=0 fall outside the 300s window by t=400.
    machine.feed_all(_requests(count=20, errors=2, start=0))
    machine.feed_all(_requests(count=20, errors=0, start=350))
    assert machine.evaluate(400) is None
    assert machine.state == "ok"


def test_full_evaluation_window_must_clear_before_resolve():
    machine = AlertStateMachine(_rule())
    machine.feed_all(_requests(count=20, errors=2, start=0))
    assert machine.evaluate(60).state == "firing"

    # Condition clears at t=90 (new healthy traffic enters the window).
    machine.feed_all(_requests(count=20, errors=0, start=80))
    assert machine.evaluate(90) is None  # clear point recorded, still firing
    assert machine.state == "firing"

    # 30s later: less than one full 60s evaluation window -> still firing.
    assert machine.evaluate(120) is None
    assert machine.state == "firing"

    # A full evaluation window after clear -> resolved, recovered_at >= clear.
    machine.feed_all(_requests(count=5, errors=0, start=140))
    event = machine.evaluate(150)
    assert event is not None and event.state == "resolved"
    assert machine.recovered_at == 150
    assert machine.recovered_at >= 90


def test_refire_after_resolve_records_new_incident():
    machine = AlertStateMachine(_rule())
    machine.feed_all(_requests(count=20, errors=2, start=0))
    machine.evaluate(60)

    # Old errors must age out of the 300s window before the ratio clears.
    machine.feed_all(_requests(count=30, errors=0, start=310))
    assert machine.evaluate(360) is None  # clear point recorded
    assert machine.state == "firing"
    event = machine.evaluate(420)  # one full 60s evaluation window cleared
    assert event is not None and event.state == "resolved"
    assert machine.state == "resolved"

    machine.feed_all(_requests(count=20, errors=3, start=430))
    event = machine.evaluate(480)
    assert event is not None and event.state == "firing"
    assert machine.recovered_at is None
    assert len([e for e in machine.events if e.state == "firing"]) == 2


def test_readiness_requires_sustained_two_minutes():
    rule = ReadinessRule(
        "readiness_failure",
        window_s=120,
        for_duration_s=120,
        evaluation_interval_s=60,
        operator_link="docs/RUNBOOK.md#readiness-failure",
    )
    machine = AlertStateMachine(rule)
    machine.feed({"kind": "readiness", "ts": 0, "ready": False})
    machine.feed({"kind": "readiness", "ts": 60, "ready": False})
    # Only 60s of failure so far -> not firing.
    assert machine.evaluate(60) is None
    machine.feed({"kind": "readiness", "ts": 120, "ready": False})
    event = machine.evaluate(120)
    assert event is not None and event.state == "firing"


def test_readiness_recovery_resets_streak():
    rule = ReadinessRule(
        "readiness_failure",
        window_s=120,
        for_duration_s=120,
        evaluation_interval_s=60,
    )
    machine = AlertStateMachine(rule)
    machine.feed({"kind": "readiness", "ts": 0, "ready": False})
    machine.feed({"kind": "readiness", "ts": 60, "ready": True})
    machine.feed({"kind": "readiness", "ts": 90, "ready": False})
    machine.feed({"kind": "readiness", "ts": 120, "ready": False})
    # Streak restarted at t=90 -> only 30s of failure at t=120.
    assert machine.evaluate(120) is None
    machine.feed({"kind": "readiness", "ts": 210, "ready": False})
    assert machine.evaluate(210).state == "firing"


def test_load_rules_from_declared_catalog():
    rules = load_rules()
    by_name = {r.name: r for r in rules}
    assert set(by_name) == {"stable_route_error_rate", "readiness_failure"}
    rate = by_name["stable_route_error_rate"]
    assert rate.window_s == 300
    assert rate.min_requests == 20
    assert rate.error_ratio == pytest.approx(0.05)
    assert rate.evaluation_interval_s == 60
    ready = by_name["readiness_failure"]
    assert ready.for_duration_s == 120
    assert ready.evaluation_interval_s == 60
    for rule in rules:
        assert rule.operator_link.startswith("docs/RUNBOOK.md#")
