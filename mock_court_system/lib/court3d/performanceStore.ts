import type { ConflictStrategy, CourtStage, CourtSubStage } from "@/lib/conversation-types"
import { listeningActors } from "@/lib/court3d/cast"
import type {
  Actor,
  CameraShot,
  Emotion,
  GameScoreHud,
  GestureClip,
  PerformanceEvent,
  RoomId,
} from "@/lib/court3d/protocol"

export interface ActorRuntime {
  speaking: boolean
  thinking: boolean
  mouth: number
  emotion: Emotion
  intensity: number
  gesture: GestureClip | null
  strategy: ConflictStrategy
  standing: boolean
}

export interface PerformanceState {
  room: RoomId
  stage: CourtStage | null
  subStage: CourtSubStage | null
  nextSpeaker: Actor | null
  canAct: boolean
  actions: string[]
  degraded: boolean
  evidenceLit: boolean
  subtitle: string
  subtitleActor: Actor | null
  subtitleKind: string
  cameraShot: CameraShot
  cameraFocus: Actor
  auditStatus: "supported" | "unknown" | "unsupported" | "excluded" | "frozen" | null
  hud: {
    score?: GameScoreHud
    equilibrium?: unknown
    convergence?: number
    plaintiffStrategy?: ConflictStrategy
    defendantStrategy?: ConflictStrategy
  }
  actors: Record<Actor, ActorRuntime>
}

const ACTOR_KEYS: Actor[] = [
  "judge",
  "clerk",
  "plaintiff_counsel",
  "plaintiff_party",
  "defendant_counsel",
  "defendant_party",
  "interpreter",
]

function blankActor(): ActorRuntime {
  return {
    speaking: false,
    thinking: false,
    mouth: 0,
    emotion: "neutral",
    intensity: 0.2,
    gesture: null,
    strategy: "collaborating",
    standing: false,
  }
}

export function createPerformanceState(): PerformanceState {
  return {
    room: "courtroom",
    stage: "opening",
    subStage: "opening_identity",
    nextSpeaker: "judge",
    canAct: true,
    actions: ["send_message"],
    degraded: false,
    evidenceLit: false,
    subtitle: "",
    subtitleActor: null,
    subtitleKind: "agent",
    cameraShot: "wide",
    cameraFocus: "judge",
    auditStatus: null,
    hud: {},
    actors: Object.fromEntries(ACTOR_KEYS.map((a) => [a, blankActor()])) as Record<Actor, ActorRuntime>,
  }
}

export function reducePerformance(state: PerformanceState, event: PerformanceEvent): PerformanceState {
  const next: PerformanceState = {
    ...state,
    hud: { ...state.hud },
    actors: { ...state.actors },
  }
  for (const key of ACTOR_KEYS) {
    next.actors[key] = { ...state.actors[key] }
  }

  switch (event.kind) {
    case "scene":
      next.room = event.room
      next.stage = event.stage
      next.subStage = event.subStage ?? next.subStage
      break
    case "turn":
      next.nextSpeaker = event.actor
      next.canAct = event.canAct
      next.actions = event.actions ?? next.actions
      break
    case "speak":
      next.subtitle = event.sentence
      next.subtitleActor = event.actor
      next.subtitleKind = event.speechKind ?? "agent"
      next.actors[event.actor].speaking = true
      next.actors[event.actor].thinking = false
      next.actors[event.actor].emotion = event.emotion
      next.actors[event.actor].intensity = event.intensity
      for (const listener of listeningActors(event.actor)) {
        if (!next.actors[listener].speaking) {
          next.actors[listener].emotion = "attentive"
          next.actors[listener].gesture = "nod"
        }
      }
      break
    case "gesture":
      next.actors[event.actor].gesture = event.clip
      if (event.clip === "stand") next.actors[event.actor].standing = true
      if (event.clip === "sit") next.actors[event.actor].standing = false
      break
    case "stance":
      next.actors[event.actor].strategy = event.strategy
      if (event.actor === "plaintiff_party") next.hud.plaintiffStrategy = event.strategy
      if (event.actor === "defendant_party") next.hud.defendantStrategy = event.strategy
      break
    case "camera":
      next.cameraShot = event.shot
      next.cameraFocus = event.focus
      break
    case "hud":
      next.hud = { ...next.hud, ...event.payload }
      break
    case "audit":
      next.auditStatus = event.status
      if (event.status === "unknown") {
        next.canAct = false
      }
      break
    case "status":
      if (event.degraded !== undefined) next.degraded = event.degraded
      if (event.evidenceLit !== undefined) next.evidenceLit = event.evidenceLit
      if (event.thinking !== undefined) {
        for (const key of ACTOR_KEYS) next.actors[key].thinking = false
        if (event.thinking) next.actors[event.thinking].thinking = true
      }
      if (event.standing) {
        for (const [actor, stand] of Object.entries(event.standing)) {
          next.actors[actor as Actor].standing = Boolean(stand)
        }
      }
      break
    default:
      break
  }
  return next
}

export function setActorMouth(state: PerformanceState, actor: Actor, mouth: number): PerformanceState {
  return {
    ...state,
    actors: {
      ...state.actors,
      [actor]: { ...state.actors[actor], mouth, speaking: mouth > 0.05 },
    },
  }
}
