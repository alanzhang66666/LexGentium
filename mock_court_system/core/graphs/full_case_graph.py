"""全案图：CD → DD → Hearing 子图 → 评分 / 策略进化循环。"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, TypedDict

from core.case_orchestrator import FullCaseOrchestrator, FullCaseResult, StageResult
from core.graphs.hearing_runtime import get_hearing_runtime, use_hearing_graph


class FullCaseState(TypedDict, total=False):
    case_info: Dict[str, Any]
    cd_strategy: Optional[str]
    dd_strategy: Optional[str]
    plaintiff_strategy_type: Optional[str]
    defendant_strategy_type: Optional[str]
    previous_round_summary: Optional[str]
    dispute_cause: Optional[str]
    dispute_cause_detail: Optional[str]
    cd_result: Dict[str, Any]
    dd_result: Dict[str, Any]
    ci_result: Dict[str, Any]
    score: Dict[str, Any]
    finished: bool
    round_index: int
    max_rounds: int
    converged: bool
    task_id: str


def compile_full_case_graph(orchestrator: FullCaseOrchestrator, game_engine=None, checkpointer=None):
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return None

    def cd_stage(state: FullCaseState) -> Dict[str, Any]:
        result = orchestrator.run_stage_cd(
            state["case_info"],
            cd_strategy=state.get("cd_strategy"),
            cd_strategy_type=state.get("plaintiff_strategy_type"),
            previous_round_summary=state.get("previous_round_summary"),
        )
        return {"cd_result": result.to_dict() if hasattr(result, "to_dict") else _stage_to_dict(result)}

    def dd_stage(state: FullCaseState) -> Dict[str, Any]:
        cd = state.get("cd_result") or {}
        result = orchestrator.run_stage_dd(
            state["case_info"],
            complaint_text=cd.get("final_document", ""),
            cd_extracted=cd.get("extracted_info"),
            dd_strategy=state.get("dd_strategy"),
            dd_strategy_type=state.get("defendant_strategy_type"),
            previous_round_summary=state.get("previous_round_summary"),
        )
        return {"dd_result": _stage_to_dict(result)}

    def hearing(state: FullCaseState) -> Dict[str, Any]:
        cd = state.get("cd_result") or {}
        dd = state.get("dd_result") or {}
        result = orchestrator.run_stage_ci(
            state["case_info"],
            complaint_text=cd.get("final_document", ""),
            defense_text=dd.get("final_document", ""),
            cd_extracted=cd.get("extracted_info"),
            dd_extracted=dd.get("extracted_info"),
            plaintiff_strategy_type=state.get("plaintiff_strategy_type"),
            defendant_strategy_type=state.get("defendant_strategy_type"),
            previous_round_summary=state.get("previous_round_summary"),
        )
        return {"ci_result": _stage_to_dict(result), "finished": True}

    def score_and_track(state: FullCaseState) -> Dict[str, Any]:
        if game_engine is None:
            return {"score": {}}
        ci = state.get("ci_result") or {}
        dummy = StageResult(
            scenario="CI",
            dialog_history=ci.get("dialog_history") or [],
            final_document=ci.get("final_document") or "",
        )
        score = game_engine.evaluate_judgment(dummy, state.get("case_info"))
        if not score.degraded:
            try:
                game_engine.nash_tracker.record_round(
                    state.get("plaintiff_strategy_type"),
                    state.get("defendant_strategy_type"),
                    score.to_dict(),
                )
            except Exception:
                pass
        return {"score": score.to_dict()}

    def evolve_strategies(state: FullCaseState) -> Dict[str, Any]:
        return {
            "round_index": int(state.get("round_index") or 0) + 1,
            "previous_round_summary": (state.get("ci_result") or {}).get("final_document", "")[:800],
        }

    def route_loop(state: FullCaseState) -> str:
        if state.get("converged"):
            return "end"
        idx = int(state.get("round_index") or 0)
        mx = int(state.get("max_rounds") or 1)
        if idx + 1 >= mx:
            return "end"
        return "evolve_strategies"

    builder = StateGraph(FullCaseState)
    builder.add_node("cd_stage", cd_stage)
    builder.add_node("dd_stage", dd_stage)
    builder.add_node("hearing", hearing)
    builder.add_node("score_and_track", score_and_track)
    builder.add_node("evolve_strategies", evolve_strategies)
    builder.add_edge(START, "cd_stage")
    builder.add_edge("cd_stage", "dd_stage")
    builder.add_edge("dd_stage", "hearing")
    builder.add_edge("hearing", "score_and_track")
    builder.add_conditional_edges(
        "score_and_track",
        route_loop,
        {"evolve_strategies": "evolve_strategies", "end": END},
    )
    builder.add_edge("evolve_strategies", "cd_stage")
    try:
        return builder.compile(checkpointer=checkpointer)
    except Exception:
        return builder.compile()


def _stage_to_dict(result: StageResult) -> Dict[str, Any]:
    return {
        "scenario": result.scenario,
        "dialog_history": result.dialog_history,
        "final_document": result.final_document,
        "extracted_info": result.extracted_info,
        "metadata": result.metadata,
    }


def run_full_case_graph(orchestrator: FullCaseOrchestrator, case_info: Dict[str, Any], **kwargs) -> FullCaseResult:
    """走图（若可用）或直接编排器。"""
    extra = {k: v for k, v in kwargs.items() if k != "task_id"}
    # 推演流需要 on_progress；LangGraph 节点目前不转发该回调，静默超过 SSE 等待会 timeout
    if extra.get("on_progress") is not None:
        return orchestrator.run_full_case(case_info, **extra)
    graph = compile_full_case_graph(orchestrator)
    if graph is not None:
        try:
            payload: FullCaseState = {
                "case_info": case_info,
                "cd_strategy": kwargs.get("cd_strategy"),
                "dd_strategy": kwargs.get("dd_strategy"),
                "plaintiff_strategy_type": kwargs.get("plaintiff_strategy_type"),
                "defendant_strategy_type": kwargs.get("defendant_strategy_type"),
                "previous_round_summary": kwargs.get("previous_round_summary"),
                "dispute_cause": kwargs.get("dispute_cause"),
                "dispute_cause_detail": kwargs.get("dispute_cause_detail"),
                "round_index": 0,
                "max_rounds": 1,
                "task_id": kwargs.get("task_id") or case_info.get("case_id", "auto"),
            }
            config = {"configurable": {"thread_id": payload["task_id"]}}
            out = graph.invoke(payload, config)
            return FullCaseResult(
                case_id=case_info.get("case_id", "auto"),
                cd_result=_stage_from_dict(out.get("cd_result"), "CD"),
                dd_result=_stage_from_dict(out.get("dd_result"), "DD"),
                ci_result=_stage_from_dict(out.get("ci_result"), "CI"),
                judgment_score=out.get("score"),
            )
        except Exception:
            pass
    return orchestrator.run_full_case(case_info, **extra)


def _stage_from_dict(data: Optional[Dict[str, Any]], scenario: str) -> Optional[StageResult]:
    if not data:
        return None
    return StageResult(
        scenario=data.get("scenario", scenario),
        dialog_history=data.get("dialog_history") or [],
        final_document=data.get("final_document") or "",
        extracted_info=data.get("extracted_info") or {},
        metadata=data.get("metadata") or {},
    )


def run_tournament_graph(game_engine, case_info: Dict[str, Any], rounds: int = 3, **kwargs):
    return game_engine.run_tournament(case_info, rounds, **kwargs)


def persist_task_checkpoint(task_id: str, payload: Dict[str, Any]) -> None:
    from core.graphs.checkpoint import SqliteCheckpointStore
    store = SqliteCheckpointStore()
    store.save(task_id, payload)
