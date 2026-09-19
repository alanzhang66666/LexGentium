"""Release gate / manifest / decision-chain property tests.

Covers Properties 1, 2, 3, 4, 5, 16, 54, 55, 57, 58, 59.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.release.catalog import (  # noqa: E402
    all_versions_match,
    build_inventory_report,
    build_route_diff,
    version_surfaces,
)
from core.release.evidence import (  # noqa: E402
    EvidenceRecord,
    GapClassification,
    GapRecord,
    GapStatus,
    InventoryDisclosure,
    ReleaseManifest,
    engineering_blocker_count,
)
from core.release.gate import (  # noqa: E402
    DecisionLog,
    GateCriterion,
    evaluate_gate,
    make_decision,
    validate_chain,
)
from core.release.version import VERSION_ID  # noqa: E402

COMMIT = "deadbeef" * 5  # 40-hex git sha
NOW = "2026-09-19T00:00:00Z"


def _manifest(**kw) -> ReleaseManifest:
    return ReleaseManifest(
        version_id=kw.get("version_id", VERSION_ID),
        commit_id=kw.get("commit_id", COMMIT),
        generated_at=NOW,
        package_metadata_digest="pkg",
        route_catalog_digest="routes",
        configuration_digest="cfg",
        authoritative_status_digest="status",
        lock_digests={},
        disclosure=kw.get(
            "disclosure",
            InventoryDisclosure(0, (), 15, "pending", False, ("train",), "none"),
        ),
        known_limitations=(),
        evidence_index=(),
        gap_index=(),
    )


def _evidence(check_id: str, result: str = "pass", **kw) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=kw.get("evidence_id", f"ev_{check_id}"),
        check_id=check_id,
        version_id=kw.get("version_id", VERSION_ID),
        commit_id=kw.get("commit_id", COMMIT),
        command=kw.get("command", "pytest -q"),
        environment_identity=kw.get("environment_identity", "env"),
        started_at=kw.get("started_at", NOW),
        duration_ms=kw.get("duration_ms", 10),
        exit_code=kw.get("exit_code", 0),
        result=result,
        sample_count=kw.get("sample_count", 0),
        correlation_context=kw.get("correlation_context", {"request_id": "r1"}),
    )


def _gap(gap_id: str, classification: str, status: str = "open", **kw) -> GapRecord:
    return GapRecord(
        gap_id=gap_id,
        classification=classification,
        trigger="t",
        expected="e",
        actual="a",
        owner="o",
        status=status,
        approved_by=kw.get("approved_by", ""),
    )


# ---------- Property 1: 排除范围不影响发布结论 ----------


@given(
    obs_result=st.sampled_from(["pass", "fail", "timeout", "invalid"]),
    n_obs=st.integers(min_value=0, max_value=3),
)
@settings(max_examples=20)
def test_property_1_observation_checks_never_change_decision(obs_result, n_obs):
    criteria = [GateCriterion(check_id="contract", mandatory=True)]
    evidence = [_evidence("contract")]
    manifest = _manifest()
    base = evaluate_gate(criteria, evidence, [], manifest).decision

    # 任意观察类（non-mandatory）检查加入/删除/改变结果不影响 gate
    for i in range(n_obs):
        criteria.append(
            GateCriterion(check_id=f"obs_visual_{i}", mandatory=False)
        )
        evidence.append(
            _evidence(f"obs_visual_{i}", result=obs_result, evidence_id=f"obs{i}")
        )
    assert evaluate_gate(criteria, evidence, [], manifest).decision == base
    assert base == "go"


# ---------- Property 2: Gap 恰一个主分类且按分类影响 gate ----------


@given(
    cls=st.sampled_from([c.value for c in GapClassification]),
    status=st.sampled_from([s.value for s in GapStatus]),
)
@settings(max_examples=20)
def test_property_2_gap_classification_drives_gate(cls, status):
    kwargs = {"approved_by": "lead"} if cls == "accepted_risk" else {}
    gap = _gap("g1", cls, status, **kwargs)
    criteria = [GateCriterion(check_id="c1", mandatory=True)]
    evidence = [_evidence("c1")]
    outcome = evaluate_gate(criteria, evidence, [gap], _manifest())

    is_open_blocker = (
        cls == GapClassification.ENGINEERING_BLOCKER.value and status == "open"
    )
    assert gap.is_engineering_blocker() == is_open_blocker
    assert engineering_blocker_count([gap]) == (1 if is_open_blocker else 0)
    # legal_content / data_limitation / accepted_risk / out_of_scope 不阻断
    assert (outcome.decision == "no_go") == is_open_blocker
    if is_open_blocker:
        assert any(f.check_id == "gap:g1" for f in outcome.failed_criteria)


def test_property_2_gap_record_has_exactly_one_classification():
    gap = _gap("g2", "legal_content_gap")
    assert isinstance(gap.classification, str) and gap.classification
    with pytest.raises(ValueError):
        _gap("g3", "not-a-classification")
    with pytest.raises(ValueError):
        _gap("g4", "accepted_risk")  # open accepted_risk requires approver


# ---------- Property 3: 路由清单完整分区 ----------


def test_property_3_route_catalog_complete_partition():
    diff = build_route_diff()
    assert diff["is_clean"] is True, diff
    assert not diff["unclassified"] and not diff["ambiguous"]
    for section in ("stable", "experimental"):
        for route in diff["classified"][section]:
            for field in ("method", "path", "auth", "response_mode", "journey"):
                assert route[field], f"{section} route missing {field}: {route}"
            assert route["stability"] == section


# ---------- Property 4: 版本表面一致 ----------


def test_property_4_version_surface_consistency():
    surfaces = version_surfaces()
    assert set(surfaces.values()) == {VERSION_ID}
    assert all_versions_match() is True
    # 任一表面偏离 → 不一致
    for mutated in (
        {"package": "2.0.0"},
        {"release": "0.9"},
        {"routes": "1.0.1"},
    ):
        combo = {**surfaces, **mutated}
        assert (set(combo.values()) == {VERSION_ID}) is False


# ---------- Property 5: 民事 split 缺失集合准确 ----------


@given(
    present=st.frozensets(st.sampled_from(["train", "validation", "test"]))
)
@settings(max_examples=8)
def test_property_5_civil_missing_splits_exact_difference(tmp_path_factory, present):
    """构造伪 root：复制 release 声明 + SYSTEM_STATUS + 可控 split 文件。"""
    tmp_root = Path(tmp_path_factory.mktemp("inv"))
    inv = _manifest()
    del inv
    shutil.copytree(ROOT / "release", tmp_root / "release")
    (tmp_root / "docs").mkdir()
    status_rel = json.loads("{}") or {}
    del status_rel
    status_src = ROOT / "docs" / "SYSTEM_STATUS.md"
    shutil.copy(status_src, tmp_root / "docs" / "SYSTEM_STATUS.md")

    import yaml

    inventory = yaml.safe_load((tmp_root / "release" / "inventory.yaml").read_text("utf-8"))
    split_files = inventory["civil_dataset"]["required_split_files"]
    data_root = tmp_root / inventory["civil_dataset"]["path"]
    data_root.mkdir(parents=True)
    for name in present:
        (data_root / split_files[name]).write_text("x", encoding="utf-8")
    for fixture in inventory["research"]["technical_fixtures"]:
        (tmp_root / fixture["path"]).mkdir(parents=True, exist_ok=True)

    report = build_inventory_report(tmp_root)
    assert report["missing_civil_splits"] == sorted({"train", "validation", "test"} - present)


# ---------- Property 16: 契约身份不匹配必定拒绝发布 ----------


@given(
    commit=st.sampled_from([COMMIT, "bad", "1234", "f" * 40]),
    version=st.sampled_from([VERSION_ID, "9.9.9"]),
)
@settings(max_examples=20)
def test_property_16_identity_mismatch_never_go(commit, version):
    criteria = [GateCriterion(check_id="contract", mandatory=True)]
    ev = _evidence("contract", commit_id=commit, version_id=version)
    out = evaluate_gate(criteria, [ev], [], _manifest())
    mismatch = commit != COMMIT or version != VERSION_ID
    assert (out.decision == "no_go") == mismatch
    if mismatch:
        assert out.failed_criteria[0].reason == "commit_mismatch"


# ---------- Property 54: 三连跑稳定门禁 ----------


@given(st.lists(st.booleans(), min_size=3, max_size=3))
@settings(max_examples=10)
def test_property_54_three_runs_require_all_pass(run_flags):
    """同一 commit 三轮：任一 required check 在某轮失败 → 门禁不满足。"""
    criteria = [GateCriterion(check_id="c1", mandatory=True)]
    manifest = _manifest()
    decisions = []
    for ok in run_flags:
        ev = [_evidence("c1", result="pass" if ok else "fail")]
        decisions.append(evaluate_gate(criteria, ev, [], manifest).decision)
    stable = all(d == "go" for d in decisions)
    assert stable == all(run_flags)


# ---------- Property 55: required check / evidence fail-closed ----------


FAIL_MODES = [
    {"result": "fail"},
    {"result": "timeout"},
    {"result": "invalid"},
    {"exit_code": 1},
    {"sample_count": 1},  # < min_samples
    {"correlation_context": {}},  # Correlation_Context 缺失
    {"commit_id": "other"},
    {"started_at": ""},  # record 缺失字段
]


def test_property_55_any_defect_forces_no_go():
    criteria = [
        GateCriterion(check_id="a", mandatory=True, min_samples=3),
        GateCriterion(check_id="b", mandatory=True),
    ]
    base = [_evidence("a", sample_count=3), _evidence("b")]
    manifest = _manifest()
    assert evaluate_gate(criteria, base, [], manifest).decision == "go"

    for mode in FAIL_MODES:
        poisoned = [_evidence("a", **{**{"sample_count": 3}, **mode}), _evidence("b")]
        out = evaluate_gate(criteria, poisoned, [], manifest)
        assert out.decision == "no_go", mode
        assert any(f.check_id == "a" for f in out.failed_criteria)

    # 缺失整条 evidence → no_go
    assert evaluate_gate(criteria, [_evidence("b")], [], manifest).decision == "no_go"


# ---------- Property 57: 决策确定且唯一 ----------


@given(n_fail=st.integers(min_value=0, max_value=4))
@settings(max_examples=15)
def test_property_57_gate_decision_deterministic_and_unique(n_fail):
    criteria = [GateCriterion(check_id=f"c{i}", mandatory=True) for i in range(4)]
    evidence = [
        _evidence(f"c{i}", result="fail" if i < n_fail else "pass")
        for i in range(4)
    ]
    manifest = _manifest()
    out1 = evaluate_gate(criteria, evidence, [], manifest)
    out2 = evaluate_gate(criteria, evidence, [], manifest)
    assert out1 == out2  # 确定性
    if n_fail == 0:
        assert out1.decision == "go" and not out1.failed_criteria
    else:
        assert out1.decision == "no_go"
        # failed 集合恰覆盖失败 criteria
        assert {f.check_id for f in out1.failed_criteria} == {
            f"c{i}" for i in range(n_fail)
        }
        for f in out1.failed_criteria:
            assert f.owner and f.closure_action is not None


# ---------- Property 58: 决策日志可检测篡改 ----------


def test_property_58_decision_chain_detects_tamper():
    log = DecisionLog()
    manifest = _manifest()
    ok_eval = evaluate_gate([GateCriterion("c1")], [_evidence("c1")], [], manifest)
    r1 = log.append(ok_eval, approver="qa", manifest=manifest, evidence=[])
    r2 = log.append(ok_eval, approver="qa", manifest=manifest, evidence=[])
    assert r2.previous_decision_digest == r1.record_digest

    records = list(log.records)
    assert validate_chain(records)[0] is True

    # 篡改记录内容
    tampered = list(records)
    tampered[0] = type(r1)(**{**r1.__dict__, "approver": "mallory"})
    assert validate_chain(tampered)[0] is False
    # 删除中间记录
    assert validate_chain(records[1:])[0] is False
    # 重排
    assert validate_chain(records[::-1])[0] is False


# ---------- Property 59: 披露与 blocker 状态独立 ----------


@given(
    formal=st.integers(min_value=0, max_value=5),
    unreviewed=st.integers(min_value=0, max_value=20),
    case25=st.sampled_from(["pending", "confirmed", "rejected"]),
)
@settings(max_examples=15)
def test_property_59_disclosure_independent_of_blockers(formal, unreviewed, case25):
    disclosure = InventoryDisclosure(
        formal_research_pack_count=formal,
        fixture_identities=("enf-cn-notice-001", "cisg-art79-sample-001"),
        unreviewed_annotation_count=unreviewed,
        case_25_status=case25,
        civil_dataset_complete=False,
        civil_missing_splits=("train", "validation", "test"),
        observation_gate_effect="none",
    )
    manifest = _manifest(disclosure=disclosure)
    criteria = [GateCriterion(check_id="c1", mandatory=True)]
    out = evaluate_gate(criteria, [_evidence("c1")], [], manifest)
    # 披露项变化不改变结论：全过仍 go
    assert out.decision == "go"
    # 内容/数据缺口不改变 blocker count
    gaps = [_gap("g", "legal_content_gap"), _gap("g2", "data_limitation")]
    assert engineering_blocker_count(gaps) == 0
