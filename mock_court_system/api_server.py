"""
FastAPI 后端入口（薄壳）。

全部业务路由位于 api/routers/ 下，共享运行时状态位于 api/state.py；
本文件只负责 app 装配、中间件与启动。
"""
import uvicorn
import os
import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# 根日志配置必须先于 api.state 导入（agents 在 import 阶段即完成 BM25 初始化并输出日志）
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from api import state
from api.state import _make_request_id
from api.routers import ALL_ROUTERS

app = FastAPI()

# 可选鉴权：设置 API_TOKEN 后，除健康检查外所有请求需带 Authorization: Bearer <token>
API_TOKEN = os.getenv("API_TOKEN", "").strip()
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def require_bearer_token(request, call_next):
    if API_TOKEN and request.url.path not in _PUBLIC_PATHS:
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {API_TOKEN}":
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
    return await call_next(request)


@app.middleware("http")
async def add_request_id_and_error_envelope(request, call_next):
    request_id = _make_request_id()
    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail, "request_id": request_id},
            headers=e.headers,
        )
    except Exception as e:
        state.eval_logger.error(f"unhandled error on {request.url.path}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "internal server error", "request_id": request_id},
        )


for _router in ALL_ROUTERS:
    app.include_router(_router)


if __name__ == "__main__":
    # 默认仅监听本机；如需局域网访问，设置 API_HOST=0.0.0.0 并强烈建议同时设置 API_TOKEN
    uvicorn.run(app, host=os.getenv("API_HOST", "127.0.0.1"), port=int(os.getenv("API_PORT", "8000")))
