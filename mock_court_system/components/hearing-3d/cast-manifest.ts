import type { CastMember } from "./contracts"

const seats: Record<string, { position: [number, number, number]; look_at: [number, number, number] }> = {
  judge: { position: [0, 0.45, 2.8], look_at: [0, 1.35, 0] },
  clerk: { position: [-0.9, 0.45, 0.25], look_at: [-0.9, 1.35, 1.05] },
  plaintiff_counsel: { position: [-2.9, 0.45, 0.65], look_at: [0, 1.35, 0.65] },
  plaintiff_party: { position: [-2.9, 0.45, -1.15], look_at: [0, 1.35, -1.15] },
  defendant_counsel: { position: [2.9, 0.45, 0.65], look_at: [0, 1.35, 0.65] },
  defendant_party: { position: [2.9, 0.45, -1.15], look_at: [0, 1.35, -1.15] },
  interpreter: { position: [2.9, 0.45, -2.6], look_at: [0, 1.35, -2.6] },
}

const labels: Record<string, [string, string, string]> = {
  judge: ["首席仲裁员", "Presiding Arbitrator", "周岚"],
  clerk: ["仲裁庭秘书", "Tribunal Secretary", "林泽"],
  plaintiff_counsel: ["申请人代理", "Counsel for Claimant", "顾清衡"],
  plaintiff_party: ["申请人企业代表", "Claimant Representative", "陆玮"],
  defendant_counsel: ["被申请人代理", "Counsel for Respondent", "沈嘉树"],
  defendant_party: ["被申请人企业代表", "Respondent Representative", "Elena Rossi"],
  interpreter: ["口译员", "Interpreter", "唐雯"],
}

export const castManifest: CastMember[] = Object.keys(seats).map((actor_id) => {
  const [label, english, name] = labels[actor_id]
  return {
    actor_id,
    label,
    english,
    name,
    status: "placeholder",
    asset_kind: "procedural",
    reference: null,
    seat_id: actor_id,
    position: seats[actor_id].position,
    look_at: seats[actor_id].look_at,
    seat_to_root: [0, 0, 0],
    forward_axis: [0, 0, 1],
    scale: 1,
  }
})
