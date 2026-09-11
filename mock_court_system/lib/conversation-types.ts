export type Scenario = "CD" | "DD" | "CI"

export interface ConversationStartRequest {
  scenario: Scenario
  case_id: string
  input_json?: Record<string, unknown>
}

export interface ConversationStartResponse {
  session_id: string
  scenario: string
  case_id: string
  created_at: string
}

export interface ConversationMessageRequest {
  message: string
  role?: string
}

export interface ConversationMessageResponse {
  session_id: string
  response: {
    role: string
    message: string
  }
  dialog_history: DialogEntry[]
  is_finished: boolean
  /** True 表示回复由离线兜底模板生成（未调用真实 LLM） */
  degraded?: boolean
  /** CI 场景推理元数据（判决语义状态/法条回查/数据契约告警） */
  reasoning_meta?: {
    judgment_status: "ok" | "degraded" | "failed"
    citation_report?: { checked: number; verified: number; unverified: string[] } | null
    case_warnings: string[]
  } | null
}

export interface DialogEntry {
  turn: number
  role: string
  message: string
}

export type CourtStage =
  | "opening"
  | "investigation"
  | "debate"
  | "mediation"
  | "judgment"
  | "dialogue"
  | "finished"

export type CourtSubStage =
  | "opening_identity"
  | "opening_composition"
  | "opening_rights"
  | "opening_recusal"
  | "opening_absence"
  | "opening_done"
  | "investigation_claim"
  | "investigation_defense"
  | "investigation_evidence"
  | "investigation_cross_exam"
  | "investigation_fact_inquiry"
  | "investigation_done"
  | "debate_focus"
  | "debate_argument"
  | "debate_rebuttal"
  | "debate_final_statement"
  | "debate_done"
  | "mediation_ask"
  | "mediation_plaintiff_resp"
  | "mediation_defendant_resp"
  | "mediation_announce"
  | "mediation_done"
  | "judgment_generating"
  | "judgment_done"

export type ConflictStrategy =
  | "competing"
  | "collaborating"
  | "compromising"
  | "avoiding"
  | "accommodating"

export interface LawArticle {
  law: string
  content: string
  applied_to?: string
}

export interface LiabilityMapping {
  plaintiff_claims: string[]
  court_adoption: string[]
}

export interface StructuredJudgment {
  facts: Array<{ content: string; source?: string }>
  dispute_points: string[]
  legal_articles: LawArticle[]
  liability_mapping: LiabilityMapping
  conclusion: string
  mediation_result?: {
    plaintiff_response: string | null
    defendant_response: string | null
    announced: boolean
    outcome: string
  } | null
}

export interface ComplianceStep {
  step: string
  passed: boolean
}

export interface ComplianceSection {
  score: number
  details: ComplianceStep[] | Record<string, unknown>
}

export interface ComplianceReport {
  opening: ComplianceSection
  investigation: ComplianceSection
  debate: ComplianceSection
  mediation: ComplianceSection
  stage_order_correct: boolean
  overall: number
}

export interface MultiLayerEvaluation {
  composite_score: number
  result_quality: Record<string, number | null>
  process_compliance: ComplianceReport
  legality_ethics: {
    legality_score: number
    risks: Array<{ type: string; severity: string; description: string }>
    risk_count: number
  }
}

export interface ConversationInfo {
  session_id: string
  scenario: string
  case_id: string
  created_at: string
  updated_at: string
  message_count: number
  dialog_history: DialogEntry[]
  current_stage?: CourtStage | null
  current_sub_stage?: CourtSubStage | null
  next_speaker?: string | null
  available_actions?: string[]
  is_finished?: boolean
  turn_count?: number
}

export interface ConversationSummary {
  session_id: string
  scenario: string
  case_id: string
  created_at: string
  updated_at: string
  message_count: number
  is_finished?: boolean
}

export interface ConversationListResponse {
  sessions: ConversationSummary[]
  total: number
  limit: number
  offset: number
}

export interface AutoAdvanceRequest {
  max_rounds?: number
  auto_reply_roles?: string[]
}

export interface AutoAdvanceResponse {
  session_id: string
  rounds_played: number
  dialog_history: DialogEntry[]
  is_finished: boolean
  current_stage?: CourtStage | null
  current_sub_stage?: CourtSubStage | null
  next_speaker?: string | null
  available_actions?: string[]
}

