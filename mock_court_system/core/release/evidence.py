"""Release manifest / evidence / gap 模型（design §14，Task 10.1）。

- 每条 evidence 绑定完整 Version/Commit identity、命令、环境、时间、
  duration、exit code、sample count、artifact digest 与 correlation context。
- Gap 强制 one-of primary classification；``engineering_blocker`` 未 closed
  时计入 blocker，内容/数据缺口只披露不加 blocker。
- runtime data / evidence root 在 immutable source artifacts 之外。
"""
from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.fingerprint import canonical_digest
from core.release.version import VERSION_ID

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class VersionCommitError(ValueError):
    """version/commit identity 不完整或不匹配。"""


@dataclass(frozen=True)
class VersionCommitIdentity:
    """发布证据与 manifest 必须绑定的完整身份。"""

    version_id: str
    commit_id: str

    def validate(self) -> None:
        if self.version_id != VERSION_ID:
            raise VersionCommitError(
                f"version mismatch: {self.version_id} != {VERSION_ID}"
            )
        if not _COMMIT_RE.match(self.commit_id or ""):
            raise VersionCommitError("commit_id must be a full 40-hex git sha")

    def is_bound(self) -> bool:
        try:
            self.validate()
            return True
        except VersionCommitError:
            return False


class EvidenceResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    TIMEOUT = "timeout"
    INVALID = "invalid"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class EvidenceRecord:
    """一次发布检查的执行证据（design: EvidenceRecord）。"""

    evidence_id: str
    check_id: str
    version_id: str
    commit_id: str
    command: str
    environment_identity: str
    started_at: str
    duration_ms: int
    exit_code: int
    result: str
    sample_count: int = 0
    artifact_digest: str = ""
    correlation_context: Dict[str, str] = field(default_factory=dict)

    def identity(self) -> VersionCommitIdentity:
        return VersionCommitIdentity(self.version_id, self.commit_id)

    def missing_fields(self) -> Tuple[str, ...]:
        """fail-closed 必填字段检查；返回缺失字段名。"""
        missing = []
        for name in (
            "evidence_id",
            "check_id",
            "version_id",
            "commit_id",
            "command",
            "environment_identity",
            "started_at",
        ):
            if not getattr(self, name):
                missing.append(name)
        if self.duration_ms is None or self.duration_ms < 0:
            missing.append("duration_ms")
        if not self.identity().is_bound():
            missing.append("version_commit_binding")
        return tuple(missing)

    def is_valid_for_gate(self, *, min_samples: int = 0) -> bool:
        """任何 fail/timeout/样本不足/关联缺失/commit 不一致都 fail closed。"""
        if self.missing_fields():
            return False
        if self.result != EvidenceResult.PASS.value:
            return False
        if self.exit_code != 0:
            return False
        if min_samples and self.sample_count < min_samples:
            return False
        # Req 18.13: Correlation_Context 缺失即拒绝（缺失字段不生成伪值）
        if not self.correlation_context:
            return False
        return True

    def digest(self) -> str:
        return canonical_digest(asdict(self))


class GapClassification(str, Enum):
    ENGINEERING_BLOCKER = "engineering_blocker"
    LEGAL_CONTENT_GAP = "legal_content_gap"
    DATA_LIMITATION = "data_limitation"
    ACCEPTED_RISK = "accepted_risk"
    OUT_OF_SCOPE = "out_of_scope"


class GapStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True)
class GapRecord:
    """Gap register 条目：恰一个 primary classification。"""

    gap_id: str
    classification: str
    trigger: str
    expected: str
    actual: str
    owner: str
    status: str = GapStatus.OPEN.value
    evidence_link: str = ""
    approved_by: str = ""
    approved_at: str = ""

    def __post_init__(self):
        if self.classification not in {c.value for c in GapClassification}:
            raise ValueError(f"unknown gap classification: {self.classification}")
        if self.status not in {s.value for s in GapStatus}:
            raise ValueError(f"unknown gap status: {self.status}")
        # accepted_risk 未关闭时必须带审批字段
        if (
            self.classification == GapClassification.ACCEPTED_RISK.value
            and self.status == GapStatus.OPEN.value
            and not self.approved_by
        ):
            raise ValueError("open accepted_risk requires approved_by")

    def is_engineering_blocker(self) -> bool:
        return (
            self.classification == GapClassification.ENGINEERING_BLOCKER.value
            and self.status == GapStatus.OPEN.value
        )

    def digest(self) -> str:
        return canonical_digest(asdict(self))


