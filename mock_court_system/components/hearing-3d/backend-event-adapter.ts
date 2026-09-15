import type { HearingEvent } from "./contracts"

export interface ConversationPayload {
  session_id: string
  scenario: string
  case_id: string
  created_at?: string
  updated_at?: string
  dialog_history?: Array<{ turn?: number; role: string; message: string }>
  is_finished?: boolean
  reasoning_meta?: Record<string, unknown> | null
}

function actorForRole(role: string): string {
  const value = role.toLowerCase()
  if (value.includes("judge") || value.includes("法官") || value.includes("审判长")) return "judge"
  if (value.includes("client") || value.includes("plaintiff") || value.includes("原告")) return "plaintiff_counsel"
  if (value.includes("defendant") || value.includes("被告")) return "defendant_counsel"
  return "clerk"
}

function baseEvent(payload: ConversationPayload, seq: number, type: HearingEvent["type"], eventPayload: Record<string, unknown>, eventId: string): HearingEvent {
  return {
    schema_version: "1.1", event_id: eventId, run_id: `conversation-${payload.session_id}`,
    session_id: payload.session_id, seq, type, occurred_at: payload.updated_at ?? new Date().toISOString(),
    source_type: "backend_run", provenance: { scenario: payload.scenario, case_id: payload.case_id, reasoning_meta: payload.reasoning_meta ?? null },
    issue_id: null, payload: eventPayload,
  }
}

export function conversationToHearingEvents(payload: ConversationPayload): HearingEvent[] {
  const events: HearingEvent[] = []
  const runId = `conversation-${payload.session_id}`
  let seq = 1
  events.push(baseEvent(payload, seq++, "session_started", {
    procedure_type: "arbitration_hearing", cast_id: "lexgentium-runtime", manifest_version: "1.1", materials: [],
  }, `${runId}-started`))
  events.push(baseEvent(payload, seq++, "stage_changed", {
    stage_id: payload.scenario.toLowerCase(), label: `LexGentium ${payload.scenario} 会话`,
  }, `${runId}-stage`))
  for (const message of payload.dialog_history ?? []) {
    events.push(conversationMessageToEvent(payload, message.message, message.role, seq++, `${runId}-message-${message.turn ?? seq}`))
  }
  if (payload.is_finished) events.push(conversationFinishedToEvent(payload, seq))
  return events
}

export function conversationMessageToEvent(payload: ConversationPayload, text: string, role: string, seq: number, eventId: string, reasoningMeta?: Record<string, unknown> | null): HearingEvent {
  const actorId = actorForRole(role)
  const event = baseEvent(payload, seq, "utterance_committed", {
    actor_id: actorId, utterance_id: eventId, segment_index: 0, is_final_segment: true,
    text: { zh: text, en: null }, claim_ids: [], reply_to_event_ids: [], material_refs: [], claims: [], audio: null,
  }, eventId)
  if (reasoningMeta) event.provenance = { ...(event.provenance ?? {}), reasoning_meta: reasoningMeta }
  return event
}

export function conversationFinishedToEvent(payload: ConversationPayload, seq: number): HearingEvent {
  return baseEvent(payload, seq, "session_finished", {
    outcome: "conversation_finished", note: "会话已结束；不自动等同于法律裁决",
  }, `conversation-${payload.session_id}-finished-${seq}`)
}
