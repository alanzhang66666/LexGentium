"""博弈会话 路由。"""
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime
import uuid
import os
import queue
import threading
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

@router.post("/game/create")
async def create_game_session(req: GameCreateRequest):
    if req.plaintiff_strategy not in state.VALID_STRATEGIES:
        raise HTTPException(400, f"Invalid plaintiff_strategy. Options: {state.VALID_STRATEGIES}")
    if req.defendant_strategy not in state.VALID_STRATEGIES:
        raise HTTPException(400, f"Invalid defendant_strategy. Options: {state.VALID_STRATEGIES}")

    game_id = f"game_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

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
    }

    state._game_store.save(game_id, config_dict, req.case_info, "created", 0)

    return {
        "game_id": game_id,
        "status": "created",
        "config": config_dict,
        "strategy_state": engine.get_strategy_state(),
        "initial_equilibrium": engine.get_equilibrium_analysis(),
    }


@router.get("/game/list")
async def list_game_sessions():
    sessions = []
    for gid, sess in state.game_sessions.items():
        engine: state.GameEngine = sess["engine"]
        sessions.append({
            "game_id": gid,
            "status": sess["status"],
            "rounds_completed": sess["rounds_completed"],
            "created_at": sess["created_at"],
            "plaintiff_strategy": engine._plaintiff_strategy_type,
            "defendant_strategy": engine._defendant_strategy_type,
            "convergence_rate": engine.nash_tracker.compute_convergence(),
        })

    # 服务重启后引擎对象不可恢复，内存中消失的会话从 SQLite 存档补全（只读展示）
    live_ids = {s["game_id"] for s in sessions}
    try:
        for row in state._game_store.list_all(limit=200):
            if row["game_id"] in live_ids:
                continue
            sessions.append({
                "game_id": row["game_id"],
                "status": row["status"],
                "rounds_completed": row["rounds_completed"],
                "created_at": row["created_at"],
                "plaintiff_strategy": None,
                "defendant_strategy": None,
                "convergence_rate": None,
                "archived": True,
            })
    except Exception as e:
        state.eval_logger.warning(f"读取博弈存档失败: {e}")

    return {"sessions": sessions, "total": len(sessions)}


