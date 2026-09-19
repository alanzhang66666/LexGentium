"""健康检查 路由。

- ``GET /health/live``：只报进程存活、version、time、Request ID；
  不访问 LLM、SQLite 业务记录或法条检索。
- ``GET /health/ready``：逐组件报告 configuration / conversation_store /
  runtime_store / evaluation_store / research_store / law_retrieval /
  hearing_runtime / plead_runtime；任一 required 失败返回 503
  ``not_ready``；不泄露路径、文件名、Secret 或 stack。
- ``GET /health``：兼容期 liveness 摘要 + 迁移提示。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api import state
from api.middleware.request_context import current_request_context
from core.release.version import VERSION_ID
from core.store.registry import StoreRegistry

router = APIRouter()


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _component(ok: bool, reason: Optional[str] = None) -> Dict[str, Any]:
    return {"ok": ok, "reason": reason}


def _check_configuration() -> Dict[str, Any]:
    """配置可用性：生产 profile 下 LLM 必填项缺失即失败。"""
    try:
        import os

        profile = os.getenv("APP_PROFILE", "development").strip().lower()
        if profile == "production":
            import settings

            missing = [
                name
                for name, value in (
                    ("LLM_API_KEY", getattr(settings.settings, "llm_api_key", "")),
                    ("LLM_BASE_URL", getattr(settings.settings, "llm_base_url", "")),
                    ("LLM_MODEL", getattr(settings.settings, "llm_model", "")),
                )
                if not str(value or "").strip()
            ]
            if missing:
                return _component(False, "config_invalid")
        return _component(True)
    except Exception:
        return _component(False, "config_invalid")


def _check_store(logical_name: str) -> Dict[str, Any]:
    try:
        result = StoreRegistry().probe(logical_name)
        return _component(result.ok, result.reason)
    except Exception:
        return _component(False, "probe_failed")


def _check_law_retrieval() -> Dict[str, Any]:
    try:
        return _component(state.get_law_retriever() is not None, None)
    except Exception:
        return _component(False, "unavailable")


def _check_runtime(module: str, attr: str) -> Dict[str, Any]:
    try:
        mod = __import__(module, fromlist=[attr])
        return _component(getattr(mod, attr, None) is not None, "unavailable")
    except Exception:
        return _component(False, "unavailable")


@router.get("/health/live")
async def health_live():
    ctx = current_request_context()
    return {
        "status": "ok",
        "version": VERSION_ID,
        "time": _utcnow_iso(),
        "request_id": ctx.request_id,
    }


#: required 组件集合（design §402）。law_retrieval/runtimes 为产品必需。
_REQUIRED_COMPONENTS = (
    "configuration",
    "conversation_store",
    "runtime_store",
    "evaluation_store",
    "research_store",
    "law_retrieval",
    "hearing_runtime",
    "plead_runtime",
)


def _collect_components() -> Dict[str, Dict[str, Any]]:
    return {
        "configuration": _check_configuration(),
        "conversation_store": _check_store("conversation_store"),
        "runtime_store": _check_store("runtime_store"),
        "evaluation_store": _check_store("evaluation_store"),
        "research_store": _check_store("research_store"),
        "law_retrieval": _check_law_retrieval(),
        "hearing_runtime": _check_runtime("core.graphs.hearing_runtime", "HearingRuntime"),
        "plead_runtime": _check_runtime("core.graphs.plead_runtime", "PleadRuntime"),
    }


@router.get("/health/ready")
async def health_ready():
    ctx = current_request_context()
    components = _collect_components()
    failed = [
        {"component": name, "reason": components[name]["reason"] or "unavailable"}
        for name in _REQUIRED_COMPONENTS
        if not components[name]["ok"]
    ]
    payload = {
        "status": "not_ready" if failed else "ok",
        "version": VERSION_ID,
        "time": _utcnow_iso(),
        "request_id": ctx.request_id,
        "components": components,
        "failed": failed,
    }
    if failed:
        return JSONResponse(status_code=503, content={**payload, "code": "not_ready"})
    return payload


@router.get("/health")
async def health_check():
    """兼容期 liveness 摘要；不再返回路径/文件名。BFF 迁移后可移除。"""
    ctx = current_request_context()
    return {
        "status": "ok",
        "version": VERSION_ID,
        "time": _utcnow_iso(),
        "request_id": ctx.request_id,
        "law_retriever_ready": state.get_law_retriever() is not None,
        "hint": "use /health/live and /health/ready",
    }
