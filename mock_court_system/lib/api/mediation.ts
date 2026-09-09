import { apiFetch } from "@/lib/api/http"

export type MediationCreateBody = {
  case_info: Record<string, unknown>
  party_names?: string[]
  max_bargaining_rounds?: number
  nbs_reference_text?: string
  auto_compute_nbs?: boolean
}

export function createMediation(body: MediationCreateBody) {
  return apiFetch<Record<string, unknown>>("/api/mediation/create", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function runMediationPreliminary(sessionId: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/mediation/${encodeURIComponent(sessionId)}/preliminary`,
    { method: "POST", body: JSON.stringify({}) },
  )
}

export function runMediationStatement(
  sessionId: string,
  body: { party_name: string; statement?: string },
) {
  return apiFetch<Record<string, unknown>>(
    `/api/mediation/${encodeURIComponent(sessionId)}/statement`,
    { method: "POST", body: JSON.stringify(body) },
  )
}

export function runMediationOptions(sessionId: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/mediation/${encodeURIComponent(sessionId)}/options`,
    { method: "POST", body: JSON.stringify({}) },
  )
}

export function runMediationBargain(
  sessionId: string,
  body?: { party_responses?: Record<string, string> },
) {
  return apiFetch<Record<string, unknown>>(
    `/api/mediation/${encodeURIComponent(sessionId)}/bargain`,
    { method: "POST", body: JSON.stringify(body || {}) },
  )
}

export function runMediationClose(sessionId: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/mediation/${encodeURIComponent(sessionId)}/close`,
    { method: "POST", body: JSON.stringify({}) },
  )
}

export function getMediationStatus(sessionId: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/mediation/${encodeURIComponent(sessionId)}/status`,
  )
}

export function runFullMediation(sessionId: string, body: MediationCreateBody) {
  return apiFetch<Record<string, unknown>>(
    `/api/mediation/${encodeURIComponent(sessionId)}/full`,
    { method: "POST", body: JSON.stringify(body) },
  )
}
