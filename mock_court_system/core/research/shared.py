"""Shared annotation, source, rule, and task-label components."""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import Field, field_validator, model_validator

from .base import ResearchModel
from .enums import (
    UNKNOWN,
    ArgumentAction,
    ArgumentKind,
    AvailabilityState,
    CisgApplicableLabel,
    CisgArticle79ElementId,
    CisgConclusionLabel,
    CompletenessDegree,
    ConditionType,
    DisclosureStatus,
    ElementCourtResult,
    EvidenceRelation,
    HandledLabel,
    MissingCode,
    NoticeEventType,
    OriginalLabelRelation,
    ProtocolBasis,
    ReviewState,
    SatisfiedLabel,
    SourceForm,
    SourceTier,
    SpeakerLabel,
    SpeechType,
    SupportStatus,
    VisibilityState,
)
from .field_keys import validate_gap_related_field
from .ids import (
    validate_document_id,
    validate_rule_id,
    validate_rule_version,
    validate_source_id,
)


def _historical_needs_source(source_tier: SourceTier, source_ids: list[str], text: str) -> None:
    if source_tier == "historical" and text != UNKNOWN and text.strip() and not source_ids:
        raise ValueError("historical values must cite source_ids or be marked unknown")


def _conflict_needs_values(missing_code: Optional[MissingCode], conflict_values: list[str]) -> None:
    if missing_code == "CF" and not conflict_values:
        raise ValueError("missing_code CF must list conflict_values; do not pick a winner")


class RevisionEntry(ResearchModel):
    at: str = ""
    by: str = ""
    from_value: Optional[Any] = None
    to_value: Optional[Any] = None
    note: str = ""


class ReviewRecord(ResearchModel):
    review_state: ReviewState
    reviewer: str = ""
    reviewed_at: str = ""
    note: str = ""


class OriginalRef(ResearchModel):
    """Workbook / catalog pointer. Not a primary key."""

    raw_id: str = ""
    raw_locator: str = ""
    catalog_no: str = ""
    workbook_sheet: str = ""


class SourceAnchor(ResearchModel):
    """Click-back locator into an original document."""

    source_id: str
    document_id: str
    locator: str = ""
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    quote: str = ""
    source_tier: SourceTier
    review_state: ReviewState = "pending"
    notes: str = ""

    @field_validator("source_id")
    @classmethod
    def _source(cls, value: str) -> str:
        return validate_source_id(value)

    @field_validator("document_id")
    @classmethod
    def _document(cls, value: str) -> str:
        return validate_document_id(value)


class ProvenanceFields(ResearchModel):
    source_ids: list[str] = Field(default_factory=list)
    source_tier: SourceTier
    review_state: ReviewState = "pending"
    notes: str = ""
    revisions: list[RevisionEntry] = Field(default_factory=list)
    speaker: Optional[SpeakerLabel] = None
    speech_type: Optional[SpeechType] = None
    support_status: Optional[SupportStatus] = None
    disclosure_status: Optional[DisclosureStatus] = None
    missing_code: Optional[MissingCode] = None
    conflict_values: list[str] = Field(default_factory=list)
    original_ref: Optional[OriginalRef] = None

    @field_validator("source_ids")
    @classmethod
    def _sources(cls, value: list[str]) -> list[str]:
        return [validate_source_id(item) for item in value]

    @model_validator(mode="after")
    def _conflict(self) -> ProvenanceFields:
        _conflict_needs_values(self.missing_code, self.conflict_values)
        return self


class AnnotatedValue(ProvenanceFields):
    """One extracted cell in a six-column pack (or any shared field)."""

    item_id: str
    field_key: str
    value: str

    @model_validator(mode="after")
    def _provenance(self) -> AnnotatedValue:
        _historical_needs_source(self.source_tier, self.source_ids, self.value)
        return self


class DocumentRecord(ResearchModel):
    document_id: str
    title: str = ""
    filename: str = ""
    source_tier: SourceTier
    language: str = ""
    review_state: ReviewState = "pending"
    notes: str = ""
    original_ref: Optional[OriginalRef] = None
    source_form: Optional[SourceForm] = None
    completeness: Optional[CompletenessDegree] = None

    @field_validator("document_id")
    @classmethod
    def _document(cls, value: str) -> str:
        return validate_document_id(value)

    @model_validator(mode="after")
    def _filename_follows_ordinal(self) -> DocumentRecord:
        expected = f"{self.document_id}.txt"
        if self.filename and self.filename != expected:
            raise ValueError(
                f"filename must keep the original ordinal; expected {expected!r}, got {self.filename!r}"
            )
        if not self.filename:
            self.filename = expected
        return self


class PartyClaim(ProvenanceFields):
    item_id: str
    party: str
    claim_text: str
    facts: str = ""
    norms: str = ""
    reasoning: str = ""

    @model_validator(mode="after")
    def _provenance(self) -> PartyClaim:
        _historical_needs_source(self.source_tier, self.source_ids, self.claim_text)
        return self


