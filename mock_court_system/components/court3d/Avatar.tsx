"use client"

import { useEffect, useRef, useState } from "react"
import { useFrame } from "@react-three/fiber"
import { Html, Text, useGLTF } from "@react-three/drei"
import { Group } from "three"
import { applyProceduralPose } from "@/components/court3d/AvatarRig"
import { SeatProps } from "@/components/court3d/Props"
import type { CastRole, SkinId } from "@/lib/court3d/cast"
import type { ActorRuntime } from "@/lib/court3d/performanceStore"
import type { SeatPose } from "@/lib/court3d/seats"
import { ACTOR_LABELS, type Actor } from "@/lib/court3d/protocol"

const BODY_COLOR: Record<Actor, string> = {
  judge: "#1a1a1a",
  clerk: "#1d3552",
  plaintiff_counsel: "#151515",
  plaintiff_party: "#4a4a4a",
  defendant_counsel: "#151515",
  defendant_party: "#1d3557",
  interpreter: "#4a6274",
}

export function Avatar({
  actor,
  role,
  skin,
  pose,
  runtime,
  lookTarget,
}: {
  actor: Actor
  role: CastRole
  skin: SkinId
  pose: SeatPose
  runtime: ActorRuntime
  lookTarget?: [number, number, number]
}) {
  const skinDef = role.skins[skin]
  const model = skinDef.model
  const ext = model.split(".").pop()?.toLowerCase()
  const useModel = Boolean(model)

  return (
    <group position={pose.position}>
      {useModel && ext === "vrm" ? (
        <VrmAvatar url={model} runtime={runtime} lookTarget={lookTarget} fallbackActor={actor} />
      ) : useModel && (ext === "glb" || ext === "gltf") ? (
        <GlbAvatar url={model} runtime={runtime} lookTarget={lookTarget} fallbackActor={actor} />
      ) : (
        <CapsuleAvatar actor={actor} runtime={runtime} lookTarget={lookTarget} />
      )}
      <SeatProps names={role.props} />
      <Html position={[0, 2.05, 0]} center distanceFactor={10}>
        <div className="rounded bg-black/70 px-2 py-0.5 text-[10px] text-white whitespace-nowrap">
          {skinDef.name} · {ACTOR_LABELS[actor]}
        </div>
      </Html>
    </group>
  )
}

function CapsuleAvatar({
  actor,
  runtime,
  lookTarget,
}: {
  actor: Actor
  runtime: ActorRuntime
  lookTarget?: [number, number, number]
}) {
  const ref = useRef<Group>(null)
  useFrame((state) => {
    if (!ref.current) return
    applyProceduralPose(
      ref.current,
      runtime,
      state.clock.elapsedTime,
      lookTarget ? { x: lookTarget[0], y: lookTarget[1], z: lookTarget[2] } : undefined,
    )
  })
  return (
    <group ref={ref}>
      <mesh position={[0, 0.7, 0]} castShadow name="body">
        <capsuleGeometry args={[0.22, 0.7, 8, 16]} />
        <meshStandardMaterial color={BODY_COLOR[actor]} />
      </mesh>
      <mesh position={[0, 1.52, 0]} castShadow name="head">
        <sphereGeometry args={[0.18, 16, 16]} />
        <meshStandardMaterial color="#d8b39a" />
        <mesh position={[0, -0.06, 0.16]} name="mouth">
          <boxGeometry args={[0.08, 0.02, 0.02]} />
          <meshStandardMaterial color="#6b2a2a" />
        </mesh>
      </mesh>
      <mesh position={[0.28, 0.85, 0]} rotation={[0, 0, -0.4]} name="rightArm">
        <capsuleGeometry args={[0.055, 0.42, 6, 10]} />
        <meshStandardMaterial color={BODY_COLOR[actor]} />
      </mesh>
      <mesh position={[-0.28, 0.85, 0]} rotation={[0, 0, 0.4]} name="leftArm">
        <capsuleGeometry args={[0.055, 0.42, 6, 10]} />
        <meshStandardMaterial color={BODY_COLOR[actor]} />
      </mesh>
      {runtime.thinking ? (
        <Text position={[0, 2.25, 0]} fontSize={0.12} color="#f3e6c5">
          …
        </Text>
      ) : null}
    </group>
  )
}

function GlbAvatar({
  url,
  runtime,
  lookTarget,
  fallbackActor,
}: {
  url: string
  runtime: ActorRuntime
  lookTarget?: [number, number, number]
  fallbackActor: Actor
}) {
  const [failed, setFailed] = useState(false)
  if (failed) {
    return <CapsuleAvatar actor={fallbackActor} runtime={runtime} lookTarget={lookTarget} />
  }
  return <GlbInner url={url} runtime={runtime} lookTarget={lookTarget} onError={() => setFailed(true)} />
}

function GlbInner({
  url,
  runtime,
  lookTarget,
  onError,
}: {
  url: string
  runtime: ActorRuntime
  lookTarget?: [number, number, number]
  onError: () => void
}) {
  const gltf = useGLTF(url)
  const ref = useRef<Group>(null)
  useEffect(() => {
    if (!gltf?.scene) onError()
  }, [gltf, onError])
  useFrame((state) => {
    if (!ref.current) return
    applyProceduralPose(
      ref.current,
      runtime,
      state.clock.elapsedTime,
      lookTarget ? { x: lookTarget[0], y: lookTarget[1], z: lookTarget[2] } : undefined,
    )
  })
  return <primitive ref={ref} object={gltf.scene} scale={1.15} />
}

function VrmAvatar({
  url,
  runtime,
  lookTarget,
  fallbackActor,
}: {
  url: string
  runtime: ActorRuntime
  lookTarget?: [number, number, number]
  fallbackActor: Actor
}) {
  const [ready, setReady] = useState(false)
  const group = useRef<Group>(null)
  const vrmRef = useRef<{ scene: Group; update?: (d: number) => void } | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js")
        const { VRMLoaderPlugin, VRMUtils } = await import("@pixiv/three-vrm")
        const loader = new GLTFLoader()
        loader.register((parser) => new VRMLoaderPlugin(parser))
        const gltf = await loader.loadAsync(url)
        if (cancelled) return
        const vrm = gltf.userData.vrm
        if (!vrm) throw new Error("not vrm")
        VRMUtils.removeUnnecessaryVertices(vrm.scene)
        vrmRef.current = vrm
        group.current?.add(vrm.scene)
        setReady(true)
      } catch {
        if (!cancelled) setReady(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [url])

  useFrame((state, delta) => {
    vrmRef.current?.update?.(delta)
    if (!group.current) return
    applyProceduralPose(
      group.current,
      runtime,
      state.clock.elapsedTime,
      lookTarget ? { x: lookTarget[0], y: lookTarget[1], z: lookTarget[2] } : undefined,
    )
  })

  if (!ready) {
    return <CapsuleAvatar actor={fallbackActor} runtime={runtime} lookTarget={lookTarget} />
  }
  return <group ref={group} />
}
