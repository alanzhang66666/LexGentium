"""固定前缀指标 catalog（design §13，Task 9.2）。

- 全部指标前缀 ``lexgentium_``。
- label 只允许低基数字段：route_template/method/status_class/purpose/
  model_tier/error_code/type 等；Request ID、Session ID 等关联身份
  只能进日志/trace，不得作 label（注册时抛错）。
- counter 单调递增；gauge 反映 active SSE；histogram 记录请求时延。
"""
from __future__ import annotations

import re
import threading
from typing import Dict, Iterable, Mapping, Optional, Tuple

#: 允许的低基数 label 名白名单
ALLOWED_LABELS = frozenset(
    {
        "route_template",
        "method",
        "status_class",
        "purpose",
        "model_tier",
        "error_code",
        "type",
        "component",
        "store",
        "check_id",
    }
)

#: 高基数/关联身份 label 黑名单（显式拒绝，防误用）
FORBIDDEN_LABELS = frozenset(
    {
        "request_id",
        "session_id",
        "operation_id",
        "task_id",
        "run_id",
        "report_id",
        "game_id",
        "user_id",
        "case_id",
        "cluster_id",
    }
)

METRIC_PREFIX = "lexgentium_"

LabelSet = Tuple[Tuple[str, str], ...]


class LabelError(ValueError):
    pass


def _labelset(labels: Optional[Mapping[str, str]]) -> LabelSet:
    if not labels:
        return ()
    for name in labels:
        if name in FORBIDDEN_LABELS:
            raise LabelError(f"forbidden high-cardinality label: {name}")
        if name not in ALLOWED_LABELS:
            raise LabelError(f"undeclared label: {name}")
    return tuple(sorted((str(k), str(v)) for k, v in labels.items()))


class Counter:
    def __init__(self, name: str, description: str):
        if not name.startswith(METRIC_PREFIX):
            raise ValueError(f"metric must start with {METRIC_PREFIX}")
        self.name = name
        self.description = description
        self._values: Dict[LabelSet, float] = {}
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0, labels: Optional[Mapping[str, str]] = None) -> None:
        key = _labelset(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def value(self, labels: Optional[Mapping[str, str]] = None) -> float:
        return self._values.get(_labelset(labels), 0.0)

    def series(self) -> Dict[LabelSet, float]:
        return dict(self._values)


class Gauge:
    def __init__(self, name: str, description: str):
        if not name.startswith(METRIC_PREFIX):
            raise ValueError(f"metric must start with {METRIC_PREFIX}")
        self.name = name
        self.description = description
        self._values: Dict[LabelSet, float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, labels: Optional[Mapping[str, str]] = None) -> None:
        key = _labelset(labels)
        with self._lock:
            self._values[key] = value

    def inc(self, amount: float = 1.0, labels: Optional[Mapping[str, str]] = None) -> None:
        key = _labelset(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0, labels: Optional[Mapping[str, str]] = None) -> None:
        self.inc(-amount, labels)

    def value(self, labels: Optional[Mapping[str, str]] = None) -> float:
        return self._values.get(_labelset(labels), 0.0)

    def series(self) -> Dict[LabelSet, float]:
        return dict(self._values)


class Histogram:
    """固定桶请求时延直方图（ms）。"""

    BUCKETS = (5, 25, 100, 500, 2000, 10000, 60000)

    def __init__(self, name: str, description: str):
        if not name.startswith(METRIC_PREFIX):
            raise ValueError(f"metric must start with {METRIC_PREFIX}")
        self.name = name
        self.description = description
        self._counts: Dict[LabelSet, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def observe(self, value_ms: float, labels: Optional[Mapping[str, str]] = None) -> None:
        key = _labelset(labels)
        with self._lock:
            entry = self._counts.setdefault(
                key,
                {"buckets": [0] * len(self.BUCKETS), "count": 0, "sum": 0.0},
            )
            for i, bound in enumerate(self.BUCKETS):
                if value_ms <= bound:
                    entry["buckets"][i] += 1
            entry["count"] += 1
            entry["sum"] += value_ms

    def series(self) -> Dict[LabelSet, Dict[str, Any]]:
        return dict(self._counts)


def _format_labels(key: LabelSet) -> str:
    if not key:
        return ""
    inner = ",".join(f'{k}="{v}"' for k, v in key)
    return "{" + inner + "}"


class MetricsRegistry:
    """固定 catalog：声明于设计文档的指标都在这里注册。"""

    def __init__(self):
        self.http_requests = Counter(
            "lexgentium_http_requests_total", "HTTP requests by route/method/status class"
        )
        self.http_errors = Counter(
            "lexgentium_http_errors_total", "HTTP error responses by error code"
        )
        self.request_duration = Histogram(
            "lexgentium_http_request_duration_ms", "HTTP request duration (ms)"
        )
        self.active_sse = Gauge(
            "lexgentium_active_sse", "Currently open SSE streams"
        )
        self.llm_calls = Counter(
            "lexgentium_llm_calls_total", "LLM calls by purpose/model tier"
        )
        self.llm_failures = Counter(
            "lexgentium_llm_failures_total", "LLM call failures by error code"
        )
        self.llm_degraded = Counter(
            "lexgentium_llm_degraded_total", "Degraded LLM/domain outputs by purpose"
        )
        self.persistence_failures = Counter(
            "lexgentium_persistence_failures_total", "Store persistence failures by store"
        )
        self.sse_duplicate_terminal = Counter(
            "lexgentium_sse_duplicate_terminal_total", "Duplicate SSE terminal events by type"
        )
        self.ci_llm_calls = Counter(
            "lexgentium_ci_llm_calls_total", "CI-scenario LLM calls by purpose"
        )
        self._all = (
            self.http_requests,
            self.http_errors,
            self.request_duration,
            self.active_sse,
            self.llm_calls,
            self.llm_failures,
            self.llm_degraded,
            self.persistence_failures,
            self.sse_duplicate_terminal,
            self.ci_llm_calls,
        )

    def render(self) -> str:
        """Prometheus 文本 exposition。"""
        lines = []
        for metric in self._all:
            if isinstance(metric, Histogram):
                lines.append(f"# TYPE {metric.name} histogram")
                for key, entry in metric.series().items():
                    for i, bound in enumerate(metric.BUCKETS):
                        labels = _format_labels(key + (("le", str(bound)),))
                        lines.append(f"{metric.name}_bucket{labels} {entry['buckets'][i]}")
                    labels = _format_labels(key + (("le", "+Inf"),))
                    lines.append(f"{metric.name}_bucket{labels} {entry['count']}")
                    lines.append(f"{metric.name}_sum{_format_labels(key)} {entry['sum']:.3f}")
                    lines.append(f"{metric.name}_count{_format_labels(key)} {entry['count']}")
            elif isinstance(metric, Gauge):
                lines.append(f"# TYPE {metric.name} gauge")
                for key, value in metric.series().items():
                    lines.append(f"{metric.name}{_format_labels(key)} {value}")
            else:
                lines.append(f"# TYPE {metric.name} counter")
                for key, value in metric.series().items():
                    lines.append(f"{metric.name}{_format_labels(key)} {value:g}")
        return "\n".join(lines) + "\n"


#: 进程级单例
metrics = MetricsRegistry()
