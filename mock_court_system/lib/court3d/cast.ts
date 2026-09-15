import type { Scenario } from "@/lib/conversation-types"
import type { Actor, SeatId, SpeechKind } from "@/lib/court3d/protocol"

export type SkinId = "original" | "swap"

export interface CastSkin {
  name: string
  gender: "m" | "f"
  model: string
  voiceLang: "zh-CN" | "en-US"
  voiceHint?: string
  checklist: string[]
}

export interface CastRole {
  actor: Actor
  seat: SeatId
  agent: string | null
  speech: SpeechKind
  relayLang?: "en" | "zh"
  relayFor?: Actor[]
  intensityCap: number
  category: "judicial" | "counsel" | "party" | "interpreter"
  props: string[]
  skins: Record<SkinId, CastSkin>
}

export interface CastDefinition {
  id: string
  title: string
  room: "courtroom" | "lawyer_office"
  seats: Record<SeatId, Actor>
  roles: Record<Actor, CastRole>
}

export function roleToActor(backendRole: string, scenario: Scenario, cast: CastDefinition): Actor | null {
  const role = backendRole.trim()
  if (role === "Judge" || role === "Final") return "judge"
  if (role === "Clerk") return "clerk"
  if (role === "Interpreter" || role === "Translator") return "interpreter"

  if (scenario === "CI") {
    if (role === "Plaintiff") return "plaintiff_counsel"
    if (role === "Defendant") return "defendant_counsel"
    return null
  }

  if (scenario === "CD") {
    if (role === "Client") return "plaintiff_party"
    if (role === "Lawyer") return "plaintiff_counsel"
    return null
  }

  if (scenario === "DD") {
    if (role === "Client") return "defendant_party"
    if (role === "Lawyer") return "defendant_counsel"
    return null
  }

  return cast.roles[role as Actor] ? (role as Actor) : null
}

export function listeningActors(speaker: Actor | null): Actor[] {
  if (!speaker) return []
  const pairs: Partial<Record<Actor, Actor[]>> = {
    judge: ["plaintiff_counsel", "defendant_counsel", "plaintiff_party", "defendant_party", "clerk"],
    clerk: ["judge"],
    plaintiff_counsel: ["plaintiff_party", "judge", "defendant_counsel"],
    defendant_counsel: ["defendant_party", "judge", "plaintiff_counsel", "interpreter"],
    plaintiff_party: ["plaintiff_counsel", "judge"],
    defendant_party: ["defendant_counsel", "interpreter", "judge"],
    interpreter: ["defendant_party", "judge"],
  }
  return pairs[speaker] ?? []
}

export async function loadCast(castId = "foreign_commercial"): Promise<CastDefinition> {
  const res = await fetch(`/court3d/casts/${castId}.json`, { cache: "no-store" })
  if (!res.ok) {
    throw new Error(`无法加载剧组 ${castId}`)
  }
  return (await res.json()) as CastDefinition
}
