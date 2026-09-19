"use client"

import { useEffect, useRef } from "react"
import { useThree } from "@react-three/fiber"
import type { SceneState } from "./contracts"

const cameras = {
  wide: { position: [0, 2.42, -6.55] as const, target: [0, 1.15, 0.45] as const },
  presiding_medium: { position: [0.75, 1.55, -0.05] as const, target: [0, 1.35, 2.65] as const },
  // 两组中景从庭审桌对面取景，避免从秘书席后方切入造成“后脑勺挡脸”。
  claimant_medium: { position: [0, 1.72, 2.75] as const, target: [-2.9, 1.28, 0.48] as const },
  respondent_medium: { position: [0, 1.72, 2.75] as const, target: [2.9, 1.28, 0.48] as const },
}

type CameraMode = keyof typeof cameras

export function CameraDirector({ state, mode, automatic = false }: { state: SceneState; mode: CameraMode; automatic?: boolean }) {
  const { camera } = useThree()
  const autoMode: CameraMode = state.active_actor_id?.startsWith("plaintiff") ? "claimant_medium"
    : state.active_actor_id?.startsWith("defendant") ? "respondent_medium"
      : state.active_actor_id === "judge" ? "presiding_medium" : "wide"
  const target = cameras[automatic ? autoMode : mode] ?? cameras.wide
  const lookAt = useRef(target.target)
  useEffect(() => {
    camera.position.set(...(target.position as [number, number, number]))
    lookAt.current = target.target
    camera.lookAt(...(lookAt.current as [number, number, number]))
  }, [camera, target])
  return null
}

export { cameras }
export type { CameraMode }
