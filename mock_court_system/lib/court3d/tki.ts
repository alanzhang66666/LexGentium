import type { ConflictStrategy } from "@/lib/conversation-types"

export interface StancePose {
  lean: number
  tilt: number
  headPitch: number
}

export const TKI_STANCE: Record<ConflictStrategy, StancePose> = {
  competing: { lean: 0.18, tilt: 0, headPitch: -0.04 },
  collaborating: { lean: 0.04, tilt: 0, headPitch: 0 },
  compromising: { lean: 0.02, tilt: 0.08, headPitch: 0 },
  avoiding: { lean: -0.12, tilt: -0.04, headPitch: 0.06 },
  accommodating: { lean: 0.0, tilt: 0, headPitch: 0.12 },
}
