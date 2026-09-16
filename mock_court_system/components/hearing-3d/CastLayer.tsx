"use client"

import type { ActorMode, CastMember } from "./contracts"
import { PlaceholderCharacter } from "./PlaceholderCharacter"
import { ProceduralCharacter } from "./ProceduralCharacter"
import { CHARACTER_ASSETS } from "./asset-adapter"

export function CastLayer({ members, actorModes, activeActorId, isSpeaking }: { members: CastMember[]; actorModes: Record<string, ActorMode>; activeActorId?: string | null; isSpeaking?: string | null }) {
  return (
    <>
      {members.map((member) => {
        const assetMode = CHARACTER_ASSETS[member.actor_id]?.mode
        const common = { member, mode: actorModes[member.actor_id] ?? ("idle" as ActorMode), isSpeaking: member.actor_id === activeActorId }
        return assetMode === "sprite" ? (
          <PlaceholderCharacter key={member.actor_id} {...common} />
        ) : (
          <ProceduralCharacter key={member.actor_id} {...common} />
        )
      })}
    </>
  )
}
