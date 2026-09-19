"""Evaluation provenance-before-score / 报告不可变 / operation 重试回放测试（Task 8.1）。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.fingerprint import canonical_digest
from core.store.evaluation_provenance_store import (
    EvaluationProvenanceStore,
    ImmutableReportError,
    ProvenanceRequiredError,
)


@pytest.fixture()
def store(tmp_path):
    return EvaluationProvenanceStore(str(tmp_path / "eval.sqlite3"))


def _begin(store, operation_id="op_1", **overrides):
    params = dict(
        operation_id=operation_id,
        input_payload={"dialog": [{"role": "Lawyer", "message": "x"}], "case_id": "C1"},
        prediction_identity="session:s1",
        evaluator_version="lexeval/1.0.0",
        rubric_namespace="civil.lexeval",
        rubric_version="v1",
        configuration_identity="cfg-abc",
        model_identity="model-x",
        session_id="s1",
        run_id="run_1",
    )
    params.update(overrides)
    return store.begin_evaluation(**params)


def test_provenance_written_before_score_with_full_identity(store):
    prov, report = _begin(store)
    assert prov.provenance_id.startswith("prov_")
    assert prov.operation_id == "op_1"
    assert prov.session_id == "s1"
    assert prov.run_id == "run_1"
    assert prov.input_digest == canonical_digest(
        {"dialog": [{"role": "Lawyer", "message": "x"}], "case_id": "C1"}
    )
    assert prov.rubric_namespace == "civil.lexeval"
    assert prov.evaluator_version == "lexeval/1.0.0"
    # 评分前 report 已存在但尚未完成 —— provenance 先于结果
    assert report.status == "running"
    assert report.provenance_id == prov.provenance_id
    assert report.result_digest is None
    assert report.immutable_results is None


def test_completed_report_is_immutable(store):
    prov, report = _begin(store)
    results = {"metrics": {"accuracy": 0.9}}
    done = store.complete_report(report.report_id, results=results)
    assert done.status == "completed"
    assert done.result_digest == canonical_digest(results)

    # 相同结果重复完成 → 幂等返回
    again = store.complete_report(report.report_id, results=results)
    assert again.result_digest == done.result_digest

    # 不同结果 → 拒绝，保持既有 digest
    with pytest.raises(ImmutableReportError):
        store.complete_report(report.report_id, results={"metrics": {"accuracy": 0.1}})
    unchanged = store.get_report(report.report_id)
    assert unchanged.result_digest == done.result_digest
    assert unchanged.immutable_results == results

    # 已完成 report 不可转 failed
    with pytest.raises(ImmutableReportError):
        store.fail_report(report.report_id, message="late failure")


def test_operation_retry_replays_existing_identities(store):
    prov1, report1 = _begin(store)
    prov2, report2 = _begin(store)  # 同 operation_id 重试
    assert prov2.provenance_id == prov1.provenance_id
    assert report2.report_id == report1.report_id
    assert store.report_count() == 1

    via_op = store.get_by_operation("op_1")
    assert via_op[0].provenance_id == prov1.provenance_id


def test_one_report_per_provenance(store):
    prov, report = _begin(store)
    with store._connect() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO evaluation_reports(
                  report_id, provenance_id, namespace, status, created_at
                ) VALUES('eval_x', ?, 'civil.lexeval', 'running', '2026-01-01')
                """,
                (prov.provenance_id,),
            )


def test_degraded_flag_and_affected_metrics(store):
    prov, _ = _begin(
        store, operation_id="op_deg", degraded=True, affected_metrics=["accuracy"]
    )
    assert prov.degraded is True
    assert prov.affected_metrics == ("accuracy",)


def test_message_mutable_but_results_not(store):
    _, report = _begin(store)
    updated = store.update_message(report.report_id, "scoring in progress")
    assert updated.message == "scoring in progress"
    done = store.complete_report(report.report_id, results={"ok": True}, message="done")
    assert done.message == "done"


def test_unknown_report_raises(store):
    with pytest.raises(ProvenanceRequiredError):
        store.complete_report("eval_missing", results={})
    with pytest.raises(ProvenanceRequiredError):
        store.fail_report("eval_missing", message="x")


def test_failed_report_can_be_marked(store):
    _, report = _begin(store)
    failed = store.fail_report(report.report_id, message="scorer crashed")
    assert failed.status == "failed"
    # failed 后仍可用幂等完成（同 operation 重跑的恢复路径由上层控制）
    done = store.complete_report(report.report_id, results={"ok": True})
    assert done.status == "completed"


# ---------- Task 8.2: evaluation input builder / 无 session_predictions ----------


class _FakeRecord:
    def __init__(self, dialog, session_id="s1", case_id="C1", input_json=None):
        self.dialog_history = dialog
        self.session_id = session_id
        self.case_id = case_id
        self.input_json = input_json or {}


