"use client"

/**
 * 程序化 3D 人物：坐姿人偶（躯干/头/手臂/腿部几何体），带呼吸、点头、发言手势动画。
 * 这是真正的 3D 几何体（有体积、随视角变化），替代照片 billboard；
 * 正式 VRM/GLB 模型到位后由 asset-adapter 的 mode 切换，本组件保留为 procedural 模式。
 */

import { useRef } from "react"
import type { Group, Mesh } from "three"
import { useFrame } from "@react-three/fiber"
import { Html } from "@react-three/drei"
import type { ActorMode, CastMember } from "./contracts"

const SUIT: Record<string, string> = {
  judge: "#243448",
  clerk: "#526174",
  plaintiff_counsel: "#4a6274",
  plaintiff_party: "#3d5166",
  defendant_counsel: "#4a4a4a",
  defendant_party: "#5a4a3a",
  interpreter: "#5a5a6a",
}

const SKIN = "#d9b38c"
const HAIR = "#1f2937"
const SHOE = "#23272e"

/** 席位朝向（弧度）：模型正面为 -Z，与 ProceduralRoom 的 Chair 一致 */
const FACING: Record<string, number> = {
  judge: 0,
  clerk: Math.PI,
  plaintiff_counsel: -Math.PI / 2,
  plaintiff_party: -Math.PI / 2,
  defendant_counsel: Math.PI / 2,
  defendant_party: Math.PI / 2,
  interpreter: Math.PI / 2,
}

export function ProceduralCharacter({ member, mode, isSpeaking }: { member: CastMember; mode: ActorMode; isSpeaking?: boolean }) {
  const [x, y, z] = member.position
  const bodyRef = useRef<Group>(null)
  const headRef = useRef<Group>(null)
  const armRef = useRef<Group>(null)

  useFrame((frameState) => {
    const t = frameState.clock.getElapsedTime()
    if (headRef.current) {
      if (mode === "nod") {
        headRef.current.rotation.x = Math.sin(t * 6) * 0.18
      } else if (mode === "talk") {
        headRef.current.rotation.x = Math.sin(t * 3.2) * 0.08
        headRef.current.rotation.y = Math.sin(t * 1.1) * 0.12
      } else {
        headRef.current.rotation.x = Math.sin(t * 0.8) * 0.02
        headRef.current.rotation.y = 0
      }
    }
    if (bodyRef.current) {
      // 呼吸起伏
      bodyRef.current.scale.y = 1 + Math.sin(t * 1.4) * 0.008
      bodyRef.current.rotation.x = mode === "talk" ? Math.sin(t * 1.6) * 0.02 : 0
    }
    if (armRef.current) {
      // 发言时右手抬起比划，其余时间垂放
      const raise = mode === "talk" ? -0.9 + Math.sin(t * 4) * 0.15 : 0
      armRef.current.rotation.x = raise
    }
  })

  const suit = SUIT[member.actor_id] ?? "#475569"
  const facing = FACING[member.actor_id] ?? 0

  return (
    <group position={[x, y, z]} rotation={[0, facing, 0]} scale={member.scale}>
      {/* 台座：不透明，避免透明排序闪烁 */}
      <mesh position={[0, -0.44, 0]}>
        <cylinderGeometry args={[0.3, 0.35, 0.02, 24]} />
        <meshStandardMaterial color="#3a4656" />
      </mesh>

      <group ref={bodyRef}>
        {/* 大腿（坐姿向前，臀部在群组原点≈椅面高度） */}
        <mesh position={[0, 0.0, -0.16]}>
          <boxGeometry args={[0.32, 0.1, 0.36]} />
          <meshStandardMaterial color={suit} />
        </mesh>
        {/* 小腿 ×2（垂下） */}
        <mesh position={[-0.09, -0.21, -0.3]}>
          <boxGeometry args={[0.1, 0.42, 0.1]} />
          <meshStandardMaterial color={suit} />
        </mesh>
        <mesh position={[0.09, -0.21, -0.3]}>
          <boxGeometry args={[0.1, 0.42, 0.1]} />
          <meshStandardMaterial color={suit} />
        </mesh>
        {/* 鞋 ×2 */}
        <mesh position={[-0.09, -0.42, -0.33]}>
          <boxGeometry args={[0.1, 0.05, 0.2]} />
          <meshStandardMaterial color={SHOE} />
        </mesh>
        <mesh position={[0.09, -0.42, -0.33]}>
          <boxGeometry args={[0.1, 0.05, 0.2]} />
          <meshStandardMaterial color={SHOE} />
        </mesh>

        {/* 躯干 */}
        <mesh position={[0, 0.36, 0]}>
          <capsuleGeometry args={[0.165, 0.32, 6, 14]} />
          <meshStandardMaterial color={suit} />
        </mesh>
        {/* 肩线 */}
        <mesh position={[0, 0.5, 0]}>
          <boxGeometry args={[0.4, 0.08, 0.17]} />
          <meshStandardMaterial color={suit} />
        </mesh>
        {/* 左臂（搭在扶手/桌沿） */}
        <mesh position={[-0.24, 0.3, -0.06]} rotation={[0.35, 0, 0.06]}>
          <capsuleGeometry args={[0.05, 0.3, 4, 10]} />
          <meshStandardMaterial color={suit} />
        </mesh>
        {/* 右臂（发言时抬起做手势） */}
        <group ref={armRef} position={[0.24, 0.48, -0.04]}>
          <mesh position={[0, -0.17, 0]}>
            <capsuleGeometry args={[0.05, 0.3, 4, 10]} />
            <meshStandardMaterial color={suit} />
          </mesh>
          <mesh position={[0, -0.36, 0]}>
            <sphereGeometry args={[0.055, 10, 8]} />
            <meshStandardMaterial color={SKIN} />
          </mesh>
        </group>

        {/* 颈 + 头 */}
        <mesh position={[0, 0.62, 0]}>
          <cylinderGeometry args={[0.045, 0.05, 0.08, 10]} />
          <meshStandardMaterial color={SKIN} />
        </mesh>
        <group ref={headRef} position={[0, 0.78, 0]}>
          <mesh>
            <sphereGeometry args={[0.115, 20, 16]} />
            <meshStandardMaterial color={SKIN} />
          </mesh>
          {/* 头发：上半球罩，脑后略厚 */}
          <mesh position={[0, 0.025, 0.015]} scale={[1.05, 0.95, 1.06]}>
            <sphereGeometry args={[0.118, 20, 12, 0, Math.PI * 2, 0, Math.PI / 1.9]} />
            <meshStandardMaterial color={HAIR} />
          </mesh>
        </group>
      </group>

      {/* 名牌 */}
      <Html position={[0, 1.18, 0]} center distanceFactor={8}>
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