def engineering_blocker_count(gaps: List[GapRecord]) -> int:
    """仅 open engineering_blocker 计入；内容/数据缺口不影响 blocker count。"""
    return sum(1 for g in gaps if g.is_engineering_blocker())


def open_gaps(gaps: List[GapRecord]) -> List[GapRecord]:
    return [g for g in gaps if g.status == GapStatus.OPEN.value]


@dataclass(frozen=True)
class InventoryDisclosure:
    """Property 59：manifest 必须分别披露的内容/数据状态。"""

    formal_research_pack_count: int
    fixture_identities: Tuple[str, ...]
    unreviewed_annotation_count: int
    case_25_status: str
    civil_dataset_complete: bool
    civil_missing_splits: Tuple[str, ...]
    observation_gate_effect: str

    @staticmethod
    def from_inventory(inventory: Dict[str, Any]) -> "InventoryDisclosure":
        research = inventory.get("research") or {}
        civil = inventory.get("civil_dataset") or inventory.get("civil") or {}
        observation = (
            inventory.get("observation_presentation") or inventory.get("observation") or {}
        )
        fixtures = research.get("technical_fixtures") or research.get("fixtures") or []
        unreviewed = research.get("unreviewed_annotations") or {}
        case_25 = research.get("case_25") or {}
        missing = tuple(civil.get("expected_missing_splits") or civil.get("missing_splits") or ())
        return InventoryDisclosure(
            formal_research_pack_count=int(research.get("formal_pack_count", 0)),
            fixture_identities=tuple(
                str(f.get("id") or f.get("cluster_id") or f) if isinstance(f, dict) else str(f)
                for f in fixtures
            ),
            unreviewed_annotation_count=int(
                unreviewed.get("count", research.get("unreviewed_annotation_count", 0))
                if isinstance(unreviewed, dict)
                else unreviewed
            ),
            case_25_status=str(
                case_25.get("confirmation", research.get("case_25_status", "unknown"))
                if isinstance(case_25, dict)
                else case_25
            ),
            civil_dataset_complete=len(missing) == 0,
            civil_missing_splits=missing,
            observation_gate_effect=str(observation.get("gate_effect", "none")),
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["fixture_identities"] = list(self.fixture_identities)
        d["civil_missing_splits"] = list(self.civil_missing_splits)
        return d


@dataclass(frozen=True)
class ReleaseManifest:
    """canonical manifest：版本/提交绑定 + 目录 digest + 披露 + 证据索引。"""

    version_id: str
    commit_id: str
    generated_at: str
    package_metadata_digest: str
    route_catalog_digest: str
    configuration_digest: str
    authoritative_status_digest: str
    lock_digests: Dict[str, str]
    disclosure: InventoryDisclosure
    known_limitations: Tuple[str, ...]
    evidence_index: Tuple[str, ...]  # evidence_id 列表
    gap_index: Tuple[str, ...]  # gap_id 列表

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "commit_id": self.commit_id,
            "generated_at": self.generated_at,
            "digests": {
                "package_metadata": self.package_metadata_digest,
                "route_catalog": self.route_catalog_digest,
                "configuration": self.configuration_digest,
                "authoritative_status": self.authoritative_status_digest,
                "locks": dict(sorted(self.lock_digests.items())),
            },
            "disclosure": self.disclosure.to_dict(),
            "known_limitations": list(self.known_limitations),
            "evidence_index": list(self.evidence_index),
            "gap_index": list(self.gap_index),
        }

    def digest(self) -> str:
        return canonical_digest(self.to_canonical_dict())


def evidence_root() -> Path:
    """Evidence root：必须在源码树外，可用 EVIDENCE_ROOT / RUNTIME_DATA_ROOT 覆盖。"""
    env = os.getenv("EVIDENCE_ROOT", "").strip()
    if env:
        return Path(env)
    from core.store.registry import runtime_data_root

    return runtime_data_root() / "evidence"


def is_within_source_tree(path: Path, source_root: Path) -> bool:
    """检查 evidence/runtime artifact 是否落在 immutable source artifacts 内。"""
    try:
        Path(path).resolve().relative_to(Path(source_root).resolve())
        return True
    except ValueError:
        return False
