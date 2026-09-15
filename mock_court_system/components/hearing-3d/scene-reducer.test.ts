import { describe, expect, it } from "vitest"
import { createInitialSceneState, reduceScene } from "./scene-reducer"
import type { HearingEvent } from "./contracts"

const event = (type: HearingEvent["type"], seq: number, payload: Record<string, unknown>, extra = {}): HearingEvent => ({
  schema_version: "1.1", event_id: `e-${seq}`, run_id: "run", session_id: "session", seq,
  type, occurred_at: "2026-09-13T00:00:00Z", source_type: "scripted_demo", payload, ...extra,
})

describe("hearing scene reducer", () => {
  it("initializes session", () => {
    const next = reduceScene(createInitialSceneState(), event("session_started", 1, {}))
    expect(next.session_id).toBe("session")
    expect(next.status).toBe("playing")
  })
  it("updates actor and subtitle", () => {
    let state = reduceScene(createInitialSceneState(), event("session_started", 1, {}))
    state = reduceScene(state, event("utterance_committed", 2, { actor_id: "judge", text: { zh: "请发言" } }))
    expect(state.active_actor_id).toBe("judge")
    expect(state.actor_modes.judge).toBe("talk")
    expect(state.subtitle?.zh).toBe("请发言")
  })
  it("deduplicates old sequence and blocks policy events", () => {
    let state = reduceScene(createInitialSceneState(), event("session_started", 1, {}))
    state = reduceScene(state, event("playback_policy_changed", 2, { policy: "blocked", target_event_ids: ["e-3"] }))
    const blocked = reduceScene(state, event("utterance_committed", 3, { actor_id: "judge", text: { zh: "blocked" } }))
    expect(blocked.subtitle).toBeNull()
  })
  it("maps materials, claims and reasoning provenance", () => {
    let state = reduceScene(createInitialSceneState(), event("session_started", 1, { materials: [{ material_id: "m1", title: "材料一" }] }, {
      provenance: { reasoning_meta: { judgment_status: "degraded", citation_report: { checked: 2, verified: 1, unverified: ["假法条"] }, case_warnings: ["事实缺失"] } },
    }))
    state = reduceScene(state, event("utterance_committed", 2, {
      actor_id: "plaintiff_counsel", text: { zh: "引用材料" },
      claims: [{ claim_id: "c1", evidence_status: "unknown" }],
      material_refs: [{ material_id: "m2", version: "v1" }],
    }))
    expect(state.materials.m1).toBeTruthy()
    expect(state.materials.m2).toBeTruthy()
    expect(state.claims.c1).toBeTruthy()
    expect(state.reasoning_meta?.judgment_status).toBe("degraded")
  })
})
