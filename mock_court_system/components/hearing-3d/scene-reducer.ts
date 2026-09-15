import type { HearingEvent, SceneState } from "./contracts"

export function createInitialSceneState(): SceneState {
  return {
    session_id: null,
    run_id: null,
    current_seq: 0,
    latest_seq: 0,
    stage: null,
    active_issue: null,
    active_actor_id: null,
    actor_modes: {},
    subtitle: null,
    claims: {},
    materials: {},
    playback_policy: {},
    status: "idle",
    source_type: null,
    reasoning_meta: null,
    skipped_seqs: [],
    pending_gap: [],
    auto_play: false,
    warnings: [],
  }
}

function isBlocked(state: SceneState, event: HearingEvent): boolean {
  return state.playback_policy[event.event_id] === "blocked"
}

export function reduceScene(state: SceneState, event: HearingEvent): SceneState {
  if (event.seq <= state.current_seq || isBlocked(state, event)) return state
  const next: SceneState = {
    ...state,
    current_seq: event.seq,
    latest_seq: Math.max(state.latest_seq, event.seq),
    source_type: event.source_type,
  }
  const p = event.payload
  switch (event.type) {
    case "stage_changed":
      return { ...next, stage: { id: String(p.stage_id ?? ""), label: String(p.label ?? p.stage_id ?? "") } }
    case "issue_opened":
      return {
        ...next,
        active_issue: { id: event.issue_id ?? String(p.issue_id ?? ""), label: String(p.label ?? ""), description: String(p.description ?? "") },
      }
    case "utterance_committed": {
      const actorId = String(p.actor_id ?? "")
      const modes: Record<string, import("./contracts").ActorMode> = Object.fromEntries(Object.keys(next.actor_modes).map((id) => [id, id === actorId ? "talk" : "listen"]))
      const textPayload = typeof p.text === "object" && p.text !== null ? p.text as Record<string, unknown> : null
      return {
        ...next,
        reasoning_meta: (event.provenance?.reasoning_meta as SceneState["reasoning_meta"]) ?? next.reasoning_meta,
        active_actor_id: actorId || null,
        actor_modes: actorId ? { ...next.actor_modes, ...modes, [actorId]: "talk" } : next.actor_modes,
        subtitle: { zh: String(textPayload?.zh ?? p.text ?? ""), en: textPayload?.en ? String(textPayload.en) : undefined, actor_id: actorId },
        claims: {
          ...next.claims,
          ...(Array.isArray(p.claims) ? Object.fromEntries(p.claims.map((claim) => [String((claim as Record<string, unknown>).claim_id ?? ""), claim])) : {}),
        },
        materials: {
          ...next.materials,
          ...(Array.isArray(p.material_refs) ? Object.fromEntries(p.material_refs.map((material) => [String((material as Record<string, unknown>).material_id ?? ""), material])) : {}),
        },
      }
    }
    case "claim_status_changed":
      return { ...next, claims: { ...next.claims, [String(p.claim_id ?? "")]: p } }
    case "playback_policy_changed": {
      const policy = String(p.policy ?? "allow") as SceneState["playback_policy"][string]
      const targetIds = Array.isArray(p.target_event_ids) ? p.target_event_ids.map(String) : [event.event_id]
      const policies = { ...next.playback_policy }
      for (const id of targetIds) policies[id] = policy
      return { ...next, playback_policy: policies }
    }
    case "session_finished":
      return { ...next, status: "finished", reasoning_meta: (p.reasoning_meta as SceneState["reasoning_meta"]) ?? next.reasoning_meta }
    case "session_started":
      return {
        ...next,
        session_id: event.session_id,
        run_id: event.run_id,
        status: "playing",
        reasoning_meta: (event.provenance?.reasoning_meta as SceneState["reasoning_meta"]) ?? null,
        materials: Array.isArray(p.materials) ? Object.fromEntries(p.materials.map((material) => [String((material as Record<string, unknown>).material_id ?? ""), material])) : next.materials,
      }
    default:
      return { ...next, warnings: [...next.warnings, `Unknown event type: ${event.type}`] }
  }
}
