"""Six-column research pack. Field names must match ``lib/research/packs.ts``."""
from __future__ import annotations

from typing import Optional

from pydantic import Field, field_validator, model_validator

from .base import ResearchModel
from .enums import CONTRACT_SCHEMA_VERSION, DatasetId, ReviewState, TASK_TYPE_BY_DATASET, TaskType
from .field_keys import validate_fact_field_key, validate_gap_related_field
from .ids import CaseCaption, PackIdentity, validate_cluster_id, validate_dataset_id, validate_pack_version
from .shared import (
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
)


SIX_COLUMN_FIELDS: tuple[str, ...] = (
    "procedural_facts",
    "party_claims",
    "court_findings",
    "legal_bases",
    "material_gaps",
    "source_anchors",
)


class ResearchPack(ResearchModel):
    schema_version: str = CONTRACT_SCHEMA_VERSION
    dataset_id: DatasetId
    cluster_id: str
    pack_version: str
    task_type: TaskType
    caption: CaseCaption
    documents: list[DocumentRecord] = Field(default_factory=list)
    procedural_facts: list[AnnotatedValue] = Field(default_factory=list)
    party_claims: list[PartyClaim] = Field(default_factory=list)
    court_findings: list[CourtFinding] = Field(default_factory=list)
    legal_bases: list[LegalBasis] = Field(default_factory=list)
    material_gaps: list[MaterialGap] = Field(default_factory=list)
    source_anchors: list[SourceAnchor] = Field(default_factory=list)
    argument_records: list[ArgumentRecord] = Field(default_factory=list)
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    rules: list[RuleCard] = Field(default_factory=list)
    task_labels: TaskLabels
    reference: Optional[ReferenceLayer] = None
    review_state: ReviewState = "pending"
    review_records: list[ReviewRecord] = Field(default_factory=list)
    notes: str = ""

    @field_validator("dataset_id")
    @classmethod
    def _dataset(cls, value: str) -> DatasetId:
        return validate_dataset_id(value)

    @field_validator("cluster_id")
    @classmethod
    def _cluster(cls, value: str) -> str:
        return validate_cluster_id(value)

    @field_validator("pack_version")
    @classmethod
    def _pack_version(cls, value: str) -> str:
        return validate_pack_version(value)

    @model_validator(mode="after")
    def _consistency(self) -> ResearchPack:
        expected_task = TASK_TYPE_BY_DATASET[self.dataset_id]
        if self.task_type != expected_task:
            raise ValueError(
                f"dataset_id {self.dataset_id!r} must use task_type {expected_task!r}"
            )
        if self.task_labels.task_type != self.task_type:
            raise ValueError("task_labels.task_type must match task_type")
        document_ids = {doc.document_id for doc in self.documents}
        for anchor in self.source_anchors:
            if anchor.document_id not in document_ids:
                raise ValueError(
                    f"source_id {anchor.source_id!r} points at unknown document_id {anchor.document_id!r}"
                )
        for item in self.procedural_facts:
            validate_fact_field_key(self.task_type, item.field_key)
        for gap in self.material_gaps:
            if gap.related_field:
                validate_gap_related_field(gap.related_field)
        labels = self.task_labels
        if labels.task_type == "enforcement_nyc":
            for event in labels.notice_events:
                if event.document_id and event.document_id not in document_ids:
                    raise ValueError(
                        f"notice event {event.event_id!r} points at unknown "
                        f"document_id {event.document_id!r}"
                    )
        if labels.task_type == "cisg_article79":
            judgment_ids = {row.judgment_id for row in labels.judgments}
            for element in labels.elements:
                if element.judgment_id and element.judgment_id not in judgment_ids:
                    raise ValueError(
                        f"element {element.element_id!r} points at unknown "
                        f"judgment_id {element.judgment_id!r}"
                    )
        known_ids = set(document_ids)
        known_ids.update(doc.document_id for doc in self.documents)
        known_ids.update(item.item_id for item in self.procedural_facts)
        known_ids.update(item.item_id for item in self.party_claims)
        known_ids.update(item.item_id for item in self.court_findings)
        known_ids.update(item.item_id for item in self.legal_bases)
        known_ids.update(gap.gap_id for gap in self.material_gaps)
        known_ids.update(anchor.source_id for anchor in self.source_anchors)
        known_ids.update(rule.rule_id for rule in self.rules)
        if labels.task_type == "enforcement_nyc":
            known_ids.update(event.event_id for event in labels.notice_events)
        if labels.task_type == "cisg_article79":
            known_ids.update(row.judgment_id for row in labels.judgments)
            known_ids.update(element.element_id for element in labels.elements)
        argument_ids = {row.argument_id for row in self.argument_records}
        known_ids.update(argument_ids)
        for row in self.argument_records:
            if row.document_id and row.document_id not in document_ids:
                raise ValueError(
                    f"argument {row.argument_id!r} points at unknown "
                    f"document_id {row.document_id!r}"
                )
            if row.rebuttal_target and row.rebuttal_target not in argument_ids:
                raise ValueError(
                    f"argument {row.argument_id!r} rebuttal_target "
                    f"{row.rebuttal_target!r} is not an argument_id"
                )
            for fact_id in row.fact_ids:
                if fact_id not in known_ids:
                    raise ValueError(
                        f"argument {row.argument_id!r} fact_id {fact_id!r} is unknown"
                    )
            for rule_id in row.rule_ids:
                if rule_id not in known_ids:
                    raise ValueError(
                        f"argument {row.argument_id!r} rule_id {rule_id!r} is unknown"
                    )
        for link in self.evidence_links:
            if link.object_id not in known_ids:
                raise ValueError(
                    f"evidence link {link.link_id!r} object_id {link.object_id!r} is unknown"
                )
            if link.evidence_id not in known_ids:
                raise ValueError(
                    f"evidence link {link.link_id!r} evidence_id {link.evidence_id!r} is unknown"
                )
        return self

    def pack_identity(self) -> PackIdentity:
        return PackIdentity(
            dataset_id=self.dataset_id,
            cluster_id=self.cluster_id,
            pack_version=self.pack_version,
        )


class PackSummary(ResearchModel):
    dataset_id: DatasetId
    cluster_id: str
    pack_version: str
    task_type: TaskType
    case_name: str = ""
    review_state: ReviewState = "pending"
    document_ids: list[str] = Field(default_factory=list)
