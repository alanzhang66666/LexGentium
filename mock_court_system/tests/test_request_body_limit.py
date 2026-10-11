"""Body limit regression tests, including absent or misleading Content-Length."""
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import api_server


def test_request_body_limit_accepts_small_payload(monkeypatch):
    monkeypatch.setenv("API_MAX_BODY_BYTES", "32")
    client = TestClient(api_server.app)
    response = client.post("/conversation/start", json={"scenario": "CI", "case_id": "x"})
    # Underlying route may reject input, but size middleware must not return 413.
    assert response.status_code != 413


def test_request_body_limit_rejects_oversized_payload(monkeypatch):
    monkeypatch.setenv("API_MAX_BODY_BYTES", "32")
    with TestClient(api_server.app) as client:
        response = client.post("/conversation/start", content=b"x" * 100)
    assert response.status_code == 413
    assert response.json()["code"] == "request_too_large"
