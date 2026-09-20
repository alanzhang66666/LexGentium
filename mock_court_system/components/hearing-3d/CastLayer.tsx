"use client"

import { Component, Suspense, useEffect, useState, type ReactNode } from "react"
import type { ActorMode, CastMember } from "./contracts"
import { PlaceholderCharacter } from "./PlaceholderCharacter"
import { ProceduralCharacter } from "./ProceduralCharacter"
import { ObjCharacterModel } from "./ObjCharacterModel"
import { CHARACTER_ASSETS } from "./asset-adapter"

class CharacterModelErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode; actorId: string },
  { failed: boolean }
> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: Error) {
    console.error(`[hearing-3d] 角色 ${this.props.actorId} 的 OBJ/PBR 资产加载失败，已降级为程序化人物。`, error)
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}

export function CastLayer({ members, actorModes, activeActorId, isSpeaking }: { members: CastMember[]; actorModes: Record<string, ActorMode>; activeActorId?: string | null; isSpeaking?: string | null }) {
  // 供应商 OBJ 体量较大，按席位逐个放入渲染树，避免首屏并发解析十三个高模导致 Canvas 空白。
  const [modelSlots, setModelSlots] = useState(1)
  useEffect(() => {
    setModelSlots(1)
    const timer = window.setInterval(() => {
      setModelSlots((current) => Math.min(members.length, current + 1))
    }, 700)
    return () => window.clearInterval(timer)
  }, [members.length])

  return (
    <>
      {members.map((member, memberIndex) => {
        const asset = CHARACTER_ASSETS[member.actor_id]
        const assetMode = asset?.mode
        const common = { member, mode: actorModes[member.actor_id] ?? ("idle" as ActorMode), isSpeaking: member.actor_id === activeActorId }
        return assetMode === "obj" ? (
          <CharacterModelErrorBoundary
            key={member.actor_id}
            actorId={member.actor_id}
            fallback={<ProceduralCharacter {...common} />}
          >
            <Suspense fallback={<ProceduralCharacter {...common} />}>
              {memberIndex < modelSlots ? <ObjCharacterModel {...common} asset={asset} /> : <ProceduralCharacter {...common} />}
            </Suspense>
          </CharacterModelErrorBoundary>
        ) : assetMode === "sprite" ? (
          <PlaceholderCharacter key={member.actor_id} {...common} />
        ) : (
          <ProceduralCharacter key={member.actor_id} {...common} />
        )
      })}
    </>
  )
}
