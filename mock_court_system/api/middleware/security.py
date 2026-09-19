"""Production security profile: bind validation, auth, Origin, body limit.

Contract (requirements 8.1–8.3, 8.6, 8.9, 8.10):

- A non-loopback bind without ``API_TOKEN`` fails startup before any socket
  is accepted (``validate_bind_security``).
- Protected routes return ``401 unauthorized`` without a valid token; no
  authentication material is echoed in responses or logs.
- Interactive docs (``/docs``, ``/redoc``, ``/openapi.json``) require the
  same token as protected routes — they are simply not public paths.
- State-changing requests with an ``Origin`` outside the allowlist are
  rejected ``403 origin_forbidden`` before the handler runs. Requests
  without an ``Origin`` header (server-to-server, e.g. the BFF) pass.
- Bodies larger than ``API_MAX_BODY_BYTES`` are rejected
  ``413 request_too_large`` before persistence or LLM invocation.

Environment:
- ``API_TOKEN`` — bearer token; empty means loopback-only dev mode.
- ``API_HOST`` — bind host for the startup validation.
- ``API_ALLOWED_ORIGINS`` — comma-separated Origin allowlist for browsers.
- ``API_MAX_BODY_BYTES`` — request body cap (default 1 MiB, same as BFF).
"""
from __future__ import annotations

import ipaddress
import os
from typing import Optional, Set

DEFAULT_MAX_BODY_BYTES = 1_048_576
_STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_DEFAULT_ALLOWED_ORIGINS = {"http://localhost:3000", "http://127.0.0.1:3000"}

# Health probes stay public; docs are intentionally absent — they require
# the same bearer validation as every protected route when a token exists.
PUBLIC_PATHS = {"/health", "/health/live", "/health/ready"}


def api_token() -> str:
    return os.getenv("API_TOKEN", "").strip()


def max_body_bytes() -> int:
    raw = os.getenv("API_MAX_BODY_BYTES", "").strip()
    try:
        value = int(raw)
        return value if value > 0 else DEFAULT_MAX_BODY_BYTES
    except (TypeError, ValueError):
        return DEFAULT_MAX_BODY_BYTES


def allowed_origins() -> Set[str]:
    raw = os.getenv("API_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return set(_DEFAULT_ALLOWED_ORIGINS)
    return {origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()}


def is_loopback(host: str) -> bool:
    host = (host or "").strip().lower()
    if host in {"localhost", "localhost."}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_bind_security(host: Optional[str] = None, token: Optional[str] = None) -> None:
    """Fail startup when binding beyond loopback without an API token."""
    host = (os.getenv("API_HOST", "127.0.0.1") if host is None else host).strip()
    token = api_token() if token is None else token
    if not is_loopback(host) and not token:
        raise RuntimeError(
            "refusing to start: non-loopback bind requires a non-empty API_TOKEN"
        )
