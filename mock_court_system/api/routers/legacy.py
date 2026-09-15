"""兼容入口（POST /） 路由。"""
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

@router.post("/", response_model=ApiResponse)
async def process_request(req: ApiRequest):
    try:
        scenario = req.scenario.upper()
        # Convert Pydantic models to dicts for the agents
        history_dicts = [msg.model_dump() for msg in req.dialog_history]

        role, response_text, _is_finished = state.run_agent_turn(
            scenario=scenario,
            case_id=req.case_id,
            dialog_history=history_dicts,
            input_json=req.input_json,
        )
            
        return ApiResponse(
            scenario=req.scenario,
            case_id=req.case_id,
            response={"role": role, "message": response_text}
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

