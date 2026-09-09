from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class DialogMessage(BaseModel):
    turn: Optional[int] = None
    role: str
    message: str


class ApiRequest(BaseModel):
    scenario: str
    case_id: str
    dialog_history: List[DialogMessage]
    input_json: Optional[Dict[str, Any]] = None


class ApiResponse(BaseModel):
    scenario: str
    case_id: str
    response: Dict[str, str]


class SessionLinks(BaseModel):
    task_id: Optional[str] = None
    game_id: Optional[str] = None
    report_id: Optional[str] = None


class EvaluationRequest(BaseModel):
    scenarios: List[str] = ["CD", "DD", "CI"]
    prediction_files: Optional[Dict[str, str]] = None
    use_default_predictions: bool = True
    session_id: Optional[str] = None


class EvaluationResponse(BaseModel):
    report_id: str
    status: str
    message: str
    results: Optional[Dict[str, Any]] = None
    report_path: Optional[str] = None


class LawSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class LawSearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    total: int


class ConversationStartRequest(BaseModel):
    scenario: str
    case_id: str
    input_json: Optional[Dict[str, Any]] = None


class ConversationStartResponse(BaseModel):
    session_id: str
    scenario: str
    case_id: str
    created_at: str


class ConversationMessageRequest(BaseModel):
    message: str
    role: Optional[str] = None


class ConversationMessageResponse(BaseModel):
    session_id: str
    response: Dict[str, str]
    dialog_history: List[Dict[str, Any]]
    is_finished: bool = False
    # True 表示该回复由离线兜底模板生成（未调用真实 LLM），实验脚本应据此过滤数据
    degraded: bool = False


class ConversationInfo(BaseModel):
    session_id: str
    scenario: str
    case_id: str
    created_at: str
    updated_at: str
    message_count: int
    dialog_history: List[Dict[str, Any]]
    links: Optional[SessionLinks] = None


class ConversationImportRequest(BaseModel):
    scenario: str
    case_id: str
    dialog_history: List[Dict[str, Any]]
    input_json: Optional[Dict[str, Any]] = None


class ConversationImportResponse(BaseModel):
    session_id: str
    scenario: str
    case_id: str
    created_at: str
    message_count: int
    is_finished: bool = False


class AutoAdvanceRequest(BaseModel):
    max_rounds: int = 5
    auto_reply_roles: Optional[List[str]] = None


class AutoAdvanceResponse(BaseModel):
    session_id: str
    rounds_played: int
    dialog_history: List[Dict[str, Any]]
    is_finished: bool
    current_stage: Optional[str] = None
    next_speaker: Optional[str] = None
    available_actions: List[str] = []


class FullSimulationRequest(BaseModel):
    case_info: Dict[str, Any]
    mode: str = "single"
    tournament_rounds: int = 3
    session_id: Optional[str] = None


class FullSimulationStatusResponse(BaseModel):
    task_id: str
    status: str
    message: str
    current_stage: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class LLMConfigRequest(BaseModel):
    provider: str = "deepseek"
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 60


class GameCreateRequest(BaseModel):
    case_info: Dict[str, Any]
    session_id: Optional[str] = None
    plaintiff_strategy: str = "compromising"
    defendant_strategy: str = "compromising"
    max_rounds: int = 5
    convergence_threshold: float = 0.05
    evolution_method: str = "llm_reflection"
    enable_dynamic_strategy: bool = True
    dispute_cause: Optional[str] = None
    dispute_cause_detail: Optional[str] = None


class GameStrategySetRequest(BaseModel):
    party: str
    strategy_type: str
    custom_instruction: Optional[str] = None


class GameRoundRequest(BaseModel):
    evolution_method: Optional[str] = None


class GameCounterfactualRequest(BaseModel):
    party: str
    hypothetical_strategy: str


class GameEvaluateRequest(BaseModel):
    party_names: Optional[List[str]] = None


class LiabilityCounterfactualRequest(BaseModel):
    party: str
    original_behavior: str
    hypothetical_behavior: str


class MediationCreateRequest(BaseModel):
    case_info: Dict[str, Any]
    party_names: Optional[List[str]] = None
    max_bargaining_rounds: int = 5
    nbs_reference_text: Optional[str] = None
    auto_compute_nbs: bool = False


class MediationStatementRequest(BaseModel):
    party_name: str
    statement: Optional[str] = None


class MediationBargainRequest(BaseModel):
    party_responses: Optional[Dict[str, str]] = None


class ProgressiveRAGRequest(BaseModel):
    stage: str
    context: Dict[str, str]
    top_k: int = 5


class DualModeRequest(BaseModel):
    case_info: str
    claims: str
    use_llm_eval: bool = True


class MultiJudgeRequest(BaseModel):
    case_facts: str
    claims: str
    trial_summary: str = ""
    num_judges: int = 3
    aggregation: str = "meta_judge"

