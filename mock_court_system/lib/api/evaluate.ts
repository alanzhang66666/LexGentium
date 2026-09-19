import { apiFetch } from "@/lib/api/http"
import type {
  EvaluationReportResponse,
  EvaluationReportsList,
  EvaluationRequest,
  EvaluationResponse,
} from "@/lib/evaluation-types"

export function startEvaluation(body: EvaluationRequest) {
  return apiFetch<EvaluationResponse>("/api/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function getEvaluationStatus(reportId: string) {
  return apiFetch<EvaluationResponse>(`/api/evaluate?report_id=${encodeURIComponent(reportId)}`)
}

export function listEvaluationReports() {
  return apiFetch<EvaluationReportsList>("/api/evaluate")
}

export function getEvaluationReport(reportId: string) {
  return apiFetch<EvaluationReportResponse>(
    `/api/evaluate/reports/${encodeURIComponent(reportId)}`,
  )
}
