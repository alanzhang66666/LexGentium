"""Deterministic gate 与 append-only decision chain 测试（Task 10.2）。"""
from __future__ import annotations

import pytest

from core.release.evidence import (
    EvidenceRecord,
    EvidenceResult,
    GapRecord,
    InventoryDisclosure,
    ReleaseManifest,
)
from core.release.gate import (
    GENESIS_DIGEST,
    DecisionLog,
    GateCriterion,
    evaluate_gate,
    make_decision,
    validate_chain,
)
from core.release.version import VERSION_ID

COMMIT = "b" * 40

DISCLOSURE = InventoryDisclosure(
    formal_research_pack_count=0,
    fixture_identities=("a",),
    unreviewed_annotation_count=15,
    case_25_status="pending",
    civil_dataset_complete=False,
    civil_missing_splits=("train",),
    observation_gate_effect="none",
)


def _manifest(commit=COMMIT):
    return ReleaseManifest(
        version_id=VERSION_ID,
        commit_id=commit,
        generated_at="2026-01-01T00:00:00Z",
        package_metadata_digest="p",
        route_catalog_digest="r",
        configuration_digest="c",
        authoritative_status_digest="s",
        lock_digests={},
        disclosure=DISCLOSURE,
        known_limitations=(),
        evidence_index=(),
        gap_index=(),
    )


def _ev(check_id, **overrides):
    params = dict(
        evidence_id=f"ev_{check_id}",
        check_id=check_id,
        version_id=VERSION_ID,
        commit_id=COMMIT,
        command="pytest -q",
        environment_identity="env",
        started_at="2026-01-01T00:00:00Z",
        duration_ms=100,
        exit_code=0,
        result=EvidenceResult.PASS.value,
        sample_count=30,
        artifact_digest="d" * 64,
        correlation_context={"request_id": f"req_{check_id}"},
    )
    params.update(overrides)
    return EvidenceRecord(**params)


CRITERIA = [
    GateCriterion("unit_tests", min_samples=10),
    GateCriterion("build", min_samples=0),
    GateCriterion("e2e", min_samples=3, mandatory=False),  # optional 不阻断
]


def test_all_pass_produces_single_go():
    manifest = _manifest()
    evidence = [_ev("unit_tests"), _ev("build")]
    result = evaluate_gate(CRITERIA, evidence, [], manifest)
    assert result.decision == "go"
    assert result.failed_criteria == ()


def test_deterministic_same_input_same_decision():
    manifest = _manifest()
    evidence = [_ev("unit_tests", result=EvidenceResult.FAIL.value, exit_code=1)]
    runs = [evaluate_gate(CRITERIA, evidence, [], manifest) for _ in range(3)]
    assert all(r.decision == "no_go" for r in runs)
    assert all(
        [f.check_id for f in r.failed_criteria]
        == [f.check_id for f in runs[0].failed_criteria]
        for r in runs
    )


@pytest.mark.parametrize(
    "override,reason",
    [
        ({"result": "timeout"}, "timeout"),
        ({"result": "fail", "exit_code": 1}, "failed"),
        ({"sample_count": 2}, "insufficient_samples"),
        ({"commit_id": "c" * 40}, "commit_mismatch"),
    ],
)
def test_each_failure_mode_fails_closed(override, reason):
    manifest = _manifest()
    evidence = [_ev("unit_tests", **override), _ev("build")]
    result = evaluate_gate(CRITERIA, evidence, [], manifest)
    assert result.decision == "no_go"
    reasons = {f.check_id: f.reason for f in result.failed_criteria}
    assert reasons["unit_tests"] == reason


def test_missing_evidence_is_no_go():
    result = evaluate_gate(CRITERIA, [], [], _manifest())
    assert result.decision == "no_go"
    assert {f.check_id for f in result.failed_criteria} == {"unit_tests", "build"}


def test_open_blocker_no_go_but_legal_gap_does_not_block():
    manifest = _manifest()
    evidence = [_ev("unit_tests"), _ev("build")]
    blocker = GapRecord(
        gap_id="g1", classification="engineering_blocker",
        trigger="t", expected="e", actual="a", owner="eng",
    )
    legal = GapRecord(
        gap_id="g2", classification="legal_content_gap",
        trigger="t", expected="e", actual="a", owner="legal",
    )
    assert evaluate_gate(CRITERIA, evidence, [blocker], manifest).decision == "no_go"
    assert evaluate_gate(CRITERIA, evidence, [legal], manifest).decision == "go"


def test_failed_criteria_have_closure_actions():
    evaluation = evaluate_gate(CRITERIA, [], [], _manifest())
    decision = make_decision(
        evaluation,
        approver="release-bot",
        manifest=_manifest(),
        evidence=[],
        decided_at="2026-01-01T00:00:00Z",
    )
    assert decision.type == "no_go"
    assert len(decision.closure_actions) == len(decision.failed_criteria)
    assert decision.previous_decision_digest == GENESIS_DIGEST
    assert decision.record_digest


def test_decision_chain_detects_tamper_delete_reorder():
    manifest = _manifest()
    evidence = [_ev("unit_tests"), _ev("build")]
    evaluation = evaluate_gate(CRITERIA, evidence, [], manifest)

    log = DecisionLog()
    r1 = log.append(evaluation, approver="a", manifest=manifest, evidence=evidence,
                    decided_at="2026-01-01T00:00:01Z")
    r2 = log.append(evaluation, approver="a", manifest=manifest, evidence=evidence,
                    decided_at="2026-01-01T00:00:02Z")
    r3 = log.append(evaluation, approver="a", manifest=manifest, evidence=evidence,
                    decided_at="2026-01-01T00:00:03Z")

    records = list(log.records)
    ok, _ = validate_chain(records)
    assert ok
    assert r2.previous_decision_digest == r1.record_digest
    assert r3.previous_decision_digest == r2.record_digest

    # 删除中间记录 → 链断
    ok, msg = validate_chain([r1, r3])
    assert not ok

    # 重排 → 链断
    ok, msg = validate_chain([r1, r3, r2])
    assert not ok

    # 篡改 approver → digest 不匹配
    tampered = type(r2)(**{**r2.__dict__, "approver": "mallory"})
    ok, msg = validate_chain([r1, tampered, r3])
    assert not ok
