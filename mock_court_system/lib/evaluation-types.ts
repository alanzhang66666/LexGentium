export interface EvaluationRequest {
  scenarios: string[] // ["CD", "DD", "CI"]
  prediction_files?: Record<string, string>
  use_default_predictions?: boolean
  session_id?: string
}

export interface EvaluationResponse {
  report_id: string
  status: "running" | "completed" | "failed"
  message: string
  results?: Record<string, unknown>
  report_path?: string
}

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

