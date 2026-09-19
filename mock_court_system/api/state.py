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

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from settings import settings
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
from api.runtime import create_runtime, rebind_runtime_llm
from core.case_orchestrator import _is_ci_final as _ci_final
from core.reasoning_state import extract_ci_reasoning_state
from core.llm_client import LLMClient
from core.store.conversation_store import build_conversation_store, ConversationRecord
from core.store.evaluation_task_store import build_evaluation_task_store, EvaluationTaskRecord

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


def ci_reasoning_state_from_record(record) -> Optional[Dict[str, Any]]:
    """从会话记录中取出上一轮保存的 CI ReasoningState（无则 None）。"""
    if record is None:
        return None
    state = (record.input_json or {}).get("_reasoning_state")
    return state if isinstance(state, dict) else None


def new_session_ci_agent():
    """为单个会话请求创建独立 CIAgent 实例（并发隔离）。

    成本分析：chains 是 LangChain 管道轻对象（内部引用共享的 chat_model），
    law_retriever 走模块级单例（BM25/FAISS 只加载一次），
    因此按请求构造不会带来重资源开销，却彻底消除共享实例在并发下的
    case_info/state_machine/dialogue 互相覆盖问题。
    """
    from agents import CIAgent
    from api.runtime import MockApiClient

    return CIAgent(
        MockApiClient(),
        llm_client,
        max_turns=settings.get_scenario_config("CI").max_turns,
        instruction_mode=settings.get_scenario_config("CI").instruction_mode,
    )


def save_ci_reasoning_state(record, ci_agent) -> None:
    """把 CIAgent 的推理状态写回会话记录（随 input_json 持久化，零 schema 变更）。"""
    record.input_json = dict(record.input_json or {})
    record.input_json["_reasoning_state"] = extract_ci_reasoning_state(ci_agent)


def state_ci_agent():
    """共享 CIAgent（向后兼容回落）。新代码建议用 new_session_ci_agent()。"""
    return ci_agent


def run_agent_turn(*, scenario: str, case_id: str, dialog_history: List[Dict[str, Any]],
                   input_json: Optional[Dict[str, Any]] = None,
                   reasoning_state: Optional[Dict[str, Any]] = None,
                   ci_agent=None):
    from core.research.runtime import bind_research_context, reset_research_context

    role = dialog_history[-1].get("role") if dialog_history else None
    token = bind_research_context(input_json, role)
    try:
        active_history = dialog_history
        if input_json and input_json.get("research"):
            from core.research.runtime import inject_material_context

            active_history = inject_material_context(
                dialog_history, input_json, scenario, role=role
            )
        return _dispatch_agent_turn(
            scenario=scenario, case_id=case_id, dialog_history=active_history,
            input_json=input_json, reasoning_state=reasoning_state, ci_agent=ci_agent,
        )
    finally:
        reset_research_context(token)


def _dispatch_agent_turn(*, scenario: str, case_id: str, dialog_history: List[Dict[str, Any]],
                         input_json: Optional[Dict[str, Any]] = None,
                         reasoning_state: Optional[Dict[str, Any]] = None,
                         ci_agent=None):
    response_text = ""
    is_finished = False
    response_role = "Lawyer"  # default for CD/DD

    if scenario == "CD":
        response_text = cd_agent.process_turn(dialog_history, case_id, input_json)
        clean_start = response_text.strip().replace("*", "").replace("#", "").replace(" ", "")
        if clean_start.startswith("民事起诉状"):
            is_finished = True
            response_role = "Final"
        else:
            response_role = "Lawyer"
    elif scenario == "DD":
        response_text = dd_agent.process_turn(dialog_history, case_id, input_json)
        clean_start = response_text.strip().replace("*", "").replace("#", "").replace(" ", "")
        if clean_start.startswith("民事答辩状"):
            is_finished = True
            response_role = "Final"
        else:
            response_role = "Lawyer"
    elif scenario == "CI":
        agent = ci_agent or state_ci_agent()
        response_text = agent.process_turn(
            dialog_history, case_id, input_json,
            reasoning_state=reasoning_state,
        )
        finished_via_sm = False
        try:
            finished_via_sm = agent.state_machine.export_state().get("is_finished", False)
        except Exception:
            pass
        if finished_via_sm or _ci_final(response_text):
            is_finished = True
            response_role = "Final"
        else:
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
    """Compatibility entry point; all callers use the attributed task service."""
    from api.services.evaluation import execute_evaluation_task

    return execute_evaluation_task(report_id, scenarios, prediction_files)



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


