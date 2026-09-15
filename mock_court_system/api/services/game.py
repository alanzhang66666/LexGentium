"""博弈会话创建、列表、存档恢复。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import HTTPException

from api import state
from api.services.conversation import bind_session_link
from api.schemas import GameCreateRequest

GAME_NOT_FOUND = "博弈局不存在。后端重启后若存档缺失，请重新开局。"


def persist_game(game_id: str) -> None:
    sess = state.game_sessions.get(game_id)
    if not sess:
        return
    try:
        engine = sess["engine"]
        snapshot = engine.export_snapshot() if hasattr(engine, "export_snapshot") else None
        state._game_store.save(
            game_id,
            sess["config"],
            sess["case_info"],
            sess.get("status") or "created",
            int(sess.get("rounds_completed") or 0),
            result=snapshot,
        )
    except Exception as exc:
        state.eval_logger.warning(f"写入博弈存档失败 {game_id}: {exc}")


def restore_game(game_id: str) -> Optional[Dict[str, Any]]:
    row = state._game_store.get(game_id)
    if not row:
        return None
    engine = state.GameEngine(state._orchestrator, state.llm_client)
    config = row.get("config") or {}
    if isinstance(config, dict):
        p_strat = config.get("plaintiff_strategy")
        d_strat = config.get("defendant_strategy")
        if p_strat in state.VALID_STRATEGIES:
            engine.set_strategy("plaintiff", p_strat)
        if d_strat in state.VALID_STRATEGIES:
            engine.set_strategy("defendant", d_strat)
        engine._dispute_cause = config.get("dispute_cause")
        engine._dispute_cause_detail = config.get("dispute_cause_detail")
    if row.get("result"):
        engine.import_snapshot(row["result"])
    sess = {
        "engine": engine,
        "config": config if isinstance(config, dict) else {},
        "case_info": row.get("case_info") or {},
        "rounds_completed": int(row.get("rounds_completed") or 0),
        "created_at": row.get("created_at") or state._utcnow_iso(),
        "status": row.get("status") or "created",
        "session_id": (config.get("session_id") if isinstance(config, dict) else None),
        "restored": True,
    }
    state.game_sessions[game_id] = sess
    return sess


def ensure_game(game_id: str) -> bool:
    if game_id in state.game_sessions:
        return True
    try:
        return restore_game(game_id) is not None
    except Exception as exc:
        state.eval_logger.warning(f"恢复博弈存档失败 {game_id}: {exc}")
        return False


def require_game(game_id: str) -> Dict[str, Any]:
    if not ensure_game(game_id):
        raise HTTPException(status_code=404, detail=GAME_NOT_FOUND)
    return state.game_sessions[game_id]


def delete_game(game_id: str) -> None:
    existed = game_id in state.game_sessions
    state.game_sessions.pop(game_id, None)
    stored = False
    try:
        stored = state._game_store.delete(game_id)
    except Exception as exc:
        state.eval_logger.warning(f"删除博弈存档失败 {game_id}: {exc}")
    if not existed and not stored:
        raise HTTPException(status_code=404, detail=GAME_NOT_FOUND)


def create_game(req: GameCreateRequest) -> Dict[str, Any]:
    if req.plaintiff_strategy not in state.VALID_STRATEGIES:
        raise HTTPException(400, f"Invalid plaintiff_strategy. Options: {state.VALID_STRATEGIES}")
    if req.defendant_strategy not in state.VALID_STRATEGIES:
        raise HTTPException(400, f"Invalid defendant_strategy. Options: {state.VALID_STRATEGIES}")

    game_id = f"game_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
    engine = state.GameEngine(state._orchestrator, state.llm_client)
    engine.set_strategy("plaintiff", req.plaintiff_strategy)
    engine.set_strategy("defendant", req.defendant_strategy)
    engine._dispute_cause = req.dispute_cause
    engine._dispute_cause_detail = req.dispute_cause_detail

    config_dict = req.model_dump()
    state.game_sessions[game_id] = {
        "engine": engine,
        "config": config_dict,
        "case_info": req.case_info,
        "rounds_completed": 0,
        "created_at": state._utcnow_iso(),
        "status": "created",
        "session_id": req.session_id,
    }
    persist_game(game_id)
    bind_session_link(req.session_id, game_id=game_id)
    return {
        "game_id": game_id,
        "status": "created",
        "config": config_dict,
        "strategy_state": engine.get_strategy_state(),
        "initial_equilibrium": engine.get_equilibrium_analysis(),
        "session_id": req.session_id,
    }


def list_games() -> List[Dict[str, Any]]:
    sessions = []
    for gid, sess in state.game_sessions.items():
        engine = sess["engine"]
        sessions.append({
            "game_id": gid,
            "status": sess["status"],
            "rounds_completed": sess["rounds_completed"],
            "created_at": sess["created_at"],
            "plaintiff_strategy": engine._plaintiff_strategy_type,
            "defendant_strategy": engine._defendant_strategy_type,
            "convergence_rate": engine.nash_tracker.compute_convergence(),
            "session_id": sess.get("session_id"),
        })
    return sessions