@router.get("/game/{game_id}")
async def get_game_session(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    sess = state.game_sessions[game_id]
    engine: state.GameEngine = sess["engine"]

    return {
        "game_id": game_id,
        "status": sess["status"],
        "rounds_completed": sess["rounds_completed"],
        "created_at": sess["created_at"],
        "strategy_state": engine.get_strategy_state(),
        "equilibrium": engine.get_equilibrium_analysis(),
        "config": sess["config"],
    }


@router.delete("/game/{game_id}")
async def delete_game_session(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")
    del state.game_sessions[game_id]
    return {"message": "deleted", "game_id": game_id}


@router.post("/game/{game_id}/strategy/set")
async def set_game_strategy(game_id: str, req: GameStrategySetRequest):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")
    if req.strategy_type not in state.VALID_STRATEGIES:
        raise HTTPException(400, f"Invalid strategy. Options: {list(state.VALID_STRATEGIES)}")
    if req.party not in ("plaintiff", "defendant"):
        raise HTTPException(400, "party must be 'plaintiff' or 'defendant'")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    engine.set_strategy(req.party, req.strategy_type, req.custom_instruction)

    return {
        "game_id": game_id,
        "party": req.party,
        "new_strategy": req.strategy_type,
        "strategy_state": engine.get_strategy_state(),
    }


@router.post("/game/{game_id}/strategy/reflect")
async def reflect_strategy(game_id: str, req: GameStrategySetRequest):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    if not engine.strategy_history:
        raise HTTPException(status_code=400, detail="error")

    last_round = engine.strategy_history[-1]
    method = req.strategy_type if req.strategy_type in ("llm_reflection", "best_response", "fictitious_play") else "llm_reflection"
    new_type = engine.evolve_strategy(req.party, last_round, method=method)

    return {
        "game_id": game_id,
        "party": req.party,
        "method": method,
        "new_strategy_type": new_type,
        "strategy_state": engine.get_strategy_state(),
        "equilibrium": engine.get_equilibrium_analysis(),
    }


@router.get("/game/{game_id}/strategy/history")
async def get_strategy_history(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    return {
        "game_id": game_id,
        "history": engine.get_strategy_history(),
        "rounds": [
            {
                "round": r.round_index,
                "plaintiff_strategy": r.cd_strategy,
                "defendant_strategy": r.dd_strategy,
                "score": r.score.to_dict(),
            }
            for r in engine.strategy_history
        ],
    }


@router.get("/game/{game_id}/strategy/payoff-matrix")
async def get_payoff_matrix(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    return {
        "game_id": game_id,
        "payoff_matrix": engine.get_payoff_matrix(),
    }


@router.post("/game/{game_id}/round")
async def run_game_round(game_id: str, req: Optional[GameRoundRequest] = None):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    sess = state.game_sessions[game_id]
    engine: state.GameEngine = sess["engine"]
    config = sess["config"]
    case_info = sess["case_info"]

    max_rounds = config.get("max_rounds", 5)
    if sess["rounds_completed"] >= max_rounds:
        raise HTTPException(400, f"无效的 max_rounds: {max_rounds}")

    method = (req.evolution_method if req and req.evolution_method else None) or config.get("evolution_method", "llm_reflection")
    round_idx = sess["rounds_completed"]

    try:
        sess["status"] = "running"
        game_round = await asyncio.to_thread(
            engine.run_game_round,
            case_info,
            round_idx,
            evolution_method=method,
        )
        sess["rounds_completed"] = round_idx + 1

        # 未收敛则按进化方法更新双方策略
        if sess["rounds_completed"] < max_rounds and config.get("enable_dynamic_strategy", True):
            await asyncio.to_thread(engine.evolve_both_strategies, game_round, method)

        # 检查收敛
        conv = engine.nash_tracker.compute_convergence()
        threshold = config.get("convergence_threshold", 0.05)
        converged = conv >= (1 - threshold) and round_idx >= 1

        sess["status"] = "converged" if converged else "in_progress"
        state._game_store.update_status(game_id, sess["status"], sess["rounds_completed"])

        return {
            "game_id": game_id,
            "round_index": round_idx,
            "status": sess["status"],
            "score": game_round.score.to_dict(),
            "strategy_state": engine.get_strategy_state(),
            "equilibrium_snapshot": game_round.equilibrium_snapshot,
            "converged": converged,
            "convergence_rate": conv,
            "rounds_completed": sess["rounds_completed"],
            "rounds_remaining": max_rounds - sess["rounds_completed"],
        }
    except Exception as e:
        sess["status"] = "failed"
        state._game_store.update_status(game_id, "failed", sess["rounds_completed"])
        state.eval_logger.error(f"博弈轮次执行失败: {e}", exc_info=True)
        raise HTTPException(500, f"博弈轮次执行失败: {str(e)}")


@router.get("/game/{game_id}/equilibrium")
async def get_equilibrium(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    return {
        "game_id": game_id,
        "analysis": engine.get_equilibrium_analysis(),
    }


@router.get("/game/{game_id}/equilibrium/convergence")
async def get_equilibrium_convergence(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    snapshots = []
    for r in engine.strategy_history:
        if r.equilibrium_snapshot:
            snapshots.append({
                "round": r.round_index,
                "convergence_rate": r.equilibrium_snapshot.get("convergence_rate", 0),
                "plaintiff_strategy": r.cd_strategy,
                "defendant_strategy": r.dd_strategy,
            })

    return {
        "game_id": game_id,
        "current_convergence": engine.nash_tracker.compute_convergence(),
        "estimated_rounds_remaining": engine.nash_tracker.estimate_rounds_to_convergence(),
        "history": snapshots,
    }


@router.post("/game/{game_id}/strategy/counterfactual")
async def run_counterfactual(game_id: str, req: GameCounterfactualRequest):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")
    if req.party not in ("plaintiff", "defendant"):
        raise HTTPException(400, "party must be 'plaintiff' or 'defendant'")
    if req.hypothetical_strategy not in state.VALID_STRATEGIES:
        raise HTTPException(400, f"Invalid strategy. Options: {list(state.VALID_STRATEGIES)}")

    sess = state.game_sessions[game_id]
    engine: state.GameEngine = sess["engine"]

    result = await asyncio.to_thread(
        engine.counterfactual_analysis,
        req.party,
        req.hypothetical_strategy,
        sess["case_info"],
    )

    return {
        "game_id": game_id,
        **result,
    }


@router.post("/game/{game_id}/stream-round")
async def stream_game_round(game_id: str, req: Optional[GameRoundRequest] = None):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    sess = state.game_sessions[game_id]
    engine: state.GameEngine = sess["engine"]
    config = sess["config"]
    case_info = sess["case_info"]

    max_rounds = config.get("max_rounds", 5)
    if sess["rounds_completed"] >= max_rounds:
        raise HTTPException(400, f"无效的 max_rounds: {max_rounds}")

    method = (req.evolution_method if req and req.evolution_method else None) or config.get("evolution_method", "llm_reflection")
    round_idx = sess["rounds_completed"]
    event_queue: queue.Queue = queue.Queue()

    def on_progress(stage, round_i, role, finished):
        event_queue.put(state._sse_event("stage_transition", {
            "stage": stage,
            "round_within_stage": round_i,
            "role": role,
            "finished": finished,
        }))

    def run_round():
        try:
            sess["status"] = "running"
            event_queue.put(state._sse_event("round_start", {
                "round_index": round_idx,
                "plaintiff_strategy": engine._plaintiff_strategy_type,
                "defendant_strategy": engine._defendant_strategy_type,
            }))

            game_round = engine.run_game_round(
                case_info, round_idx,
                on_progress=on_progress,
                evolution_method=method,
            )
            sess["rounds_completed"] = round_idx + 1

            event_queue.put(state._sse_event("score_update", {
                "round_index": round_idx,
                "score": game_round.score.to_dict(),
            }))

            event_queue.put(state._sse_event("equilibrium_update", {
                "equilibrium": game_round.equilibrium_snapshot,
            }))

            # 未收敛则执行策略进化
            if sess["rounds_completed"] < max_rounds and config.get("enable_dynamic_strategy", True):
                old_p = engine._plaintiff_strategy_type
                old_d = engine._defendant_strategy_type

                engine.evolve_both_strategies(game_round, method)

                if engine._plaintiff_strategy_type != old_p:
                    event_queue.put(state._sse_event("strategy_switch", {
                        "party": "plaintiff",
                        "old": old_p,
                        "new": engine._plaintiff_strategy_type,
                    }))

                if engine._defendant_strategy_type != old_d:
                    event_queue.put(state._sse_event("strategy_switch", {
                        "party": "defendant",
                        "old": old_d,
                        "new": engine._defendant_strategy_type,
                    }))

            conv = engine.nash_tracker.compute_convergence()
            threshold = config.get("convergence_threshold", 0.05)
            converged = conv >= (1 - threshold) and round_idx >= 1
            sess["status"] = "converged" if converged else "in_progress"

            event_queue.put(state._sse_event("round_complete", {
                "round_index": round_idx,
                "converged": converged,
                "convergence_rate": conv,
                "rounds_completed": sess["rounds_completed"],
                "strategy_state": engine.get_strategy_state(),
            }))

        except Exception as e:
            sess["status"] = "failed"
            event_queue.put(state._sse_event("error", {"message": str(e)}))
        finally:
            event_queue.put(None)

    thread = threading.Thread(target=run_round, daemon=True)
    thread.start()

    async def event_generator():
        while True:
            try:
                event = await asyncio.to_thread(event_queue.get, timeout=120)
            except Exception:
                yield state._sse_event("error", {"message": "timeout"})
                break
            if event is None:
                break
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/game/{game_id}/evaluate/outcome")
async def evaluate_game_outcome(game_id: str, req: Optional[GameEvaluateRequest] = None):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    sess = state.game_sessions[game_id]
    engine: state.GameEngine = sess["engine"]

    if not engine.strategy_history:
        raise HTTPException(status_code=400, detail="error")

    last_round = engine.strategy_history[-1]
    ci_result = last_round.case_result.ci_result
    if not ci_result:
        raise HTTPException(400, "最后一轮无博弈结果")

    case_info = sess["case_info"]
    case_bg = json.dumps(
        {k: str(v)[:300] for k, v in case_info.items() if k != "dialog_history"},
        ensure_ascii=False,
    )[:2000]

    party_names = (req.party_names if req and req.party_names else None) or ["原告", "被告"]
    evaluator = state._get_outcome_evaluator()

    result = await asyncio.to_thread(
        evaluator.evaluate_outcome,
        case_bg,
        ci_result.dialog_history,
        ci_result.final_document,
        party_names,
    )

    return {
        "game_id": game_id,
        "round_index": last_round.round_index,
        "outcome_evaluation": result,
    }


@router.post("/game/{game_id}/evaluate/composite")
async def evaluate_game_composite(game_id: str, req: Optional[GameEvaluateRequest] = None):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    sess = state.game_sessions[game_id]
    engine: state.GameEngine = sess["engine"]

    if not engine.strategy_history:
        raise HTTPException(status_code=400, detail="error")

    last_round = engine.strategy_history[-1]
    ci_result = last_round.case_result.ci_result
    if not ci_result:
        raise HTTPException(400, "最后一轮无博弈结果")

    case_info = sess["case_info"]
    case_bg = json.dumps(
        {k: str(v)[:300] for k, v in case_info.items() if k != "dialog_history"},
        ensure_ascii=False,
    )[:2000]

    party_names = (req.party_names if req and req.party_names else None) or ["原告", "被告"]
    evaluator = state._get_outcome_evaluator()

    # AgentMediation 鍥涙寚鏍?
    outcome_eval = await asyncio.to_thread(
        evaluator.evaluate_outcome,
        case_bg,
        ci_result.dialog_history,
        ci_result.final_document,
        party_names,
    )

    # MultiLayer 三层评测
    from evaluation.lib.multi_layer_evaluator import MultiLayerEvaluator

    compliance_report = {}
    try:
        compliance_report = state.ci_agent.state_machine.get_compliance_report()
    except Exception:
        pass

    judgment_json = None
    try:
        sj = state.ci_agent.get_structured_judgment()
        if sj:
            judgment_json = sj.to_dict()
    except Exception:
        pass

    multi_layer = MultiLayerEvaluator.evaluate_all(
        judgment_json=judgment_json,
        judgment_text=ci_result.final_document,
        compliance_report=compliance_report,
    )

    # 综合打分
    outcome_score = outcome_eval.get("composite_score", 0)
    multi_score = multi_layer.get("composite_score", 0)
    final_composite = round(outcome_score * 0.5 + multi_score * 0.5, 4)

    return {
        "game_id": game_id,
        "round_index": last_round.round_index,
        "outcome_evaluation": outcome_eval,
        "multi_layer_evaluation": multi_layer,
        "final_composite_score": final_composite,
        "game_score": last_round.score.to_dict(),
        "equilibrium_snapshot": last_round.equilibrium_snapshot,
    }


@router.get("/game/{game_id}/compliance/realtime")
async def get_game_compliance(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    try:
        realtime = state.ci_agent.state_machine.get_realtime_compliance()
    except Exception as e:
        realtime = {"error": f"鏃犳硶鑾峰彇鍚堣鐘舵? {str(e)}"}

    return {
        "game_id": game_id,
        "compliance": realtime,
    }


@router.post("/game/{game_id}/evaluate/lexeval")
async def evaluate_lexeval_cognitive(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    if not engine.strategy_history:
        raise HTTPException(status_code=400, detail="error")

    ci_result = engine.strategy_history[-1].case_result.ci_result
    if not ci_result:
        raise HTTPException(status_code=400, detail="error")

    evaluator = state.LexEvalCognitiveEvaluator(state.llm_client)
    result = await asyncio.to_thread(evaluator.evaluate_all, ci_result.final_document)

    return {"game_id": game_id, "lexeval_cognitive": result}


@router.post("/game/{game_id}/evaluate/j1eval")
async def evaluate_j1eval(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    if not engine.strategy_history:
        raise HTTPException(status_code=400, detail="error")

    last = engine.strategy_history[-1]
    ci_result = last.case_result.ci_result
    if not ci_result:
        raise HTTPException(status_code=400, detail="error")

    predicted_laws = []
    try:
        sj = state.ci_agent.get_structured_judgment()
        if sj:
            for law in sj.legal_articles:
                predicted_laws.append(law.get("law", "") if isinstance(law, dict) else str(law))
    except Exception:
        pass

    metrics = state.J1EvalMetrics(state.llm_client)
    result = await asyncio.to_thread(
        metrics.evaluate_all_level3,
        ci_result.final_document,
        predicted_laws,
    )

    return {"game_id": game_id, "j1eval_level3": result}


@router.post("/game/{game_id}/evaluate/behavior-symmetry")
async def evaluate_behavior_symmetry(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    if not engine.strategy_history:
        raise HTTPException(status_code=400, detail="error")

    ci_result = engine.strategy_history[-1].case_result.ci_result
    if not ci_result:
        raise HTTPException(status_code=400, detail="error")

    tracker = state.SymmetricBehaviorTracker(state.llm_client)
    await asyncio.to_thread(
        tracker.record_dialog_history, ci_result.dialog_history,
    )

    return {
        "game_id": game_id,
        "symmetric_summary": tracker.get_symmetric_summary(),
        "records": tracker.get_all_records(),
    }


@router.post("/game/{game_id}/evaluate/explainable")
async def evaluate_explainable_decisions(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    if not engine.strategy_history:
        raise HTTPException(status_code=400, detail="error")

    ci_result = engine.strategy_history[-1].case_result.ci_result
    if not ci_result:
        raise HTTPException(status_code=400, detail="error")

    case_info = state.game_sessions[game_id]["case_info"]
    case_summary = json.dumps(
        {k: str(v)[:200] for k, v in case_info.items() if k != "dialog_history"},
        ensure_ascii=False,
    )[:800]

    generator = state.ExplainableDecisionGenerator(state.llm_client)
    result = await asyncio.to_thread(
        generator.explain_full_judgment, ci_result.final_document, case_summary,
    )

    return {"game_id": game_id, "explainable_decisions": result}


@router.post("/game/{game_id}/evaluate/progressive-benchmark")
async def evaluate_progressive_benchmark(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    if not engine.strategy_history:
        raise HTTPException(status_code=400, detail="error")

    last = engine.strategy_history[-1]
    ci_result = last.case_result.ci_result
    if not ci_result:
        raise HTTPException(status_code=400, detail="error")

    eval_results = {}

    # 收集已有评测结果
    if last.equilibrium_snapshot:
        eval_results["equilibrium"] = last.equilibrium_snapshot
    eval_results["game_score"] = last.score.to_dict()

    # 快速运行关键评测
    lexeval = state.LexEvalCognitiveEvaluator(state.llm_client)
    eval_results["lexeval_cognitive"] = await asyncio.to_thread(
        lexeval.evaluate_all, ci_result.final_document,
    )

    from core.liability_chain import LiabilityChainExtractor
    extractor = state.LiabilityChainExtractor(state.llm_client)
    chain = await asyncio.to_thread(extractor.extract, ci_result.final_document)
    eval_results["liability_chain"] = chain.to_dict()

    level_result = state.assess_agent_capability_level(eval_results)

    return {
        "game_id": game_id,
        "progressive_benchmark": level_result,
        "benchmark_levels": state.PROGRESSIVE_BENCHMARK_LEVELS,
    }


@router.get("/game/{game_id}/evaluate/polarization")
async def detect_polarization(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    if len(engine.strategy_history) < 2:
        raise HTTPException(status_code=400, detail="error")

    rounds = engine.strategy_history
    first_result = rounds[0].score.to_dict()
    last_result = rounds[-1].score.to_dict()

    polarization = state.detect_group_polarization(
        {"success_rate": first_result.get("plaintiff_win_rate", 0.5) * 100,
         "satisfaction": 50, "consensus": 50,
         "litigation_risk": (1 - first_result.get("reasoning_quality", 0.5)) * 100},
        {"success_rate": last_result.get("plaintiff_win_rate", 0.5) * 100,
         "satisfaction": 50, "consensus": 50,
         "litigation_risk": (1 - last_result.get("reasoning_quality", 0.5)) * 100},
    )

    return {
        "game_id": game_id,
        "rounds_analyzed": len(rounds),
        "polarization_analysis": polarization,
    }


@router.get("/game/{game_id}/liability-chain")
async def get_liability_chain(game_id: str):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    if not engine.strategy_history:
        raise HTTPException(status_code=400, detail="error")

    last_round = engine.strategy_history[-1]
    ci_result = last_round.case_result.ci_result
    if not ci_result:
        raise HTTPException(400, "最后一轮无博弈结果")

    extractor = state._get_liability_extractor()
    result = await asyncio.to_thread(
        extractor.extract, ci_result.final_document,
    )

    return {
        "game_id": game_id,
        "round_index": last_round.round_index,
        "liability_chain": result.to_dict(),
    }


@router.post("/game/{game_id}/liability-chain/counterfactual")
async def liability_counterfactual(game_id: str, req: LiabilityCounterfactualRequest):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    engine: state.GameEngine = state.game_sessions[game_id]["engine"]
    if not engine.strategy_history:
        raise HTTPException(status_code=400, detail="error")

    last_round = engine.strategy_history[-1]
    ci_result = last_round.case_result.ci_result
    if not ci_result:
        raise HTTPException(400, "最后一轮无博弈结果")

    extractor = state._get_liability_extractor()
    chain = await asyncio.to_thread(extractor.extract, ci_result.final_document)

    cf_result = await asyncio.to_thread(
        extractor.counterfactual,
        chain, req.party, req.original_behavior, req.hypothetical_behavior,
    )

    return {
        "game_id": game_id,
        "original_chain": chain.to_dict(),
        "counterfactual_analysis": cf_result,
    }


@router.post("/game/{game_id}/progressive-rag")
async def run_progressive_rag(game_id: str, req: ProgressiveRAGRequest):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    retriever = state.get_law_retriever()
    if not retriever:
        raise HTTPException(503, "法条检索器未初始化")

    prag = state.ProgressiveRAG(retriever, state.llm_client)
    results = await asyncio.to_thread(
        prag.retrieve_for_stage, req.stage, req.context, req.top_k, "api_call",
    )

    return {
        "game_id": game_id,
        "stage": req.stage,
        "new_results": results,
        "retrieval_summary": prag.get_retrieval_summary(),
    }


@router.post("/game/{game_id}/dual-mode-reasoning")
async def run_game_dual_mode(game_id: str, req: Optional[DualModeRequest] = None):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    sess = state.game_sessions[game_id]
    case_info = json.dumps(sess["case_info"], ensure_ascii=False)[:3000]
    claims = str(sess["case_info"].get("plaintiff_claims", ""))

    if req:
        case_info = req.case_info or case_info
        claims = req.claims or claims

    reasoner = state.DualModeReasoner(state.llm_client)
    result = await asyncio.to_thread(
        reasoner.dual_mode_judgment, case_info, claims, True,
    )
    return {"game_id": game_id, **result}


@router.post("/game/{game_id}/multi-judge")
async def run_game_multi_judge(game_id: str, req: Optional[MultiJudgeRequest] = None):
    if game_id not in state.game_sessions:
        raise HTTPException(status_code=404, detail="error")

    sess = state.game_sessions[game_id]
    case_facts = str(sess["case_info"].get("case_description", ""))
    claims = str(sess["case_info"].get("plaintiff_claims", ""))

    num_judges = 3
    aggregation = "meta_judge"
    if req:
        case_facts = req.case_facts or case_facts
        claims = req.claims or claims
        num_judges = req.num_judges
        aggregation = req.aggregation

    engine = state.MultiJudgeEngine(state.llm_client)
    result = await asyncio.to_thread(
        engine.run, case_facts, claims, "", num_judges, aggregation,
    )
    return {"game_id": game_id, **result.to_dict()}


if __name__ == "__main__":
    # 默认仅监听本机；如需局域网访问，设置 API_HOST=0.0.0.0 并强烈建议同时设置 API_TOKEN
    uvicorn.run(app, host=os.getenv("API_HOST", "127.0.0.1"), port=int(os.getenv("API_PORT", "8000")))

