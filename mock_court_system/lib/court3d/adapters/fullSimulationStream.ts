import type { CastDefinition } from "@/lib/court3d/cast"
import { roleToActor } from "@/lib/court3d/cast"
import { sceneEvents } from "@/lib/court3d/director/blocking"
import type { PerformanceEvent } from "@/lib/court3d/protocol"
import { consumeSse } from "@/lib/court3d/parseSse"
import type { Scenario } from "@/lib/conversation-types"
import { clientAuthHeaders } from "@/lib/session/unlock"

const STAGE_TO_SCENARIO: Record<string, Scenario> = {
  CD: "CD",
  DD: "DD",
  CI: "CI",
}

export async function streamFullSimulation(
  caseInfo: Record<string, unknown>,
  emit: (e: PerformanceEvent) => void,
  cast: CastDefinition,
  signal?: AbortSignal,
  sessionId?: string,
) {
  if (!sessionId) {
    throw new Error("全案流必须绑定 session_id")
  }
  const res = await fetch("/api/case/full-simulation/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...clientAuthHeaders() },
    body: JSON.stringify({ case_info: caseInfo, mode: "full", session_id: sessionId }),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`全案流启动失败 HTTP ${res.status}`)

  await consumeSse(
    res,
    (evt) => {
      const type = String(evt.type || "")
      if (type === "stage_transition") {
        const stage = String(evt.stage || "CI")
        const scenario = STAGE_TO_SCENARIO[stage] ?? "CI"
        const role = typeof evt.role === "string" ? evt.role : "Judge"
        const actor = roleToActor(role, scenario, cast)
        const sub = typeof evt.sub_stage === "string" ? evt.sub_stage : null
        const courtStage = stage === "CI" ? "investigation" : "dialogue"
        for (const ev of sceneEvents(courtStage as never, sub as never, stage === "CI" ? "courtroom" : "lawyer_office")) {
          emit(ev)
        }
        if (actor) {
          emit({ kind: "turn", actor, canAct: false })
          emit({ kind: "status", thinking: actor })
          emit({ kind: "camera", shot: "close_up", focus: actor })
        }
      }
      if (type === "simulation_complete") {
        emit({ kind: "status", thinking: null })
        emit({ kind: "scene", stage: "finished", room: "courtroom" })
      }
      if (type === "error") {
        throw new Error(String(evt.message || "全案模拟失败"))
      }
    },
    signal,
  )
}
