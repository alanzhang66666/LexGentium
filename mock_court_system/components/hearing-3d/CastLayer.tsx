"use client"

import type { ActorMode, CastMember } from "./contracts"
import { PlaceholderCharacter } from "./PlaceholderCharacter"

export function CastLayer({ members, actorModes, activeActorId }: { members: CastMember[]; actorModes: Record<string, ActorMode>; activeActorId?: string | null }) {
  return <>{members.map((member) => <PlaceholderCharacter key={member.actor_id} member={member} mode={actorModes[member.actor_id] ?? (member.actor_id === activeActorId ? "talk" : "idle")} />)}</>
}
