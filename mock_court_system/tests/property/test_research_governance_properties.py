"""研究治理 / 数据分轨 / pack codec 属性测试。

覆盖 Properties 6, 12, 24, 40, 41, 42, 43, 44。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# research 包可独立导入（绕过 core/__init__ 重依赖）
_CORE_DIR = ROOT / "core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from core.data_boundaries import (  # noqa: E402
    CIVIL_DISCRIMINATOR,
    CIVIL_EVAL_NAMESPACES,
    CIVIL_IMPORT_BOUNDARY,
    RESEARCH_DISCRIMINATOR,
    RESEARCH_IMPORT_BOUNDARY,
    TRACK_CIVIL,
    TRACK_RESEARCH,
    TRACK_UNKNOWN,
    DataBoundaryClassifier,
    WrongDataTrackError,
    assert_no_research_context,
    eval_track_of_namespace,
    research_eval_namespace,
    session_has_research_identity,
)
from research.governance import (  # noqa: E402
    FormalReviewRecordV2,
    PackCodec,
    classify_pack,
    formal_pack_count,
    is_formal_eligible,
    pack_content_digest,
)
from research import ResearchPackLoader  # noqa: E402

CLASSIFIER = DataBoundaryClassifier()


def _packs():
    loader = ResearchPackLoader()
    return [
        loader.get_pack("enforcement", "enf-cn-notice-001"),
        loader.get_pack("cisg", "cisg-art79-sample-001"),
    ]


# ---------- Property 6: 正式研究包资格与计数 ----------


@given(
    reviewer=st.text(max_size=16),
    ts=st.text(max_size=24),
    outcome=st.sampled_from(["approved", "rejected", "changes_required", "bogus"]),
    version_delta=st.booleans(),
    digest_delta=st.booleans(),
)
@settings(max_examples=30)
def test_property_6_formal_eligibility_exact_rule(
    reviewer, ts, outcome, version_delta, digest_delta
):
    pack = _packs()[1]
    # 改成非 fixture cluster 以便 formal 资格可达
    payload = pack.model_dump(mode="json")
    payload["cluster_id"] = "cisg-art79-prop-candidate"
    candidate = ResearchPackLoader().get_pack("cisg", "cisg-art79-sample-001")
    candidate = type(pack).model_validate(payload)

    digest = pack_content_digest(candidate)
    review = FormalReviewRecordV2(
        independent_reviewer_id=reviewer,
        review_timestamp=ts,
        reviewed_pack_version=(
            "other" if version_delta else candidate.pack_version
        ),
        outcome=outcome,
        reviewed_content_digest=("0" * 64 if digest_delta else digest),
    )
    expected = (
        reviewer.strip() != ""
        and ts.strip() != ""
        and outcome == "approved"
        and not version_delta
        and not digest_delta
    )
    assert is_formal_eligible(candidate, [review]) == expected
    assert (classify_pack(candidate, [review]) == "formal") == expected


def test_property_6_fixtures_never_formal_and_count_zero():
    packs = _packs()
    for pack in packs:
        assert classify_pack(pack, ()) == "technical_fixture"
    assert formal_pack_count([(p, ()) for p in packs]) == 0


# ---------- Property 12/40/41: 分轨双向对称拒绝 ----------


@given(disc=st.sampled_from([CIVIL_DISCRIMINATOR, RESEARCH_DISCRIMINATOR, "other/v9"]))
@settings(max_examples=10)
def test_property_40_discriminator_determines_track(disc):
    payload = {"data_track": disc, "x": 1}
    expected = {
        CIVIL_DISCRIMINATOR: TRACK_CIVIL,
        RESEARCH_DISCRIMINATOR: TRACK_RESEARCH,
    }.get(disc, TRACK_UNKNOWN)
    assert CLASSIFIER.classify(payload) == expected
    # 未识别 discriminator 绝不猜测归轨
    if expected == TRACK_UNKNOWN:
        with pytest.raises(WrongDataTrackError):
            CLASSIFIER.assert_track(payload, TRACK_CIVIL)
        with pytest.raises(WrongDataTrackError):
            CLASSIFIER.assert_track(payload, TRACK_RESEARCH)


def test_property_41_cross_track_rejected_both_directions():
    civil = {"data_track": CIVIL_DISCRIMINATOR}
    research = {"data_track": RESEARCH_DISCRIMINATOR}
    with pytest.raises(WrongDataTrackError) as e1:
        CIVIL_IMPORT_BOUNDARY.validate_before_parse(research)
    assert e1.value.code == "wrong_data_track"
    with pytest.raises(WrongDataTrackError):
        RESEARCH_IMPORT_BOUNDARY.validate_before_parse(civil)
    # 同轨通过
    assert CIVIL_IMPORT_BOUNDARY.validate_before_parse(civil) == TRACK_CIVIL
    assert RESEARCH_IMPORT_BOUNDARY.validate_before_parse(research) == TRACK_RESEARCH


@given(version=st.text(min_size=1, max_size=16))
@settings(max_examples=10)
def test_property_40_eval_namespace_track_mapping(version):
    for ns in CIVIL_EVAL_NAMESPACES:
        assert eval_track_of_namespace(ns) == TRACK_CIVIL
    assert eval_track_of_namespace(research_eval_namespace(version)) == TRACK_RESEARCH
    assert eval_track_of_namespace(f"other.{version}") == TRACK_UNKNOWN


# ---------- Property 12: 无研究身份的 civil session 不得携带 research context ----------


@given(
    field=st.sampled_from(["dataset_id", "cluster_id", "pack_version", "run_id"]),
    value=st.text(min_size=0, max_size=12),
)
@settings(max_examples=20)
def test_property_12_research_identity_detection(field, value):
    session = {"research": {field: value}}
    has_identity = bool(value)
    assert session_has_research_identity(session) == has_identity
    if not has_identity:
        # 空 research context → civil session 拒绝
        with pytest.raises(WrongDataTrackError):
            assert_no_research_context(session)
    else:
        assert_no_research_context(session)  # 有身份：合法研究上下文


def test_property_12_no_research_key_is_clean():
    assert_no_research_context(None)
    assert_no_research_context({})
    assert_no_research_context({"case_id": "c1"})
    assert not session_has_research_identity({"research": {}})


# ---------- Property 24/42/43: unknown 与 anchor 在 codec 往返中保持 ----------


@given(pack_idx=st.integers(min_value=0, max_value=1))
@settings(max_examples=6)
def test_property_43_pack_codec_roundtrip_preserves_semantics(pack_idx):
    pack = _packs()[pack_idx]
    text = PackCodec.pretty_print(pack)
    reparsed = PackCodec.parse(text)
    assert PackCodec.compare(pack, reparsed)
    assert pack_content_digest(reparsed) == pack_content_digest(pack)
    # unknown 不丢失
    orig = pack.model_dump(mode="json")
    new = reparsed.model_dump(mode="json")
    assert orig == new


def test_property_24_unknown_values_survive_parse():
    pack = _packs()[1]
    dumped = pack.model_dump(mode="json")
    dumped["caption"]["court"] = "unknown"
    reparsed = type(pack).model_validate(dumped)
    assert reparsed.caption.court == "unknown"


# ---------- Property 44: 兼容身份才可比较 ----------


def test_property_44_compare_requires_identical_content():
    a, b = _packs()
    assert not PackCodec.compare(a, b)  # 不同 pack 不相等
    assert PackCodec.compare(a, a)
    # 内容相同、引用路径不同 → 语义相等
    clone = type(a).model_validate(a.model_dump(mode="json"))
    assert PackCodec.compare(a, clone)
