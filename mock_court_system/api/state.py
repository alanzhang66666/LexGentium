"""共享运行时状态与辅助函数。

所有 router 通过 `state.xxx` 属性访问可变状态（agents/stores/tasks），
确保 LLM 热重载（rebind）后引用始终新鲜。仅本模块内允许裸名访问。
"""
import sys
import os
import json
import asyncio
import logging
import uuid
import hashlib
import queue
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import HTTPException

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config import settings
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
from api_runtime import create_runtime, rebind_runtime_llm
from core.case_orchestrator import _is_ci_final as _ci_final
from core.llm_client import LLMClient
from core.conversation_store import build_conversation_store, ConversationRecord
from core.evaluation_task_store import build_evaluation_task_store, EvaluationTaskRecord

eval_logger = logging.getLogger("evaluation")
eval_logger.setLevel(logging.INFO)

# ========== 会话管理存储 ==========
# 通过环境变量选择存储方式：
# - CONVERSATION_STORE=sqlite|memory（默认 sqlite）
# - CONVERSATION_DB_PATH=...（sqlite 文件路径，默认 ./data/conversations.sqlite3）
conversation_store = build_conversation_store(project_root)
evaluation_task_store = build_evaluation_task_store(project_root)


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _make_request_id() -> str:
    raw = f"{uuid.uuid4()}-{datetime.utcnow().isoformat()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def generate_session_id() -> str:
    return str(uuid.uuid4())

def cleanup_old_sessions(max_age_hours: int = 24) -> int:
    try:
        return conversation_store.cleanup(max_age_hours=max_age_hours)
    except Exception:
        return 0


def _research_claim_actions(input_json: Optional[Dict[str, Any]]) -> List[str]:
    from core.research.runtime import research_block

    run_id = research_block(input_json).get("run_id")
    if not run_id:
        return []
    try:
        from api.services.claims import list_claim_events

        return [str(item.get("action") or "") for item in list_claim_events(str(run_id))]
    except Exception:
        return []


def run_agent_turn(*, scenario: str, case_id: str, dialog_history: List[Dict[str, Any]], input_json: Optional[Dict[str, Any]]):
    from core.research.runtime import (
        bind_research_context,
        has_research,
        inject_material_context,
        research_llm_blocked,
        research_stop_notice,
        reset_research_context,
        role_model_input,
    )

    blocked = research_llm_blocked(
        input_json,
        dialog_history,
        _research_claim_actions(input_json),
    )
    if blocked:
        return "Final", research_stop_notice(blocked), True

    speaking = None
    if dialog_history:
        speaking = str((dialog_history[-1] or {}).get("role") or "") or None
    filtered_input = input_json
    working_history = dialog_history
    token = None
    if has_research(input_json):
        filtered_input = role_model_input(input_json, speaking)
        if input_json and input_json.get("_session_id"):
            filtered_input["_session_id"] = input_json["_session_id"]
        working_history = inject_material_context(list(dialog_history or []), filtered_input, scenario)
        token = bind_research_context(filtered_input, speaking, cache_mode="replay")

    try:
        return _run_agent_turn_inner(
            scenario=scenario,
            case_id=case_id,
            dialog_history=working_history,
            input_json=filtered_input,
        )
    finally:
        reset_research_context(token)


