import type { ConflictStrategy } from "@/lib/conversation-types"
import type { PerformanceEvent } from "@/lib/court3d/protocol"
import { consumeSse } from "@/lib/court3d/parseSse"
import { clientAuthHeaders } from "@/lib/session/unlock"

export async function streamGameRound(
  gameId: string,
  emit: (e: PerformanceEvent) => void,
  signal?: AbortSignal,
) {
  const res = await fetch(`/api/game/${encodeURIComponent(gameId)}/stream-round`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...clientAuthHeaders() },
    body: JSON.stringify({}),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`博弈流启动失败 HTTP ${res.status}`)

  await consumeSse(
    res,
    (evt) => {
      const type = String(evt.type || "")
      if (type === "round_start") {
        const p = evt.plaintiff_strategy as ConflictStrategy | undefined
        const d = evt.defendant_strategy as ConflictStrategy | undefined
        if (p) emit({ kind: "stance", actor: "plaintiff_party", strategy: p })
        if (d) emit({ kind: "stance", actor: "defendant_party", strategy: d })
        emit({ kind: "hud", payload: { plaintiffStrategy: p, defendantStrategy: d } })
      }
      if (type === "strategy_switch") {
        const party = evt.party === "defendant" ? "defendant_party" : "plaintiff_party"
        const next = evt.new as ConflictStrategy
        if (next) emit({ kind: "stance", actor: party, strategy: next })
      }
      if (type === "score_update") {
        const score = (evt.score || {}) as Record<string, number> & { degraded?: boolean }
        emit({ kind: "hud", payload: { score } })
        if (score.degraded || evt.degraded) {
          emit({ kind: "status", thinking: null, degraded: true })
        }
      }
      if (type === "round_complete" && evt.degraded) {
        emit({ kind: "status", thinking: null, degraded: true })
      }
      if (type === "equilibrium_update") {
        emit({ kind: "hud", payload: { equilibrium: evt.equilibrium } })
      }
      if (type === "round_complete") {
        emit({
          kind: "hud",
          payload: {
            convergence: typeof evt.convergence_rate === "number" ? evt.convergence_rate : undefined,
          },
        })
        emit({ kind: "status", thinking: null })
      }
      if (type === "error") throw new Error(String(evt.message || "博弈流失败"))
    },
    signal,
  )
}
