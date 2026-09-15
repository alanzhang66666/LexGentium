import type { Scenario } from "@/lib/conversation-types"
import type { CastDefinition } from "@/lib/court3d/cast"
import { roleToActor } from "@/lib/court3d/cast"
import { annotateSentence } from "@/lib/court3d/director/annotate"
import { sceneEvents } from "@/lib/court3d/director/blocking"
import { flushAll } from "@/lib/court3d/director/sentenceSplitter"
import type { PerformanceEvent } from "@/lib/court3d/protocol"

export interface ReplayTurn {
  role: string
  message: string
  delayMs?: number
}

export interface ReplayScript {
  id: string
  title: string
  scenario: Scenario
  stage?: "opening" | "investigation" | "debate" | "mediation" | "judgment" | "dialogue"
  subStage?: string
  turns: ReplayTurn[]
}

export async function loadReplay(id = "demo_ci"): Promise<ReplayScript> {
  const res = await fetch(`/court3d/replays/${id}.json`, { cache: "no-store" })
  if (!res.ok) throw new Error(`无法加载回放 ${id}`)
  return (await res.json()) as ReplayScript
}

export function* replayToEvents(script: ReplayScript, cast: CastDefinition): Generator<PerformanceEvent> {
  if (script.stage) {
    yield* sceneEvents(script.stage, script.subStage as never, script.scenario === "CI" ? "courtroom" : "lawyer_office")
  }
  for (const turn of script.turns) {
    const actor = roleToActor(turn.role, script.scenario, cast)
    if (!actor) continue
    yield { kind: "turn", actor, canAct: false }
    yield { kind: "camera", shot: "close_up", focus: actor }
    yield { kind: "status", thinking: actor }
    for (const sentence of flushAll(turn.message)) {
      const ann = annotateSentence(sentence, actor, undefined, cast.roles[actor]?.intensityCap)
      yield {
        kind: "speak",
        actor,
        sentence,
        emotion: ann.emotion,
        intensity: ann.intensity,
        speechKind: turn.role === "Clerk" ? "scripted" : "agent",
      }
      if (ann.gesture) yield { kind: "gesture", actor, clip: ann.gesture }
      if (cast.roles.interpreter?.relayFor?.includes(actor)) {
        yield { kind: "gesture", actor: "interpreter", clip: "relay_note", target: actor }
        yield {
          kind: "speak",
          actor: "interpreter",
          sentence: `【口译】${sentence.length > 36 ? `${sentence.slice(0, 36)}……` : sentence}`,
          emotion: "attentive",
          intensity: 0.22,
          speechKind: "relay",
        }
      }
    }
    yield { kind: "status", thinking: null }
  }
}

export function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
