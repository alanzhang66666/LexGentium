export const RESEARCH_DISCLAIMER =
  "本仿真仅说明系统在既定实验条件下的表现；关于司法实践的判断仍须以真实裁判文书为依据。"

export const CLAIM_ACTIONS = [
  "assert",
  "ground",
  "rebut",
  "supplement",
  "revise",
  "withdraw",
  "admit_insufficient",
] as const

export type ClaimAction = (typeof CLAIM_ACTIONS)[number]

export const POST_REBUTTAL_ACTIONS = [
  "supplement",
  "revise",
  "withdraw",
  "admit_insufficient",
] as const

export const CLAIM_ACTION_LABELS: Record<ClaimAction, string> = {
  assert: "主张",
  ground: "立据",
  rebut: "反驳",
  supplement: "补充",
  revise: "修正",
  withdraw: "撤回",
  admit_insufficient: "承认不足",
}

export interface ResearchClaimEvent {
  event_id: string
  run_id: string
  session_id?: string | null
  seq: number
  claim_id: string
  at: string
  role: string
  action: ClaimAction | string
  fact?: string
  norm?: string
  reasoning?: string
  target_claim_id?: string | null
  source_ids?: string[]
}

export interface ResearchClaimNode {
  claim_id: string
  role: string
  status: ClaimAction | string
  fact?: string
  norm?: string
  reasoning?: string
  source_ids?: string[]
  events: ResearchClaimEvent[]
}

export interface ResearchSessionMeta {
  run_id?: string
  derived_from?: string | null
  dataset_id?: string
  cluster_id?: string
  pack_version?: string
  task_type?: string
  materials_hash?: string
  visible_materials?: Record<string, { document_ids?: string[]; source_ids?: string[]; rule_ids?: string[] }>
  experiment_conditions?: Record<string, unknown>
  model_config?: Record<string, unknown>
  caption?: { case_name?: string; case_number?: string }
  disclaimer?: string
}

export interface ResearchRubricResult {
  report_id: string
  run_id: string
  session_id?: string | null
  materials_hash?: string
  rubric: {
    rubric_version?: string
    dimensions?: Record<string, number>
    overall?: number
    machine_checks?: Record<string, unknown>
    legal_quality?: Record<string, unknown>
    penalties?: Record<string, unknown>
    failures?: Array<Record<string, unknown>>
    disagreements?: Array<Record<string, unknown>>
    undecidable?: Array<Record<string, unknown>>
  }
  disclaimer?: string
}
