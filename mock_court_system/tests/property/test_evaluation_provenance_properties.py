"""Evaluation provenance / 不可变报告 / 输入构建 属性测试。

覆盖 Properties 11, 22, 45, 46, 47。
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.evaluation_input import (  # noqa: E402
    EvaluationInputBuilder,
    MissingEvaluationInputError,
    normalize_dialog,
)
from core.store.evaluation_provenance_store import (  # noqa: E402
    EvaluationProvenanceStore,
    ImmutableReportError,
)


def _store(tmp_path_factory) -> EvaluationProvenanceStore:
    return EvaluationProvenanceStore(str(Path(tmp_path_factory.mktemp("p")) / "p.sqlite3"))


def _begin(store: EvaluationProvenanceStore, op_id: str, **kw):
    params = dict(
        operation_id=op_id,
        input_payload={"input": op_id},
        prediction_identity="pred1",
        evaluator_version="lexeval-1.0.0",
        rubric_namespace="civil",
        rubric_version="v1",
        configuration_identity="cfg",
        model_identity="model",
    )
    params.update(kw)
    return store.begin_evaluation(**params)


# ---------- Property 11: report 唯一归属 + 重试回放 ----------


def test_property_11_report_unique_attribution_and_retry_replay(tmp_path):
    store = EvaluationProvenanceStore(str(tmp_path / "prov.sqlite3"))
    p1, r1 = _begin(store, "op1")
    p2, r2 = _begin(store, "op2")
    # 不同 operation → 不同 provenance/report 身份
    assert p1.provenance_id != p2.provenance_id
    assert r1.report_id != r2.report_id
    # 同一 operation 重试 → 回放既有身份，不新增
    p1b, r1b = _begin(store, "op1")
    assert (p1b.provenance_id, r1b.report_id) == (p1.provenance_id, r1.report_id)
    assert store.report_count() == 2
    # report ↔ provenance 一一对应
    assert store.get_report_by_provenance(p1.provenance_id).report_id == r1.report_id


# ---------- Property 46: completed report immutable ----------


@given(score=st.integers(min_value=0, max_value=100))
@settings(max_examples=10)
def test_property_46_completed_report_immutable(tmp_path_factory, score):
    store = _store(tmp_path_factory)
    _, report = _begin(store, "op1")
    results = {"score": score}
    done = store.complete_report(report.report_id, results=results)
    assert done.result_digest
    # 同结果重复完成 → 幂等返回
    again = store.complete_report(report.report_id, results=results)
    assert again.result_digest == done.result_digest
    # 异结果 → ImmutableReportError；fail 同样被拒
    with pytest.raises(ImmutableReportError):
        store.complete_report(report.report_id, results={"score": score + 1})
    with pytest.raises(ImmutableReportError):
        store.fail_report(report.report_id, message="late")
    assert store.get_report(report.report_id).immutable_results == results


# ---------- Property 22: degraded + affected metrics 持久化传播 ----------


@given(degraded=st.booleans(), metrics=st.lists(st.text(min_size=1, max_size=8), max_size=4))
@settings(max_examples=15)
def test_property_22_degraded_flag_propagates(tmp_path_factory, degraded, metrics):
    store = _store(tmp_path_factory)
    prov, _ = _begin(store, "op1", degraded=degraded, affected_metrics=metrics)
    assert prov.degraded == degraded
    assert list(prov.affected_metrics) == list(metrics)


# ---------- Property 45: 评测输入按 committed turn 排序且 digest 稳定 ----------


@given(
    messages=st.lists(
        st.fixed_dictionaries(
            {"turn": st.integers(min_value=0, max_value=20), "message": st.text(min_size=1, max_size=30)}
        ),
        min_size=1,
        max_size=8,
    )
)
@settings(max_examples=20)
def test_property_45_input_ordering_by_turn(messages):
    for m in messages:
        m["role"] = "plaintiff"
    norm = normalize_dialog(messages)
    turns = [r["turn"] for r in norm]
    assert turns == sorted(turns)

    # 乱序输入 → 相同规范化结果与 digest
    import random

    shuffled = list(messages)
    random.Random(42).shuffle(shuffled)
    record = SimpleNamespace(
        dialog_history=shuffled,
        session_id="s1",
        case_id="c1",
        input_json={},
    )
    inputs = EvaluationInputBuilder().build_from_session(record, ["lexeval"], run_id="r1")
    record2 = SimpleNamespace(
        dialog_history=messages, session_id="s1", case_id="c1", input_json={}
    )
    inputs2 = EvaluationInputBuilder().build_from_session(record2, ["lexeval"], run_id="r1")
    assert inputs[0].input_digest == inputs2[0].input_digest
    assert inputs[0].normalized_dialog == inputs2[0].normalized_dialog


# ---------- Property 47: 缺输入拒绝且不产生伪报告 ----------


def test_property_47_missing_input_refused():
    builder = EvaluationInputBuilder()
    # 空 dialog → 拒绝
    with pytest.raises(MissingEvaluationInputError) as e1:
        builder.build_from_session(
            SimpleNamespace(dialog_history=[], session_id="s", case_id="c", input_json={}),
            ["lexeval"],
            run_id="r",
        )
    assert e1.value.field_errors
    # 缺 session_id → 拒绝
    with pytest.raises(MissingEvaluationInputError):
        builder.build_from_session(
            SimpleNamespace(
                dialog_history=[{"turn": 0, "role": "p", "message": "m"}],
                session_id=None,
                case_id="c",
                input_json={},
            ),
            ["lexeval"],
            run_id="r",
        )
    # 全空白 message → 拒绝
    with pytest.raises(MissingEvaluationInputError):
        builder.build_from_session(
            SimpleNamespace(
                dialog_history=[{"turn": 0, "role": "p", "message": "   "}],
                session_id="s",
                case_id="c",
                input_json={},
            ),
            ["lexeval"],
            run_id="r",
        )
