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

@router.post("/case/progressive-rag")
async def run_standalone_progressive_rag(req: ProgressiveRAGRequest):
    retriever = state.get_law_retriever()
    if not retriever:
        raise HTTPException(503, "法条检索器未初始化")

    prag = state.ProgressiveRAG(retriever, state.llm_client)
    results = await asyncio.to_thread(
        prag.retrieve_for_stage, req.stage, req.context, req.top_k, "standalone",
    )

    return {
        "stage": req.stage,
        "new_results": results,
        "retrieval_summary": prag.get_retrieval_summary(),
    }


@router.post("/case/dual-mode-reasoning")
async def run_dual_mode_reasoning(req: DualModeRequest):
    reasoner = state.DualModeReasoner(state.llm_client)
    result = await asyncio.to_thread(
        reasoner.dual_mode_judgment,
        req.case_info, req.claims, req.use_llm_eval,
    )
    return result


@router.post("/case/multi-judge")
async def run_multi_judge(req: MultiJudgeRequest):
    engine = state.MultiJudgeEngine(state.llm_client)
    result = await asyncio.to_thread(
        engine.run,
        req.case_facts, req.claims, req.trial_summary,
        req.num_judges, req.aggregation,
    )
    return result.to_dict()

