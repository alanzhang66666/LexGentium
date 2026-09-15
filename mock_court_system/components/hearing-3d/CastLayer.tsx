"use client"

import type { ActorMode, CastMember } from "./contracts"
import { PlaceholderCharacter } from "./PlaceholderCharacter"

export function CastLayer({ members, actorModes, activeActorId, isSpeaking }: { members: CastMember[]; actorModes: Record<string, ActorMode>; activeActorId?: string | null; isSpeaking?: string | null }) {
  return <>{members.map((member) => <PlaceholderCharacter key={member.actor_id} member={member} mode={actorModes[member.actor_id] ?? "idle"} isSpeaking={member.actor_id === activeActorId} />)}</>
}
