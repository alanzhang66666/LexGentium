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

const includesAny = (value: string, candidates: string[]) => candidates.some((candidate) => value.includes(candidate))

/** Map backend/legacy role names to stable HearingEvent 1.1 actor IDs. */
export function actorForRole(role: string): string {
  const value = role.trim().toLowerCase().replace(/[_-]+/g, " ")

  if (includesAny(value, ["venue security", "security officer", "会务安保", "安保"])) return "judicial_police"
  if (includesAny(value, ["tribunal secretary", "hearing secretary", "仲裁庭秘书", "记录员", "速记员", "clerk", "书记员"])) return "clerk"
  if (includesAny(value, ["co arbitrator 2", "second co arbitrator", "第二仲裁员"])) return "people_juror"
  if (includesAny(value, ["co arbitrator", "共同仲裁员", "第一仲裁员"])) return "associate_judge"
  if (includesAny(value, ["presiding arbitrator", "arbitrator", "tribunal", "judge", "首席仲裁员", "仲裁员", "仲裁庭", "法官", "审判长"])) return "judge"
  if (includesAny(value, ["interpreter", "口译", "翻译"])) return "interpreter"
  if (includesAny(value, ["expert witness", "expert", "专家证人", "专家"])) return "technical_expert_witness"
  if (includesAny(value, ["witness", "事实证人", "证人"])) return "fact_witness"

  const respondent = includesAny(value, ["respondent", "defendant", "被申请人", "被申请方", "被告"])
  if (respondent) {
    if (includesAny(value, ["representative", "company", "party", "代表", "当事人"])) return "defendant_party"
    return "defendant_counsel"
  }

  const claimant = includesAny(value, ["claimant", "applicant", "petitioner", "client", "plaintiff", "申请人", "申请方", "原告"])
  if (claimant) {
    if (includesAny(value, ["co counsel", "second counsel", "共同代理", "第二代理"])) return "prosecutor"
    if (includesAny(value, ["representative", "company", "party", "代表", "当事人"])) return "china_company_rep"
    return "plaintiff_counsel"
  }

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