class CourtFinding(ProvenanceFields):
    item_id: str
    finding: str
    reasons: str = ""

    @model_validator(mode="after")
    def _provenance(self) -> CourtFinding:
        _historical_needs_source(self.source_tier, self.source_ids, self.finding)
        return self


class LegalBasis(ProvenanceFields):
    item_id: str
    rule_id: str
    rule_version: str
    citation: str = ""
    application_note: str = ""

    @field_validator("rule_id")
    @classmethod
    def _rule(cls, value: str) -> str:
        return validate_rule_id(value)

    @field_validator("rule_version")
    @classmethod
    def _version(cls, value: str) -> str:
        return validate_rule_version(value)


class MaterialGap(ResearchModel):
    gap_id: str
    description: str
    related_field: str = ""
    related_item_ids: list[str] = Field(default_factory=list)
    status: Literal["unknown", "missing_document", "untranslated"] = "unknown"
    missing_code: Optional[MissingCode] = None
    conflict_values: list[str] = Field(default_factory=list)
    checked: str = ""
    impact: str = ""
    blocks: Optional[SatisfiedLabel] = None
    review_state: ReviewState = "pending"
    notes: str = ""

    @model_validator(mode="after")
    def _conflict(self) -> MaterialGap:
        _conflict_needs_values(self.missing_code, self.conflict_values)
        if self.related_field:
            validate_gap_related_field(self.related_field)
        return self


class RuleCard(ResearchModel):
    rule_id: str
    rule_version: str
    title: str = ""
    text: str = ""
    source: str = ""
    applicability_conditions: list[str] = Field(default_factory=list)
    controversies: list[str] = Field(default_factory=list)
    usage_boundary: str = ""
    source_ids: list[str] = Field(default_factory=list)
    source_tier: SourceTier = "historical"
    review_state: ReviewState = "pending"
    notes: str = ""

    @field_validator("rule_id")
    @classmethod
    def _rule(cls, value: str) -> str:
        return validate_rule_id(value)

    @field_validator("rule_version")
    @classmethod
    def _version(cls, value: str) -> str:
        return validate_rule_version(value)

    @field_validator("source_ids")
    @classmethod
    def _sources(cls, value: list[str]) -> list[str]:
        return [validate_source_id(item) for item in value]


class RoleProtocolEntry(ResearchModel):
    """Skeleton for round 2. Duties / turns / stop rules stay empty in phase 1."""

    role: str
    duties: list[str] = Field(default_factory=list)
    turn_order: Optional[int] = None
    stop_conditions: list[str] = Field(default_factory=list)


class CisgJudgmentObject(ResearchModel):
    """One Art. 79 unit: who × obligation × period. Not the case cluster."""

    judgment_id: str
    claimant: str = ""
    obligation: str = ""
    request: str = ""
    period: str = ""
    task: str = ""
    cisg_applicable: CisgApplicableLabel = "not_judged"
    claim_raised: SatisfiedLabel = "unknown"
    handled: HandledLabel = "insufficient"
    result: CisgConclusionLabel = "unknown"
    original_label: str = ""
    original_label_relation: OriginalLabelRelation = "pending"
    notes: str = ""


class CisgArticle79Element(ProvenanceFields):
    element_id: CisgArticle79ElementId
    label: str
    satisfied: SatisfiedLabel = "unknown"
    value: str = ""
    judgment_id: str = ""
    claimant_view: str = ""
    opponent_view: str = ""
    court_result: Optional[ElementCourtResult] = None

    @model_validator(mode="after")
    def _provenance(self) -> CisgArticle79Element:
        text = self.value or self.label
        _historical_needs_source(self.source_tier, self.source_ids, text)
        return self


class CisgArticle79Labels(ResearchModel):
    task_type: Literal["cisg_article79"] = "cisg_article79"
    article: str = "79"
    judgments: list[CisgJudgmentObject] = Field(default_factory=list)
    elements: list[CisgArticle79Element] = Field(default_factory=list)
    conclusion_label: CisgConclusionLabel = "unknown"
    conclusion_note: str = ""
    original_label: str = ""
    original_label_relation: Optional[OriginalLabelRelation] = None
    review_state: ReviewState = "pending"


class NoticeEvent(ProvenanceFields):
    """One notice, service attempt, or key procedural act. Workbook sheet 10."""

    event_id: str
    document_id: str = ""
    procedure_id: str = ""
    notice_name: str = ""
    event_type: NoticeEventType = "other"
    sender: str = ""
    recipient: str = ""
    channel: str = ""
    address: str = ""
    address_basis: str = ""
    date_raw: str = UNKNOWN
    arrival: str = UNKNOWN
    language: str = ""
    content: str = ""
    opportunity: str = ""
    objection: str = ""
    court_view: str = ""

    @field_validator("document_id")
    @classmethod
    def _document(cls, value: str) -> str:
        if not value:
            return value
        return validate_document_id(value)


