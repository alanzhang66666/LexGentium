import { apiFetch } from "@/lib/api/http"

export function startFullSimulation(body: {
  case_info: Record<string, unknown>
  mode?: string
  tournament_rounds?: number
  session_id?: string
}) {
  return apiFetch<{ task_id: string; status: string; session_id?: string }>("/api/case/full-simulation", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function getFullSimulation(taskId: string) {
  return apiFetch<{
    task_id: string
    status: string
    message: string
    current_stage?: string
    result?: unknown
  }>(`/api/case/full-simulation/${encodeURIComponent(taskId)}`)
}

export function listCases(limit = 40, split = "test") {
  return apiFetch<{ cases: Array<Record<string, string>>; total: number; split: string }>(
    `/api/reference/cases?limit=${limit}&split=${encodeURIComponent(split)}`,
  )
}

export function runSimulate(body: {
  scenario: string
  case_id: string
  dialog_history: unknown[]
  input_json?: Record<string, unknown>
}) {
  return apiFetch<unknown>("/api/simulate", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function runProgressiveRag(body: {
  stage: string
  context: Record<string, string>
  top_k?: number
}) {
  return apiFetch<Record<string, unknown>>("/api/case/progressive-rag", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function runDualModeReasoning(body: {
  case_info: string
  claims: string
  use_llm_eval?: boolean
}) {
  return apiFetch<Record<string, unknown>>("/api/case/dual-mode-reasoning", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function runMultiJudge(body: {
  case_facts: string
  claims: string
  trial_summary?: string
  num_judges?: number
  aggregation?: string
}) {
  return apiFetch<Record<string, unknown>>("/api/case/multi-judge", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function getDisputeCauses() {
  return apiFetch<{ taxonomy: unknown }>("/api/reference/dispute-causes")
}

export function getBigFiveTraits() {
  return apiFetch<{ traits: unknown; example?: unknown }>("/api/reference/big-five")
}

export function getProgressiveBenchmark() {
  return apiFetch<{ levels: unknown }>("/api/reference/progressive-benchmark")
}
