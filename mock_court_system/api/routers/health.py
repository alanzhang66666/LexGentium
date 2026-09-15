"""健康检查 路由。"""
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime
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

@router.get("/health")
async def health_check():
    law_db = state.project_root / "database" / "legal_articles.db"
    history_file = state.project_root / "api_history" / "interactions.jsonl"
    conv_db_default = state.project_root / "data" / "conversations.sqlite3"
    state_db_default = state.project_root / "data" / "app_state.sqlite3"
    retriever_ready = False
    try:
        retriever_ready = state.get_law_retriever() is not None
    except Exception:
        retriever_ready = False
    return {
        "status": "ok",
        "law_retriever_ready": retriever_ready,
        "time": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "paths": {
            "state.project_root": str(state.project_root),
            "law_db_exists": law_db.exists(),
            "law_retriever_ready": retriever_ready,
            "api_history_exists": history_file.exists(),
            "conversation_db_default": str(conv_db_default),
            "app_state_db_default": str(state_db_default),
        },
    }

