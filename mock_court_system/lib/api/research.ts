import { apiFetch } from "@/lib/api/http"
import type { DatasetId, ReviewState } from "@/lib/research"
import type { PackSummary, ResearchPack } from "@/lib/research"

export type ResearchDocument = {
  document_id: string
  title?: string
  filename?: string
  source_tier?: string
  language?: string
  review_state?: ReviewState
  notes?: string
  text: string
}

export type ResearchPackBundle = {
  pack: ResearchPack
  documents: ResearchDocument[]
  pack_version: string
  overlay_count: number
  pack_json_unmodified: boolean
}

export type ResearchPackList = {
  packs: Array<PackSummary & { overlay_count?: number }>
  total: number
}

export type ResearchSourceSpan = {
  source_id: string
  document_id: string
  locator?: string
  quote?: string
  excerpt?: string
  start_offset?: number | null
  end_offset?: number | null
  source_tier?: string
  review_state?: ReviewState
  notes?: string
  document_text?: string
  dataset_id?: DatasetId
  cluster_id?: string
  pack_version?: string
}

export type ResearchChangeEntry = {
  id: number
  dataset_id: DatasetId | string
  cluster_id: string
  pack_version: string
  field_path: string
  item_id: string
  actor: string
  action: string
  from_value?: unknown
  to_value?: unknown
  review_state?: ReviewState | null
  note?: string
  created_at: string
}

export type ResearchChangelog = {
  dataset_id: string
  cluster_id: string
  pack_version: string
  entries: ResearchChangeEntry[]
  total: number
}

export type FieldPatchBody = {
  field_path: string
  actor?: string
  note?: string
  value?: unknown
  review_state?: ReviewState
  patch?: Record<string, unknown>
  pack_version?: string
}

export type FieldPatchResult = ResearchPackBundle & {
  field_path: string
  item: unknown
  change: ResearchChangeEntry
}

function packBase(dataset: string, cluster: string) {
  return `/api/research/packs/${encodeURIComponent(dataset)}/${encodeURIComponent(cluster)}`
}

export function listAnnotatedPacks(dataset?: string) {
  const query = dataset ? `?dataset=${encodeURIComponent(dataset)}` : ""
  return apiFetch<ResearchPackList>(`/api/research/packs${query}`)
}

export function getAnnotatedPack(
  dataset: string,
  cluster: string,
  options?: { pack_version?: string; include_reference?: boolean },
) {
  const params = new URLSearchParams()
  if (options?.pack_version) params.set("pack_version", options.pack_version)
  if (options?.include_reference === false) params.set("include_reference", "false")
  const suffix = params.toString() ? `?${params}` : ""
  return apiFetch<ResearchPackBundle>(`${packBase(dataset, cluster)}${suffix}`)
}

export function getResearchSource(
  dataset: string,
  cluster: string,
  sourceId: string,
  packVersion?: string,
) {
  const params = new URLSearchParams({ source_id: sourceId })
  if (packVersion) params.set("pack_version", packVersion)
  return apiFetch<ResearchSourceSpan>(`${packBase(dataset, cluster)}/source?${params}`)
}

export function patchResearchField(dataset: string, cluster: string, body: FieldPatchBody) {
  return apiFetch<FieldPatchResult>(`${packBase(dataset, cluster)}/fields`, {
    method: "PATCH",
    body: JSON.stringify(body),
  })
}

export function patchResearchReview(
  dataset: string,
  cluster: string,
  body: { review_state: ReviewState; actor?: string; note?: string; field_path?: string; pack_version?: string },
) {
  return apiFetch<FieldPatchResult>(`${packBase(dataset, cluster)}/review`, {
    method: "PATCH",
    body: JSON.stringify(body),
  })
}

export function scoreResearchRun(body: { run_id?: string; session_id?: string; output?: Record<string, unknown> }) {
  return apiFetch<Record<string, unknown>>("/api/research/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function reviewResearchRun(body: {
  run_id: string
  review_state: ReviewState
  reviewer?: string
  note?: string
  report_id?: string
}) {
  return apiFetch<Record<string, unknown>>("/api/research/review", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function compareResearchRuns(runIds: string[]) {
  return apiFetch<Record<string, unknown>>(
    `/api/research/compare?run_ids=${encodeURIComponent(runIds.join(","))}`,
  )
}

export function exportResearchRun(runId: string) {
  return apiFetch<Record<string, unknown>>(`/api/research/export/${encodeURIComponent(runId)}`)
}

export function listResearchRuns(datasetId?: string, clusterId?: string) {
  const params = new URLSearchParams()
  if (datasetId) params.set("dataset_id", datasetId)
  if (clusterId) params.set("cluster_id", clusterId)
  const suffix = params.toString() ? `?${params}` : ""
  return apiFetch<{ runs: Array<Record<string, unknown>>; total: number }>(`/api/research/runs${suffix}`)
}

export function listResearchChangelog(dataset: string, cluster: string, packVersion?: string, limit = 200) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (packVersion) params.set("pack_version", packVersion)
  return apiFetch<ResearchChangelog>(`${packBase(dataset, cluster)}/changelog?${params}`)
}
