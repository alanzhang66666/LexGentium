/** Shared annotation, source, rule, and task-label components. */

import {
  REFERENCE_FIELD,
  UNKNOWN,
  type CisgApplicableLabel,
  type CisgArticle79ElementId,
  type CisgConclusionLabel,
  type CompletenessDegree,
  type DisclosureStatus,
  type ElementCourtResult,
  type HandledLabel,
  type MissingCode,
  type NoticeEventType,
  type OriginalLabelRelation,
  type ReviewState,
  type SatisfiedLabel,
  type SourceForm,
  type ArgumentAction,
  type ArgumentKind,
  type AvailabilityState,
  type ConditionType,
  type EvidenceRelation,
  type ProtocolBasis,
  type SourceTier,
  type SpeakerLabel,
  type SpeechType,
  type SupportStatus,
  type VisibilityState,
} from "@/lib/research/enums"

export interface RevisionEntry {
  at?: string
  by?: string
  from_value?: unknown
  to_value?: unknown
  note?: string
}

export interface ReviewRecord {
  review_state: ReviewState
  reviewer?: string
  reviewed_at?: string
  note?: string
}

export interface OriginalRef {
  raw_id?: string
  raw_locator?: string
  catalog_no?: string
  workbook_sheet?: string
}

export interface SourceAnchor {
  source_id: string
  document_id: string
  locator?: string
  start_offset?: number | null
  end_offset?: number | null
  quote?: string
  source_tier: SourceTier
  review_state?: ReviewState
  notes?: string
}

export interface ProvenanceFields {
  source_ids?: string[]
  source_tier: SourceTier
  review_state?: ReviewState
  notes?: string
  revisions?: RevisionEntry[]
  speaker?: SpeakerLabel | null
  speech_type?: SpeechType | null
  support_status?: SupportStatus | null
  disclosure_status?: DisclosureStatus | null
  missing_code?: MissingCode | null
  conflict_values?: string[]
  original_ref?: OriginalRef | null
}

export interface AnnotatedValue extends ProvenanceFields {
  item_id: string
  field_key: string
  value: string
}

export interface DocumentRecord {
  document_id: string
  title?: string
  filename?: string
  source_tier: SourceTier
  language?: string
  review_state?: ReviewState
  notes?: string
  original_ref?: OriginalRef | null
  source_form?: SourceForm | null
  completeness?: CompletenessDegree | null
}

export interface PartyClaim extends ProvenanceFields {
  item_id: string
  party: string
  claim_text: string
  facts?: string
  norms?: string
  reasoning?: string
}

export interface CourtFinding extends ProvenanceFields {
  item_id: string
  finding: string
  reasons?: string
}

export interface LegalBasis extends ProvenanceFields {
  item_id: string
  rule_id: string
  rule_version: string
  citation?: string
  application_note?: string
}

export interface MaterialGap {
  gap_id: string
  description: string
  related_field?: string
  related_item_ids?: string[]
  status?: "unknown" | "missing_document" | "untranslated"
  missing_code?: MissingCode | null
  conflict_values?: string[]
  checked?: string
  impact?: string
  blocks?: SatisfiedLabel | null
  review_state?: ReviewState
  notes?: string
}

export interface RuleCard {
  rule_id: string
  rule_version: string
  title?: string
  text?: string
  source?: string
  applicability_conditions?: string[]
  controversies?: string[]
  usage_boundary?: string
  source_ids?: string[]
  source_tier?: SourceTier
  review_state?: ReviewState
  notes?: string
}

export interface RoleProtocolEntry {
  role: string
  duties?: string[]
  turn_order?: number | null
  stop_conditions?: string[]
}

export interface CisgJudgmentObject {
  judgment_id: string
  claimant?: string
  obligation?: string
  request?: string
  period?: string
  task?: string
  cisg_applicable?: CisgApplicableLabel
  claim_raised?: SatisfiedLabel
  handled?: HandledLabel
  result?: CisgConclusionLabel
  original_label?: string
  original_label_relation?: OriginalLabelRelation
  notes?: string
}

export interface CisgArticle79Element extends ProvenanceFields {
  element_id: CisgArticle79ElementId
  label: string
  satisfied?: SatisfiedLabel
  value?: string
  judgment_id?: string
  claimant_view?: string
  opponent_view?: string
  court_result?: ElementCourtResult | null
}

export interface CisgArticle79Labels {
  task_type: "cisg_article79"
  article?: string
  judgments?: CisgJudgmentObject[]
  elements?: CisgArticle79Element[]
  conclusion_label?: CisgConclusionLabel
  conclusion_note?: string
  original_label?: string
  original_label_relation?: OriginalLabelRelation | null
  review_state?: ReviewState
}

export interface NoticeEvent extends ProvenanceFields {
  event_id: string
  document_id?: string
  procedure_id?: string
  notice_name?: string
  event_type?: NoticeEventType
  sender?: string
  recipient?: string
  channel?: string
  address?: string
  address_basis?: string
  date_raw?: string
  arrival?: string
  language?: string
  content?: string
  opportunity?: string
  objection?: string
  court_view?: string
}

export interface EnforcementNycLabels {
  task_type: "enforcement_nyc"
  enforcement_forum?: string
  procedure_type?: string
  convention_issues?: string[]
  notice_events?: NoticeEvent[]
  role_protocol?: RoleProtocolEntry[]
  review_state?: ReviewState
}

export type TaskLabels = CisgArticle79Labels | EnforcementNycLabels

export interface AcceptablePath {
  path_id: string
  conclusion_label?: string
  requires?: string[]
  requires_any?: string[]
  notes?: string
}

export interface ReferenceLayer {
  reference_version: string
  gold_labels?: Record<string, unknown>
  acceptable_paths?: AcceptablePath[]
  notes?: string
}

export interface ArgumentRecord extends ProvenanceFields {
  argument_id: string
  target_id: string
  document_id?: string
  kind?: ArgumentKind
  claim: string
  reasoning?: string
  assumptions?: string
  rebuttal_target?: string
  target_part?: string
  action?: ArgumentAction
  fact_ids?: string[]
  rule_ids?: string[]
  stage?: string
}

export interface EvidenceLink {
  link_id: string
  object_id: string
  relation: EvidenceRelation
  evidence_id: string
  field?: string
  purpose?: string
  limits?: string
}

export interface VisibilityGrant {
  grant_id: string
  role: string
  stage?: string
  visibility?: VisibilityState
  availability?: AvailabilityState
  document_id?: string
  source_id?: string
  rule_id?: string
  reason?: string
  expected_unknown?: string
}

export interface VisibleMaterials {
  document_ids?: string[]
  source_ids?: string[]
  rule_ids?: string[]
}

export interface ExperimentConditions {
  include_counterparty?: boolean
  hide_source_ids?: string[]
  natural_missing_source_ids?: string[]
  enable_source_audit?: boolean
  condition_type?: ConditionType
  protocol_basis?: ProtocolBasis | null
  stage?: string
  notes?: string
}

export interface ModelConfigSnapshot {
  provider?: string
  model?: string
  temperature?: number | null
}

export function isUnknown(value: string): boolean {
  return value === UNKNOWN
}

export function stripReference<T>(payload: T): T {
  if (Array.isArray(payload)) {
    return payload.map((item) => stripReference(item)) as T
  }
  if (payload && typeof payload === "object") {
    const result: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(payload)) {
      if (key === REFERENCE_FIELD) {
        continue
      }
      result[key] = stripReference(value)
    }
    return result as T
  }
  return payload
}
