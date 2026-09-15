/** Stable research identifiers. Case number is display-only, never a primary key. */

import type { DatasetId } from "@/lib/research/enums"

export interface PackIdentity {
  dataset_id: DatasetId
  cluster_id: string
  pack_version: string
}

export interface DocumentIdentity {
  dataset_id: DatasetId
  cluster_id: string
  document_id: string
}

export interface SourceIdentity {
  dataset_id: DatasetId
  cluster_id: string
  document_id: string
  source_id: string
}

export interface RuleIdentity {
  rule_id: string
  rule_version: string
}

export interface RunIdentity {
  run_id: string
  derived_from?: string | null
  session_id?: string | null
}

export interface ReportIdentity {
  report_id: string
  run_id: string
}

export interface CaseCaption {
  case_name?: string
  case_number?: string
  court?: string
  date?: string
  source?: string
  procedure_chain?: string[]
}

export function newRunId(): string {
  return `run_${crypto.randomUUID().replace(/-/g, "")}`
}

export function newReportId(): string {
  return crypto.randomUUID()
}