def test_input_builder_normalizes_ordered_dialog_and_digest():
    from api.services.evaluation_input import EvaluationInputBuilder

    record = _FakeRecord(
        [
            {"turn": 2, "role": "Defendant", "message": "答辩"},
            {"turn": 1, "role": "Plaintiff", "message": "起诉"},
            {"turn": 3, "role": "Judge", "message": "  "},  # 空白被剔除
        ]
    )
    inputs = EvaluationInputBuilder().build_from_session(record, ["CD"], run_id="run_1")
    assert len(inputs) == 1
    inp = inputs[0]
    # 按 turn 排序、空白剔除
    assert [r["turn"] for r in inp.normalized_dialog] == [1, 2]
    assert inp.normalized_dialog[0]["role"] == "Plaintiff"
    assert inp.model_output == "起诉\n答辩"
    assert inp.input_digest
    assert inp.session_id == "s1"
    assert inp.run_id == "run_1"
    # 同输入 → 同 digest（immutable input model）
    again = EvaluationInputBuilder().build_from_session(record, ["CD"], run_id="run_1")[0]
    assert again.input_digest == inp.input_digest


def test_input_missing_dialog_raises_422_fields_no_report(store):
    from api.services.evaluation_input import (
        EvaluationInputBuilder,
        MissingEvaluationInputError,
    )

    before = store.report_count()
    with pytest.raises(MissingEvaluationInputError) as exc:
        EvaluationInputBuilder().build_from_session(
            _FakeRecord([]), ["CD"], run_id="run_1"
        )
    assert exc.value.code == "missing_evaluation_input"
    assert exc.value.field_errors[0]["path"] == "/dialog_history"
    # 不创建 report
    assert store.report_count() == before


def test_input_missing_session_id_raises(store):
    from api.services.evaluation_input import (
        EvaluationInputBuilder,
        MissingEvaluationInputError,
    )

    record = _FakeRecord([{"turn": 0, "role": "x", "message": "y"}], session_id=None)
    with pytest.raises(MissingEvaluationInputError):
        EvaluationInputBuilder().build_from_session(record, ["CD"], run_id="r")


def test_input_materialize_uses_runtime_root_not_session_predictions(tmp_path, monkeypatch):
    from api.services.evaluation_input import (
        EvaluationInputBuilder,
        materialize_legacy_files,
    )

    monkeypatch.setenv("RUNTIME_DATA_ROOT", str(tmp_path / "rt"))
    record = _FakeRecord(
        [{"turn": 0, "role": "Plaintiff", "message": "起诉"}],
        input_json={"research": {"dataset_id": "cisg", "cluster_id": "c1", "pack_version": "0.1"}},
    )
    inputs = EvaluationInputBuilder().build_from_session(record, ["CI"], run_id="run_1")
    files, cleanup = materialize_legacy_files(inputs, "task-abc")

    path = Path(files["CI"])
    assert path.exists()
    # 在 runtime data root 下，不在 data/session_predictions
    assert "session_predictions" not in str(path)
    assert "evaluation_inputs" in str(path)
    row = __import__("json").loads(path.read_text(encoding="utf-8").strip())
    assert row["id"] == "c1"
    assert row["cluster_id"] == "c1"
    assert row["run_id"] == "run_1"

    cleanup()
    assert not path.exists()
    assert not (tmp_path / "rt" / "evaluation_inputs" / "task-abc").exists()


def test_input_degraded_marks_affected_metrics():
    from api.services.evaluation_input import EvaluationInputBuilder

    record = _FakeRecord(
        [{"turn": 0, "role": "x", "message": "y"}],
        input_json={"degraded": True, "affected_metrics": ["accuracy"]},
    )
    inp = EvaluationInputBuilder().build_from_session(record, ["CD"], run_id="r")[0]
    assert inp.degraded is True
    assert inp.affected_metrics == ("accuracy",)


# ---------- Task 8.3: API 层 provenance / Correlation_Context 暴露 ----------


def _isolated_eval_state(tmp_path, monkeypatch):
    """MemoryConversationStore + tmp task/provenance store，避免写真实 DB。"""
    from api.services import evaluation as ev
    from core.store.conversation_store import MemoryConversationStore
    from core.store.evaluation_task_store import SqliteEvaluationTaskStore

    conv = MemoryConversationStore()
    prov_store = EvaluationProvenanceStore(str(tmp_path / "prov.sqlite3"))
    monkeypatch.setattr(ev.state, "conversation_store", conv)
    monkeypatch.setattr(
        ev.state,
        "evaluation_task_store",
        SqliteEvaluationTaskStore(str(tmp_path / "tasks.sqlite3")),
    )
    monkeypatch.setattr(ev.state, "evaluation_provenance_store", prov_store)
    monkeypatch.setattr(ev, "bind_session_link", lambda *a, **k: None)
    ev.state.evaluation_tasks.clear()
    return ev, conv, prov_store


def _seed_session(conv, session_id="sess-prov", input_json=None):
    record = conv.create(
        session_id=session_id,
        scenario="CD",
        case_id="CD-Test",
        input_json=input_json or {},
    )
    record.dialog_history = [{"turn": 0, "role": "Client", "message": "起诉借款纠纷"}]
    conv.save(record)
    return record


