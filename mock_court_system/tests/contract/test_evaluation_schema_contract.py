"""Contract tests for evaluation request, task status, and report responses."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.schemas import EvaluationRequest, EvaluationResponse
from core.store.evaluation_task_store import EvaluationTaskRecord, SqliteEvaluationTaskStore
from tests.test_offline_governance import _load_api_server, _runtime_path


def test_evaluation_models_declare_attribution_and_reject_implicit_fields():
    request = EvaluationRequest.model_validate(
        {
            "scenarios": ["CD"],
            "session_id": "session-contract",
            "run_id": "run_contract",
            "use_default_predictions": False,
        }
    )
    assert request.model_dump() == {
        "scenarios": ["CD"],
        "prediction_files": None,
        "use_default_predictions": False,
        "session_id": "session-contract",
        "run_id": "run_contract",
    }

    with pytest.raises(ValidationError) as extra_error:
        EvaluationRequest.model_validate({"session_id": "session-contract", "implicit": True})
    assert extra_error.value.errors()[0]["type"] == "extra_forbidden"

    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(
            {"scenarios": ["CD"], "use_default_predictions": False}
        )


def test_evaluation_response_has_closed_status_and_explicit_error_contract():
    response = EvaluationResponse.model_validate(
        {
            "report_id": "report-contract",
            "status": "failed",
            "message": "evaluation failed",
            "session_id": "session-contract",
            "run_id": "run_contract",
            "error": {"code": "evaluation_failed", "message": "evaluation failed"},
        }
    )
    dumped = response.model_dump()
    assert dumped["session_id"] == "session-contract"
    assert dumped["run_id"] == "run_contract"
    assert dumped["error"] == {
        "code": "evaluation_failed",
        "message": "evaluation failed",
    }

    with pytest.raises(ValidationError):
        EvaluationResponse.model_validate(
            {
                "report_id": "report-contract",
                "status": "unknown",
                "message": "invalid state",
            }
        )


def test_status_and_report_routes_serialize_the_same_declared_contract(tmp_path, monkeypatch):
    api_server = _load_api_server(monkeypatch, _runtime_path("evaluation-contract-api"))
    from api import state

    store = SqliteEvaluationTaskStore(str(tmp_path / "evaluation-contract.sqlite3"))
    monkeypatch.setattr(state, "evaluation_task_store", store)
    state.evaluation_tasks.clear()

    record = EvaluationTaskRecord(
        report_id="report-contract",
        status="completed",
        message="done",
        created_at="2026-09-12T00:00:00Z",
        updated_at="2026-09-12T00:00:00Z",
        results_json=json.dumps({"CD": [{"score": 1}]}),
        report_path="evaluation/results/evaluation_report_report-contract.json",
        session_id="session-contract",
        run_id="run_contract",
    )
    store.upsert(record)

    client = TestClient(api_server.app)
    expected_keys = {
        "report_id",
        "status",
        "message",
        "results",
        "report_path",
        "session_id",
        "run_id",
        "error",
        "provenance",
        "correlation",
    }
    for path in (
        "/evaluation/status/report-contract",
        "/evaluation/reports/report-contract",
    ):
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        assert set(body) == expected_keys
        assert body["report_id"] == "report-contract"
        assert body["session_id"] == "session-contract"
        assert body["run_id"] == "run_contract"
        assert body["status"] == "completed"
        assert body["error"] is None


def test_evaluate_route_rejects_undeclared_and_missing_input_fields(monkeypatch):
    api_server = _load_api_server(monkeypatch, _runtime_path("evaluation-contract-validation"))
    client = TestClient(api_server.app)

    undeclared = client.post("/evaluate", json={"unexpected": "value"})
    assert undeclared.status_code == 422
    assert any(
        error["loc"][-1] == "unexpected" and error["type"] == "extra_forbidden"
        for error in undeclared.json()["detail"]
    )

    missing_input = client.post(
        "/evaluate",
        json={"scenarios": ["CD"], "use_default_predictions": False},
    )
    assert missing_input.status_code == 422
