"""法条库与 API 历史 路由。"""
from typing import Optional, Dict, Any, List
import asyncio
import json
import os
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

@router.post("/database/search", response_model=LawSearchResponse)
async def search_laws(request: LawSearchRequest):
    retriever = state.get_law_retriever()
    if not retriever:
        raise HTTPException(status_code=503, detail="法条检索器未初始化")
    
    try:
        # 鍙兘娑夊強澶栭儴 embedding/rerank 璋冪敤锛屽鍔犺秴鏃堕伩鍏嶈姹傚崱姝?
        async def _run():
            return await asyncio.to_thread(retriever.search, request.query, request.top_k)

        try:
            results = await asyncio.wait_for(_run(), timeout=15)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="error")
        return LawSearchResponse(results=results, total=len(results))
    except Exception as e:
        state.eval_logger.error(f"搜索法条失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/database/stats")
async def get_database_stats():
    db_path = state.project_root / "database" / "legal_articles.db"
    if not db_path.exists():
        return {
            "exists": False,
            "total_articles": 0,
            "index_exists": False
        }
    
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # 获取文章总数
        cursor.execute("SELECT COUNT(*) FROM articles")
        total_articles = cursor.fetchone()[0]
        
        # 检查索引文件
        index_path = state.project_root / "database" / "legal_articles.index"
        mapping_path = state.project_root / "database" / "legal_articles_id_map.npy"
        
        conn.close()
        
        return {
            "exists": True,
            "total_articles": total_articles,
            "index_exists": index_path.exists(),
            "mapping_exists": mapping_path.exists(),
            "db_path": str(db_path),
            "index_path": str(index_path) if index_path.exists() else None,
        }
    except Exception as e:
        state.eval_logger.error(f"鑾峰彇鏁版嵁搴撶粺璁″け璐? {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


@router.get("/api-history/stats")
async def get_api_history_stats():
    history_file = state.project_root / "api_history" / "interactions.jsonl"
    if not history_file.exists():
        return {"exists": False, "total_interactions": 0, "by_scenario": {}}
    try:
        interactions = []
        scenario_counts = {}
        with open(history_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        interactions.append(data)
                        scenario = data.get("scenario", "Unknown")
                        scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1
                    except Exception:
                        continue
        return {"exists": True, "total_interactions": len(interactions), "by_scenario": scenario_counts, "file_path": str(history_file)}
    except Exception as e:
        state.eval_logger.error(f"failed to get API history stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"failed to get API history stats: {str(e)}")



@router.get("/api-history/list")
async def list_api_history(
    scenario: Optional[str] = None,
    case_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    history_file = state.project_root / "api_history" / "interactions.jsonl"
    if not history_file.exists():
        return {"interactions": [], "total": 0}
    try:
        interactions = []
        with open(history_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if scenario and data.get("scenario") != scenario:
                        continue
                    if case_id and data.get("case_id") != case_id:
                        continue
                    interactions.append(data)
                except Exception:
                    continue
        total = len(interactions)
        return {"interactions": interactions[offset:offset + limit], "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        state.eval_logger.error(f"failed to list API history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"failed to list API history: {str(e)}")

