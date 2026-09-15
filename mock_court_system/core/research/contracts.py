"""Input / run / eval contracts. Field names must match ``lib/research/contracts.ts``."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import AliasChoices, Field, field_validator, model_validator

from .base import ResearchModel
from .enums import CONTRACT_SCHEMA_VERSION, DatasetId, StopReason, TaskType
from .ids import (
    PackIdentity,
    validate_cluster_id,
    validate_dataset_id,
    validate_pack_version,
    validate_report_id,
    validate_run_id,
)
from .shared import (
    ExperimentConditions,
    ModelConfigSnapshot,
    ReferenceLayer,
    ReviewRecord,
    TaskLabels,
    VisibilityGrant,
    VisibleMaterials,
)


class InputContract(ResearchModel):
    """Frozen experiment input. ``reference`` is evaluator-only."""

    schema_version: str = CONTRACT_SCHEMA_VERSION
    dataset_id: DatasetId
    cluster_id: str
    pack_version: str
    task_type: TaskType
    visible_materials: dict[str, VisibleMaterials]
    visibility_grants: list[VisibilityGrant] = Field(default_factory=list)
    experiment_conditions: ExperimentConditions
    # Pydantic reserves class-level ``model_config``; JSON/TS field is still model_config.
    model_config_snapshot: ModelConfigSnapshot = Field(
        default_factory=ModelConfigSnapshot,
        validation_alias=AliasChoices("model_config", "model_config_snapshot"),
        serialization_alias="model_config",
    )
    task_labels: Optional[TaskLabels] = None
    reference: Optional[ReferenceLayer] = None

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
    def _labels_match_task(self) -> InputContract:
        if self.task_labels is not None and self.task_labels.task_type != self.task_type:
            raise ValueError("task_labels.task_type must match task_type")
        return self

    def pack_identity(self) -> PackIdentity:
        return PackIdentity(
            dataset_id=self.dataset_id,
            cluster_id=self.cluster_id,
            pack_version=self.pack_version,
        )

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        kwargs.setdefault("by_alias", True)
        return super().model_dump(*args, **kwargs)

    def model_dump_json(self, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        kwargs.setdefault("by_alias", True)
        return super().model_dump_json(*args, **kwargs)


class RunUtterance(ResearchModel):
    turn: int
    role: str
    text: str
    source_ids: list[str] = Field(default_factory=list)


class RetrievedSpan(ResearchModel):
    source_id: str
    document_id: str
    quote: str = ""
    score: Optional[float] = None


class RunContract(ResearchModel):
    """Skeleton of one experiment run. Condition changes mint a new run_id."""

    schema_version: str = CONTRACT_SCHEMA_VERSION
    run_id: str
    derived_from: Optional[str] = None
    session_id: Optional[str] = None
    dataset_id: DatasetId
    cluster_id: str
    pack_version: str
    task_type: TaskType
    materials_hash: str = ""
    utterances: list[RunUtterance] = Field(default_factory=list)
    retrieved_spans: list[RetrievedSpan] = Field(default_factory=list)
    stop_reason: Optional[StopReason] = None
    created_at: str = ""

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


class EvalContract(ResearchModel):
    """Skeleton evaluation record. ``report_id`` is a UUID bound to one run_id."""

    schema_version: str = CONTRACT_SCHEMA_VERSION
    report_id: str
    run_id: str
    reference_version: str = ""
    rubric_version: str = ""
    machine_checks: dict[str, Any] = Field(default_factory=dict)
    legal_quality: dict[str, Any] = Field(default_factory=dict)
    review_records: list[ReviewRecord] = Field(default_factory=list)
    created_at: str = ""

    @field_validator("report_id", mode="before")
    @classmethod
    def _report(cls, value: object) -> str:
        return validate_report_id(str(value))

    @field_validator("run_id")
    @classmethod
    def _run(cls, value: str) -> str:
        return validate_run_id(value)
