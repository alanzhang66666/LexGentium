"""Deterministic release gate 与 append-only decision chain（design §14，Task 10.2）。

- 同一组 criteria/evidence/gaps/manifest 永远产出唯一决策（go 或 no_go）。
- 任何 mandatory 失败、timeout、样本不足、关联缺失、commit 不一致、
  open engineering blocker 都 fail closed → no_go。
- ``ReleaseDecision`` append-only；``previous_decision_digest`` 链向前一条
  canonical digest，篡改/删除/重排可被 ``validate_chain`` 检测。
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.fingerprint import canonical_digest
from core.release.evidence import (
    EvidenceRecord,
    GapRecord,
    ReleaseManifest,
    engineering_blocker_count,
)
from core.release.version import VERSION_ID


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass(frozen=True)
class GateCriterion:
    """一条 mandatory/optional 检查声明。"""

    check_id: str
    mandatory: bool = True
    min_samples: int = 0
    owner: str = "release"
    closure_action: str = ""


@dataclass(frozen=True)
class FailedCriterion:
    check_id: str
    reason: str  # failed|timeout|invalid|missing_evidence|insufficient_samples|commit_mismatch|open_blocker
    owner: str
    closure_action: str


@dataclass(frozen=True)
class GateEvaluation:
    """gate 求值结果（确定性）：failed 集合恰覆盖失败 criteria。"""

    decision: str  # "go" | "no_go"
    failed_criteria: Tuple[FailedCriterion, ...]


def evaluate_gate(
    criteria: List[GateCriterion],
    evidence: List[EvidenceRecord],
    gaps: List[GapRecord],
    manifest: ReleaseManifest,
) -> GateEvaluation:
    """确定性 gate：任一 mandatory 失败即 no_go；全过才 go。"""
    by_check: Dict[str, List[EvidenceRecord]] = {}
    for ev in evidence:
        by_check.setdefault(ev.check_id, []).append(ev)

    failed: List[FailedCriterion] = []

    for crit in criteria:
        if not crit.mandatory:
            continue
        records = by_check.get(crit.check_id) or []
        if not records:
            failed.append(
                FailedCriterion(crit.check_id, "missing_evidence", crit.owner, crit.closure_action)
            )
            continue
        # 至少一条对该 commit 完全有效的证据
        def _ok(ev: EvidenceRecord) -> bool:
            if not ev.is_valid_for_gate(min_samples=crit.min_samples):
                return False
            return ev.version_id == manifest.version_id and ev.commit_id == manifest.commit_id

        if not any(_ok(ev) for ev in records):
            reason = _failure_reason(records, crit, manifest)
            failed.append(FailedCriterion(crit.check_id, reason, crit.owner, crit.closure_action))

    # open engineering blocker → no_go（内容/数据缺口不阻断）
    for gap in gaps:
        if gap.is_engineering_blocker():
            failed.append(
                FailedCriterion(
                    f"gap:{gap.gap_id}", "open_blocker", gap.owner,
                    f"close gap {gap.gap_id}",
                )
            )

    return GateEvaluation(
        decision="no_go" if failed else "go",
        failed_criteria=tuple(failed),
    )


def _failure_reason(
    records: List[EvidenceRecord], crit: GateCriterion, manifest: ReleaseManifest
) -> str:
    if any(ev.result == "timeout" for ev in records):
        return "timeout"
    if all(ev.commit_id != manifest.commit_id or ev.version_id != manifest.version_id for ev in records):
        return "commit_mismatch"
    if all(0 < ev.sample_count < crit.min_samples for ev in records):
        return "insufficient_samples"
    if all(ev.missing_fields() for ev in records):
        return "invalid"
    return "failed"


# ---------- append-only decision chain ----------


@dataclass(frozen=True)
class ReleaseDecision:
    decision_id: str
    type: str  # go | no_go
    decided_at: str
    approver: str
    version_id: str
    commit_id: str
    manifest_digest: str
    evidence_links: Tuple[str, ...]
    failed_criteria: Tuple[str, ...]
    closure_actions: Tuple[str, ...]
    previous_decision_digest: str
    record_digest: str = ""

    def canonical_payload(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("record_digest", None)
        d["evidence_links"] = list(self.evidence_links)
        d["failed_criteria"] = list(self.failed_criteria)
        d["closure_actions"] = list(self.closure_actions)
        return d


GENESIS_DIGEST = "0" * 64


def make_decision(
    evaluation: GateEvaluation,
    *,
    approver: str,
    manifest: ReleaseManifest,
    evidence: List[EvidenceRecord],
    previous_digest: str = GENESIS_DIGEST,
    decided_at: Optional[str] = None,
) -> ReleaseDecision:
    """从 gate evaluation 铸造一条 decision（digest 由调用方 append 时算）。"""
    record = ReleaseDecision(
        decision_id=f"dec_{uuid.uuid4().hex[:16]}",
        type=evaluation.decision,
        decided_at=decided_at or _utcnow_iso(),
        approver=approver,
        version_id=manifest.version_id,
        commit_id=manifest.commit_id,
        manifest_digest=manifest.digest(),
        evidence_links=tuple(ev.evidence_id for ev in evidence),
        failed_criteria=tuple(f.check_id for f in evaluation.failed_criteria),
        closure_actions=tuple(
            f.closure_action or f"resolve {f.check_id}"
            for f in evaluation.failed_criteria
        ),
        previous_decision_digest=previous_digest,
    )
    return _seal(record)


def _seal(record: ReleaseDecision) -> ReleaseDecision:
    return ReleaseDecision(
        **{**asdict(record), "record_digest": canonical_digest(record.canonical_payload())}
    )


class DecisionLog:
    """append-only decision 链；previous_decision_digest 串成 hash chain。"""

    def __init__(self, records: Optional[List[ReleaseDecision]] = None):
        self._records: List[ReleaseDecision] = list(records or [])

    @property
    def records(self) -> Tuple[ReleaseDecision, ...]:
        return tuple(self._records)

    def head_digest(self) -> str:
        return self._records[-1].record_digest if self._records else GENESIS_DIGEST

    def append(self, evaluation: GateEvaluation, *, approver: str,
               manifest: ReleaseManifest, evidence: List[EvidenceRecord],
               decided_at: Optional[str] = None) -> ReleaseDecision:
        record = make_decision(
            evaluation,
            approver=approver,
            manifest=manifest,
            evidence=evidence,
            previous_digest=self.head_digest(),
            decided_at=decided_at,
        )
        self._records.append(record)
        return record


def validate_chain(records: List[ReleaseDecision]) -> Tuple[bool, str]:
    """校验链：任一记录被改/删/重排都失败。返回 (ok, 失败原因或 '')。"""
    prev = GENESIS_DIGEST
    for idx, rec in enumerate(records):
        if rec.previous_decision_digest != prev:
            return False, f"record {idx}: previous_decision_digest mismatch"
        if canonical_digest(rec.canonical_payload()) != rec.record_digest:
            return False, f"record {idx}: record_digest mismatch"
        prev = rec.record_digest
    return True, ""
