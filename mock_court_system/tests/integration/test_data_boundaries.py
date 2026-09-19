"""Civil / Research 数据分轨与双向导入拒绝测试（Task 7.1）。"""
from __future__ import annotations

import sqlite3

import pytest

from core.data_boundaries import (
    CIVIL_DISCRIMINATOR,
    CIVIL_IMPORT_BOUNDARY,
    RESEARCH_DISCRIMINATOR,
    RESEARCH_IMPORT_BOUNDARY,
    TRACK_CIVIL,
    TRACK_RESEARCH,
    TRACK_UNKNOWN,
    WrongDataTrackError,
    DataBoundaryClassifier,
    assert_no_research_context,
    eval_track_of_namespace,
    research_eval_namespace,
    session_has_research_identity,
)
from core.fingerprint import tables_fingerprint


classifier = DataBoundaryClassifier()

RESEARCH_PACK = {
    "schema_version": "1",
    "dataset_id": "cisg",
    "cluster_id": "c1",
    "pack_version": "0.1.0",
    "task_type": "cisg_article79",
    "visible_materials": {},
}
CIVIL_CASE = {
    "case_id": "CASE-1",
    "cause": "民间借贷纠纷",
    "case_description": "desc",
    "plaintiff_claims": ["c1"],
}


def _track_db(tmp_path, name):
    conn = sqlite3.connect(str(tmp_path / f"{name}.sqlite3"))
    conn.execute("CREATE TABLE records (id TEXT PRIMARY KEY, body TEXT)")
    return conn


def test_classifier_discriminator_wins_over_shape():
    payload = dict(RESEARCH_PACK)
    payload["data_track"] = CIVIL_DISCRIMINATOR
    assert classifier.classify(payload) == TRACK_CIVIL
    payload["data_track"] = RESEARCH_DISCRIMINATOR
    assert classifier.classify(payload) == TRACK_RESEARCH


def test_classifier_structural_fallback():
    assert classifier.classify(RESEARCH_PACK) == TRACK_RESEARCH
    assert classifier.classify(CIVIL_CASE) == TRACK_CIVIL
    assert classifier.classify({"dataset_id": "dataset_1000"}) == TRACK_CIVIL
    assert classifier.classify({"dataset_id": "enforcement"}) == TRACK_RESEARCH
    assert classifier.classify("not-a-mapping") == TRACK_UNKNOWN
    assert classifier.classify({"data_track": "alien/v9"}) == TRACK_UNKNOWN


def test_civil_boundary_rejects_research_pack(tmp_path):
    civil_conn = _track_db(tmp_path, "civil")
    research_conn = _track_db(tmp_path, "research")
    civil_fp = tables_fingerprint(civil_conn, ["records"])
    research_fp = tables_fingerprint(research_conn, ["records"])

    with pytest.raises(WrongDataTrackError) as exc:
        CIVIL_IMPORT_BOUNDARY.validate_before_parse(RESEARCH_PACK)
    assert exc.value.code == "wrong_data_track"
    assert exc.value.actual_track == TRACK_RESEARCH

    assert tables_fingerprint(civil_conn, ["records"]) == civil_fp
    assert tables_fingerprint(research_conn, ["records"]) == research_fp


def test_research_boundary_rejects_civil_case(tmp_path):
    civil_conn = _track_db(tmp_path, "civil")
    research_conn = _track_db(tmp_path, "research")
    civil_fp = tables_fingerprint(civil_conn, ["records"])
    research_fp = tables_fingerprint(research_conn, ["records"])

    with pytest.raises(WrongDataTrackError):
        RESEARCH_IMPORT_BOUNDARY.validate_before_parse(CIVIL_CASE)

    assert tables_fingerprint(civil_conn, ["records"]) == civil_fp
    assert tables_fingerprint(research_conn, ["records"]) == research_fp


def test_boundaries_accept_own_track():
    assert CIVIL_IMPORT_BOUNDARY.validate_before_parse(CIVIL_CASE) == TRACK_CIVIL
    assert RESEARCH_IMPORT_BOUNDARY.validate_before_parse(RESEARCH_PACK) == TRACK_RESEARCH


def test_boundary_validate_after_parse_on_model():
    class FakeModel:
        def model_dump(self):
            return dict(CIVIL_CASE)

    assert CIVIL_IMPORT_BOUNDARY.validate_after_parse(FakeModel()) == TRACK_CIVIL
    with pytest.raises(WrongDataTrackError):
        RESEARCH_IMPORT_BOUNDARY.validate_after_parse(FakeModel())


def test_eval_namespaces_do_not_cross():
    for ns in ("civil.lexeval", "civil.j1", "civil.cadd"):
        assert eval_track_of_namespace(ns) == TRACK_CIVIL
    assert eval_track_of_namespace("research.v1") == TRACK_RESEARCH
    assert research_eval_namespace("v1") == "research.v1"
    assert eval_track_of_namespace("random") == TRACK_UNKNOWN


def test_civil_session_without_research_identity_has_no_research_block():
    civil_input = {"case_id": "CASE-1", "case_description": "x"}
    assert session_has_research_identity(civil_input) is False
    assert_no_research_context(civil_input)  # 不抛

    # 空 research block 是无 research identity 的污染
    with pytest.raises(WrongDataTrackError):
        assert_no_research_context({"research": {}})

    research_input = {"research": {"dataset_id": "cisg", "run_id": "run_1"}}
    assert session_has_research_identity(research_input) is True
    assert_no_research_context(research_input)


def test_empty_material_directories_not_created(tmp_path):
    """无源文件时不得创建空选案/原文/规则卡目录。"""
    from core.data_boundaries import CIVIL_IMPORT_BOUNDARY as boundary

    with pytest.raises(WrongDataTrackError):
        boundary.validate_before_parse(RESEARCH_PACK)
    for name in ("selections", "source_texts", "rule_cards"):
        assert not (tmp_path / name).exists()
