"""Shared research enumerations. Values must match ``lib/research/enums.ts``."""
from __future__ import annotations

from typing import Literal, get_args

DatasetId = Literal["cisg", "enforcement"]
DATASET_IDS: tuple[DatasetId, ...] = get_args(DatasetId)

# Isolated from the domestic-civil corpus. Never a research dataset_id.
CIVIL_DATASET_ID = "dataset_1000"
FORBIDDEN_DATASET_IDS: frozenset[str] = frozenset({CIVIL_DATASET_ID})

TaskType = Literal["cisg_article79", "enforcement_nyc"]
TASK_TYPES: tuple[TaskType, ...] = get_args(TaskType)

ReviewState = Literal["pending", "tech_checked", "law_reviewed", "disputed"]
REVIEW_STATES: tuple[ReviewState, ...] = get_args(ReviewState)

SourceTier = Literal["historical", "researcher", "system"]
SOURCE_TIERS: tuple[SourceTier, ...] = get_args(SourceTier)

# Missing facts stay unknown. Do not invent a value to finish a run.
UNKNOWN: Literal["unknown"] = "unknown"
UnknownValue = Literal["unknown"]

StopReason = Literal["completed", "max_turns", "material_insufficient", "aborted", "unknown"]
STOP_REASONS: tuple[StopReason, ...] = get_args(StopReason)

SatisfiedLabel = Literal["yes", "no", "unknown"]
SATISFIED_LABELS: tuple[SatisfiedLabel, ...] = get_args(SatisfiedLabel)

CisgConclusionLabel = Literal["exempt", "not_exempt", "partial", "unknown"]
CISG_CONCLUSION_LABELS: tuple[CisgConclusionLabel, ...] = get_args(CisgConclusionLabel)

CisgArticle79ElementId = Literal[
    "impediment",
    "beyond_control",
    "unforeseeable",
    "unavoidable",
    "notice",
    "third_person",
    "duration",
    "other_remedies",
]
CISG_ART79_ELEMENT_IDS: tuple[CisgArticle79ElementId, ...] = get_args(CisgArticle79ElementId)

# Workbook 21 / 标签集 missing. Empty cells must become one of these on submit.
MissingCode = Literal["NR", "UV", "NA", "CF"]
MISSING_CODES: tuple[MissingCode, ...] = get_args(MissingCode)

# Workbook 21 / actor. claimant is the CISG sales-side alias of applicant.
SpeakerLabel = Literal[
    "applicant",
    "respondent",
    "claimant",
    "tribunal",
    "other",
    "researcher",
    "system",
    "NR",
    "UV",
]
SPEAKER_LABELS: tuple[SpeakerLabel, ...] = get_args(SpeakerLabel)

# Workbook 21 / nature. Not the same axis as source_tier.
SpeechType = Literal[
    "party_claim",
    "court_finding",
    "undisputed",
    "court_reasons",
    "court_operative",
    "procedural_record",
    "researcher_judgment",
]
SPEECH_TYPES: tuple[SpeechType, ...] = get_args(SpeechType)

# Workbook 21 / support.
SupportStatus = Literal["direct", "indirect", "unsupported", "conflict"]
SUPPORT_STATUSES: tuple[SupportStatus, ...] = get_args(SupportStatus)

# Workbook 21 / dispute.
DisclosureStatus = Literal["disputed", "undisputed", "undisclosed"]
DISCLOSURE_STATUSES: tuple[DisclosureStatus, ...] = get_args(DisclosureStatus)

# Workbook 21 / cisg.
CisgApplicableLabel = Literal[
    "applicable",
    "not_applicable",
    "assumed",
    "not_judged",
    "insufficient",
]
CISG_APPLICABLE_LABELS: tuple[CisgApplicableLabel, ...] = get_args(CisgApplicableLabel)

# Workbook 21 / handled.
HandledLabel = Literal["handled", "not_handled", "insufficient"]
HANDLED_LABELS: tuple[HandledLabel, ...] = get_args(HandledLabel)

# Workbook 21 / oldrelation. Collector F-column vs legal re-annotation.
OriginalLabelRelation = Literal["consistent", "corrected", "incomparable", "pending"]
ORIGINAL_LABEL_RELATIONS: tuple[OriginalLabelRelation, ...] = get_args(OriginalLabelRelation)

