"""Exercise the production HTTP task dispatch, not just the replacement service."""
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    from api import state
    from api.routers.evaluate import router
    from core.store.conversation_store import MemoryConversationStore
    from core.store.evaluation_task_store import SqliteEvaluationTaskStore

    monkeypatch.setattr(state, "conversation_store", MemoryConversationStore())
    monkeypatch.setattr(state, "evaluation_task_store", SqliteEvaluationTaskStore(str(tmp_path / "tasks.sqlite3")))
    monkeypatch.setattr(state, "evaluation_tasks", {})
    monkeypatch.setattr(state, "project_root", tmp_path)
    config = {"evaluation": {
        "paths": {
            "ground_truth": {"ci": str(PROJECT / "evaluation/data/test_run/CI_test_gt.jsonl")},
            "output": {"root": str(tmp_path / "evaluation/results")},
        },
        "scenarios": {"CI": {"enabled": True}},
    }}
    (tmp_path / "evaluation/results").mkdir(parents=True)
    (tmp_path / "evaluation/eval_config.yaml").write_text(json.dumps(config))
    app = FastAPI()
    app.include_router(router)
    return state, TestClient(app), tmp_path, config


def create_session(state, session_id, text="最终文书", role="Final"):
    record = state.conversation_store.create(session_id=session_id, scenario="CI", case_id="CI-Test", input_json={})
    record.dialog_history = [{"role": role, "turn": 0, "message": text}]
    state.conversation_store.save(record)
    return record


