"""五阶段调解 路由。"""
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime
import uuid
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

@router.post("/mediation/create")
async def create_mediation(req: MediationCreateRequest):
    session_id = f"med_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    nbs_text = (req.nbs_reference_text or "").strip() or None
    if req.auto_compute_nbs and not nbs_text:
        try:
            from core.nash_bargaining import NashBargainingEngine

            nb = NashBargainingEngine(
                state._game_engine.nash_tracker, state.llm_client, use_spne_disagreement=True,
            )
            nb.refresh_spne_disagreement_point()
            feasible = nb.default_feasible_outcomes()
            d_pt = nb.compute_disagreement_point("compromising", "compromising")
            nbs_sol = nb.compute_nbs(feasible, d_pt)
            nbs_text = nb.generate_nbs_reference_text(nbs_sol)
        except Exception:
            nbs_text = None
    result = state._mediation_engine.create_session(
        session_id,
        req.case_info,
        req.party_names,
        req.max_bargaining_rounds,
        nbs_reference_text=nbs_text,
    )
    return result


@router.post("/mediation/{session_id}/preliminary")
async def run_mediation_preliminary(session_id: str):
    try:
        result = await asyncio.to_thread(
            state._mediation_engine.run_preliminary, session_id,
        )
        return {"session_id": session_id, **result}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"璋冭В鍒濇闃舵澶辫触: {str(e)}")


@router.post("/mediation/{session_id}/statement")
async def run_mediation_statement(session_id: str, req: MediationStatementRequest):
    try:
        result = await asyncio.to_thread(
            state._mediation_engine.run_statement,
            session_id, req.party_name, req.statement,
        )
        return {"session_id": session_id, **result}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"闄堣堪闃舵澶辫触: {str(e)}")


@router.post("/mediation/{session_id}/options")
async def run_mediation_options(session_id: str):
    try:
        result = await asyncio.to_thread(
            state._mediation_engine.run_option_generation, session_id,
        )
        return {"session_id": session_id, **result}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"方案生成失败: {str(e)}")


@router.post("/mediation/{session_id}/bargain")
async def run_mediation_bargain(session_id: str, req: Optional[MediationBargainRequest] = None):
    try:
        party_resp = req.party_responses if req else None
        result = await asyncio.to_thread(
            state._mediation_engine.run_bargaining_turn,
            session_id, party_resp,
        )
        return {"session_id": session_id, **result}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"协商失败: {str(e)}")


@router.post("/mediation/{session_id}/close")
async def run_mediation_close(session_id: str):
    try:
        result = await asyncio.to_thread(
            state._mediation_engine.run_closure, session_id,
        )
        return {"session_id": session_id, **result.to_dict()}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"调解收尾失败: {str(e)}")


@router.get("/mediation/{session_id}/status")
async def get_mediation_status(session_id: str):
    try:
        return state._mediation_engine.get_session_status(session_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/mediation/{session_id}/full")
async def run_full_mediation(session_id: str, req: MediationCreateRequest):
    try:
        result = await asyncio.to_thread(
            state._mediation_engine.run_full_mediation,
            session_id, req.case_info, req.party_names, req.max_bargaining_rounds,
        )
        return {"session_id": session_id, **result.to_dict()}
    except Exception as e:
        state.eval_logger.error(f"完整调解失败: {e}", exc_info=True)
        raise HTTPException(500, f"调解失败: {str(e)}")

