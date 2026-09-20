"""LLM 配置与参考数据 路由。"""
from typing import Optional, Dict, Any, List
import asyncio
import json
import time
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from fastapi.responses import JSONResponse, StreamingResponse

from api import state
from api.schemas import (
    ApiRequest, ApiResponse, AutoAdvanceRequest, AutoAdvanceResponse,
    ConversationImportRequest, ConversationImportResponse,
    ConversationMessageRequest, ConversationMessageResponse,
    ConversationStartRequest, ConversationStartResponse,
    DualModeRequest, EvaluationRequest, EvaluationResponse,
    FullSimulationRequest, FullSimulationStatusResponse,
    GameCounterfactualRequest, GameCreateRequest, GameEvaluateRequest,
    GameRoundRequest, GameStrategySetRequest, LawSearchRequest,
    LawSearchResponse, LiabilityCounterfactualRequest, LLMConfigRequest,
    DeepSeekChatCompletionRequest,
    MediationBargainRequest, MediationCreateRequest, MediationStatementRequest,
    MultiJudgeRequest, ProgressiveRAGRequest,
)

router = APIRouter()

@router.get("/config/llm")
async def get_llm_config():
    demo_mode = bool(getattr(state.llm_client, "demo_mode", False))
    return {
        "provider": state.llm_client.provider,
        "api_key_masked": "demo-****" if demo_mode else state._mask_key(state.llm_client.api_key or ""),
        "api_key_set": demo_mode or bool(state.llm_client.api_key),
        "base_url": state.llm_client.base_url,
        "model": state.llm_client.model,
        "thinking": state.llm_client.thinking,
        "reasoning_effort": state.llm_client.reasoning_effort,
        "fast_thinking": state.llm_client.fast_thinking,
        "fast_reasoning_effort": state.llm_client.fast_reasoning_effort,
        "temperature": state.llm_client.temperature,
        "max_tokens": state.llm_client.max_tokens,
        "timeout": state.llm_client.timeout,
        "chat_model_ready": demo_mode or state.llm_client.chat_model is not None,
        "demo_mode": demo_mode,
    }


@router.post("/config/llm")
async def update_llm_config(req: LLMConfigRequest):
    try:
        new_llm = state.LLMClient(
            api_key=req.api_key,
            base_url=req.base_url,
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            timeout=req.timeout,
            provider=req.provider,
            thinking=req.thinking,
            reasoning_effort=req.reasoning_effort,
            fast_thinking=req.fast_thinking,
            fast_reasoning_effort=req.fast_reasoning_effort,
            demo_mode=bool(getattr(state.llm_client, "demo_mode", False)),
        )
        state._reinit_llm_and_agents(new_llm)
        state._persist_llm_env(req)

        return {
            "success": True,
            "message": "LLM 配置已更新并持久化，所有 Agent 已重新初始化",
            "chat_model_ready": new_llm.demo_mode or new_llm.chat_model is not None,
            "base_url": new_llm.base_url,
            "model": new_llm.model,
        }
    except Exception as e:
        state.eval_logger.error(f"更新 LLM 配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.post("/config/llm/test")
async def test_llm_config(req: LLMConfigRequest):
    try:
        if bool(getattr(state.llm_client, "demo_mode", False)):
            return {
                "success": True,
                "message": "DeepSeek V4.1 Flash 演示接口连接成功",
                "reply": "connection successful (simulated; preset content active)",
                "simulated": True,
                "model": "deepseek-flash",
            }
        test_llm = state.LLMClient(
            api_key=req.api_key,
            base_url=req.base_url,
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            timeout=min(req.timeout, 30),
            provider=req.provider,
            thinking=req.thinking,
            reasoning_effort=req.reasoning_effort,
            fast_thinking=req.fast_thinking,
            fast_reasoning_effort=req.fast_reasoning_effort,
        )
        reply = await asyncio.to_thread(
            test_llm.chat_completion,
            [{"role": "user", "content": "Please reply connection successful."}],
        )
        reply_text = (reply or "").strip()
        # llm_client 的降级链会把失败吞成带标记的文本返回（保证主流程韧性），
        # 连通性测试必须识别这些标记，否则假 key 也会显示"测试成功"
        _failure_markers = ("[LLM 请求失败", "[LLM 返回为空]", "[离线模式回复]", "（离线演示模板")
        if not reply_text or any(m in reply_text[:120] for m in _failure_markers):
            return {
                "success": False,
                "message": "连接失败：LLM 未返回有效回复（鉴权失败或服务不可达）",
                "reply": reply_text[:200],
            }
        return {
            "success": True,
            "message": "LLM 连接测试成功",
            "reply": reply_text[:200],
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)}",
            "reply": "",
        }


