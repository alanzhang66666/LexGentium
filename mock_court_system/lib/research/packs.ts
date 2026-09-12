/** Six-column research pack. Field names must match ``core/research/packs.py``. */

import type { DatasetId, ReviewState, TaskType } from "@/lib/research/enums"
import type { CaseCaption } from "@/lib/research/ids"
import type {
  AnnotatedValue,
  ArgumentRecord,
  CourtFinding,
  DocumentRecord,
  EvidenceLink,
  LegalBasis,
  MaterialGap,
  PartyClaim,
  ReferenceLayer,
  ReviewRecord,
  RuleCard,
  SourceAnchor,
  TaskLabels,
} from "@/lib/research/shared"

export const SIX_COLUMN_FIELDS = [
  "procedural_facts",
  "party_claims",
  "court_findings",
  "legal_bases",
  "material_gaps",
  "source_anchors",
] as const

export type SixColumnField = (typeof SIX_COLUMN_FIELDS)[number]

export interface ResearchPack {
  schema_version?: string
  dataset_id: DatasetId
  cluster_id: string
  pack_version: string
  task_type: TaskType
  caption: CaseCaption
  documents?: DocumentRecord[]
  procedural_facts?: AnnotatedValue[]
  party_claims?: PartyClaim[]
  court_findings?: CourtFinding[]
  legal_bases?: LegalBasis[]
  material_gaps?: MaterialGap[]
  source_anchors?: SourceAnchor[]
  argument_records?: ArgumentRecord[]
  evidence_links?: EvidenceLink[]
  rules?: RuleCard[]
  task_labels: TaskLabels
  reference?: ReferenceLayer | null
  review_state?: ReviewState
  review_records?: ReviewRecord[]
  notes?: string
}

export interface PackSummary {
  dataset_id: DatasetId
  cluster_id: string
  pack_version: string
  task_type: TaskType
  case_name?: string
  review_state?: ReviewState
  document_ids?: string[]
}
