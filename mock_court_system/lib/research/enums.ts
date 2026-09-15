/** Shared research enumerations. Values must match ``core/research/enums.py``. */

export const DATASET_IDS = ["cisg", "enforcement"] as const
export type DatasetId = (typeof DATASET_IDS)[number]

export const CIVIL_DATASET_ID = "dataset_1000"
export const FORBIDDEN_DATASET_IDS = [CIVIL_DATASET_ID] as const

export const TASK_TYPES = ["cisg_article79", "enforcement_nyc"] as const
export type TaskType = (typeof TASK_TYPES)[number]

export const REVIEW_STATES = ["pending", "tech_checked", "law_reviewed", "disputed"] as const
export type ReviewState = (typeof REVIEW_STATES)[number]

export const SOURCE_TIERS = ["historical", "researcher", "system"] as const
export type SourceTier = (typeof SOURCE_TIERS)[number]

export const UNKNOWN = "unknown" as const
export type UnknownValue = typeof UNKNOWN

export const STOP_REASONS = [
  "completed",
  "max_turns",
  "material_insufficient",
  "aborted",
  "unknown",
] as const
export type StopReason = (typeof STOP_REASONS)[number]

export const SATISFIED_LABELS = ["yes", "no", "unknown"] as const
export type SatisfiedLabel = (typeof SATISFIED_LABELS)[number]

export const CISG_CONCLUSION_LABELS = ["exempt", "not_exempt", "partial", "unknown"] as const
export type CisgConclusionLabel = (typeof CISG_CONCLUSION_LABELS)[number]

export const CISG_ART79_ELEMENT_IDS = [
  "impediment",
  "beyond_control",
  "unforeseeable",
  "unavoidable",
  "notice",
  "third_person",
  "duration",
  "other_remedies",
] as const
export type CisgArticle79ElementId = (typeof CISG_ART79_ELEMENT_IDS)[number]

export const MISSING_CODES = ["NR", "UV", "NA", "CF"] as const
export type MissingCode = (typeof MISSING_CODES)[number]

export const SPEAKER_LABELS = [
  "applicant",
  "respondent",
  "claimant",
  "tribunal",
  "other",
  "researcher",
  "system",
  "NR",
  "UV",
] as const
export type SpeakerLabel = (typeof SPEAKER_LABELS)[number]

export const SPEECH_TYPES = [
  "party_claim",
  "court_finding",
  "undisputed",
  "court_reasons",
  "court_operative",
  "procedural_record",
  "researcher_judgment",
] as const
export type SpeechType = (typeof SPEECH_TYPES)[number]

export const SUPPORT_STATUSES = ["direct", "indirect", "unsupported", "conflict"] as const
export type SupportStatus = (typeof SUPPORT_STATUSES)[number]

export const DISCLOSURE_STATUSES = ["disputed", "undisputed", "undisclosed"] as const
export type DisclosureStatus = (typeof DISCLOSURE_STATUSES)[number]

export const CISG_APPLICABLE_LABELS = [
  "applicable",
  "not_applicable",
  "assumed",
  "not_judged",
  "insufficient",
] as const
export type CisgApplicableLabel = (typeof CISG_APPLICABLE_LABELS)[number]

export const HANDLED_LABELS = ["handled", "not_handled", "insufficient"] as const
export type HandledLabel = (typeof HANDLED_LABELS)[number]

export const ORIGINAL_LABEL_RELATIONS = [
  "consistent",
  "corrected",
  "incomparable",
  "pending",
] as const
export type OriginalLabelRelation = (typeof ORIGINAL_LABEL_RELATIONS)[number]

export const ELEMENT_COURT_RESULTS = [
  "satisfied",
  "not_satisfied",
  "not_handled",
  "insufficient",
  "not_applicable",
] as const
export type ElementCourtResult = (typeof ELEMENT_COURT_RESULTS)[number]

