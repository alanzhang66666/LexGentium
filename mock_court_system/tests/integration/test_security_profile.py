"""Production security profile: bind, auth, docs, origin, body limit."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(_PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PRODUCT_ROOT))

from api.middleware import security  # noqa: E402


@pytest.fixture(scope="module")
def app():
    import api_server

    return api_server.app


@pytest.fixture()
def client(app):
    # Lifespan runs on enter; loopback default with no token is dev mode.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_loopback_helpers():
    assert security.is_loopback("127.0.0.1")
    assert security.is_loopback("::1")
    assert security.is_loopback("localhost")
    assert not security.is_loopback("0.0.0.0")
    assert not security.is_loopback("192.168.1.10")


def test_non_loopback_without_token_fails_startup(monkeypatch, app):
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.delenv("API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="API_TOKEN"):
        with TestClient(app):
            pass


def test_non_loopback_with_token_starts(monkeypatch, app):
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_TOKEN", "tok-abc")
    with TestClient(app) as c:
        assert c.get("/health/live").status_code == 200


def test_protected_route_requires_token(monkeypatch, client):
    monkeypatch.setenv("API_TOKEN", "tok-secret-123")
    resp = client.post("/conversation/start", json={"scenario": "CI", "case_id": "x"})
    assert resp.status_code == 401
    body = resp.json()
    assert "tok-secret-123" not in resp.text
    assert body["error"]["code"] == "unauthorized"

    resp = client.post(
        "/conversation/start",
        json={"scenario": "CI", "case_id": "x"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401


def test_docs_require_same_token(monkeypatch, client):
    monkeypatch.setenv("API_TOKEN", "tok-docs")
    for path in ("/docs", "/openapi.json", "/redoc"):
        resp = client.get(path)
        assert resp.status_code == 401, path
        resp = client.get(path, headers={"Authorization": "Bearer tok-docs"})
        assert resp.status_code != 401, path


def test_health_endpoints_stay_public(monkeypatch, client):
    monkeypatch.setenv("API_TOKEN", "tok-hp")
    assert client.get("/health/live").status_code == 200


def test_origin_outside_allowlist_rejected_before_handler(monkeypatch, client):
    monkeypatch.delenv("API_TOKEN", raising=False)
    resp = client.post(
        "/conversation/nonexistent-session/message",
        json={"message": "hi"},
        headers={"Origin": "https://evil.example.com"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "origin_forbidden"


def test_allowed_origin_and_no_origin_pass(monkeypatch, client):
    monkeypatch.delenv("API_TOKEN", raising=False)
    allowed = client.post(
        "/conversation/nonexistent-session/message",
        json={"message": "hi"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert allowed.status_code == 404  # reached the handler
    no_origin = client.post(
        "/conversation/nonexistent-session/message",
        json={"message": "hi"},
    )
    assert no_origin.status_code == 404


def test_custom_origin_allowlist(monkeypatch, client):
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.setenv("API_ALLOWED_ORIGINS", "https://app.example.com")
    resp = client.post(
        "/conversation/x/message",
        json={"message": "hi"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert resp.status_code == 403
    ok = client.post(
        "/conversation/x/message",
        json={"message": "hi"},
        headers={"Origin": "https://app.example.com"},
    )
    assert ok.status_code == 404


def test_body_limit_rejected_before_handler(monkeypatch, client):
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.setenv("API_MAX_BODY_BYTES", "16")
    resp = client.post(
        "/conversation/start",
        content=b'{"scenario": "CI", "case_id": "this body is way over 16 bytes"}',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "request_too_large"


def test_get_requests_not_limited_or_origin_checked(monkeypatch, client):
    monkeypatch.delenv("API_TOKEN", raising=False)
    resp = client.get(
        "/conversation/nonexistent",
        headers={"Origin": "https://evil.example.com"},
    )
    assert resp.status_code in (404, 405)
    assert resp.status_code != 403
