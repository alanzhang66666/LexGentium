"use client"

import { Html } from "@react-three/drei"
import type { ActorMode, CastMember } from "./contracts"

export function PlaceholderCharacter({ member, mode }: { member: CastMember; mode: ActorMode }) {
  const [x, y, z] = member.position
  return (
    <group position={[x, y, z]} scale={member.scale}>
      <mesh position={[0, 0.55, 0]}>
        <capsuleGeometry args={[0.22, 0.7, 6, 12]} />
        <meshStandardMaterial color={member.actor_id.includes("defendant") ? "#334155" : "#475569"} />
      </mesh>
      <mesh position={[0, 1.15, 0]}>
        <sphereGeometry args={[0.18, 12, 8]} />
        <meshStandardMaterial color="#d5a47a" />
      </mesh>
      <Html position={[0, 1.55, 0]} center distanceFactor={8}>
        <div className="rounded bg-slate-950/85 px-2 py-1 text-[10px] text-white whitespace-nowrap">
          {member.label} · {mode === "talk" ? "发言" : "占位"}
        </div>
      </Html>
    </group>
  )
}
