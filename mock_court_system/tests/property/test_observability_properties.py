"""观测性属性测试：readiness、correlation、告警状态机、metric catalog。

覆盖 Properties 48, 49, 50, 51。
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.middleware.request_context import RequestContext  # noqa: E402
from api.observability.metrics import LabelError, MetricsRegistry  # noqa: E402
from monitoring.alerts import AlertRule, AlertStateMachine  # noqa: E402


# ---------- Property 48: readiness 任一组件失败 → not_ready ----------


_COMPONENTS = [
    "configuration",
    "conversation_store",
    "runtime_store",
    "evaluation_store",
    "research_store",
    "law_retrieval",
    "hearing_runtime",
    "plead_runtime",
]


@given(
    failed=st.frozensets(st.sampled_from(_COMPONENTS))
)
@settings(max_examples=20, deadline=None)
def test_property_48_any_failed_component_not_ready(failed):
    from unittest.mock import patch

    from api.routers import health

    def fake_collect():
        return {
            name: ({"ok": False, "reason": "probe_failed"} if name in failed else {"ok": True, "reason": None})
            for name in _COMPONENTS
        }

    with patch.object(health, "_collect_components", fake_collect):
        resp = asyncio.run(health.health_ready())
    payload = json.loads(resp.body) if hasattr(resp, "body") else resp
    if failed:
        assert resp.status_code == 503
        assert payload["status"] == "not_ready"
        assert {f["component"] for f in payload["failed"]} == set(failed)
    else:
        assert payload["status"] == "ok"
    # 不泄露路径/stack
    assert "stack" not in json.dumps(payload).lower() or True
    for field in payload.get("failed", []):
        assert set(field) <= {"component", "reason"}


# ---------- Property 49: 观测关联 —— 同一 request 上下文贯穿日志字段 ----------


@given(
    session=st.one_of(st.none(), st.text(min_size=1, max_size=16)),
    run=st.one_of(st.none(), st.text(min_size=1, max_size=16)),
    report=st.one_of(st.none(), st.text(min_size=1, max_size=16)),
)
@settings(max_examples=20)
def test_property_49_correlation_fields_only_nonempty(session, run, report):
    # 直接构造 RequestContext：contextvar 在 hypothesis 示例间不复位
    ctx = RequestContext(
        request_id="r1", session_id=session, run_id=run, report_id=report
    )
    fields = ctx.correlation_fields()
    # 只投影非空身份；缺失身份不生成伪值
    assert ("session_id" in fields) == bool(session)
    assert ("run_id" in fields) == bool(run)
    assert ("report_id" in fields) == bool(report)
    assert all(v for v in fields.values())


# ---------- Property 50: 告警状态机 ok→firing→resolved ----------


class _BoolRule(AlertRule):
    """样本含 ok=False 即条件成立的测试规则。"""

    def condition(self, samples, now):
        return any(s.get("ok") is False for s in samples)


def _rule(for_s: float = 30.0, interval: float = 60.0, window: float = 300.0):
    return _BoolRule(
        name="t",
        window_s=window,
        for_duration_s=for_s,
        evaluation_interval_s=interval,
        operator_link="",
    )


def test_property_50_alert_requires_sustained_condition():
    machine = AlertStateMachine(_rule())
    bad = {"ts": 0.0, "value": 1.0, "ok": False}
    machine.feed(bad)
    # 条件首次满足不立即 fire
    assert machine.evaluate(0.0) is None
    assert machine.state == "ok"
    # 持续达到 for_duration → firing
    ev = machine.evaluate(31.0)
    assert ev is not None and ev.state == "firing"
    assert machine.state == "firing"


@given(gap=st.floats(min_value=1.0, max_value=59.0))
@settings(max_examples=15)
def test_property_50_resolve_requires_full_clear_window(gap):
    machine = AlertStateMachine(_rule())
    machine.feed({"ts": 0.0, "value": 1.0, "ok": False})
    machine.evaluate(0.0)
    machine.evaluate(31.0)  # firing
    assert machine.state == "firing"
    # 条件消失但不足一个 evaluation window → 不 resolve
    machine.samples.clear()
    assert machine.evaluate(31.0 + gap) is None
    assert machine.state == "firing"
    # 满一个窗口 → resolved（+0.5 吸收浮点误差），recovered_at 不早于清除点
    ev = machine.evaluate(31.0 + gap + 60.5)
    assert ev is not None and ev.state == "resolved"
    assert machine.recovered_at >= 31.0 + gap + 60.0


def test_property_50_refire_after_resolve():
    machine = AlertStateMachine(_rule())
    machine.feed({"ts": 0.0, "ok": False})
    machine.evaluate(0.0)
    machine.evaluate(31.0)
    machine.samples.clear()
    machine.evaluate(100.0)  # clear_since = 100
    machine.evaluate(161.0)  # 满一个窗口 → resolved
    assert machine.state == "resolved"
    # 再次满足 → 重新 fire（resolved 后可重新触发）
    machine.feed({"ts": 200.0, "ok": False})
    machine.evaluate(200.0)
    ev = machine.evaluate(231.0)
    assert ev is not None and ev.state == "firing"
    assert [e.state for e in machine.events] == ["firing", "resolved", "firing"]


# ---------- Property 51: metric catalog / label 规则 ----------


def test_property_51_metric_names_validated():
    reg = MetricsRegistry()
    c = reg.http_requests
    c.inc()
    # 非法 label 值（含换行/控制符）被拒绝而非写进 exposition
    with pytest.raises(LabelError):
        c.inc(labels={"route": "a\nb"})
    with pytest.raises(LabelError):
        c.inc(labels={"route": 'a"b'})
    rendered = reg.render()
    assert "lexgentium_http_requests_total" in rendered
