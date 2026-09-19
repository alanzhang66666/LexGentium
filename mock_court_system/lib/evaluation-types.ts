export type EvaluationScenario = "CD" | "DD" | "CI"
export type EvaluationTaskStatus = "running" | "completed" | "failed"

export interface EvaluationRequest {
  scenarios: EvaluationScenario[]
  prediction_files?: Record<string, string>
  use_default_predictions?: boolean
  session_id?: string
  run_id?: string
}

export interface EvaluationError {
  code: string
  message: string
}

export interface CorrelationContext {
  request_id?: string | null
  session_id?: string | null
  task_id?: string | null
  operation_id?: string | null
  game_id?: string | null
  report_id?: string | null
  run_id?: string | null
}

export interface EvaluationProvenanceView {
  provenance_id: string
  namespace: string
  rubric_version: string
  evaluator_version: string
  configuration_identity: string
  model_identity: string
  input_digest: string
  degraded: boolean
  affected_metrics: string[]
  report_status?: string | null
  result_digest?: string | null
}

export interface EvaluationResponse {
  report_id: string
  status: EvaluationTaskStatus
  message: string
  results?: Record<string, unknown> | null
  report_path?: string | null
  session_id?: string | null
  run_id?: string | null
  error?: EvaluationError | null
  provenance?: EvaluationProvenanceView | null
  correlation?: CorrelationContext | null
}

export type EvaluationReportResponse = EvaluationResponse

export interface EvaluationReport {
  report_id: string
  file_name: string
  file_path: string
  created_at: string
  scenarios: string[]
}

export interface EvaluationReportsList {
  reports: EvaluationReport[]
}
