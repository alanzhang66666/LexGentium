"""Backend API contract tests: Request ID, PublicError envelope, validation errors."""
from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from api.contracts.common import is_valid_request_id
from tests.test_offline_governance import _load_api_server, _runtime_path


def _client(monkeypatch, name="contract"):
    api_server = _load_api_server(monkeypatch, _runtime_path(f"api-{name}"))
    return api_server, TestClient(api_server.app)


def test_request_id_valid_incoming_preserved(monkeypatch):
    _, client = _client(monkeypatch, "reqid-keep")
    rid = "req-0123456789abcdef"
    response = client.get("/health", headers={"X-Request-Id": rid})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == rid


@pytest.mark.parametrize("bad", ["", "short", "has space and is too long", "x" * 65, "invalid*request*id*chars"])
def test_request_id_invalid_or_missing_generates_one(monkeypatch, bad):
    _, client = _client(monkeypatch, "reqid-gen")
    headers = {"X-Request-Id": bad} if bad else {}
    response = client.get("/health", headers=headers)
    assert response.status_code == 200
    generated = response.headers["x-request-id"]
    assert generated != bad
    assert is_valid_request_id(generated)


def test_request_id_echoed_in_completion_log(monkeypatch, caplog):
    _, client = _client(monkeypatch, "reqid-log")
    rid = "req-abcdef0123456789"
    with caplog.at_level(logging.INFO, logger="lexgentium.request"):
        client.get("/health", headers={"X-Request-Id": rid})
    records = [json.loads(r.message) for r in caplog.records if r.name == "lexgentium.request"]
    assert len(records) == 1
    record = records[0]
    assert record["request_id"] == rid
    assert record["method"] == "GET"
    assert record["status"] == 200
    assert record["route_template"] == "/health"
    assert isinstance(record["duration_ms"], (int, float))


def test_validation_error_field_paths_and_reasons(monkeypatch):
    _, client = _client(monkeypatch, "validation")

    extra = client.post("/evaluate", json={"unexpected": "value"})
    assert extra.status_code == 422
    error = extra.json()["error"]
    assert error["code"] == "validation_failed"
    assert is_valid_request_id(error["request_id"])
    paths = {fe["path"] for fe in error["field_errors"]}
    reasons = {fe["reason"] for fe in error["field_errors"]}
    assert "/body/unexpected" in paths
    assert "conflict" in reasons  # extra_forbidden -> conflict
    assert "detail" in extra.json()  # 兼容字段保留

    missing = client.post("/evaluate", json={"use_default_predictions": False})
    assert missing.status_code == 422
    missing_error = missing.json()["error"]
    assert missing_error["code"] == "validation_failed"
    assert any(fe["reason"] == "required" for fe in missing_error["field_errors"])


def test_validation_error_request_id_matches_header(monkeypatch):
    _, client = _client(monkeypatch, "validation-rid")
    response = client.post("/evaluate", json={"unexpected": 1})
    assert response.status_code == 422
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_not_found_error_envelope(monkeypatch):
    _, client = _client(monkeypatch, "notfound")
    response = client.get("/evaluation/status/no-such-report")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "resource_not_found"
    assert is_valid_request_id(body["error"]["request_id"])
    assert body["detail"]


def test_unhandled_error_is_public_error_without_internals(monkeypatch):
    api_server, _ = _client(monkeypatch, "boom")
    # Starlette 在 handler 生成响应后仍会 re-raise，供 server/test client 记录
    client = TestClient(api_server.app, raise_server_exceptions=False)

    @api_server.app.get("/_test_boom")
    def _boom():
        raise RuntimeError("secret C:\\Users\\x\\.env token=abc123def456")

    response = client.get("/_test_boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "internal server error"
    assert is_valid_request_id(body["error"]["request_id"])
    text = json.dumps(body, ensure_ascii=False)
    assert "C:\\Users" not in text
    assert "abc123def456" not in text
    assert "RuntimeError" not in text