def _run_agent_turn_inner(*, scenario: str, case_id: str, dialog_history: List[Dict[str, Any]], input_json: Optional[Dict[str, Any]]):
    response_text = ""
    is_finished = False
    response_role = "Lawyer"  # default for CD/DD

    if scenario in ("CD", "DD"):
        session_id = (input_json or {}).get("_session_id")
        from core.graphs.plead_runtime import get_plead_runtime, use_plead_runtime
        if session_id and use_plead_runtime():
            runtime = get_plead_runtime(
                cd_agent=cd_agent, dd_agent=dd_agent, llm=llm_client,
            )
            response_text, is_finished = runtime.live_turn(
                session_id, scenario, dialog_history, case_id, input_json,
            )
        elif scenario == "CD":
            response_text = cd_agent.process_turn(dialog_history, case_id, input_json)
            is_finished = response_text.strip().replace("*", "").replace("#", "").replace(" ", "").startswith("民事起诉状")
        else:
            response_text = dd_agent.process_turn(dialog_history, case_id, input_json)
            is_finished = response_text.strip().replace("*", "").replace("#", "").replace(" ", "").startswith("民事答辩状")
        response_role = "Final" if is_finished else "Lawyer"
    elif scenario == "CI":
        session_id = (input_json or {}).get("_session_id")
        from core.graphs.hearing_runtime import get_hearing_runtime, use_hearing_graph
        if session_id and use_hearing_graph():
            runtime = get_hearing_runtime(ci_agent=ci_agent, llm=llm_client)
            if not dialog_history:
                response_text, is_finished = runtime.start_court(session_id, case_id, input_json)
            else:
                last = dialog_history[-1]
                response_text, is_finished = runtime.live_turn(
                    session_id,
                    last.get("role", "Plaintiff"),
                    last.get("message", ""),
                    case_id,
                    input_json,
                )
        else:
            response_text = ci_agent.process_turn(dialog_history, case_id, input_json)
            is_finished = False
            try:
                is_finished = ci_agent.state_machine.export_state().get("is_finished", False)
            except Exception:
                pass
        finished_via_sm = bool(is_finished)
        if session_id and use_hearing_graph():
            try:
                sm = get_hearing_runtime().get_state_machine(session_id)
                if sm and sm.export_state().get("is_finished"):
                    finished_via_sm = True
            except Exception:
                pass
        else:
            try:
                finished_via_sm = finished_via_sm or ci_agent.state_machine.export_state().get("is_finished", False)
            except Exception:
                pass
        if finished_via_sm or _ci_final(response_text):
            is_finished = True
            response_role = "Final"
        else:
            is_finished = False
            response_role = "Judge"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {scenario}")

    return response_role, response_text, is_finished

# Initialize shared runtime dependencies.
runtime = create_runtime(settings)
api_client = runtime.api_client
llm_client = runtime.llm_client
cd_agent = runtime.cd_agent
dd_agent = runtime.dd_agent
ci_agent = runtime.ci_agent


# ========== 评测任务 ==========


evaluation_tasks: Dict[str, Dict[str, Any]] = {}

def run_evaluation_task(report_id: str, scenarios: List[str], prediction_files: Optional[Dict[str, str]]):
    from api.services.evaluation import execute_evaluation_task

    execute_evaluation_task(report_id, scenarios, prediction_files)



# ========== 法条检索（延迟初始化）==========


_law_retriever = None

def get_law_retriever():
    """返回共享 LawRetriever 单例；数据文件缺失时返回 None（检索接口降级）。"""
    global _law_retriever
    if _law_retriever is None:
        try:
            from core.law_retriever import get_shared_law_retriever
            _law_retriever = get_shared_law_retriever()
        except FileNotFoundError as e:
            eval_logger.warning(f"法条数据库缺失，检索不可用: {e}")
            return None
        except Exception as e:
            eval_logger.warning(f"无法初始化 LawRetriever: {e}")
            return None
    return _law_retriever

# 历史管理


# 会话管理


# ========== 会话辅助 ==========


