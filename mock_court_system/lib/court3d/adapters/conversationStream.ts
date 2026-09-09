import type { ConversationInfo, ConversationMessageResponse, Scenario } from "@/lib/conversation-types"
import type { CastDefinition } from "@/lib/court3d/cast"
import { roleToActor } from "@/lib/court3d/cast"
import { annotateSentence } from "@/lib/court3d/director/annotate"
import { sceneEvents } from "@/lib/court3d/director/blocking"
import { flushAll, pushDelta } from "@/lib/court3d/director/sentenceSplitter"
import type { Actor, PerformanceEvent } from "@/lib/court3d/protocol"
import { consumeSse } from "@/lib/court3d/parseSse"
import { clientAuthHeaders } from "@/lib/session/unlock"

export interface ConversationStreamHandlers {
  emit: (event: PerformanceEvent) => void
  scenario: Scenario
  cast: CastDefinition
  userRole?: string
}

export async function streamConversationMessage(
  sessionId: string,
  message: string,
  handlers: ConversationStreamHandlers,
  signal?: AbortSignal,
): Promise<ConversationMessageResponse | null> {
  const { emit, scenario, cast } = handlers
  const userActor = roleToActor(handlers.userRole || defaultUserRole(scenario), scenario, cast)
  if (userActor) {
    const ann = annotateSentence(message, userActor)
    emit({
      kind: "speak",
      actor: userActor,
      sentence: message,
      emotion: ann.emotion,
      intensity: ann.intensity,
      speechKind: "agent",
    })
    if (ann.gesture) emit({ kind: "gesture", actor: userActor, clip: ann.gesture })
  }

  const res = await fetch(`/api/conversation/${sessionId}/message/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...clientAuthHeaders() },
    body: JSON.stringify({ message, role: handlers.userRole }),
    signal,
  })
  if (!res.ok || !res.body) {
    throw new Error(await res.text().catch(() => `HTTP ${res.status}`))
  }

  let buffer = ""
  let speaker: Actor | null = null
  let gotDelta = false
  let finalPayload: ConversationMessageResponse | null = null

  await consumeSse(
    res,
    (evt) => {
      if (evt.type === "heartbeat") return
      if (evt.type === "delta" && typeof evt.text === "string") {
        gotDelta = true
        if (!speaker) {
          speaker = guessStreamingActor(scenario)
          emit({ kind: "status", thinking: speaker })
          emit({ kind: "camera", shot: "close_up", focus: speaker })
        }
        const split = pushDelta(buffer, evt.text)
        buffer = split.remainder
        for (const sentence of split.sentences) {
          emitSpeak(emit, speaker, sentence, scenario, cast)
        }
        return
      }
      if (evt.type === "final") {
        if (evt.error) throw new Error(String(evt.error))
        finalPayload = evt as unknown as ConversationMessageResponse
        const role = finalPayload.response?.role || "Judge"
        speaker = roleToActor(role, scenario, cast) ?? speaker
        const leftover = flushAll(buffer)
        buffer = ""
        if (speaker) {
          if (leftover.length) {
            for (const sentence of leftover) emitSpeak(emit, speaker, sentence, scenario, cast)
          } else if (!gotDelta && finalPayload.response?.message) {
            for (const sentence of flushAll(finalPayload.response.message)) {
              emitSpeak(emit, speaker, sentence, scenario, cast)
            }
          }
        }
        emit({ kind: "status", thinking: null, degraded: Boolean(finalPayload.degraded) })
        const meta = finalPayload as ConversationMessageResponse & {
          current_stage?: ConversationInfo["current_stage"]
          current_sub_stage?: ConversationInfo["current_sub_stage"]
          next_speaker?: string | null
          available_actions?: string[]
        }
        if (meta.current_stage) {
          for (const ev of sceneEvents(meta.current_stage, meta.current_sub_stage, scenario === "CI" ? "courtroom" : "lawyer_office")) {
            emit(ev)
          }
        }
        if (meta.next_speaker) {
          const next = roleToActor(meta.next_speaker, scenario, cast)
          emit({ kind: "turn", actor: next, canAct: true, actions: meta.available_actions })
        }
      }
    },
    signal,
  )

  if (finalPayload && !(finalPayload as ConversationMessageResponse & { current_stage?: string }).current_stage) {
    await applyConversationMeta(sessionId, handlers)
  }
  return finalPayload
}

export async function applyConversationMeta(sessionId: string, handlers: ConversationStreamHandlers) {
  const res = await fetch(`/api/conversation/${sessionId}`, {
    cache: "no-store",
    headers: { ...clientAuthHeaders() },
  })
  if (!res.ok) return
  const data = (await res.json()) as ConversationInfo
  const room = data.scenario === "CI" ? "courtroom" : "lawyer_office"
  if (data.current_stage) {
    for (const ev of sceneEvents(data.current_stage, data.current_sub_stage, room)) {
      handlers.emit(ev)
    }
  }
  const next = data.next_speaker ? roleToActor(data.next_speaker, handlers.scenario, handlers.cast) : null
  handlers.emit({ kind: "turn", actor: next, canAct: !data.is_finished, actions: data.available_actions })
}

function emitSpeak(
  emit: (e: PerformanceEvent) => void,
  actor: Actor,
  sentence: string,
  _scenario: Scenario,
  cast: CastDefinition,
) {
  const cap = cast.roles[actor]?.intensityCap
  const ann = annotateSentence(sentence, actor, undefined, cap)
  emit({
    kind: "speak",
    actor,
    sentence,
    emotion: ann.emotion,
    intensity: ann.intensity,
    speechKind: "agent",
  })
  if (ann.gesture) emit({ kind: "gesture", actor, clip: ann.gesture })
  const role = cast.roles[actor]
  if (role && cast.roles.interpreter?.relayFor?.includes(actor)) {
    emit({ kind: "gesture", actor: "interpreter", clip: "relay_note", target: actor })
    emit({
      kind: "speak",
      actor: "interpreter",
      sentence: `【口译】${sentence.length > 36 ? `${sentence.slice(0, 36)}……` : sentence}`,
      emotion: "attentive",
      intensity: 0.25,
      speechKind: "relay",
    })
  }
}

function defaultUserRole(scenario: Scenario) {
  return scenario === "CI" ? "Plaintiff" : "Client"
}

function guessStreamingActor(scenario: Scenario): Actor {
  if (scenario === "CI") return "judge"
  if (scenario === "CD") return "plaintiff_counsel"
  return "defendant_counsel"
}
