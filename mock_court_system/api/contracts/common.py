"""Shared identity and error contract primitives.

Request ID 格式、错误代码与 PublicError envelope 是 Backend_API 与 BFF
之间的稳定契约；BFF 校验后端返回值与本模块定义一致，否则视为
backend_contract_violation。
"""
from __future__ import annotations

import re
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

#: 合法 Request ID：16-64 位 [A-Za-z0-9._-]
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{16,64}$")

REQUEST_ID_HEADER = "x-request-id"
OPERATION_ID_HEADER = "x-operation-id"
CORRELATION_HEADERS = {
    "session_id": "x-session-id",
    "task_id": "x-task-id",
    "run_id": "x-run-id",
    "report_id": "x-report-id",
    "game_id": "x-game-id",
}

SECRET_MASK = "********"


def is_valid_request_id(value: Optional[str]) -> bool:
    return bool(value) and bool(REQUEST_ID_PATTERN.fullmatch(value))


def new_request_id() -> str:
    """生成一个合法 Request ID（uuid4 hex，32 字符）。"""
    return uuid.uuid4().hex


#: HTTP status -> 稳定错误代码（见 design.md 错误分类表）
STATUS_ERROR_CODES = {
    400: "invalid_request",
    401: "unauthorized",
    403: "forbidden",
    404: "resource_not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "request_too_large",
    422: "validation_failed",
    429: "capacity_exceeded",
    500: "internal_error",
    502: "backend_unavailable",
    503: "service_unavailable",
    504: "backend_timeout",
}


def error_code_for_status(status: int) -> str:
    if status in STATUS_ERROR_CODES:
        return STATUS_ERROR_CODES[status]
    return "internal_error" if status >= 500 else "invalid_request"


class FieldError(BaseModel):
    """一个可判定字段违规；path 为稳定的 JSON Pointer 风格路径。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    reason: str  # required | type | range | format | conflict


class PublicError(BaseModel):
    """对外安全的错误对象：不含 Secret/stack/绝对路径/原始 prompt。"""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: str
    retriable: bool = False
    field_errors: list[FieldError] = Field(default_factory=list)