def _infer_conversation_meta(scenario: str, dialog_history: List[Dict[str, Any]],
                             session_id: Optional[str] = None,
                             input_json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
            try:
                exported = ci_agent.state_machine.export_state()
                if exported.get("is_finished"):
                    is_finished = True
            except Exception:
                pass
            if not is_finished and _ci_final(last_msg):
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
        current_stage = _guess_ci_stage(dialog_history)
        last_role = dialog_history[-1]["role"] if dialog_history else None
        if last_role == "Judge":
            next_speaker = "Plaintiff"
        elif last_role == "Plaintiff":
            next_speaker = "Defendant"
        else:
            next_speaker = "Judge"
        available_actions = ["send_message", "auto_advance"]
        try:
            current_sub_stage = ci_agent.state_machine.current_sub_stage.value
        except Exception:
            pass

    return {
        "current_stage": current_stage,
        "current_sub_stage": current_sub_stage,
        "next_speaker": next_speaker,
        "available_actions": available_actions,
        "is_finished": is_finished,
        "turn_count": len(dialog_history),
    }


def _guess_ci_stage(dialog_history: List[Dict[str, Any]]) -> str:
    try:
        exported = ci_agent.state_machine.export_state()
        return exported.get("stage_label", "opening")
    except Exception:
        pass
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


def _run_full_simulation_task(task_id: str, case_info: Dict[str, Any]):
    try:
        simulation_tasks[task_id]["status"] = "running"
        simulation_tasks[task_id]["current_stage"] = "CD"

        def on_progress(stage, round_idx, role, finished):
            simulation_tasks[task_id]["current_stage"] = stage
            simulation_tasks[task_id]["message"] = f"阶段 {stage}，轮次 {round_idx}，角色 {role}"

        result = _orchestrator.run_full_case(case_info, on_progress=on_progress)

        simulation_tasks[task_id]["status"] = "completed"
        simulation_tasks[task_id]["message"] = "completed"
        simulation_tasks[task_id]["result"] = result.to_dict()
        simulation_tasks[task_id]["current_stage"] = "finished"

    except Exception as e:
        eval_logger.error(f"全流程模拟失败: {e}", exc_info=True)
        simulation_tasks[task_id]["status"] = "failed"
        simulation_tasks[task_id]["message"] = f"妯℃嫙澶辫触: {str(e)}"


def _run_tournament_task(task_id: str, case_info: Dict[str, Any], rounds: int):
    try:
        simulation_tasks[task_id]["status"] = "running"
        simulation_tasks[task_id]["current_stage"] = "round_1"

        def on_progress(stage, round_idx, role, finished):
            simulation_tasks[task_id]["current_stage"] = f"{stage}_round_{round_idx}"
            simulation_tasks[task_id]["message"] = f"锦标赛 {stage}，轮次 {round_idx}"

        result = _game_engine.run_tournament(
            case_info, rounds=rounds, on_progress=on_progress,
        )

        simulation_tasks[task_id]["status"] = "completed"
        simulation_tasks[task_id]["message"] = f"博弈锦标赛完成（{rounds} 轮）"
        simulation_tasks[task_id]["result"] = result.to_dict()
        simulation_tasks[task_id]["current_stage"] = "finished"

    except Exception as e:
        eval_logger.error(f"博弈锦标赛失败: {e}", exc_info=True)
        simulation_tasks[task_id]["status"] = "failed"
        simulation_tasks[task_id]["message"] = f"锦标赛失败: {str(e)}"




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
from core.store.game_session_store import GameSessionStore

game_sessions: Dict[str, Dict[str, Any]] = {}
_game_store = GameSessionStore(str(project_root / "data" / "game_sessions.sqlite3"))



# ========== SSE ==========


def _sse_event(event_type: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"



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

from core.lab.liability_chain import LiabilityChainExtractor

_liability_extractor: Optional[LiabilityChainExtractor] = None


def _get_liability_extractor() -> LiabilityChainExtractor:
    global _liability_extractor
    if _liability_extractor is None or _liability_extractor.llm is not llm_client:
        _liability_extractor = LiabilityChainExtractor(llm_client)
    return _liability_extractor



# ========== 调解与 P0 创新模块 ==========


_mediation_engine = runtime.mediation_engine


# ========== P0 创新模块 API（Progressive RAG + Dual-Mode + Multi-Judge）==========

from core.lab.progressive_rag import ProgressiveRAG
from core.lab.dual_mode_reasoning import DualModeReasoner
from core.lab.multi_judge import MultiJudgeEngine
