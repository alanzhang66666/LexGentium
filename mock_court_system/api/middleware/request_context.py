"""RequestContext：每请求关联上下文（contextvars）+ 纯 ASGI middleware。

- 合法传入 ``X-Request-Id`` 原样保留；缺失或非法时只生成一个合法 ID。
- Request ID 同时写入响应头 ``X-Request-Id`` 与每请求一条的 JSON
  completion log（request_id/route_template/method/status/duration_ms +
  可用 correlation identities）。
- 路由/服务可通过 ``bind_request_context`` 补充 session/task/run/report
  等身份，日志按可用性投影，缺失身份不生成伪值。
"""
from __future__ import annotations

import json
import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any, MutableMapping, Optional

from api.contracts.common import CORRELATION_HEADERS, is_valid_request_id, new_request_id

_request_log = logging.getLogger("lexgentium.request")


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    operation_id: Optional[str] = None
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    run_id: Optional[str] = None
    report_id: Optional[str] = None
    game_id: Optional[str] = None
    started_monotonic_ns: int = 0

    def correlation_fields(self) -> dict:
        """可用非空身份字段（不含 request_id）。"""
        fields = {
            "operation_id": self.operation_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "report_id": self.report_id,
            "game_id": self.game_id,
        }
        return {k: v for k, v in fields.items() if v}


_current: ContextVar[RequestContext] = ContextVar("lexgentium_request_context")


def current_request_context() -> RequestContext:
    """返回当前请求的 RequestContext；无请求上下文时生成一个临时上下文。"""
    try:
        return _current.get()
    except LookupError:
        return RequestContext(
            request_id=new_request_id(),
            started_monotonic_ns=time.perf_counter_ns(),
        )


def bind_request_context(**fields: Optional[str]) -> RequestContext:
    """为当前请求上下文补充身份字段；None 值被忽略。"""
    ctx = current_request_context()
    updated = replace(ctx, **{k: v for k, v in fields.items() if v is not None})
    _current.set(updated)
    return updated


def _header_map(scope: MutableMapping[str, Any]) -> dict:
    headers: dict = {}
    for key, value in scope.get("headers") or []:
        headers[key.decode("latin-1").lower()] = value.decode("latin-1")
    return headers


def _emit_completion_log(scope: MutableMapping[str, Any], status: int, ctx: RequestContext) -> None:
    route = scope.get("route")
    route_template = getattr(route, "path", None) or scope.get("path", "")
    duration_ms = round((time.perf_counter_ns() - ctx.started_monotonic_ns) / 1_000_000, 3)
    record = {
        "request_id": ctx.request_id,
        "route_template": route_template,
        "method": scope.get("method", ""),
        "status": status,
        "duration_ms": duration_ms,
    }
    record.update(ctx.correlation_fields())
    _request_log.info(json.dumps(record, ensure_ascii=False))


class RequestContextMiddleware:
    """最外层 ASGI middleware：归一化 Request ID 并输出 completion log。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = _header_map(scope)
        incoming = headers.get("x-request-id")
        request_id = incoming if is_valid_request_id(incoming) else new_request_id()
        ctx = RequestContext(
            request_id=request_id,
            operation_id=headers.get("x-operation-id") or None,
            session_id=headers.get(CORRELATION_HEADERS["session_id"]) or None,
            task_id=headers.get(CORRELATION_HEADERS["task_id"]) or None,
            run_id=headers.get(CORRELATION_HEADERS["run_id"]) or None,
            report_id=headers.get(CORRELATION_HEADERS["report_id"]) or None,
            game_id=headers.get(CORRELATION_HEADERS["game_id"]) or None,
            started_monotonic_ns=time.perf_counter_ns(),
        )
        token = _current.set(ctx)
        scope.setdefault("state", {})["request_context"] = ctx
        state_holder = {"status": 500, "started": False}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                state_holder["status"] = message["status"]
                state_holder["started"] = True
                raw_headers = message.setdefault("headers", [])
                raw_headers.append((b"x-request-id", request_id.encode("latin-1")))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            if not state_holder["started"]:
                # 内层未产生响应：由本层给出受控 500，保证 Request ID 一致。
                body = json.dumps(
                    {
                        "error": {
                            "code": "internal_error",
                            "message": "internal server error",
                            "request_id": request_id,
                            "retriable": False,
                            "field_errors": [],
                        }
                    },
                    ensure_ascii=False,
                ).encode("utf-8")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"x-request-id", request_id.encode("latin-1")),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
            raise
        finally:
            final_ctx = _current.get()
            _emit_completion_log(scope, state_holder["status"], final_ctx)
            _current.reset(token)
