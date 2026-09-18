"use client"

/**
 * 程序化 3D 人物：坐姿人偶（躯干/头/手臂/腿部几何体），带呼吸、点头、发言手势动画。
 * 这是真正的 3D 几何体（有体积、随视角变化），替代照片 billboard；
 * 正式 VRM/GLB 模型到位后由 asset-adapter 的 mode 切换，本组件保留为 procedural 模式。
 */

import { useMemo, useRef } from "react"
import type { Group, Mesh } from "three"
import { useFrame, useLoader } from "@react-three/fiber"
import { Html } from "@react-three/drei"
import { CanvasTexture, DoubleSide, SRGBColorSpace, TextureLoader } from "three"
import type { ActorMode, CastMember } from "./contracts"
import { CHARACTER_ASSETS } from "./asset-adapter"

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

/**
 * 把交付包中的正面人物参考图裁成椭圆人脸，并作为真实 3D 头部的前侧贴片。
 * 身体和头部仍然是几何体，头部的点头/转动动画也会继续生效。
 */
function FaceOverlay({ sourceUrl }: { sourceUrl: string }) {
  const sourceTexture = useLoader(TextureLoader, sourceUrl)
  const faceTexture = useMemo(() => {
    const image = sourceTexture.image as HTMLImageElement
    const canvas = document.createElement("canvas")
    canvas.width = 256
    canvas.height = 320
    const context = canvas.getContext("2d")
    if (!context) return sourceTexture

    const sourceWidth = image.naturalWidth || image.width
    const sourceHeight = image.naturalHeight || image.height
    const cropWidth = sourceWidth * 0.42
    const cropHeight = sourceHeight * 0.28
    const cropX = sourceWidth * 0.29
    const cropY = sourceHeight * 0.04

    context.clearRect(0, 0, canvas.width, canvas.height)
    context.save()
    context.beginPath()
    context.ellipse(canvas.width / 2, canvas.height / 2, canvas.width * 0.46, canvas.height * 0.5, 0, 0, Math.PI * 2)
    context.clip()
    context.drawImage(image, cropX, cropY, cropWidth, cropHeight, 0, 0, canvas.width, canvas.height)
    context.restore()

    // 去掉参考图的浅灰背景，避免人脸贴上头部后呈现明显的“椭圆贴纸”边界。
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height)
    const { data } = pixels
    const sample = (x: number, y: number) => {
      const index = (y * canvas.width + x) * 4
      return [data[index], data[index + 1], data[index + 2]]
    }
    const samples = [sample(8, 8), sample(canvas.width - 9, 8), sample(8, canvas.height - 9), sample(canvas.width - 9, canvas.height - 9)]
    const background = samples[0].map((_, channel) => samples.reduce((sum, value) => sum + value[channel], 0) / samples.length)
    const isBackground = (pixelIndex: number) => {
      const distance = Math.hypot(data[pixelIndex] - background[0], data[pixelIndex + 1] - background[1], data[pixelIndex + 2] - background[2])
      return distance < 52
    }
    const visited = new Uint8Array(canvas.width * canvas.height)
    const queue = new Int32Array(canvas.width * canvas.height)
    let head = 0
    let tail = 0
    const enqueue = (x: number, y: number) => {
      const position = y * canvas.width + x
      if (visited[position]) return
      const pixelIndex = position * 4
      if (!isBackground(pixelIndex)) return
      visited[position] = 1
      queue[tail++] = position
    }
    for (let x = 0; x < canvas.width; x += 1) {
      enqueue(x, 0)
      enqueue(x, canvas.height - 1)
    }
    for (let y = 1; y < canvas.height - 1; y += 1) {
      enqueue(0, y)
      enqueue(canvas.width - 1, y)
    }
    while (head < tail) {
      const position = queue[head++]
      const x = position % canvas.width
      const y = Math.floor(position / canvas.width)
      data[position * 4 + 3] = 0
      if (x > 0) enqueue(x - 1, y)
      if (x < canvas.width - 1) enqueue(x + 1, y)
      if (y > 0) enqueue(x, y - 1)
      if (y < canvas.height - 1) enqueue(x, y + 1)
    }
    context.putImageData(pixels, 0, 0)

    const texture = new CanvasTexture(canvas)
    texture.colorSpace = SRGBColorSpace
    texture.needsUpdate = true
    return texture
  }, [sourceTexture])

  return (
    <mesh position={[0, 0.0, -0.13]} renderOrder={5}>
      <planeGeometry args={[0.175, 0.215]} />
      <meshBasicMaterial map={faceTexture} transparent alphaTest={0.08} side={DoubleSide} depthTest={false} toneMapped={false} />
    </mesh>
  )
}

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
  const faceUrl = CHARACTER_ASSETS[member.actor_id]?.sprite_url

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
        {/* 简洁的衬衫、领带和西装驳领，让程序化身体不再只是单色低模块。 */}
        <mesh position={[0, 0.46, -0.155]}>
          <boxGeometry args={[0.13, 0.23, 0.018]} />
          <meshStandardMaterial color="#f3f4f6" roughness={0.8} />
        </mesh>
        <mesh position={[0, 0.45, -0.168]}>
          <boxGeometry args={[0.035, 0.17, 0.018]} />
          <meshStandardMaterial color={member.actor_id === "judge" ? "#38bdf8" : "#1f2937"} roughness={0.65} />
        </mesh>
        <mesh position={[-0.075, 0.48, -0.157]} rotation={[0, 0, -0.3]}>
          <boxGeometry args={[0.025, 0.2, 0.018]} />
          <meshStandardMaterial color={suit} roughness={0.75} />
        </mesh>
        <mesh position={[0.075, 0.48, -0.157]} rotation={[0, 0, 0.3]}>
          <boxGeometry args={[0.025, 0.2, 0.018]} />
          <meshStandardMaterial color={suit} roughness={0.75} />
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
          {faceUrl && <FaceOverlay sourceUrl={faceUrl} />}
          {/* 头发：上半球罩，脑后略厚 */}
          <mesh position={[0, 0.025, 0.015]} scale={[1.05, 0.95, 1.06]}>
            <sphereGeometry args={[0.118, 20, 12, 0, Math.PI * 2, 0, Math.PI / 1.9]} />
            <meshStandardMaterial color={HAIR} />
          </mesh>
        </group>
      </group>

      {/* 名牌 */}
      <Html position={[0, 1.04, 0]} center>
        <div className="pointer-events-none flex items-center gap-1.5 whitespace-nowrap rounded-md border border-cyan-200/25 bg-slate-950/88 px-1.5 py-0.5 text-center shadow-md shadow-black/25 backdrop-blur">
          <span className="text-[8px] font-medium tracking-wide text-white/80">{member.label}</span>
          <span className="text-[9px] font-semibold text-cyan-100">{member.name}</span>
          {(mode === "talk" || isSpeaking) && <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400" />}
        </div>
      </Html>
    </group>
  )
}
