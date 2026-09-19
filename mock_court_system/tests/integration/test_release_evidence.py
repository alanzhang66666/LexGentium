"""Release evidence / gap / manifest 模型测试（Task 10.1）。"""
from __future__ import annotations

import yaml
import pytest

from core.release.evidence import (
    EvidenceRecord,
    EvidenceResult,
    GapClassification,
    GapRecord,
    InventoryDisclosure,
    ReleaseManifest,
    VersionCommitError,
    VersionCommitIdentity,
    engineering_blocker_count,
    evidence_root,
    is_within_source_tree,
)
from core.release.version import VERSION_ID

COMMIT = "a" * 40
PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


def _evidence(**overrides):
    params = dict(
        evidence_id="ev_1",
        check_id="pytest_unit",
        version_id=VERSION_ID,
        commit_id=COMMIT,
        command="python -m pytest tests -q",
        environment_identity="env-abc",
        started_at="2026-01-01T00:00:00Z",
        duration_ms=1234,
        exit_code=0,
        result=EvidenceResult.PASS.value,
        sample_count=30,
        artifact_digest="d" * 64,
        correlation_context={"request_id": "r1"},
    )
    params.update(overrides)
    return EvidenceRecord(**params)


def test_identity_requires_version_and_full_commit():
    VersionCommitIdentity(VERSION_ID, COMMIT).validate()
    with pytest.raises(VersionCommitError):
        VersionCommitIdentity("0.9.9", COMMIT).validate()
    for bad in ("", "abc123", "g" * 40, "a" * 39, "a" * 41, None):
        with pytest.raises(VersionCommitError):
            VersionCommitIdentity(VERSION_ID, bad).validate()
    assert not VersionCommitIdentity(VERSION_ID, "abc123").is_bound()


def test_pass_evidence_valid_for_gate():
    ev = _evidence()
    assert ev.missing_fields() == ()
    assert ev.is_valid_for_gate(min_samples=10)
    assert ev.digest()


@pytest.mark.parametrize(
    "override",
    [
        {"result": EvidenceResult.FAIL.value},
        {"result": EvidenceResult.TIMEOUT.value},
        {"exit_code": 1},
        {"commit_id": "short"},
        {"version_id": "0.9.9"},
        {"command": ""},
        {"environment_identity": ""},
        {"sample_count": 2},
    ],
)
def test_fail_closed_on_bad_evidence(override):
    ev = _evidence(**override)
    assert not ev.is_valid_for_gate(min_samples=10)


def test_gap_one_of_classification_and_blocker_count():
    blocker = GapRecord(
        gap_id="g1",
        classification="engineering_blocker",
        trigger="t",
        expected="e",
        actual="a",
        owner="eng",
    )
    legal = GapRecord(
        gap_id="g2",
        classification="legal_content_gap",
        trigger="t",
        expected="e",
        actual="a",
        owner="legal",
    )
    data_gap = GapRecord(
        gap_id="g3",
        classification="data_limitation",
        trigger="t",
        expected="e",
        actual="a",
        owner="data",
    )
    closed_blocker = GapRecord(
        gap_id="g4",
        classification="engineering_blocker",
        trigger="t",
        expected="e",
        actual="a",
        owner="eng",
        status="closed",
    )
    gaps = [blocker, legal, data_gap, closed_blocker]
    # 内容/数据缺口与已关闭 blocker 不增加 blocker count
    assert engineering_blocker_count(gaps) == 1

    with pytest.raises(ValueError):
        GapRecord(
            gap_id="g5",
            classification="made_up",
            trigger="t",
            expected="e",
            actual="a",
            owner="x",
        )


def test_open_accepted_risk_requires_approval():
    with pytest.raises(ValueError):
        GapRecord(
            gap_id="g6",
            classification="accepted_risk",
            trigger="t",
            expected="e",
            actual="a",
            owner="x",
        )
    ok = GapRecord(
        gap_id="g7",
        classification="accepted_risk",
        trigger="t",
        expected="e",
        actual="a",
        owner="x",
        approved_by="release-owner",
    )
    assert not ok.is_engineering_blocker()


def test_inventory_disclosure_from_real_yaml():
    inventory = yaml.safe_load(
        (PROJECT_ROOT / "release" / "inventory.yaml").read_text(encoding="utf-8")
    )
    d = InventoryDisclosure.from_inventory(inventory)
    assert d.formal_research_pack_count == 0
    assert set(d.fixture_identities) == {"enf-cn-notice-001", "cisg-art79-sample-001"}
    assert d.unreviewed_annotation_count == 15
    assert d.case_25_status == "pending"
    assert d.civil_dataset_complete is False
    assert set(d.civil_missing_splits) == {"train", "validation", "test"}
    assert d.observation_gate_effect == "none"


def test_manifest_canonical_digest_stable():
    disclosure = InventoryDisclosure(
        formal_research_pack_count=0,
        fixture_identities=("a", "b"),
        unreviewed_annotation_count=15,
        case_25_status="pending",
        civil_dataset_complete=False,
        civil_missing_splits=("train",),
        observation_gate_effect="none",
    )
    kwargs = dict(
        version_id=VERSION_ID,
        commit_id=COMMIT,
        generated_at="2026-01-01T00:00:00Z",
        package_metadata_digest="p" * 8,
        route_catalog_digest="r" * 8,
        configuration_digest="c" * 8,
        authoritative_status_digest="s" * 8,
        lock_digests={"requirements.lock": "x", "package-lock.json": "y"},
        disclosure=disclosure,
        known_limitations=("formal packs = 0",),
        evidence_index=("ev_1",),
        gap_index=("g1",),
    )
    m1 = ReleaseManifest(**kwargs)
    m2 = ReleaseManifest(**kwargs)
    assert m1.digest() == m2.digest()
    # 内容缺口披露变化会改变 manifest digest，但不改变 blocker count 语义
    other = ReleaseManifest(**{**kwargs, "gap_index": ("g1", "g2")})
    assert other.digest() != m1.digest()


def test_evidence_root_outside_source_when_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("EVIDENCE_ROOT", str(tmp_path / "ev"))
    root = evidence_root()
    assert root == tmp_path / "ev"
    assert not is_within_source_tree(root, PROJECT_ROOT)

    monkeypatch.delenv("EVIDENCE_ROOT")
    monkeypatch.setenv("RUNTIME_DATA_ROOT", str(tmp_path / "rt"))
    root = evidence_root()
    assert root == tmp_path / "rt" / "evidence"
    assert not is_within_source_tree(root, PROJECT_ROOT)

    assert is_within_source_tree(PROJECT_ROOT / "release" / "version.json", PROJECT_ROOT)