# Workbook 21 / elementresult. One element ≠ overall exemption.
ElementCourtResult = Literal[
    "satisfied",
    "not_satisfied",
    "not_handled",
    "insufficient",
    "not_applicable",
]
ELEMENT_COURT_RESULTS: tuple[ElementCourtResult, ...] = get_args(ElementCourtResult)

# Workbook 21 / datetype.
NoticeEventType = Literal[
    "sent",
    "attempted_service",
    "returned",
    "received",
    "deemed_service",
    "actual_knowledge",
    "objection",
    "hearing_opportunity",
    "other",
]
NOTICE_EVENT_TYPES: tuple[NoticeEventType, ...] = get_args(NoticeEventType)

# Workbook 21 / form.
SourceForm = Literal[
    "official_full",
    "official_abstract",
    "database_full",
    "reprint_full",
    "commentary",
    "later_restatement",
    "catalog_only",
    "UV",
]
SOURCE_FORMS: tuple[SourceForm, ...] = get_args(SourceForm)

# Workbook 21 / completeness.
CompletenessDegree = Literal["complete", "excerpt", "abstract", "missing_pages", "undetermined"]
COMPLETENESS_DEGREES: tuple[CompletenessDegree, ...] = get_args(CompletenessDegree)

# Workbook 21 / argumentkind. Pack-side annotation, not a live run CLAIM_ACTION.
ArgumentKind = Literal["historical", "researcher", "system", "teaching"]
ARGUMENT_KINDS: tuple[ArgumentKind, ...] = get_args(ArgumentKind)

# Workbook 21 / action on 12论证回应.
ArgumentAction = Literal[
    "first_raised",
    "maintain",
    "supplement",
    "correct",
    "withdraw",
    "admit_insufficient",
]
ARGUMENT_ACTIONS: tuple[ArgumentAction, ...] = get_args(ArgumentAction)

# Workbook 21 / relation. Runtime slice of 13依据关系.
EvidenceRelation = Literal[
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
]
EVIDENCE_RELATIONS: tuple[EvidenceRelation, ...] = get_args(EvidenceRelation)

# Workbook 21 / visibility.
VisibilityState = Literal["visible", "hidden", "stage_open", "evaluator_only"]
VISIBILITY_STATES: tuple[VisibilityState, ...] = get_args(VisibilityState)

# Workbook 21 / availability.
AvailabilityState = Literal["available", "natural_missing", "experimentally_hidden"]
AVAILABILITY_STATES: tuple[AvailabilityState, ...] = get_args(AvailabilityState)

# Workbook 21 / condition.
ConditionType = Literal[
    "baseline",
    "add_counterparty",
    "hide_materials",
    "enable_audit",
    "other",
]
CONDITION_TYPES: tuple[ConditionType, ...] = get_args(ConditionType)

# Workbook 21 / basis.
ProtocolBasis = Literal["historical_procedure", "research_design", "both_stated"]
PROTOCOL_BASES: tuple[ProtocolBasis, ...] = get_args(ProtocolBasis)

# Recommended visible_materials keys. Free-string roles are still allowed.
ROLE_APPLICANT = "applicant"
ROLE_RESPONDENT = "respondent"
ROLE_CLAIMANT = "claimant"
ROLE_TRIBUNAL = "tribunal"
ROLE_AUDITOR = "auditor"
ROLE_EVALUATOR = "evaluator"

RESEARCH_ROLES: tuple[str, ...] = (
    ROLE_APPLICANT,
    ROLE_RESPONDENT,
    ROLE_CLAIMANT,
    ROLE_TRIBUNAL,
    ROLE_AUDITOR,
    ROLE_EVALUATOR,
)

TASK_TYPE_BY_DATASET: dict[DatasetId, TaskType] = {
    "cisg": "cisg_article79",
    "enforcement": "enforcement_nyc",
}

# Evaluation answers live here. Must never enter a role view or model prompt.
REFERENCE_FIELD = "reference"
ROLE_VIEW_EXCLUDED_FIELDS: frozenset[str] = frozenset({REFERENCE_FIELD})

CONTRACT_SCHEMA_VERSION = "1"
