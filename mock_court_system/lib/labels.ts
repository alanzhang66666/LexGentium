import type { Actor } from "@/lib/court3d/protocol"
import type { CourtStage, CourtSubStage } from "@/lib/conversation-types"

/** 听证场景展示名。英文 Actor ID 不变。 */
export const ACTOR_LABELS: Record<Actor, string> = {
  judge: "首席仲裁员",
  clerk: "仲裁庭秘书",
  plaintiff_counsel: "申请人代理",
  plaintiff_party: "申请人企业代表",
  defendant_counsel: "被申请人代理",
  defendant_party: "被申请人企业代表",
  interpreter: "口译员",
}

export const STAGE_LABELS: Record<CourtStage | string, string> = {
  opening: "核对通知与出庭",
  investigation: "陈述与举证",
  debate: "抗辩与询问",
  mediation: "和解",
  judgment: "裁决",
  dialogue: "会见",
  finished: "已结束",
}

export const SUB_STAGE_LABELS: Record<CourtSubStage | string, string> = {
  opening_identity: "核对身份",
  opening_composition: "宣布庭组",
  opening_rights: "程序权利",
  opening_recusal: "回避确认",
  opening_absence: "缺席说明",
  opening_done: "准备完毕",
  investigation_claim: "申请人陈述",
  investigation_defense: "被申请人答辩",
  investigation_evidence: "举证",
  investigation_cross_exam: "质证",
  investigation_fact_inquiry: "事实核实",
  investigation_done: "调查完毕",
  debate_focus: "归纳争议焦点",
  debate_argument: "辩论",
  debate_rebuttal: "反驳",
  debate_final_statement: "最后陈述",
  debate_done: "辩论完毕",
  mediation_ask: "询问和解意愿",
  mediation_plaintiff_resp: "等待申请人表态",
  mediation_defendant_resp: "等待被申请人表态",
  mediation_announce: "宣布和解结果",
  mediation_done: "和解完毕",
  judgment_generating: "生成裁决中",
  judgment_done: "裁决完成",
}

export const SCENARIO_LABELS: Record<string, string> = {
  CD: "申请准备",
  DD: "答辩准备",
  CI: "仲裁听证",
}

export const SCENARIO_DESCRIPTIONS: Record<string, string> = {
  CD: "申请书草稿",
  DD: "答辩书草稿",
  CI: "听证与裁决",
}

export const ROLE_LABELS: Record<string, string> = {
  Client: "当事人",
  Lawyer: "代理律师",
  Judge: "首席仲裁员",
  Plaintiff: "申请人",
  Defendant: "被申请人",
  Final: "裁决文书",
}

export const STRATEGY_LABELS: Record<string, string> = {
  competing: "竞争",
  collaborating: "合作",
  compromising: "妥协",
  avoiding: "回避",
  accommodating: "迁就",
}

export function roleDisplayName(role: string): string {
  return ROLE_LABELS[role] || role
}

export const AUDIT_STATUS_LABELS = {
  supported: "证据支持",
  unknown: "未知",
  unsupported: "未支持",
  excluded: "已排除",
  frozen: "人工冻结",
} as const