def test_start_evaluation_writes_provenance_with_task_report_id(tmp_path, monkeypatch):
    ev, conv, prov_store = _isolated_eval_state(tmp_path, monkeypatch)
    _seed_session(conv)

    report_id, _files = ev.start_evaluation_task(["CD"], None, "sess-prov", False)

    found = prov_store.get_by_operation(f"eval:{report_id}")
    assert found is not None
    prov, report = found
    # 任务 report_id 与 provenance report_id 同一身份 —— 不再有两个无关 ID
    assert report.report_id == report_id
    assert report.provenance_id == prov.provenance_id
    assert report.status == "running"  # 评分前已存在
    assert prov.session_id == "sess-prov"
    assert prov.run_id
    assert prov.rubric_namespace == "civil"
    assert prov.evaluator_version
    assert prov.configuration_identity
    assert prov.input_digest


def test_provenance_view_and_task_response_surface_context(tmp_path, monkeypatch):
    ev, conv, _prov = _isolated_eval_state(tmp_path, monkeypatch)
    _seed_session(
        conv,
        input_json={"degraded": True, "affected_metrics": ["accuracy"]},
    )

    report_id, _ = ev.start_evaluation_task(["CD"], None, "sess-prov", False)

    view = ev.evaluation_provenance_view(report_id)
    assert view["namespace"] == "civil"
    assert view["degraded"] is True
    assert view["affected_metrics"] == ["accuracy"]
    assert view["report_status"] == "running"

    from api.routers.evaluate import _task_response

    resp = _task_response(
        report_id=report_id,
        status="running",
        message="started",
        session_id="sess-prov",
        run_id=view.get("run_id"),
    )
    assert resp.provenance is not None
    assert resp.provenance.provenance_id == view["provenance_id"]
    assert resp.provenance.degraded is True
    assert resp.correlation is not None
    assert resp.correlation.report_id == report_id
    assert resp.correlation.session_id == "sess-prov"
    assert resp.correlation.operation_id == f"eval:{report_id}"


def test_provenance_retrievable_after_store_restart(tmp_path, monkeypatch):
    ev, conv, prov_store = _isolated_eval_state(tmp_path, monkeypatch)
    _seed_session(conv)
    report_id, _ = ev.start_evaluation_task(["CD"], None, "sess-prov", False)

    # 模拟重启：新 store 实例指向同一 DB 文件
    fresh = EvaluationProvenanceStore(str(tmp_path / "prov.sqlite3"))
    monkeypatch.setattr(ev.state, "evaluation_provenance_store", fresh)
    view = ev.evaluation_provenance_view(report_id)
    assert view["provenance_id"]
    assert view["report_status"] == "running"

    # 同 operation 重试回放既有 identity，不产生第二份 provenance/report
    prov_store2 = fresh
    p1, r1 = prov_store2.get_by_operation(f"eval:{report_id}")
    ev._begin_provenance(
        report_id=report_id,
        record=None,
        scenarios=["CD"],
        prediction_files={},
        session_id="sess-prov",
        run_id="run_again",
        inputs=None,
    )
    assert prov_store2.report_count() == 1
    p2, r2 = prov_store2.get_by_operation(f"eval:{report_id}")
    assert p2.provenance_id == p1.provenance_id
    assert r2.report_id == r1.report_id


def test_research_session_uses_research_namespace(tmp_path, monkeypatch):
    ev, conv, prov_store = _isolated_eval_state(tmp_path, monkeypatch)
    _seed_session(
        conv,
        session_id="sess-research",
        input_json={
            "research": {
                "dataset_id": "cisg",
                "cluster_id": "cisg-art79-sample-001",
                "pack_version": "0.1.0",
            }
        },
    )

    # research 校验路径需要 reference —— 直接放行
    monkeypatch.setattr(ev, "_require_research_reference", lambda record: None)

    report_id, _ = ev.start_evaluation_task(["CD"], None, "sess-research", False)
    prov, report = prov_store.get_by_operation(f"eval:{report_id}")
    assert prov.rubric_namespace == "research"
    assert prov.rubric_version == "research-6d-1.0"
    assert report.namespace == "research"


def test_failed_scoring_marks_provenance_report(tmp_path, monkeypatch):
    ev, conv, prov_store = _isolated_eval_state(tmp_path, monkeypatch)
    _seed_session(conv)
    report_id, files = ev.start_evaluation_task(["CD"], None, "sess-prov", False)

    import evaluation.run_evaluation as runner

    def _boom(*a, **k):
        raise RuntimeError("scorer down")

    monkeypatch.setattr(runner, "run_evaluation", _boom)
    ev.execute_evaluation_task(report_id, ["CD"], files)

    prov, report = prov_store.get_by_operation(f"eval:{report_id}")
    assert report.status == "failed"
    assert "scorer down" in report.message
