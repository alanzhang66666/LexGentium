"use client"

import { useEffect, useRef, useState } from "react"
import type { Group, Mesh } from "three"
import { useFrame } from "@react-three/fiber"
import { TextureLoader, type Texture } from "three"
import { Html } from "@react-three/drei"
import type { ActorMode, CastMember } from "./contracts"
import { CHARACTER_ASSETS } from "./asset-adapter"

const COLORS: Record<string, string> = {
  judge: "#243448",
  clerk: "#526174",
  plaintiff_counsel: "#4a6274",
  plaintiff_party: "#3d5166",
  defendant_counsel: "#4a4a4a",
  defendant_party: "#5a4a3a",
  interpreter: "#5a5a6a",
}

export function PlaceholderCharacter({ member, mode, isSpeaking }: { member: CastMember; mode: ActorMode; isSpeaking?: boolean }) {
  const [x, y, z] = member.position
  const asset = CHARACTER_ASSETS[member.actor_id]
  const groupRef = useRef<Group>(null)

  // 说话时微微前倾 + 轻微上下浮动
  const meshRef = useRef<Mesh>(null)
  useFrame((frameState) => {
    if (!meshRef.current) return
    const t = frameState.clock.getElapsedTime()
    if (mode === "talk") {
      meshRef.current.position.y = Math.sin(t * 3) * 0.01
      meshRef.current.rotation.z = Math.sin(t * 2) * 0.008
    } else if (mode === "nod") {
      meshRef.current.rotation.x = Math.sin(t * 6) * 0.05
    } else {
      meshRef.current.position.y = Math.sin(t * 1.2) * 0.005
      meshRef.current.rotation.set(0, 0, 0)
    }
  })

  const spriteUrl = asset?.sprite_url
  // 加载成功才用 billboard；失败/缺失降级为胶囊体，避免渲染空纹理导致的隐形角色
  const [spriteTexture, setSpriteTexture] = useState<Texture | null>(null)
  const [textureFailed, setTextureFailed] = useState(false)
  useEffect(() => {
    let cancelled = false
    setSpriteTexture(null)
    setTextureFailed(false)
    if (!spriteUrl) {
      setTextureFailed(true)
      return
    }
    new TextureLoader().load(
      spriteUrl,
      (t) => { if (!cancelled) setSpriteTexture(t) },
      undefined,
      () => { if (!cancelled) setTextureFailed(true) },
    )
    return () => { cancelled = true }
  }, [spriteUrl])
  const showBillboard = spriteTexture !== null && !textureFailed

  const color = COLORS[member.actor_id] ?? "#475569"
  const height = 1.65
  const width = height * 0.35

  return (
    <group position={[x, y, z]} scale={member.scale}>
      {/* 台座：不透明，避免透明排序闪烁 */}
      <mesh position={[0, 0.01, 0]}>
        <cylinderGeometry args={[0.3, 0.35, 0.02, 24]} />
        <meshStandardMaterial color="#3a4656" />
      </mesh>

      {showBillboard ? (
        /* Billboard sprite：高质量参考图面板（始终面向相机）
         * 照片是不透明矩形：transparent=false 走不透明通道，深度写入正常，消除排序闪烁；
         * key 绑定纹理 uuid：R3F v9 对已创建材质设置 map 不会触发 shader 重编译，
         * 必须强制重挂材质，否则纹理显示为黑色。 */
        <mesh ref={meshRef} position={[0, height / 2, 0]}>
          <planeGeometry args={[width, height]} />
          <meshStandardMaterial
            key={spriteTexture?.uuid ?? "no-texture"}
            map={spriteTexture}
            alphaTest={0.1}
            side={2 /* DoubleSide */}
            toneMapped={false}
          />
        </mesh>
      ) : (
        /* 降级：简单胶囊体（纹理加载中/失败，或未配置 sprite） */
        <mesh ref={meshRef} position={[0, height / 2, 0]}>
          <capsuleGeometry args={[0.22, height * 0.6, 6, 12]} />
          <meshStandardMaterial color={color} transparent opacity={0.9} />
        </mesh>
      )}

      {/* 名牌 */}
      <Html position={[0, height + 0.25, 0]} center distanceFactor={8}>
        <div className="whitespace-nowrap rounded-md border border-white/20 bg-slate-950/90 px-3 py-1.5 text-center backdrop-blur">
          <div className="text-xs font-bold text-white">{member.label}</div>
          <div className="text-[9px] text-cyan-300">{member.name}</div>
          {mode === "talk" && (
            <div className="mt-0.5 flex items-center justify-center gap-0.5">
              <span className="inline-block h-1 w-1 animate-pulse rounded-full bg-cyan-400" />
              <span className="inline-block h-1 w-1 animate-pulse rounded-full bg-cyan-400" style={{ animationDelay: "0.2s" }} />
              <span className="inline-block h-1 w-1 animate-pulse rounded-full bg-cyan-400" style={{ animationDelay: "0.4s" }} />
            </div>
          )}
          {isSpeaking && <div className="mt-0.5 text-[8px] text-cyan-200">▶ 发言中</div>}
        </div>
      </Html>
    </group>
  )
}