def test_http_evaluation_owns_report_even_with_history_and_concurrency(runtime):
    state, client, tmp, _ = runtime
    decoy_id = "ffffffff-ffff-4fff-bfff-ffffffffffff"
    (tmp / "evaluation/results" / f"evaluation_report_{decoy_id}.json").write_text(
        json.dumps({"report_id": decoy_id, "CI": [{"case_id": "DECOY"}]}))
    for name in ("A", "B"):
        create_session(state, name, f"已确认文书-{name}")

    def run(name):
        started = client.post("/evaluate", json={"scenarios": ["CI"], "session_id": name, "use_default_predictions": False})
        assert started.status_code == 200, started.text
        body = started.json()
        assert body["session_id"] == name
        result = client.get(f"/evaluation/status/{body['report_id']}").json()
        assert result["status"] == "completed", result
        assert result["results"]["report_id"] == body["report_id"]
        assert result["run_id"] == result["results"]["run_id"]
        assert result["results"]["CI"][0]["model_output"] == f"已确认文书-{name}"
        assert result["results"]["CI"][0]["score"]["method"] == "structure_check"
        return result["report_id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(run, ("A", "B")))
    assert len(set(ids)) == 2
    listed = client.get("/evaluation/results").json()["reports"]
    assert all(row["scenarios"] == ["CI"] for row in listed)


def test_same_session_tasks_keep_independent_documents(runtime):
    from api.services.evaluation import start_evaluation_task, execute_evaluation_task
    state, _, _, _ = runtime
    record = create_session(state, "same", "first document")
    report_a, files_a = start_evaluation_task(["CI"], None, "same", False)
    record.dialog_history.append({"turn": 1, "role": "Final", "message": "second document"})
    state.conversation_store.save(record)
    report_b, files_b = start_evaluation_task(["CI"], None, "same", False)
    assert files_a != files_b
    execute_evaluation_task(report_b, ["CI"], files_b)
    execute_evaluation_task(report_a, ["CI"], files_a)
    for report, text in ((report_a, "first document"), (report_b, "second document")):
        stored = state.evaluation_task_store.get(report)
        assert stored.status == "completed"
        assert stored.results()["CI"][0]["model_output"] == text
        assert stored.results()["CI"][0]["input_hash"]


def test_http_rejects_user_keywords_without_final_output(runtime):
    state, client, _, _ = runtime
    create_session(state, "words", "案号 本院认为 判决 适用法律", "Plaintiff")
    response = client.post("/evaluate", json={"scenarios": ["CI"], "session_id": "words"})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "missing_final_output"
    assert state.evaluation_tasks == {}


def test_only_final_output_is_scored_and_scenario_cannot_change(runtime):
    state, client, _, _ = runtime
    record = create_session(state, "words", "案号 本院认为 判决 适用法律", "Plaintiff")
    record.dialog_history.append({"turn": 1, "role": "Final", "message": "尚无法作出结论"})
    state.conversation_store.save(record)
    response = client.post("/evaluate", json={"scenarios": ["CI"], "session_id": "words"})
    report = client.get(f"/evaluation/status/{response.json()['report_id']}").json()
    assert report["results"]["CI"][0]["score"]["score"] == 0
    mismatch = client.post("/evaluate", json={"scenarios": ["CD"], "session_id": "words"})
    assert mismatch.status_code == 400


@pytest.mark.parametrize("content", [None, "", "not json"])
def test_missing_empty_or_broken_prediction_never_completes(runtime, content):
    state, client, tmp, _ = runtime
    prediction = tmp / "prediction.jsonl"
    if content is not None:
        prediction.write_text(content)
    started = client.post("/evaluate", json={"scenarios": ["CI"], "prediction_files": {"CI": str(prediction)}, "use_default_predictions": False})
    assert started.status_code == 200
    report_id = started.json()["report_id"]
    status = client.get(f"/evaluation/status/{report_id}").json()
    assert status["status"] == "failed"
    assert not (tmp / "evaluation/results" / f"evaluation_report_{report_id}.json").exists()


def test_zero_samples_and_scoring_failure_do_not_write_success(runtime, monkeypatch):
    from evaluation.run_evaluation import run_evaluation, EmptyEvaluationBodyError, ScoringFailedError, EvaluatorWrapper
    _, _, tmp, config = runtime
    with pytest.raises(EmptyEvaluationBodyError):
        run_evaluation(config, [])
    prediction = tmp / "pred.jsonl"
    prediction.write_text(json.dumps({"id": "CI-Test", "model_output": "confirmed output"}))
    def fail(*args):
        raise RuntimeError("scorer failed")
    monkeypatch.setattr(EvaluatorWrapper, "evaluate_one", fail)
    with pytest.raises(ScoringFailedError):
        run_evaluation(config, ["CI"], {"CI": str(prediction)})
    assert not list((tmp / "evaluation/results").glob("evaluation_report_*.json"))


def test_selected_dataset_case_evaluates_with_its_same_split_reference(runtime):
    from api.services.cases import get_civil_identity
    from api import state

    _, client, tmp, _ = runtime
    # Freeze the real selected case, then run through the HTTP evaluation entry point.
    state.project_root = PROJECT
    try:
        identity = get_civil_identity("dataset_1000:val:CASE-0001")
    finally:
        state.project_root = tmp
    assert identity and identity["split"] == "val"
    record = create_session(state, "selected-civil")
    record.case_id = "dataset_1000:val:CASE-0001"
    record.input_json["civil_case"] = identity
    state.conversation_store.save(record)
    started = client.post("/evaluate", json={"scenarios": ["CI"], "session_id": record.session_id})
    assert started.status_code == 200, started.text
    status = client.get(f"/evaluation/status/{started.json()['report_id']}").json()
    assert status["status"] == "completed", status
    result = status["results"]["CI"][0]
    assert result["case_id"] == "dataset_1000:val:CASE-0001"
    assert result["reference_id"] == "CI-0001"
    assert result["civil_case"]["split"] == "val"


def test_imported_case_cannot_borrow_another_valid_civil_identity(runtime):
    from api.services.cases import get_civil_identity
    state, client, tmp, _ = runtime
    state.project_root = PROJECT
    try:
        identity = get_civil_identity("dataset_1000:test:CASE-0001")
    finally:
        state.project_root = tmp
    record = create_session(state, "wrong-identity")
    record.case_id = "dataset_1000:val:CASE-0001"
    record.input_json["civil_case"] = identity
    state.conversation_store.save(record)
    response = client.post("/evaluate", json={"scenarios": ["CI"], "session_id": record.session_id})
    assert response.status_code == 200
    report_id = response.json()["report_id"]
    status = client.get(f"/evaluation/status/{report_id}").json()
    assert status["status"] == "failed"
    assert not (tmp / "evaluation/results" / f"evaluation_report_{report_id}.json").exists()