def _infer_conversation_meta(
    scenario: str,
    dialog_history: List[Dict[str, Any]],
    session_id: Optional[str] = None,
    input_json: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    is_finished = False
    if dialog_history:
        last_role = dialog_history[-1].get("role", "")
        last_msg = dialog_history[-1].get("message", "")
        if last_role == "Final":
            is_finished = True
        elif scenario == "CD":
            clean = last_msg.strip().replace("*", "").replace("#", "").replace(" ", "")
            if clean.startswith("民事起诉状"):
                is_finished = True
        elif scenario == "DD":
            clean = last_msg.strip().replace("*", "").replace("#", "").replace(" ", "")
            if clean.startswith("民事答辩状"):
                is_finished = True
        elif scenario == "CI":
            exported = _ci_exported_state(session_id)
            if exported.get("is_finished"):
                is_finished = True
            if not is_finished and _ci_final(last_msg):
                is_finished = True

    if not is_finished:
        from core.research.runtime import research_llm_blocked

        if research_llm_blocked(input_json, dialog_history, _research_claim_actions(input_json)):
            is_finished = True

    current_stage = None
    next_speaker = None
    available_actions: List[str] = []

    if is_finished:
        available_actions = ["export", "delete"]
        return {
            "current_stage": "finished",
            "next_speaker": None,
            "available_actions": available_actions,
            "is_finished": True,
            "turn_count": len(dialog_history),
        }

    current_sub_stage = None

    if scenario in ("CD", "DD"):
        current_stage = "dialogue"
        last_role = dialog_history[-1]["role"] if dialog_history else None
        if last_role in ("Lawyer", None):
            next_speaker = "Client"
        else:
            next_speaker = "Lawyer"
        available_actions = ["send_message", "auto_advance"]
    elif scenario == "CI":
        current_stage = _guess_ci_stage(dialog_history, session_id)
        last_role = dialog_history[-1]["role"] if dialog_history else None
        if last_role == "Judge":
            next_speaker = "Plaintiff"
        elif last_role == "Plaintiff":
            next_speaker = "Defendant"
        else:
            next_speaker = "Judge"
        available_actions = ["send_message", "auto_advance"]
        exported = _ci_exported_state(session_id)
        if exported.get("stage_label"):
            current_stage = exported["stage_label"]
        current_sub_stage = exported.get("current_sub_stage") or current_sub_stage

    return {
        "current_stage": current_stage,
        "current_sub_stage": current_sub_stage,
        "next_speaker": next_speaker,
        "available_actions": available_actions,
        "is_finished": is_finished,
        "turn_count": len(dialog_history),
    }


def _ci_exported_state(session_id: Optional[str] = None) -> Dict[str, Any]:
    if session_id:
        try:
            from core.graphs.hearing_runtime import get_hearing_runtime, use_hearing_graph
            if use_hearing_graph():
                sm = get_hearing_runtime().get_state_machine(session_id)
                if sm:
                    return sm.export_state()
        except Exception:
            pass
    try:
        return ci_agent.state_machine.export_state()
    except Exception:
        return {}


def _guess_ci_stage(dialog_history: List[Dict[str, Any]], session_id: Optional[str] = None) -> str:
    exported = _ci_exported_state(session_id)
    if exported.get("stage_label"):
        return exported["stage_label"]
    text_blob = " ".join(item.get("message", "") for item in dialog_history[-20:])
    if any(k in text_blob for k in ["判决", "裁定", "案号", "判决结果"]):
        return "judgment"
    if any(k in text_blob for k in ["调解", "和解", "双方是否愿意"]):
        return "mediation"
    if any(k in text_blob for k in ["辩论", "辩护", "最后陈述"]):
        return "debate"
    if any(k in text_blob for k in ["举证", "质证", "证据", "诉讼请求", "陈述"]):
        return "investigation"
    return "opening"


# ========== 鑷姩鎺ㄨ繘 API ==========

def _determine_auto_roles(scenario: str, auto_reply_roles: Optional[List[str]]) -> List[str]:
    if auto_reply_roles:
        return auto_reply_roles
    if scenario in ("CD", "DD"):
        return ["Client"]
    elif scenario == "CI":
        return ["Plaintiff", "Defendant"]
    return ["Client"]



# ========== 全流程模拟与锦标赛任务 ==========


from core.game_engine import GameEngine

_orchestrator = runtime.orchestrator
_game_engine = runtime.game_engine

simulation_tasks: Dict[str, Dict[str, Any]] = {}


def persist_simulation_task(task_id: str) -> None:
    payload = simulation_tasks.get(task_id)
    if not payload:
        return
    try:
        from core.graphs.checkpoint import SqliteCheckpointStore
        SqliteCheckpointStore().save(task_id, payload)
    except Exception:
        pass


def load_simulation_task(task_id: str) -> Optional[Dict[str, Any]]:
    if task_id in simulation_tasks:
        return simulation_tasks[task_id]
    try:
        from core.graphs.checkpoint import SqliteCheckpointStore
        data = SqliteCheckpointStore().load(task_id)
        if data:
            simulation_tasks[task_id] = data
            return data
    except Exception:
        pass
    return None


def _run_full_simulation_task(task_id: str, case_info: Dict[str, Any]):
    try:
        simulation_tasks[task_id]["status"] = "running"
        simulation_tasks[task_id]["current_stage"] = "CD"
        persist_simulation_task(task_id)

        def on_progress(stage, round_idx, role, finished, sub_stage=None):
            simulation_tasks[task_id]["current_stage"] = stage
            simulation_tasks[task_id]["current_sub_stage"] = sub_stage
            simulation_tasks[task_id]["message"] = f"阶段 {stage}，轮次 {round_idx}，角色 {role}"
            persist_simulation_task(task_id)

        from core.graphs.full_case_graph import run_full_case_graph
        result = run_full_case_graph(_orchestrator, case_info, on_progress=on_progress, task_id=task_id)

        simulation_tasks[task_id]["status"] = "completed"
        simulation_tasks[task_id]["message"] = "completed"
        simulation_tasks[task_id]["result"] = result.to_dict()
        simulation_tasks[task_id]["current_stage"] = "finished"
        persist_simulation_task(task_id)

    except Exception as e:
        eval_logger.error(f"全流程模拟失败: {e}", exc_info=True)
        simulation_tasks[task_id]["status"] = "failed"
        simulation_tasks[task_id]["message"] = f"模拟失败: {str(e)}"
        persist_simulation_task(task_id)


def _run_tournament_task(task_id: str, case_info: Dict[str, Any], rounds: int):
    try:
        simulation_tasks[task_id]["status"] = "running"
        simulation_tasks[task_id]["current_stage"] = "round_1"

        def on_progress(stage, round_idx, role, finished, sub_stage=None):
            simulation_tasks[task_id]["current_stage"] = f"{stage}_round_{round_idx}"
            simulation_tasks[task_id]["current_sub_stage"] = sub_stage
            simulation_tasks[task_id]["message"] = f"锦标赛 {stage}，轮次 {round_idx}"
            persist_simulation_task(task_id)

        from core.graphs.full_case_graph import run_tournament_graph
        result = run_tournament_graph(
            _game_engine, case_info, rounds=rounds, on_progress=on_progress,
        )

        simulation_tasks[task_id]["status"] = "completed"
        simulation_tasks[task_id]["message"] = f"博弈锦标赛完成（{rounds} 轮）"
        simulation_tasks[task_id]["result"] = result.to_dict()
        simulation_tasks[task_id]["current_stage"] = "finished"
        persist_simulation_task(task_id)

    except Exception as e:
        eval_logger.error(f"博弈锦标赛失败: {e}", exc_info=True)
        simulation_tasks[task_id]["status"] = "failed"
        simulation_tasks[task_id]["message"] = f"锦标赛失败: {str(e)}"
        persist_simulation_task(task_id)




# 配置管理

def _reinit_llm_and_agents(new_llm: "LLMClient"):
    global runtime, api_client, llm_client, cd_agent, dd_agent, ci_agent, sim_agent
    global _orchestrator, _game_engine, _mediation_engine

    runtime = rebind_runtime_llm(runtime, new_llm, logger=eval_logger)
    api_client = runtime.api_client
    llm_client = runtime.llm_client
    cd_agent = runtime.cd_agent
    dd_agent = runtime.dd_agent
    ci_agent = runtime.ci_agent
    sim_agent = runtime.sim_agent
    _orchestrator = runtime.orchestrator
    _game_engine = runtime.game_engine
    if "_mediation_engine" in globals():
        _mediation_engine = runtime.mediation_engine
    try:
        from core.graphs.hearing_runtime import get_hearing_runtime
        get_hearing_runtime(ci_agent=ci_agent, llm=llm_client).bind(ci_agent=ci_agent, llm=llm_client)
    except Exception:
        pass
    try:
        from core.graphs.plead_runtime import get_plead_runtime
        get_plead_runtime(cd_agent=cd_agent, dd_agent=dd_agent, llm=llm_client).bind(
            cd_agent=cd_agent, dd_agent=dd_agent, llm=llm_client,
        )
    except Exception:
        pass


def _mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "***"
    return key[:4] + "***" + key[-4:]


def _persist_llm_env(cfg: LLMConfigRequest):
    env_path = project_root / ".env"
    lines: list[str] = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    keys_to_set = {
        "LLM_API_KEY": cfg.api_key,
        "LLM_BASE_URL": cfg.base_url,
        "LLM_MODEL": cfg.model,
        "LLM_PROVIDER": cfg.provider,
    }

    written = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            k = stripped.split("=", 1)[0]
            if k in keys_to_set:
                new_lines.append(f"{k}={keys_to_set[k]}\n")
                written.add(k)
                continue
        new_lines.append(line)

    # 追加尚未写入的 key
    for k, v in keys_to_set.items():
        if k not in written:
            new_lines.append(f"{k}={v}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)



# ========== 博弈会话 ==========


from core.nash_equilibrium import STRATEGY_NAMES as VALID_STRATEGIES
from core.game_session_store import GameSessionStore

game_sessions: Dict[str, Dict[str, Any]] = {}
_game_store = GameSessionStore(str(project_root / "data" / "game_sessions.sqlite3"))



# ========== SSE ==========


def _sse_event(event_type: str, data: Any) -> str:
    from api.services.sse import sse_event
    return sse_event(event_type, data)



# ========== 评估器（延迟单例）==========


from evaluation.lib.outcome_evaluator import OutcomeEvaluator

_outcome_evaluator: Optional[OutcomeEvaluator] = None


def _get_outcome_evaluator() -> OutcomeEvaluator:
    global _outcome_evaluator
    if _outcome_evaluator is None or _outcome_evaluator.llm is not llm_client:
        _outcome_evaluator = OutcomeEvaluator(llm_client)
    return _outcome_evaluator




from evaluation.lib.lexeval_cognitive import LexEvalCognitiveEvaluator
from evaluation.lib.j1eval_metrics import J1EvalMetrics, BIG_FIVE_TRAITS, generate_random_personality, build_personality_instruction
from evaluation.lib.solution_evaluator import (
    SolutionEvaluator, DISPUTE_CAUSES_TAXONOMY,
    detect_group_polarization, detect_surface_consensus,
)
from evaluation.lib.cadd_framework import (
    SymmetricBehaviorTracker, ExplainableDecisionGenerator,
    PROGRESSIVE_BENCHMARK_LEVELS, assess_agent_capability_level,
)


# ========== Behavior-Liability-Statute 鎺ㄧ悊閾?API ==========

from core.liability_chain import LiabilityChainExtractor

_liability_extractor: Optional[LiabilityChainExtractor] = None


def _get_liability_extractor() -> LiabilityChainExtractor:
    global _liability_extractor
    if _liability_extractor is None or _liability_extractor.llm is not llm_client:
        _liability_extractor = LiabilityChainExtractor(llm_client)
    return _liability_extractor



# ========== 调解与 P0 创新模块 ==========


_mediation_engine = runtime.mediation_engine


# ========== P0 创新模块 API（Progressive RAG + Dual-Mode + Multi-Judge）==========

from core.progressive_rag import ProgressiveRAG
from core.dual_mode_reasoning import DualModeReasoner
from core.multi_judge import MultiJudgeEngine
