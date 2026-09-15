"""P0 创新模块（Progressive RAG / Dual-Mode / Multi-Judge） 路由。"""
from typing import Optional, Dict, Any, List
import asyncio
import json
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse

from api import state
from api_schemas import (
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


def _require_text(value: str, field: str) -> str:
    text = (value or "").strip()
    if not text:
        raise HTTPException(400, f"{field} 不能为空")
    return text


@router.post("/case/progressive-rag")
async def run_standalone_progressive_rag(req: ProgressiveRAGRequest):
    retriever = state.get_law_retriever()
    if not retriever:
        raise HTTPException(503, "法条检索器未初始化")
    if not req.stage.strip():
        raise HTTPException(400, "stage 不能为空")
    if not isinstance(req.context, dict):
        raise HTTPException(400, "context 必须是对象")

    try:
        prag = state.ProgressiveRAG(retriever, state.llm_client)
        results = await asyncio.to_thread(
            prag.retrieve_for_stage, req.stage, req.context, req.top_k, "standalone",
        )
    except KeyError as e:
        raise HTTPException(400, f"context 缺少字段: {e}") from e
    except Exception as e:
        raise HTTPException(500, f"Progressive RAG 失败: {e}") from e

    return {
        "stage": req.stage,
        "new_results": results,
        "retrieval_summary": prag.get_retrieval_summary(),
    }


@router.post("/case/dual-mode-reasoning")
async def run_dual_mode_reasoning(req: DualModeRequest):
    case_info = _require_text(req.case_info, "case_info")
    claims = _require_text(req.claims, "claims")
    try:
        reasoner = state.DualModeReasoner(state.llm_client)
        return await asyncio.to_thread(
            reasoner.dual_mode_judgment,
            case_info, claims, req.use_llm_eval,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"双模式推理失败: {e}") from e


@router.post("/case/multi-judge")
async def run_multi_judge(req: MultiJudgeRequest):
    case_facts = _require_text(req.case_facts, "case_facts")
    claims = _require_text(req.claims, "claims")
    try:
        engine = state.MultiJudgeEngine(state.llm_client)
        result = await asyncio.to_thread(
            engine.run,
            case_facts, claims, req.trial_summary,
            req.num_judges, req.aggregation,
        )
        return result.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"多法官推理失败: {e}") from e