class EnforcementNycLabels(ResearchModel):
    task_type: Literal["enforcement_nyc"] = "enforcement_nyc"
    enforcement_forum: str = UNKNOWN
    procedure_type: str = UNKNOWN
    convention_issues: list[str] = Field(default_factory=list)
    notice_events: list[NoticeEvent] = Field(default_factory=list)
    role_protocol: list[RoleProtocolEntry] = Field(default_factory=list)
    review_state: ReviewState = "pending"


TaskLabels = Annotated[
    Union[CisgArticle79Labels, EnforcementNycLabels],
    Field(discriminator="task_type"),
]


class AcceptablePath(ResearchModel):
    path_id: str
    conclusion_label: str = ""
    requires: list[str] = Field(default_factory=list)
    requires_any: list[str] = Field(default_factory=list)
    notes: str = ""


class ReferenceLayer(ResearchModel):
    """Evaluation answers. Must not appear in a role view."""

    reference_version: str
    gold_labels: dict[str, Any] = Field(default_factory=dict)
    acceptable_paths: list[AcceptablePath] = Field(default_factory=list)
    notes: str = ""


class ArgumentRecord(ProvenanceFields):
    """One annotated argument or reply. Workbook sheet 12; not a live run event."""

    argument_id: str
    target_id: str
    document_id: str = ""
    kind: ArgumentKind = "researcher"
    claim: str
    reasoning: str = ""
    assumptions: str = ""
    rebuttal_target: str = ""
    target_part: str = ""
    action: ArgumentAction = "first_raised"
    fact_ids: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    stage: str = ""

    @field_validator("document_id")
    @classmethod
    def _document(cls, value: str) -> str:
        if not value:
            return value
        return validate_document_id(value)

    @field_validator("rule_ids")
    @classmethod
    def _rules(cls, value: list[str]) -> list[str]:
        return [validate_rule_id(item) for item in value]

    @model_validator(mode="after")
    def _provenance(self) -> ArgumentRecord:
        _historical_needs_source(self.source_tier, self.source_ids, self.claim)
        return self


class EvidenceLink(ResearchModel):
    """One typed edge. Workbook sheet 13; one relation per row."""

    link_id: str
    object_id: str
    relation: EvidenceRelation
    evidence_id: str
    field: str = ""
    purpose: str = ""
    limits: str = ""


class VisibilityGrant(ResearchModel):
    """One fragment × role × stage permission. Workbook sheet 16."""

    grant_id: str
    role: str
    stage: str = ""
    visibility: VisibilityState = "visible"
    availability: AvailabilityState = "available"
    document_id: str = ""
    source_id: str = ""
    rule_id: str = ""
    reason: str = ""
    expected_unknown: str = ""

    @field_validator("document_id")
    @classmethod
    def _document(cls, value: str) -> str:
        if not value:
            return value
        return validate_document_id(value)

    @field_validator("source_id")
    @classmethod
    def _source(cls, value: str) -> str:
        if not value:
            return value
        return validate_source_id(value)

    @field_validator("rule_id")
    @classmethod
    def _rule(cls, value: str) -> str:
        if not value:
            return value
        return validate_rule_id(value)


class VisibleMaterials(ResearchModel):
    document_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)

    @field_validator("document_ids")
    @classmethod
    def _docs(cls, value: list[str]) -> list[str]:
        return [validate_document_id(item) for item in value]

    @field_validator("source_ids")
    @classmethod
    def _sources(cls, value: list[str]) -> list[str]:
        return [validate_source_id(item) for item in value]

    @field_validator("rule_ids")
    @classmethod
    def _rules(cls, value: list[str]) -> list[str]:
        return [validate_rule_id(item) for item in value]


class ExperimentConditions(ResearchModel):
    include_counterparty: bool = True
    hide_source_ids: list[str] = Field(default_factory=list)
    natural_missing_source_ids: list[str] = Field(default_factory=list)
    enable_source_audit: bool = False
    condition_type: ConditionType = "baseline"
    protocol_basis: Optional[ProtocolBasis] = None
    stage: str = ""
    notes: str = ""

    @field_validator("hide_source_ids")
    @classmethod
    def _hidden(cls, value: list[str]) -> list[str]:
        return [validate_source_id(item) for item in value]

    @field_validator("natural_missing_source_ids")
    @classmethod
    def _natural(cls, value: list[str]) -> list[str]:
        return [validate_source_id(item) for item in value]

    @model_validator(mode="after")
    def _hide_is_not_natural(self) -> ExperimentConditions:
        overlap = set(self.hide_source_ids) & set(self.natural_missing_source_ids)
        if overlap:
            raise ValueError(
                "natural_missing_source_ids cannot also be hide_source_ids; "
                f"overlap={sorted(overlap)}"
            )
        return self


class ModelConfigSnapshot(ResearchModel):
    provider: str = ""
    model: str = ""
    temperature: Optional[float] = None
