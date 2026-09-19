import type { CastMember } from "./contracts"

const seats: Record<string, { position: [number, number, number]; look_at: [number, number, number] }> = {
  judge: { position: [0, 0.45, 2.8], look_at: [0, 1.35, 0] },
  associate_judge: { position: [1.0, 0.45, 2.8], look_at: [0, 1.35, 0] },
  people_juror: { position: [-1.0, 0.45, 2.8], look_at: [0, 1.35, 0] },
  clerk: { position: [-0.9, 0.45, 0.25], look_at: [-0.9, 1.35, 1.05] },
  plaintiff_counsel: { position: [-2.9, 0.45, 0.65], look_at: [0, 1.35, 0.65] },
  plaintiff_party: { position: [-2.9, 0.45, -1.15], look_at: [0, 1.35, -1.15] },
  china_company_rep: { position: [-2.9, 0.45, -2.55], look_at: [0, 1.35, -2.55] },
  defendant_counsel: { position: [2.9, 0.45, 0.65], look_at: [0, 1.35, 0.65] },
  defendant_party: { position: [2.9, 0.45, -1.15], look_at: [0, 1.35, -1.15] },
  interpreter: { position: [2.9, 0.45, -2.6], look_at: [0, 1.35, -2.6] },
  prosecutor: { position: [-4.0, 0.45, -2.35], look_at: [0, 1.35, -2.35] },
  technical_expert_witness: { position: [4.0, 0.45, -0.8], look_at: [0, 1.35, -0.8] },
  fact_witness: { position: [4.0, 0.45, -2.35], look_at: [0, 1.35, -2.35] },
}

const labels: Record<string, [string, string, string]> = {
  judge: ["审判长", "Presiding Judge", "周岚"],
  associate_judge: ["审判员", "Associate Judge", "审判员"],
  people_juror: ["人民陪审员", "People's Juror", "人民陪审员"],
  clerk: ["书记员", "Court Clerk", "林泽"],
  plaintiff_counsel: ["中方代理律师", "China Counsel", "顾清衡"],
  plaintiff_party: ["外籍被告人", "Foreign Defendant", "被告人"],
  china_company_rep: ["中方企业代表", "China Company Representative", "中方企业代表"],
  defendant_counsel: ["外方代理律师", "Foreign Counsel", "沈嘉树"],
  defendant_party: ["外方企业代表", "Foreign Company Representative", "Elena Rossi"],
  interpreter: ["法庭口译员", "Court Interpreter", "唐雯"],
  prosecutor: ["公诉人", "Prosecutor", "公诉人"],
  technical_expert_witness: ["技术专家证人", "Technical Expert Witness", "技术专家证人"],
  fact_witness: ["外籍事实证人", "Foreign Fact Witness", "证人"],
}

export const castManifest: CastMember[] = Object.keys(seats).map((actor_id) => {
  const [label, english, name] = labels[actor_id]
  return {
    actor_id,
    label,
    english,
    name,
    status: "reference",
    asset_kind: "reference",
    reference: null,
    seat_id: actor_id,
    position: seats[actor_id].position,
    look_at: seats[actor_id].look_at,
    seat_to_root: [0, 0, 0],
    forward_axis: [0, 0, 1],
    scale: 1,
  }
})
