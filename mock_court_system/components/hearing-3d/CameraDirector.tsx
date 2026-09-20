"use client"

import { useEffect, useRef } from "react"
import { useFrame, useThree } from "@react-three/fiber"
import { PerspectiveCamera, Vector3 } from "three"
import type { SceneState } from "./contracts"

// Conversational medium shots. Faces stay readable after the head-preserving
// OBJ rebuild; we still avoid portrait close-ups that the atlas cannot support.
const cameras = {
  wide: { position: [0, 2.65, -7.8] as const, target: [0, 1.16, 0.45] as const, fov: 36 },
  presiding_medium: { position: [0, 2.04, -3.05] as const, target: [0, 1.44, 2.68] as const, fov: 30 },
  claimant_medium: { position: [0.18, 2.0, -3.45] as const, target: [-2.72, 1.26, -0.1] as const, fov: 33 },
  respondent_medium: { position: [-0.18, 2.0, -3.45] as const, target: [2.72, 1.26, -0.1] as const, fov: 33 },
}

const CLAIMANT_ACTORS = new Set(["plaintiff_counsel", "prosecutor", "china_company_rep"])
const RESPONDENT_ACTORS = new Set(["defendant_counsel", "defendant_party"])
const TRIBUNAL_ACTORS = new Set(["judge", "associate_judge", "people_juror"])

type CameraMode = keyof typeof cameras

export function CameraDirector({ state, mode, automatic = false }: { state: SceneState; mode: CameraMode; automatic?: boolean }) {
  const { camera } = useThree()
  const activeActorId = state.active_actor_id
  const autoMode: CameraMode = activeActorId && CLAIMANT_ACTORS.has(activeActorId) ? "claimant_medium"
    : activeActorId && RESPONDENT_ACTORS.has(activeActorId) ? "respondent_medium"
      : activeActorId && TRIBUNAL_ACTORS.has(activeActorId) ? "presiding_medium" : "wide"
  const target = cameras[automatic ? autoMode : mode] ?? cameras.wide
  const targetPosition = useRef(new Vector3(...target.position))
  const lookAt = useRef(new Vector3(...target.target))

  useEffect(() => {
    targetPosition.current.set(target.position[0], target.position[1], target.position[2])
    lookAt.current.set(target.target[0], target.target[1], target.target[2])
    const perspective = camera as PerspectiveCamera
    perspective.fov = target.fov
    perspective.updateProjectionMatrix()
  }, [camera, target])

  useFrame((_, delta) => {
    camera.position.lerp(targetPosition.current, Math.min(1, delta * 3.2))
    camera.lookAt(lookAt.current)
  })

  return null
}

export { cameras }
export type { CameraMode }
