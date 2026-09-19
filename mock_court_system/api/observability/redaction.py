"""Secret redactor：日志/错误/metric/trace/health/browser/evidence 六出口复用。"""
from __future__ import annotations

import re
from typing import Any, Mapping

SECRET_MASK = "********"

#: key=value / "key": "value" 形式的 secret 键名
_SECRET_KEY_RE = re.compile(
    r"(?i)\b(\w*(?:api[_-]?key|token|secret|password|authorization|bearer|credential)\w*)"
    r"([\"']?)\s*[:=]\s*([\"']?)(?:bearer\s+)?([^\s,\"'}]+)\3"
)
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-+/=]{8,}")
_URL_CREDENTIAL_RE = re.compile(r"(https?://)[^/@\s]+@")

#: 默认按名字识别的 secret 字段（结构化数据）
_SECRET_FIELD_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "token",
        "api_token",
        "secret",
        "password",
        "authorization",
        "dashscope_api_key",
        "llm_api_key",
        "court_api_key",
        "credential",
        "access_token",
        "refresh_token",
    }
)


def _is_secret_name(name: str) -> bool:
    lowered = name.lower()
    return lowered in _SECRET_FIELD_NAMES or any(
        lowered.endswith(suffix) for suffix in ("_key", "_token", "_secret", "_password")
    )


def redact_secrets(value: Any) -> Any:
    """递归脱敏：字符串按 pattern、mapping 按字段名，其余原样返回。"""
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, Mapping):
        out = {}
        for k, v in value.items():
            if isinstance(k, str) and _is_secret_name(k) and v not in (None, ""):
                out[k] = SECRET_MASK
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(value, (list, tuple)):
        return type(value)(redact_secrets(v) for v in value)
    return value


def _redact_text(text: str) -> str:
    text = _SECRET_KEY_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}={m.group(3)}{SECRET_MASK}{m.group(3)}", text)
    text = _BEARER_RE.sub(f"Bearer {SECRET_MASK}", text)
    text = _URL_CREDENTIAL_RE.sub(r"\1" + SECRET_MASK + "@", text)
    return text
