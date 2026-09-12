import type { DatasetId, ReviewState, TaskType } from "@/lib/research"
import { SIX_COLUMN_FIELDS, type SixColumnField } from "@/lib/research"

export const REVIEW_STATE_LABELS: Record<ReviewState, string> = {
  pending: "待复核",
  tech_checked: "技术已核",
  law_reviewed: "法学已核",
  disputed: "有争议",
}

export const DATASET_LABELS: Record<DatasetId, string> = {
  cisg: "CISG",
  enforcement: "承认执行",
}

export const TASK_TYPE_LABELS: Record<TaskType, string> = {
  cisg_article79: "CISG 第79条",
  enforcement_nyc: "纽约公约执行",
}

export const COLUMN_LABELS: Record<SixColumnField, string> = {
  procedural_facts: "程序事实",
  party_claims: "双方主张",
  court_findings: "法院认定",
  legal_bases: "法律依据",
  material_gaps: "材料缺口",
  source_anchors: "原文锚点",
}

export const COLUMN_ORDER = SIX_COLUMN_FIELDS

export function formatChangeValue(value: unknown): string {
  if (value == null || value === "") return "—"
  if (typeof value === "string") return value
  try {
    return JSON.stringify(value, null, 0)
  } catch {
    return String(value)
  }
}
