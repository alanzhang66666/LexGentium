import type { Object3D } from "three"
import { TKI_STANCE } from "@/lib/court3d/tki"
import type { ActorRuntime } from "@/lib/court3d/performanceStore"

export function applyProceduralPose(
  root: Object3D,
  runtime: ActorRuntime,
  elapsed: number,
  lookAt?: { x: number; y: number; z: number },
) {
  const stance = TKI_STANCE[runtime.strategy]
  const breath = 1 + Math.sin(elapsed * 1.6) * 0.012
  const think = runtime.thinking ? Math.sin(elapsed * 3) * 0.04 : 0
  const speak = runtime.speaking ? Math.sin(elapsed * 8) * 0.03 : 0
  const standLift = runtime.standing ? 0.18 : 0

  root.position.y = standLift
  root.rotation.x = stance.lean + think
  root.rotation.z = stance.tilt
  root.scale.set(1, breath, 1)

  const head = root.getObjectByName("head")
  if (head) {
    head.rotation.x = stance.headPitch + speak
    if (lookAt) {
      head.lookAt(lookAt.x, lookAt.y, lookAt.z)
    }
  }

  const mouth = root.getObjectByName("mouth")
  if (mouth) {
    mouth.scale.y = 0.15 + runtime.mouth * 0.9
  }

  const rightArm = root.getObjectByName("rightArm")
  if (rightArm) {
    let lift = -0.35
    if (runtime.gesture === "point" || runtime.gesture === "hand_over_doc") lift = -1.15
    if (runtime.gesture === "flip_file") lift = -0.85 + Math.sin(elapsed * 4) * 0.2
    if (runtime.gesture === "type") lift = -0.7 + Math.sin(elapsed * 10) * 0.15
    if (runtime.gesture === "relay_note") lift = -0.95
    if (runtime.gesture === "nod") head && (head.rotation.x += Math.sin(elapsed * 6) * 0.08)
    if (runtime.gesture === "lean_forward") root.rotation.x += 0.08
    rightArm.rotation.x = lift
  }
}
