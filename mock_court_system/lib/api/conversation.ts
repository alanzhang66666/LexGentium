import { apiFetch } from "@/lib/api/http"
import type {
  AutoAdvanceResponse,
  ConversationInfo,
  ConversationListResponse,
  ConversationStartRequest,
  ConversationStartResponse,
  Scenario,
  SessionLinks,
} from "@/lib/conversation-types"

export function startConversation(body: ConversationStartRequest) {
  return apiFetch<ConversationStartResponse>("/api/conversation/start", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function listConversations(limit = 20, offset = 0) {
  return apiFetch<ConversationListResponse>(`/api/conversation/list?limit=${limit}&offset=${offset}`)
}

export function getConversation(sessionId: string) {
  return apiFetch<ConversationInfo>(`/api/conversation/${encodeURIComponent(sessionId)}`)
}

export function deleteConversation(sessionId: string) {
  return apiFetch<{ message: string }>(`/api/conversation/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  })
}

export function autoAdvance(sessionId: string, maxRounds = 5) {
  return apiFetch<AutoAdvanceResponse>(`/api/conversation/${encodeURIComponent(sessionId)}/auto-advance`, {
    method: "POST",
    body: JSON.stringify({ max_rounds: maxRounds }),
  })
}

export function getCompliance(sessionId: string) {
  return apiFetch<{ session_id: string; scenario: string; compliance: unknown }>(
    `/api/conversation/${encodeURIComponent(sessionId)}/compliance`,
  )
}

export function deriveConversation(body: {
  session_id: string
  visible_materials?: Record<string, unknown>
  experiment_conditions?: Record<string, unknown>
  model_config_snapshot?: Record<string, unknown>
}) {
  return apiFetch<ConversationStartResponse>("/api/conversation/derive", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function getSessionClaims(sessionId: string) {
  return apiFetch<{
    session_id: string
    research: unknown
    claim_chain: unknown[]
    task_protocol: unknown
    stop_reason: string | null
  }>(`/api/conversation/${encodeURIComponent(sessionId)}/claims`)
}

export function postSessionClaim(
  sessionId: string,
  body: {
    role: string
    action: string
    fact?: string
    norm?: string
    reasoning?: string
    claim_id?: string
    target_claim_id?: string
    source_ids?: string[]
  },
) {
  return apiFetch<{
    event: unknown
    claim_chain: unknown[]
    research: unknown
  }>(`/api/conversation/${encodeURIComponent(sessionId)}/claims`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function importConversation(body: {
  scenario: Scenario
  case_id: string
  dialog_history: unknown[]
  input_json?: Record<string, unknown>
}) {
  return apiFetch<ConversationStartResponse>("/api/conversation/import", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function emptyLinks(): SessionLinks {
  return {}
}

export async function streamSessionMessage(
  sessionId: string,
  body: { message: string; role?: string; operation_id?: string },
  onEvent: (evt: Record<string, unknown>) => void,
  signal?: AbortSignal,
) {
  const { streamJson } = await import("@/lib/api/sse")
  await streamJson(
    `/api/conversation/${encodeURIComponent(sessionId)}/message/stream`,
    body,
    onEvent,
    signal,
  )
}
