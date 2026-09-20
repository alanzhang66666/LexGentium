from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


EvaluationScenario = Literal["CD", "DD", "CI"]
EvaluationTaskStatus = Literal["running", "completed", "failed"]


class EvaluationRequest(BaseModel):
    """Public contract for starting an evaluation task.

    Unknown fields are rejected so route behavior cannot depend on attributes that
    are absent from the API schema.
    """

    model_config = ConfigDict(extra="forbid")

    scenarios: List[EvaluationScenario] = Field(default_factory=lambda: ["CD", "DD", "CI"])
    prediction_files: Optional[Dict[str, str]] = None
    use_default_predictions: bool = True
    session_id: Optional[str] = Field(default=None, min_length=1)
    run_id: Optional[str] = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_evaluation_input(self) -> "EvaluationRequest":
        if not self.session_id and not self.prediction_files and not self.use_default_predictions:
            raise ValueError(
                "one of session_id, prediction_files, or use_default_predictions=true is required"
            )
        return self


class EvaluationError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class CorrelationContext(BaseModel):
    """可用非秘密关联身份的投影（缺省字段不生成伪值）。"""

    model_config = ConfigDict(extra="forbid")

    request_id: Optional[str] = None
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    operation_id: Optional[str] = None
    game_id: Optional[str] = None
    report_id: Optional[str] = None
    run_id: Optional[str] = None


class EvaluationProvenanceView(BaseModel):
    """评分 provenance 公开视图（Task 8.3）。"""

    model_config = ConfigDict(extra="forbid")

    provenance_id: str
    namespace: str
    rubric_version: str
    evaluator_version: str
    configuration_identity: str
    model_identity: str
    input_digest: str
    degraded: bool = False
    affected_metrics: List[str] = Field(default_factory=list)
    report_status: Optional[str] = None
    result_digest: Optional[str] = None


class EvaluationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str
    status: EvaluationTaskStatus
    message: str
    results: Optional[Dict[str, Any]] = None
    report_path: Optional[str] = None
    session_id: Optional[str] = None
    run_id: Optional[str] = None
    error: Optional[EvaluationError] = None
    provenance: Optional[EvaluationProvenanceView] = None
    correlation: Optional[CorrelationContext] = None


class EvaluationReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str
    file_name: str
    file_path: str
    created_at: str
    scenarios: List[str]


class EvaluationReportsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reports: List[EvaluationReportSummary]


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
    # 研究身份三元组：必须同现，经 freeze_role_snapshot 校验，未知 pack/cluster 拒绝
    dataset_id: Optional[str] = None
    cluster_id: Optional[str] = None
    pack_version: Optional[str] = None
    derived_from: Optional[str] = None
    visible_materials: Optional[Dict[str, Any]] = None
    experiment_conditions: Optional[Dict[str, Any]] = None
    model_config_: Optional[Dict[str, Any]] = Field(default=None, alias="model_config")
    visibility_grants: Optional[List[Dict[str, Any]]] = None


class ConversationStartResponse(BaseModel):
    session_id: str
    scenario: str
    case_id: str
    created_at: str
    run_id: Optional[str] = None
    dataset_id: Optional[str] = None
    cluster_id: Optional[str] = None
    pack_version: Optional[str] = None
    derived_from: Optional[str] = None
    materials_hash: Optional[str] = None


class ConversationMessageRequest(BaseModel):
    message: str
    role: Optional[str] = None
    # 幂等重试用的客户端 Operation ID；缺省由服务端生成
    operation_id: Optional[str] = None


class ConversationMessageResponse(BaseModel):
    session_id: str
    response: Dict[str, str]
    dialog_history: List[Dict[str, Any]]
    is_finished: bool = False
    # True 表示该回复由离线兜底模板生成（未调用真实 LLM），实验脚本应据此过滤数据
    degraded: bool = False
    # CI 场景的推理元数据：judgment_status(ok/degraded/failed)、
    # citation_report（法条回查命中/未命中）、case_warnings（数据契约告警）
    reasoning_meta: Optional[Dict[str, Any]] = None
    # 研究协议终态：material_insufficient | max_turns | completed（民事会话恒 None）
    stop_reason: Optional[str] = None


class ConversationInfo(BaseModel):
    session_id: str
    scenario: str
    case_id: str
    created_at: str
    updated_at: str
    message_count: int
    dialog_history: List[Dict[str, Any]]


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
    stop_reason: Optional[str] = None


class FullSimulationRequest(BaseModel):
    case_info: Dict[str, Any]
    mode: str = "single"
    tournament_rounds: int = 3
    operation_id: Optional[str] = None
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
    thinking: Literal["enabled", "disabled"] = "enabled"
    reasoning_effort: Literal["low", "high", "max"] = "high"
    fast_thinking: Literal["enabled", "disabled"] = "disabled"
    fast_reasoning_effort: Literal["low", "high", "max"] = "low"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 60


class DeepSeekChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class DeepSeekChatCompletionRequest(BaseModel):
    """DeepSeek/OpenAI-compatible Chat Completions demo contract."""

    model_config = ConfigDict(extra="allow")

    model: Literal["deepseek-flash"] = "deepseek-flash"
    messages: List[DeepSeekChatMessage]
    stream: bool = False
    stream_options: Optional[Dict[str, Any]] = None
    max_tokens: Optional[int] = Field(default=None, ge=1)
    thinking: Optional[Dict[str, Literal["enabled", "disabled"]]] = None
    reasoning_effort: Optional[Literal["low", "high", "max"]] = None
    response_format: Optional[Dict[str, str]] = None


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
    operation_id: Optional[str] = None


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
