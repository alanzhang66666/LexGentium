"""LLM 配置与参考数据 路由。"""
from typing import Optional, Dict, Any, List
import asyncio
import json
from fastapi import APIRouter, HTTPException, BackgroundTasks
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
    MediationBargainRequest, MediationCreateRequest, MediationStatementRequest,
    MultiJudgeRequest, ProgressiveRAGRequest,
)

router = APIRouter()

@router.get("/config/llm")
async def get_llm_config():
    return {
        "provider": state.llm_client.provider,
        "api_key_masked": state._mask_key(state.llm_client.api_key or ""),
        "api_key_set": bool(state.llm_client.api_key),
        "base_url": state.llm_client.base_url,
        "model": state.llm_client.model,
        "temperature": state.llm_client.temperature,
        "max_tokens": state.llm_client.max_tokens,
        "timeout": state.llm_client.timeout,
        "chat_model_ready": state.llm_client.chat_model is not None,
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
        )
        state._reinit_llm_and_agents(new_llm)
        state._persist_llm_env(req)

        return {
            "success": True,
            "message": "LLM 配置已更新并持久化，所有 Agent 已重新初始化",
            "chat_model_ready": new_llm.chat_model is not None,
            "base_url": new_llm.base_url,
            "model": new_llm.model,
        }
    except Exception as e:
        state.eval_logger.error(f"更新 LLM 配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.post("/config/llm/test")
async def test_llm_config(req: LLMConfigRequest):
    try:
        test_llm = state.LLMClient(
            api_key=req.api_key,
            base_url=req.base_url,
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            timeout=min(req.timeout, 30),
            provider=req.provider,
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

