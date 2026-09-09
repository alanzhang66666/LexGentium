import type { ConflictStrategy, CourtStage, CourtSubStage } from "@/lib/conversation-types"

export type Actor =
  | "judge"
  | "clerk"
  | "plaintiff_counsel"
  | "plaintiff_party"
  | "defendant_counsel"
  | "defendant_party"
  | "interpreter"

export type SeatId =
  | "bench_center"
  | "clerk"
  | "plaintiff_counsel"
  | "plaintiff_party"
  | "defendant_counsel"
  | "defendant_party"
  | "interpreter"

export type RoomId = "courtroom" | "lawyer_office" | "mediation"

export type Emotion =
  | "neutral"
  | "stern"
  | "attentive"
  | "questioning"
  | "assertive"
  | "conciliatory"
  | "tense"
  | "calm"

export type GestureClip =
  | "point"
  | "nod"
  | "shake_head"
  | "lean_forward"
  | "hand_over_doc"
  | "relay_note"
  | "type"
  | "stand"
  | "sit"
  | "flip_file"

export type CameraShot = "wide" | "over_shoulder" | "close_up" | "two_shot"

export type SpeechKind = "agent" | "scripted" | "relay" | "none"

export interface GameScoreHud {
  plaintiff_win_rate?: number
  defendant_win_rate?: number
  reasoning_quality?: number
  evidence_strength?: number
  degraded?: boolean
}

export type PerformanceEvent =
  | {
      kind: "scene"
      stage: CourtStage
      subStage?: CourtSubStage | null
      room: RoomId
    }
  | {
      kind: "turn"
      actor: Actor | null
      canAct: boolean
      actions?: string[]
    }
  | {
      kind: "speak"
      actor: Actor
      sentence: string
      emotion: Emotion
      intensity: number
      speechKind?: SpeechKind
      audioUrl?: string
    }
  | {
      kind: "gesture"
      actor: Actor
      clip: GestureClip
      target?: Actor
    }
  | {
      kind: "stance"
      actor: Actor
      strategy: ConflictStrategy
    }
  | {
      kind: "camera"
      shot: CameraShot
      focus: Actor
    }
  | {
      kind: "hud"
      payload: {
        score?: GameScoreHud
        equilibrium?: unknown
        convergence?: number
        plaintiffStrategy?: ConflictStrategy
        defendantStrategy?: ConflictStrategy
      }
    }
  | {
      kind: "status"
      degraded?: boolean
      thinking?: Actor | null
      evidenceLit?: boolean
      standing?: Partial<Record<Actor, boolean>>
    }
  | {
      kind: "audit"
      status: "supported" | "unknown" | "unsupported" | "excluded" | "frozen"
      nodeId?: string
      note?: string
    }

export const ACTORS: Actor[] = [
  "judge",
  "clerk",
  "plaintiff_counsel",
  "plaintiff_party",
  "defendant_counsel",
  "defendant_party",
  "interpreter",
]

export const ACTOR_LABELS: Record<Actor, string> = {
  judge: "首席仲裁员",
  clerk: "仲裁庭秘书",
  plaintiff_counsel: "申请人代理",
  plaintiff_party: "申请人企业代表",
  defendant_counsel: "被申请人代理",
  defendant_party: "被申请人企业代表",
  interpreter: "口译员",
}

export const SEAT_OF_ACTOR: Record<Actor, SeatId> = {
  judge: "bench_center",
  clerk: "clerk",
  plaintiff_counsel: "plaintiff_counsel",
  plaintiff_party: "plaintiff_party",
  defendant_counsel: "defendant_counsel",
  defendant_party: "defendant_party",
  interpreter: "interpreter",
}