def _deepseek_demo_text(messages: List[Dict[str, str]]) -> str:
    last_content = messages[-1].get("content", "") if messages else ""
    if "connection successful" in last_content.lower():
        return "connection successful"
    return "[DeepSeek V4.1 Flash 演示响应] 预制案例内容已加载，可继续比赛流程。"


@router.post("/mock/deepseek/chat/completions")
async def mock_deepseek_chat_completions(
    req: DeepSeekChatCompletionRequest,
    authorization: Optional[str] = Header(default=None),
):
    """Local, no-network DeepSeek Chat Completions-compatible demo endpoint."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication Fails (simulated)")

    created = int(time.time())
    completion_id = f"chatcmpl-demo-{uuid.uuid4().hex[:20]}"
    messages = [message.model_dump() for message in req.messages]
    content = _deepseek_demo_text(messages)
    prompt_tokens = max(1, sum(len(message.get("content", "")) for message in messages) // 4)
    completion_tokens = max(1, len(content) // 4)

    if req.stream:
        include_usage = bool((req.stream_options or {}).get("include_usage"))

        def event_stream():
            chunks = [
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": req.model,
                    "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
                },
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": req.model,
                    "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
                },
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": req.model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                },
            ]
            for chunk in chunks:
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            if include_usage:
                usage_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": req.model,
                    "choices": [],
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                    },
                }
                yield f"data: {json.dumps(usage_chunk, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "reasoning_content": "" if (req.thinking or {}).get("type") == "enabled" else None,
                },
                "logprobs": None,
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
@router.get("/reference/dispute-causes")
async def get_dispute_causes_taxonomy():
    return {"taxonomy": state.DISPUTE_CAUSES_TAXONOMY}


@router.get("/reference/big-five-traits")
async def get_big_five_traits():
    return {"traits": state.BIG_FIVE_TRAITS, "example": state.generate_random_personality()}


@router.get("/reference/progressive-benchmark")
async def get_progressive_benchmark_info():
    return {"levels": state.PROGRESSIVE_BENCHMARK_LEVELS}


@router.get("/reference/cases")
async def list_reference_cases(limit: int = 40, split: str = "test"):
    from api.services.cases import list_case_index
    cases = list_case_index(limit=limit, split=split)
    return {"cases": cases, "total": len(cases), "split": split}


@router.get("/reference/cases/{case_id}")
async def get_reference_case(case_id: str, split: Optional[str] = None):
    from api.services.cases import get_case_full
    row = get_case_full(case_id, split=split)
    if row is None:
        raise HTTPException(status_code=404, detail=f"case not found: {case_id}")
    return {"case": row, "case_id": case_id}


@router.get("/reference/research-packs")
async def list_research_packs(dataset: Optional[str] = None):
    from api.services.materials import list_packs
    from core.research.governance import summarize_pack_inventory

    packs = list_packs(dataset)
    return {"packs": packs, "total": len(packs), "governance": summarize_pack_inventory(packs)}


@router.get("/reference/research-packs/{dataset}/{cluster}")
async def get_research_pack(dataset: str, cluster: str, pack_version: Optional[str] = None):
    from api.services.materials import pack_public_view
    return pack_public_view(dataset, cluster, pack_version)

