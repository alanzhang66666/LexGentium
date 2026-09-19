"""Deterministic alert state machines for release observability.

Pure logic, no I/O: callers feed timestamped samples and tick the machine at
the declared evaluation interval. Rules are declared in ``rules.yaml`` so the
gate can diff them and tests can replay recorded windows.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_EVALUATION_INTERVAL_S = 60.0


@dataclass(frozen=True)
class AlertEvent:
    rule: str
    state: str  # "firing" | "resolved"
    at: float
    operator_link: str
    detail: Dict[str, Any] = field(default_factory=dict)


class AlertRule:
    """Base rule: evaluate a boolean condition over a trailing window."""

    def __init__(
        self,
        name: str,
        *,
        window_s: float,
        evaluation_interval_s: float = DEFAULT_EVALUATION_INTERVAL_S,
        for_duration_s: float = 0.0,
        operator_link: str = "",
    ) -> None:
        self.name = name
        self.window_s = float(window_s)
        self.evaluation_interval_s = float(evaluation_interval_s)
        self.for_duration_s = float(for_duration_s)
        self.operator_link = operator_link
        # When True the condition receives samples including the
        # for_duration lookback, not just the trailing window.
        self.uses_extended_window = False

    @property
    def machine_for_s(self) -> float:
        """Duration the state machine requires the condition to hold.

        Rules whose condition already embeds a sustained-duration check
        (readiness) override this to 0 so the duration is not applied twice.
        """
        return self.for_duration_s

    def condition(self, samples: List[Dict[str, Any]], now: float) -> bool:
        raise NotImplementedError


class ErrorRatioRule(AlertRule):
    """error_ratio > threshold over window, gated by a minimum request count."""

    def __init__(self, name: str, *, min_requests: int, error_ratio: float, **kw: Any) -> None:
        super().__init__(name, **kw)
        self.min_requests = int(min_requests)
        self.error_ratio = float(error_ratio)

    def condition(self, samples: List[Dict[str, Any]], now: float) -> bool:
        requests = [s for s in samples if s.get("kind") == "request"]
        if len(requests) < self.min_requests:
            return False
        errors = sum(1 for s in requests if s.get("error"))
        return errors / len(requests) > self.error_ratio


class ReadinessRule(AlertRule):
    """Fires when readiness has been continuously failing for for_duration_s."""

    def __init__(self, name: str, **kw: Any) -> None:
        super().__init__(name, **kw)
        self.uses_extended_window = True

    @property
    def machine_for_s(self) -> float:
        return 0.0

    def condition(self, samples: List[Dict[str, Any]], now: float) -> bool:
        checks = [s for s in samples if s.get("kind") == "readiness"]
        if not checks or not self.for_duration_s:
            return False
        checks.sort(key=lambda s: s["ts"])
        streak_start: Optional[float] = None
        for sample in checks:
            if sample.get("ready"):
                streak_start = None
            elif streak_start is None:
                streak_start = float(sample["ts"])
        if streak_start is None:
            return False
        return now - streak_start >= self.for_duration_s


_RULE_TYPES = {
    "error_ratio": ErrorRatioRule,
    "readiness": ReadinessRule,
}


class AlertStateMachine:
    """ok -> firing -> resolved, driven by evaluation ticks.

    The condition must hold for ``for_duration_s`` before firing. After
    firing, the condition must stay false for one full evaluation window
    before the alert resolves with ``recovered_at`` recorded at the resolve
    tick (never earlier than the clear point).
    """

    def __init__(self, rule: AlertRule) -> None:
        self.rule = rule
        self.state = "ok"
        self.samples: List[Dict[str, Any]] = []
        self.events: List[AlertEvent] = []
        self._condition_since: Optional[float] = None
        self._clear_since: Optional[float] = None
        self.fired_at: Optional[float] = None
        self.recovered_at: Optional[float] = None

    def feed(self, sample: Dict[str, Any]) -> None:
        if "ts" not in sample:
            raise ValueError("sample requires 'ts'")
        self.samples.append(dict(sample))

    def feed_all(self, samples: Iterable[Dict[str, Any]]) -> None:
        for sample in samples:
            self.feed(sample)

    def evaluate(self, now: float) -> Optional[AlertEvent]:
        now = float(now)
        cutoff = now - self.rule.window_s
        self.samples = [s for s in self.samples if float(s["ts"]) >= cutoff - self.rule.for_duration_s]
        if self.rule.uses_extended_window:
            window = sorted(self.samples, key=lambda s: float(s["ts"]))
        else:
            window = sorted(
                (s for s in self.samples if float(s["ts"]) >= cutoff),
                key=lambda s: float(s["ts"]),
            )
        holds = self.rule.condition(window, now)

        if self.state in ("ok", "resolved"):
            self._clear_since = None
            if not holds:
                self._condition_since = None
                return None
            if self._condition_since is None:
                self._condition_since = now
            if now - self._condition_since >= self.rule.machine_for_s:
                self.state = "firing"
                self.fired_at = now
                self.recovered_at = None
                event = AlertEvent(
                    rule=self.rule.name,
                    state="firing",
                    at=now,
                    operator_link=self.rule.operator_link,
                    detail={"condition_since": self._condition_since},
                )
                self.events.append(event)
                return event
            return None

        # firing
        if holds:
            self._clear_since = None
            return None
        if self._clear_since is None:
            self._clear_since = now
            return None
        if now - self._clear_since >= self.rule.evaluation_interval_s:
            self.state = "resolved"
            self.recovered_at = now
            self._condition_since = None
            event = AlertEvent(
                rule=self.rule.name,
                state="resolved",
                at=now,
                operator_link=self.rule.operator_link,
                detail={"cleared_since": self._clear_since},
            )
            self.events.append(event)
            return event
        return None


def load_rules(path: Optional[Path] = None) -> List[AlertRule]:
    """Load rule declarations from monitoring/rules.yaml.

    The file is YAML; to keep this module dependency-free we accept the small
    subset used by rules.yaml (a ``rules:`` list of flat mappings). A JSON
    twin is also accepted.
    """
    path = path or Path(__file__).with_name("rules.yaml")
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        raw = json.loads(text)
    else:
        raw = _parse_rules_yaml(text)
    rules: List[AlertRule] = []
    for entry in raw.get("rules", []):
        entry = dict(entry)
        rule_type = entry.pop("type")
        cls = _RULE_TYPES[rule_type]
        rules.append(cls(**entry))
    return rules


def _parse_rules_yaml(text: str) -> Dict[str, Any]:
    """Minimal parser for the flat ``rules:`` list shape used here."""
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        pass
    rules: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "rules:":
            continue
        if stripped.startswith("- "):
            current = {}
            rules.append(current)
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if current is None or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        current[key.strip()] = _yaml_scalar(value.strip())
    return {"rules": rules}


def _yaml_scalar(value: str) -> Any:
    if value in ("true", "false"):
        return value == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value.strip('"').strip("'")