export const NOTICE_EVENT_TYPES = [
  "sent",
  "attempted_service",
  "returned",
  "received",
  "deemed_service",
  "actual_knowledge",
  "objection",
  "hearing_opportunity",
  "other",
] as const
export type NoticeEventType = (typeof NOTICE_EVENT_TYPES)[number]

export const SOURCE_FORMS = [
  "official_full",
  "official_abstract",
  "database_full",
  "reprint_full",
  "commentary",
  "later_restatement",
  "catalog_only",
  "UV",
] as const
export type SourceForm = (typeof SOURCE_FORMS)[number]

export const COMPLETENESS_DEGREES = [
  "complete",
  "excerpt",
  "abstract",
  "missing_pages",
  "undetermined",
] as const
export type CompletenessDegree = (typeof COMPLETENESS_DEGREES)[number]

export const ARGUMENT_KINDS = ["historical", "researcher", "system", "teaching"] as const
export type ArgumentKind = (typeof ARGUMENT_KINDS)[number]

export const ARGUMENT_ACTIONS = [
  "first_raised",
  "maintain",
  "supplement",
  "correct",
  "withdraw",
  "admit_insufficient",
] as const
export type ArgumentAction = (typeof ARGUMENT_ACTIONS)[number]

export const EVIDENCE_RELATIONS = [
  "original_record",
  "source_to_document",
  "source_support",
  "fact_basis",
  "rule_basis",
  "rebuttal_target",
  "same_cluster",
  "related_procedure",
  "related_award",
  "prior_document",
  "translation",
  "duplicate_candidate",
  "same_split",
  "alternate_source",
  "eval_basis",
  "review_basis",
  "other",
] as const
export type EvidenceRelation = (typeof EVIDENCE_RELATIONS)[number]

export const VISIBILITY_STATES = ["visible", "hidden", "stage_open", "evaluator_only"] as const
export type VisibilityState = (typeof VISIBILITY_STATES)[number]

export const AVAILABILITY_STATES = [
  "available",
  "natural_missing",
  "experimentally_hidden",
] as const
export type AvailabilityState = (typeof AVAILABILITY_STATES)[number]

export const CONDITION_TYPES = [
  "baseline",
  "add_counterparty",
  "hide_materials",
  "enable_audit",
  "other",
] as const
export type ConditionType = (typeof CONDITION_TYPES)[number]

export const PROTOCOL_BASES = ["historical_procedure", "research_design", "both_stated"] as const
export type ProtocolBasis = (typeof PROTOCOL_BASES)[number]

export const ROLE_APPLICANT = "applicant"
export const ROLE_RESPONDENT = "respondent"
export const ROLE_CLAIMANT = "claimant"
export const ROLE_TRIBUNAL = "tribunal"
export const ROLE_AUDITOR = "auditor"
export const ROLE_EVALUATOR = "evaluator"

export const RESEARCH_ROLES = [
  ROLE_APPLICANT,
  ROLE_RESPONDENT,
  ROLE_CLAIMANT,
  ROLE_TRIBUNAL,
  ROLE_AUDITOR,
  ROLE_EVALUATOR,
] as const

export const TASK_TYPE_BY_DATASET: Record<DatasetId, TaskType> = {
  cisg: "cisg_article79",
  enforcement: "enforcement_nyc",
}

export const REFERENCE_FIELD = "reference"
export const ROLE_VIEW_EXCLUDED_FIELDS = [REFERENCE_FIELD] as const

export const CONTRACT_SCHEMA_VERSION = "1"

export function isDatasetId(value: string): value is DatasetId {
  return (DATASET_IDS as readonly string[]).includes(value)
}

export function isTaskType(value: string): value is TaskType {
  return (TASK_TYPES as readonly string[]).includes(value)
}

export function isReviewState(value: string): value is ReviewState {
  return (REVIEW_STATES as readonly string[]).includes(value)
}

export function isSourceTier(value: string): value is SourceTier {
  return (SOURCE_TIERS as readonly string[]).includes(value)
}
