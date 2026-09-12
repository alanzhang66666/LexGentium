"""Stable research identifiers. Case number is display-only, never a primary key."""
from __future__ import annotations

import re
import uuid
from typing import Optional

from pydantic import Field, field_validator, model_validator

from .base import ResearchModel
from .enums import CIVIL_DATASET_ID, DATASET_IDS, DatasetId, FORBIDDEN_DATASET_IDS

_CLUSTER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")
_DOCUMENT_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]*$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


def validate_dataset_id(value: str) -> DatasetId:
    if value in FORBIDDEN_DATASET_IDS or value == CIVIL_DATASET_ID:
        raise ValueError(
            f"dataset_id {value!r} is reserved for the civil corpus; "
            "research packs use only 'cisg' or 'enforcement'"
        )
    if value not in DATASET_IDS:
        raise ValueError(f"dataset_id must be one of {DATASET_IDS}, got {value!r}")
    return value  # type: ignore[return-value]


def validate_cluster_id(value: str) -> str:
    if not value or value.strip() != value:
        raise ValueError("cluster_id must be a non-empty trimmed token")
    if not _CLUSTER_RE.match(value):
        raise ValueError(
            "cluster_id must start with a letter and use [A-Za-z0-9._-]; "
            "do not use a bare case number as cluster_id"
        )
    return value


def validate_document_id(value: str) -> str:
    """Keep the original table-row / directory ordinal (e.g. '001')."""
    if not value or value.strip() != value:
        raise ValueError("document_id must be a non-empty trimmed ordinal")
    if not _DOCUMENT_RE.match(value):
        raise ValueError("document_id must keep the original ordinal token")
    return value


def validate_source_id(value: str) -> str:
    if not value or value.strip() != value:
        raise ValueError("source_id must be a non-empty trimmed token")
    if not _TOKEN_RE.match(value):
        raise ValueError("source_id must be a stable locator token")
    return value


def validate_rule_id(value: str) -> str:
    if not value or value.strip() != value:
        raise ValueError("rule_id must be a non-empty trimmed token")
    if not _TOKEN_RE.match(value):
        raise ValueError("rule_id must be a stable token")
    return value


def validate_rule_version(value: str) -> str:
    if not value or value.strip() != value:
        raise ValueError("rule_version must be a non-empty trimmed token")
    return value


def validate_pack_version(value: str) -> str:
    if not value or value.strip() != value:
        raise ValueError("pack_version must be a non-empty trimmed token")
    return value


def validate_run_id(value: str) -> str:
    if not value or value.strip() != value:
        raise ValueError("run_id must be a non-empty trimmed token")
    return value


def validate_report_id(value: str) -> str:
    try:
        parsed = uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("report_id must be a UUID string") from exc
    return str(parsed)


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex}"


def new_report_id() -> str:
    return str(uuid.uuid4())


class PackIdentity(ResearchModel):
    """Primary key of a frozen case pack. Not a case number."""

    dataset_id: DatasetId
    cluster_id: str
    pack_version: str

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


class DocumentIdentity(ResearchModel):
    dataset_id: DatasetId
    cluster_id: str
    document_id: str

    @field_validator("dataset_id")
    @classmethod
    def _dataset(cls, value: str) -> DatasetId:
        return validate_dataset_id(value)

    @field_validator("cluster_id")
    @classmethod
    def _cluster(cls, value: str) -> str:
        return validate_cluster_id(value)

    @field_validator("document_id")
    @classmethod
    def _document(cls, value: str) -> str:
        return validate_document_id(value)


class SourceIdentity(ResearchModel):
    dataset_id: DatasetId
    cluster_id: str
    document_id: str
    source_id: str

    @field_validator("dataset_id")
    @classmethod
    def _dataset(cls, value: str) -> DatasetId:
        return validate_dataset_id(value)

    @field_validator("cluster_id")
    @classmethod
    def _cluster(cls, value: str) -> str:
        return validate_cluster_id(value)

    @field_validator("document_id")
    @classmethod
    def _document(cls, value: str) -> str:
        return validate_document_id(value)

    @field_validator("source_id")
    @classmethod
    def _source(cls, value: str) -> str:
        return validate_source_id(value)


class RuleIdentity(ResearchModel):
    rule_id: str
    rule_version: str

    @field_validator("rule_id")
    @classmethod
    def _rule(cls, value: str) -> str:
        return validate_rule_id(value)

    @field_validator("rule_version")
    @classmethod
    def _version(cls, value: str) -> str:
        return validate_rule_version(value)


class RunIdentity(ResearchModel):
    run_id: str
    derived_from: Optional[str] = None
    session_id: Optional[str] = None

    @field_validator("run_id")
    @classmethod
    def _run(cls, value: str) -> str:
        return validate_run_id(value)

    @field_validator("derived_from")
    @classmethod
    def _parent(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return validate_run_id(value)


class ReportIdentity(ResearchModel):
    report_id: str
    run_id: str

    @field_validator("report_id", mode="before")
    @classmethod
    def _report(cls, value: object) -> str:
        return validate_report_id(str(value))

    @field_validator("run_id")
    @classmethod
    def _run(cls, value: str) -> str:
        return validate_run_id(value)


class CaseCaption(ResearchModel):
    """Display metadata. ``case_number`` is never a primary key."""

    case_name: str = ""
    case_number: str = ""
    court: str = ""
    date: str = ""
    source: str = ""
    procedure_chain: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _case_number_not_identity(self) -> CaseCaption:
        # Structural guard: a caption may record a number, but identity is elsewhere.
        return self
