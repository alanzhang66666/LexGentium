import type { CastMember } from "./contracts"

// actor_id 是 HearingEvent 1.1 的兼容键；可见角色及姓名来自经筛选的最新角色资料。
const seats: Record<string, { position: [number, number, number]; look_at: [number, number, number] }> = {
  judge: { position: [0, 0.45, 2.8], look_at: [0, 1.35, 0] },
  associate_judge: { position: [1.0, 0.45, 2.8], look_at: [0, 1.35, 0] },
  people_juror: { position: [-1.0, 0.45, 2.8], look_at: [0, 1.35, 0] },
  clerk: { position: [-0.9, 0.45, 0.25], look_at: [-0.9, 1.35, 1.05] },
  plaintiff_counsel: { position: [-2.9, 0.45, 0.65], look_at: [0, 1.35, 0.65] },
  prosecutor: { position: [-2.9, 0.45, -1.15], look_at: [0, 1.35, -1.15] },
  china_company_rep: { position: [-2.9, 0.45, -2.55], look_at: [0, 1.35, -2.55] },
  defendant_counsel: { position: [2.9, 0.45, 0.65], look_at: [0, 1.35, 0.65] },
  defendant_party: { position: [2.9, 0.45, -1.15], look_at: [0, 1.35, -1.15] },
  interpreter: { position: [2.9, 0.45, -2.6], look_at: [0, 1.35, -2.6] },
  technical_expert_witness: { position: [4.0, 0.45, -0.8], look_at: [0, 1.35, -0.8] },
  fact_witness: { position: [4.0, 0.45, -2.35], look_at: [0, 1.35, -2.35] },
  judicial_police: { position: [1.5, 0.45, -2.7], look_at: [0, 1.35, 0] },
}

/**
 * 角色名是产品人物档案，不代表具体案件中的真实参与人。
 * 原法院角色仅作为已交付 OBJ 的来源身份，运行时统一映射为国际商事仲裁职能。
 */
const labels: Record<string, [string, string, string]> = {
  judge: ["首席仲裁员", "Presiding Arbitrator", "周屹"],
  associate_judge: ["仲裁员", "Co-Arbitrator", "陈启澜"],
  people_juror: ["仲裁员", "Co-Arbitrator", "何敬"],
  clerk: ["仲裁庭秘书", "Tribunal Secretary", "林澄"],
  plaintiff_counsel: ["申请人首席代理律师", "Lead Counsel for Claimant", "顾清衡"],
  prosecutor: ["申请人共同代理律师", "Co-Counsel for Claimant", "谢衡宁"],
  china_company_rep: ["申请人代表", "Claimant Representative", "陆玮宁"],
  defendant_counsel: ["被申请人代理律师", "Counsel for Respondent", "沈嘉宁"],
  defendant_party: ["被申请人代表", "Respondent Representative", "Marco Rossi"],
  interpreter: ["听证口译员", "Hearing Interpreter", "唐闻"],
  technical_expert_witness: ["专家证人", "Expert Witness", "Dr. Leila Haddad"],
  fact_witness: ["事实证人", "Fact Witness", "Adrian Tan"],
  judicial_police: ["会务安保", "Venue Security", "赵峥"],
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

const castByActorId = new Map(castManifest.map((member) => [member.actor_id, member]))

export function castMemberForActor(actorId: string | null | undefined): CastMember | undefined {
  return actorId ? castByActorId.get(actorId) : undefined
}
