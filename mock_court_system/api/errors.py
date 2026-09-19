"""统一错误契约：PublicError envelope、异常处理器与 Secret 脱敏。

所有错误响应形状固定为 ``{"error": PublicError}``；为兼容既有契约测试，
同时保留 FastAPI 风格的 ``detail`` 字段。公开错误不含 Secret、stack、
绝对路径、原始 prompt、完整对话或法律原文。
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.contracts.common import (
    FieldError,
    PublicError,
    SECRET_MASK,
    error_code_for_status,
)
from api.middleware.request_context import current_request_context

logger = logging.getLogger("lexgentium.error")

_SECRET_ENV_VARS = (
    "LLM_API_KEY",
    "API_TOKEN",
    "BACKEND_API_TOKEN",
    "DASHSCOPE_API_KEY",
    "COURT_API_KEY",
)
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-+/=]+")
_URL_RE = re.compile(r"(?i)https?://[^\s\"']+")
_KEY_VALUE_RE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|token|secret|password|authorization)([\"']?\s*[:=]\s*[\"']?)([^\s,\"']+)"
)
_ABS_PATH_RE = re.compile(r"(?:[A-Za-z]:\\|\\\\|/)[^\s\"']*(?:[/\\][^\s\"']*)+")


def redact_sensitive(text: Any) -> str:
    """对公开输出脱敏：Secret 值、Bearer、key=value 凭据、绝对路径。"""
    if text is None:
        return ""
    out = str(text)
    out = _URL_RE.sub("<url>", out)
    out = _BEARER_RE.sub("Bearer " + SECRET_MASK, out)
    out = _KEY_VALUE_RE.sub(lambda m: m.group(1) + m.group(2) + SECRET_MASK, out)
    for var in _SECRET_ENV_VARS:
        value = os.getenv(var, "")
        if value:
            out = out.replace(value, SECRET_MASK)
    out = _ABS_PATH_RE.sub("<path>", out)
    return out


def _request_id(request: Request) -> str:
    ctx = getattr(request.state, "request_context", None)
    if ctx is None:
        ctx = current_request_context()
    return ctx.request_id


def public_error_payload(
    *,
    code: str,
    message: str,
    request_id: str,
    retriable: bool = False,
    field_errors: Optional[list] = None,
    detail: Any = None,
) -> dict:
    error = PublicError(
        code=code,
        message=redact_sensitive(message),
        request_id=request_id,
        retriable=retriable,
        field_errors=field_errors or [],
    )
    payload = {"error": error.model_dump()}
    if detail is not None:
        payload["detail"] = detail
    return payload


_REASON_BY_TYPE = {
    "missing": "required",
    "extra_forbidden": "conflict",
    "value_error": "required",
    "model_attributes_type": "type",
    "string_type": "type",
    "int_type": "type",
    "float_type": "type",
    "bool_type": "type",
    "list_type": "type",
    "dict_type": "type",
    "int_parsing": "type",
    "float_parsing": "type",
    "bool_parsing": "type",
    "json_type": "type",
    "json_invalid": "format",
    "string_too_short": "range",
    "string_too_long": "range",
    "too_short": "range",
    "too_long": "range",
    "greater_than": "range",
    "greater_than_equal": "range",
    "less_than": "range",
    "less_than_equal": "range",
    "literal_error": "format",
    "enum": "format",
    "string_pattern_mismatch": "format",
    "union_tag_invalid": "format",
    "is_instance_of": "type",
    "date_type": "type",
    "datetime_type": "type",
    "url_type": "format",
    "url_parsing": "format",
}


def reason_from_error_type(error_type: str) -> str:
    """把 pydantic 错误类型映射为稳定 reason：required|type|range|format|conflict。"""
    if error_type in _REASON_BY_TYPE:
        return _REASON_BY_TYPE[error_type]
    if error_type.startswith("missing"):
        return "required"
    if error_type.endswith("_type") or error_type.endswith("_parsing"):
        return "type"
    if (
        "greater" in error_type
        or "less" in error_type
        or "too_" in error_type
        or error_type.startswith("min")
        or error_type.startswith("max")
    ):
        return "range"
    return "format"


def _field_path(loc) -> str:
    parts = [str(p) for p in loc]
    return "/" + "/".join(parts) if parts else "/body"


async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = _request_id(request)
    field_errors = [
        FieldError(path=_field_path(err.get("loc", ())), reason=reason_from_error_type(err.get("type", "")))
        for err in exc.errors()
    ]
    payload = public_error_payload(
        code="validation_failed",
        message="request validation failed",
        request_id=request_id,
        field_errors=field_errors,
        detail=jsonable_encoder(exc.errors()),
    )
    return JSONResponse(status_code=422, content=payload)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = _request_id(request)
    code = error_code_for_status(exc.status_code)
    message = exc.detail if isinstance(exc.detail, str) else "request failed"
    if exc.status_code >= 500:
        message = "internal server error"
    payload = public_error_payload(
        code=code,
        message=redact_sensitive(message),
        request_id=request_id,
        detail=exc.detail,
    )
    return JSONResponse(status_code=exc.status_code, content=payload, headers=getattr(exc, "headers", None))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    logger.error("unhandled exception on %s %s", request.method, request.url.path, exc_info=True)
    payload = public_error_payload(
        code="internal_error",
        message="internal server error",
        request_id=request_id,
    )
    return JSONResponse(status_code=500, content=payload)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
