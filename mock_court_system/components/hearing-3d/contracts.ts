export type HearingEventType =
  | "session_started"
  | "stage_changed"
  | "issue_opened"
  | "utterance_committed"
  | "claim_status_changed"
  | "playback_policy_changed"
  | "session_finished"

export interface HearingEvent {
  schema_version: "1.1"
  event_id: string
  run_id: string
  session_id: string
  seq: number
  type: HearingEventType
  occurred_at: string
  source_type: "backend_run" | "scripted_demo"
  provenance?: Record<string, unknown>
  issue_id?: string | null
  supersedes_event_id?: string | null
  payload: Record<string, unknown>
}

export type ActorMode = "idle" | "listen" | "talk" | "nod"
export type PlaybackStatus = "idle" | "playing" | "paused" | "disconnected" | "finished"
export type PlaybackPolicy = "allow" | "blocked" | "redacted"

export interface CastMember {
  actor_id: string
  label: string
  english: string
  name: string
  status: "formal" | "placeholder" | "reference"
  asset_kind: "procedural" | "vrm" | "glb" | "reference"
  reference?: string | null
  model?: string
  seat_id: string
  position: [number, number, number]
  look_at: [number, number, number]
  seat_to_root: [number, number, number]
  forward_axis: [number, number, number]
  scale: number
}

export interface SceneState {
  session_id: string | null
  run_id: string | null
  current_seq: number
  latest_seq: number
  stage: { id: string; label: string } | null
  active_issue: { id: string; label: string; description?: string } | null
  active_actor_id: string | null
  actor_modes: Record<string, ActorMode>
  subtitle: { zh: string; en?: string; actor_id?: string } | null
  claims: Record<string, Record<string, unknown>>
  materials: Record<string, Record<string, unknown>>
  playback_policy: Record<string, PlaybackPolicy>
  status: PlaybackStatus
  source_type: "backend_run" | "scripted_demo" | null
  reasoning_meta: {
    judgment_status?: "ok" | "degraded" | "failed"
    citation_report?: { checked?: number; verified?: number; unverified?: string[] } | null
    case_warnings?: string[]
  } | null
  skipped_seqs: number[]
  pending_gap: number[]
  auto_play: boolean
  warnings: string[]
}
