"use client"

import type { ActorMode, CastMember } from "./contracts"
import { PlaceholderCharacter } from "./PlaceholderCharacter"
import { ProceduralCharacter } from "./ProceduralCharacter"

export function CastLayer({ members, actorModes, activeActorId }: { members: CastMember[]; actorModes: Record<string, ActorMode>; activeActorId?: string | null }) {
  return (
    <>
      {members.map((member) => {
        const mode = actorModes[member.actor_id] ?? (member.actor_id === activeActorId ? "talk" : "idle")
        if (member.asset_kind === "procedural") {
          return (
            <ProceduralCharacter
              key={member.actor_id}
              member={member}
              mode={mode}
              isSpeaking={member.actor_id === activeActorId}
            />
          )
        }
        return <PlaceholderCharacter key={member.actor_id} member={member} mode={mode} />
      })}
    </>
  )
}
