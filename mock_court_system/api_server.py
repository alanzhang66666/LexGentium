"""
FastAPI 后端入口（薄壳）。

全部业务路由位于 api/routers/ 下，共享运行时状态位于 api/state.py；
本文件只负责 app 装配、中间件与启动。
"""
import uvicorn
import os
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# 根日志配置必须先于 api.state 导入（agents 在 import 阶段即完成 BM25 初始化并输出日志）
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from api.routers import ALL_ROUTERS
from api.errors import public_error_payload, register_exception_handlers
from api.middleware.request_context import RequestContextMiddleware, current_request_context
from api.middleware import security


def _public_error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=public_error_payload(
            code=code,
            message=message,
            request_id=current_request_context().request_id,
            detail=message,
        ),
    )


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # 非 loopback 绑定且无 API_TOKEN 时 fail-closed：在接受 socket 前终止启动。
    security.validate_bind_security()
    yield


app = FastAPI(lifespan=_lifespan)


# 注意注册顺序：先注册的装饰器更靠内层；require_bearer_token 最后注册，
# 请求处理顺序为 RequestContext -> bearer -> origin -> body limit -> route。

@app.middleware("http")
async def enforce_body_limit(request: Request, call_next):
    if request.method in security._STATE_CHANGING_METHODS:
        limit = security.max_body_bytes()
        content_length = request.headers.get("content-length", "").strip()
        if content_length.isdigit() and int(content_length) > limit:
            return _public_error(413, "request_too_large", "request body too large")

        # Inspect the actual stream, including chunked/unknown-length requests.
        # Reject before invoking the route, without trusting Content-Length.
        chunks = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > limit:
                return _public_error(413, "request_too_large", "request body too large")
            chunks.append(chunk)
        body = b"".join(chunks)

        async def replay_body():
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = replay_body
    return await call_next(request)


@app.middleware("http")
async def enforce_origin_allowlist(request, call_next):
    if request.method in security._STATE_CHANGING_METHODS:
        origin = request.headers.get("origin", "").strip().rstrip("/")
        if origin and origin not in security.allowed_origins():
            return _public_error(403, "origin_forbidden", "origin not allowed")
    return await call_next(request)


@app.middleware("http")
async def require_bearer_token(request, call_next):
    token = security.api_token()
    if token and request.url.path not in security.PUBLIC_PATHS:
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {token}":
            return _public_error(401, "unauthorized", "unauthorized")
    return await call_next(request)


# RequestContextMiddleware 最后注册 => 最外层，保证 401/403/413/500 也携带 Request ID。
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)


for _router in ALL_ROUTERS:
    app.include_router(_router)


if __name__ == "__main__":
    # 默认仅监听本机；如需局域网访问，设置 API_HOST=0.0.0.0 并必须设置 API_TOKEN
    host = os.getenv("API_HOST", "127.0.0.1")
    security.validate_bind_security(host=host)
    uvicorn.run(app, host=host, port=int(os.getenv("API_PORT", "8000")))
