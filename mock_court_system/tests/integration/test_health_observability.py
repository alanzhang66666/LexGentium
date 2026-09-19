"""Observability：指标 catalog、低基数 label、secret redactor、SSE gauge 测试（Task 9.2）。"""
from __future__ import annotations

import pytest

from api.observability.metrics import (
    ALLOWED_LABELS,
    FORBIDDEN_LABELS,
    Counter,
    Histogram,
    LabelError,
    MetricsRegistry,
    metrics,
)
from api.observability.redaction import SECRET_MASK, redact_secrets


# ---------- metrics ----------


def test_metric_names_have_fixed_prefix():
    registry = MetricsRegistry()
    rendered = registry.render()
    for line in rendered.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        name = line.split("{")[0].split(" ")[0]
        for suffix in ("_bucket", "_sum", "_count", "_total"):
            name = name.replace(suffix, "")
        assert name.startswith("lexgentium_"), name


def test_metric_counter_increments_and_labels():
    c = Counter("lexgentium_test_total", "t")
    c.inc(labels={"method": "GET", "status_class": "2xx"})
    c.inc(2, labels={"method": "GET", "status_class": "2xx"})
    assert c.value({"method": "GET", "status_class": "2xx"}) == 3.0


def test_metric_forbidden_and_undeclared_labels_rejected():
    c = Counter("lexgentium_test2_total", "t")
    for bad in ("request_id", "session_id", "operation_id"):
        with pytest.raises(LabelError):
            c.inc(labels={bad: "x"})
    with pytest.raises(LabelError):
        c.inc(labels={"arbitrary_label": "x"})


def test_metric_allowed_labels_are_low_cardinality():
    # 白名单里不应出现任何关联身份字段
    assert FORBIDDEN_LABELS.isdisjoint(ALLOWED_LABELS)


def test_metric_histogram_buckets_and_render():
    h = Histogram("lexgentium_test_duration_ms", "t")
    h.observe(10, labels={"route_template": "/health"})
    h.observe(3000, labels={"route_template": "/health"})
    series = h.series()
    key = (("route_template", "/health"),)
    entry = series[key]
    assert entry["count"] == 2
    assert entry["sum"] == pytest.approx(3010)
    # 10ms 落在 <=25 及更大桶；3000ms 落在 <=10000 及更大桶
    assert entry["buckets"][1] == 1  # le=25
    assert entry["buckets"][5] == 2  # le=10000

    registry = MetricsRegistry()
    registry.request_duration.observe(50, labels={"route_template": "/x", "method": "GET"})
    text = registry.render()
    assert "lexgentium_http_request_duration_ms_bucket" in text
    assert 'le="+Inf"' in text


def test_metric_sse_gauge_tracks_active_streams():
    registry = MetricsRegistry()
    registry.active_sse.inc()
    registry.active_sse.inc()
    assert registry.active_sse.value() == 2.0
    registry.active_sse.dec()
    assert registry.active_sse.value() == 1.0


def test_metric_catalog_contains_required_series():
    registry = MetricsRegistry()
    names = {
        "lexgentium_http_requests_total",
        "lexgentium_http_errors_total",
        "lexgentium_http_request_duration_ms",
        "lexgentium_active_sse",
        "lexgentium_llm_calls_total",
        "lexgentium_llm_failures_total",
        "lexgentium_llm_degraded_total",
        "lexgentium_persistence_failures_total",
        "lexgentium_sse_duplicate_terminal_total",
        "lexgentium_ci_llm_calls_total",
    }
    registered = {m.name for m in registry._all}
    assert names <= registered


# ---------- redaction ----------


def test_log_redaction_masks_secrets_in_text():
    text = 'config api_key="sk-live-123" token=abc12345 Authorization: Bearer verylongtoken123'
    out = redact_secrets(text)
    assert "sk-live-123" not in out
    assert "abc12345" not in out
    assert "verylongtoken123" not in out
    assert SECRET_MASK in out


def test_log_redaction_masks_mapping_fields():
    payload = {
        "llm_api_key": "sk-real",
        "LLM_MODEL": "m",
        "nested": {"api_token": "tok-9", "note": "ok"},
    }
    out = redact_secrets(payload)
    assert out["llm_api_key"] == SECRET_MASK
    assert out["LLM_MODEL"] == "m"
    assert out["nested"]["api_token"] == SECRET_MASK
    assert "sk-real" not in str(out)
    assert "tok-9" not in str(out)


def test_log_redaction_masks_url_credentials():
    out = redact_secrets("connect https://user:pass@host/db")
    assert "user:pass" not in out
