"""Testable alert rules and state machines.

Design contract (release-readiness design.md §observability):
- error-rate rule: 5m window, stable-route request count >= 20 and error
  ratio > 5% -> firing within the 60s evaluation interval.
- readiness rule: readiness failure sustained for 2m -> firing within 60s.
- recovery: condition cleared for one full evaluation window -> record
  recovered_at (not earlier than the clear point) and resolve.
- request volume below min_requests can never fire.
"""

from .alerts import (  # noqa: F401
    AlertEvent,
    AlertRule,
    AlertStateMachine,
    ErrorRatioRule,
    ReadinessRule,
    load_rules,
)
