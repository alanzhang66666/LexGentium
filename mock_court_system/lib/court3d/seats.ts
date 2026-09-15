import type { SeatId } from "@/lib/court3d/protocol"
import { Vector3 } from "three"

export interface SeatPose {
  position: [number, number, number]
  lookAt: [number, number, number]
}

/** 面向审判台：原告在左（-X），被告在右（+X），审判台在 +Z。 */
export const COURTROOM_SEATS: Record<SeatId, SeatPose> = {
  bench_center: { position: [0, 0.95, 7.2], lookAt: [0, 1.2, 0] },
  clerk: { position: [0, 0.35, 5.15], lookAt: [0, 1.1, 0] },
  plaintiff_counsel: { position: [-3.15, 0.05, 1.7], lookAt: [0, 1.4, 7.2] },
  plaintiff_party: { position: [-4.45, 0.05, 1.7], lookAt: [0, 1.4, 7.2] },
  defendant_counsel: { position: [3.15, 0.05, 1.7], lookAt: [0, 1.4, 7.2] },
  defendant_party: { position: [4.45, 0.05, 1.7], lookAt: [0, 1.4, 7.2] },
  interpreter: { position: [2.35, 0.05, 2.85], lookAt: [4.2, 1.2, 1.7] },
}

export const OFFICE_SEATS: Record<SeatId, SeatPose> = {
  bench_center: { position: [0, -10, 0], lookAt: [0, 0, 0] },
  clerk: { position: [0, -10, 0], lookAt: [0, 0, 0] },
  plaintiff_counsel: { position: [-1.1, 0.05, 0.4], lookAt: [1.1, 1.1, 0.4] },
  plaintiff_party: { position: [1.1, 0.05, 0.4], lookAt: [-1.1, 1.1, 0.4] },
  defendant_counsel: { position: [-1.1, 0.05, 0.4], lookAt: [1.1, 1.1, 0.4] },
  defendant_party: { position: [1.1, 0.05, 0.4], lookAt: [-1.1, 1.1, 0.4] },
  interpreter: { position: [0, -10, 0], lookAt: [0, 0, 0] },
}

export const MEDIATION_SEATS: Record<SeatId, SeatPose> = {
  bench_center: { position: [0, 0.05, 1.6], lookAt: [0, 1, 0] },
  clerk: { position: [0, -10, 0], lookAt: [0, 0, 0] },
  plaintiff_counsel: { position: [-1.6, 0.05, 0.2], lookAt: [0, 1, 1.4] },
  plaintiff_party: { position: [-1.6, 0.05, -0.9], lookAt: [0, 1, 1.4] },
  defendant_counsel: { position: [1.6, 0.05, 0.2], lookAt: [0, 1, 1.4] },
  defendant_party: { position: [1.6, 0.05, -0.9], lookAt: [0, 1, 1.4] },
  interpreter: { position: [1.6, 0.05, 1.15], lookAt: [1.6, 1, -0.6] },
}

export function seatToLookTarget(pose: SeatPose) {
  return new Vector3(...pose.lookAt)
}
