"""Contract parse/validate tests for research IDs, packs, and role-view isolation."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

# Import the research package without booting core/__init__.py (LLM/jieba).
# Application code should still use: from core.research import ResearchPackLoader
_CORE_DIR = Path(__file__).resolve().parents[1] / "core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from research import (  # noqa: E402
    ALL_FACT_FIELD_KEYS,
    ARGUMENT_ACTIONS,
    ARGUMENT_KINDS,
    AVAILABILITY_STATES,
    CISG_APPLICABLE_LABELS,
    CISG_ART79_ELEMENT_IDS,
    CISG_FACT_FIELD_KEYS,
    CIVIL_DATASET_ID,
    COMPLETENESS_DEGREES,
    CONDITION_TYPES,
    DATASET_IDS,
    DISCLOSURE_STATUSES,
    ELEMENT_COURT_RESULTS,
    ENFORCEMENT_FACT_FIELD_KEYS,
    EVIDENCE_RELATIONS,
    GAP_RELATED_FIELDS,
    HANDLED_LABELS,
    MISSING_CODES,
    NOTICE_EVENT_TYPES,
    ORIGINAL_LABEL_RELATIONS,
    PROTOCOL_BASES,
    REVIEW_STATES,
    SIX_COLUMN_FIELDS,
    SOURCE_FORMS,
    SOURCE_TIERS,
    SPEAKER_LABELS,
    SPEECH_TYPES,
    SUPPORT_STATUSES,
    TASK_TYPES,
    VISIBILITY_STATES,
    UNKNOWN,
    AnnotatedValue,
    EvalContract,
    ExperimentConditions,
    InputContract,
    MaterialGap,
    ModelConfigSnapshot,
    PackIdentity,
    PackNotFoundError,
    PackVersionMismatchError,
    ResearchPack,
    ResearchPackLoader,
    RunContract,
    VisibleMaterials,
    new_report_id,
    new_run_id,
    strip_reference,
    validate_dataset_id,
)
from research.ids import validate_cluster_id  # noqa: E402

LIB_RESEARCH = Path(__file__).resolve().parents[1] / "lib" / "research"


def _loader() -> ResearchPackLoader:
    return ResearchPackLoader()


def _ts_const_list(filename: str, name: str) -> list[str]:
    text = (LIB_RESEARCH / filename).read_text(encoding="utf-8")
    match = re.search(rf"export const {name} = \[(.*?)\] as const", text, re.S)
    assert match, f"{name} not found in {filename}"
    return re.findall(r'"([^"]+)"', match.group(1))


def _ts_interface_fields(filename: str, name: str) -> set[str]:
    text = (LIB_RESEARCH / filename).read_text(encoding="utf-8")
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", text, re.S)
    assert match, f"interface {name} not found in {filename}"
    return set(re.findall(r"^\s+([A-Za-z_][A-Za-z0-9_]*)\??:", match.group(1), re.M))


def _schema_fields(model) -> set[str]:
    return set(model.model_json_schema()["properties"])


def test_dataset_id_isolated_from_civil_corpus():
    with pytest.raises(ValueError):
        validate_dataset_id(CIVIL_DATASET_ID)
    with pytest.raises(ValidationError):
        PackIdentity(dataset_id="dataset_1000", cluster_id="enf-cn-notice-001", pack_version="0.1.0")
    assert DATASET_IDS == ("cisg", "enforcement")


def test_cluster_id_rejects_bare_case_number():
    with pytest.raises(ValueError):
        validate_cluster_id("2019粤01协外认1号")
    with pytest.raises(ValueError):
        validate_cluster_id("(2019)粤01协外认1号")
    identity = PackIdentity(
        dataset_id="enforcement",
        cluster_id="enf-cn-notice-001",
        pack_version="0.1.0-draft",
    )
    pack = _loader().get_pack(identity.dataset_id, identity.cluster_id, identity.pack_version)
    assert pack.caption.case_number == "SAMPLE-ENF-2019-001"
    assert pack.caption.case_number != pack.cluster_id


def test_enum_values_match_typescript():
    assert list(DATASET_IDS) == _ts_const_list("enums.ts", "DATASET_IDS")
    assert list(TASK_TYPES) == _ts_const_list("enums.ts", "TASK_TYPES")
    assert list(REVIEW_STATES) == _ts_const_list("enums.ts", "REVIEW_STATES")
    assert list(SOURCE_TIERS) == _ts_const_list("enums.ts", "SOURCE_TIERS")
    assert list(MISSING_CODES) == _ts_const_list("enums.ts", "MISSING_CODES")
    assert list(SPEAKER_LABELS) == _ts_const_list("enums.ts", "SPEAKER_LABELS")
    assert list(SPEECH_TYPES) == _ts_const_list("enums.ts", "SPEECH_TYPES")
    assert list(SUPPORT_STATUSES) == _ts_const_list("enums.ts", "SUPPORT_STATUSES")
    assert list(DISCLOSURE_STATUSES) == _ts_const_list("enums.ts", "DISCLOSURE_STATUSES")
    assert list(CISG_APPLICABLE_LABELS) == _ts_const_list("enums.ts", "CISG_APPLICABLE_LABELS")
    assert list(HANDLED_LABELS) == _ts_const_list("enums.ts", "HANDLED_LABELS")
    assert list(ORIGINAL_LABEL_RELATIONS) == _ts_const_list("enums.ts", "ORIGINAL_LABEL_RELATIONS")
    assert list(ELEMENT_COURT_RESULTS) == _ts_const_list("enums.ts", "ELEMENT_COURT_RESULTS")
    assert list(NOTICE_EVENT_TYPES) == _ts_const_list("enums.ts", "NOTICE_EVENT_TYPES")
    assert list(SOURCE_FORMS) == _ts_const_list("enums.ts", "SOURCE_FORMS")
    assert list(COMPLETENESS_DEGREES) == _ts_const_list("enums.ts", "COMPLETENESS_DEGREES")
    assert list(ARGUMENT_KINDS) == _ts_const_list("enums.ts", "ARGUMENT_KINDS")
    assert list(ARGUMENT_ACTIONS) == _ts_const_list("enums.ts", "ARGUMENT_ACTIONS")
    assert list(EVIDENCE_RELATIONS) == _ts_const_list("enums.ts", "EVIDENCE_RELATIONS")
    assert list(VISIBILITY_STATES) == _ts_const_list("enums.ts", "VISIBILITY_STATES")
    assert list(AVAILABILITY_STATES) == _ts_const_list("enums.ts", "AVAILABILITY_STATES")
    assert list(CONDITION_TYPES) == _ts_const_list("enums.ts", "CONDITION_TYPES")
    assert list(PROTOCOL_BASES) == _ts_const_list("enums.ts", "PROTOCOL_BASES")
    assert list(SIX_COLUMN_FIELDS) == _ts_const_list("packs.ts", "SIX_COLUMN_FIELDS")
    assert list(CISG_FACT_FIELD_KEYS) == _ts_const_list("field_keys.ts", "CISG_FACT_FIELD_KEYS")
    assert list(ENFORCEMENT_FACT_FIELD_KEYS) == _ts_const_list(
        "field_keys.ts", "ENFORCEMENT_FACT_FIELD_KEYS"
    )
    assert list(ALL_FACT_FIELD_KEYS) == _ts_const_list("field_keys.ts", "ALL_FACT_FIELD_KEYS")
    assert list(GAP_RELATED_FIELDS) == _ts_const_list("field_keys.ts", "GAP_RELATED_FIELDS")


def test_contract_fields_match_typescript():
    assert _schema_fields(InputContract) == _ts_interface_fields("contracts.ts", "InputContract")
    assert _schema_fields(RunContract) == _ts_interface_fields("contracts.ts", "RunContract")
    assert _schema_fields(EvalContract) == _ts_interface_fields("contracts.ts", "EvalContract")
    assert _schema_fields(ResearchPack) == _ts_interface_fields("packs.ts", "ResearchPack")
    assert "model_config" in _schema_fields(InputContract)
    assert "model_config_snapshot" not in _schema_fields(InputContract)


def test_input_contract_parse_and_role_view_hides_reference():
    payload = {
        "dataset_id": "enforcement",
        "cluster_id": "enf-cn-notice-001",
        "pack_version": "0.1.0-draft",
        "task_type": "enforcement_nyc",
        "visible_materials": {
            "applicant": {
                "document_ids": ["001", "002"],
                "source_ids": ["001:p3", "002:zh-v-1-b"],
                "rule_ids": ["nyc-v-1-b"],
            },
            "respondent": {
                "document_ids": ["001", "002"],
                "source_ids": ["001:p4", "002:zh-v-1-b"],
                "rule_ids": ["nyc-v-1-b"],
            },
        },
        "experiment_conditions": {
            "include_counterparty": True,
            "hide_source_ids": [],
            "enable_source_audit": False,
        },
        "model_config": {"provider": "deepseek", "model": "deepseek-chat", "temperature": 0.1},
        "reference": {
            "reference_version": "0.1.0-draft",
            "gold_labels": {"outcome": "hidden-from-roles"},
        },
    }
    contract = InputContract.model_validate(payload)
    dumped = contract.model_dump(mode="json")
    assert dumped["model_config"]["model"] == "deepseek-chat"
    assert dumped["reference"]["gold_labels"]["outcome"] == "hidden-from-roles"

    role_view = contract.role_view()
    assert "reference" not in role_view
    assert "reference" not in json.dumps(role_view)
    assert "hidden-from-roles" not in json.dumps(role_view)
    assert role_view["dataset_id"] == "enforcement"
    assert "applicant" in role_view["visible_materials"]
    assert strip_reference(dumped)["cluster_id"] == "enf-cn-notice-001"
    assert "reference" not in strip_reference(dumped)


def test_run_and_eval_skeletons_bind_report_to_run():
    run_id = new_run_id()
    report_id = new_report_id()
    UUID(report_id)
    run = RunContract(
        run_id=run_id,
        derived_from=None,
        session_id="sess-demo",
        dataset_id="cisg",
        cluster_id="cisg-art79-sample-001",
        pack_version="0.1.0",
        task_type="cisg_article79",
        materials_hash="abc",
        stop_reason="completed",
    )
    report = EvalContract(report_id=report_id, run_id=run.run_id, reference_version="0.1.0")
    assert report.run_id == run.run_id
    with pytest.raises(ValidationError):
        EvalContract(report_id="eval_20260912_112700", run_id=run_id)
    copied = EvalContract.model_validate({"report_id": uuid4(), "run_id": run_id})
    UUID(copied.report_id)


def test_loader_lists_and_gets_both_sample_packs():
    loader = _loader()
    assert loader.list_datasets() == ["cisg", "enforcement"]
    packs = loader.list_packs()
    identities = {(row.dataset_id, row.cluster_id, row.pack_version) for row in packs}
    assert ("enforcement", "enf-cn-notice-001", "0.1.0-draft") in identities
    assert ("cisg", "cisg-art79-sample-001", "0.1.0") in identities

    enforcement = loader.get_pack("enforcement", "enf-cn-notice-001", "0.1.0-draft")
    cisg = loader.get_pack("cisg", "cisg-art79-sample-001", "0.1.0")
    assert enforcement.task_type == "enforcement_nyc"
    assert cisg.task_type == "cisg_article79"
    assert loader.get_document_text("enforcement", "enf-cn-notice-001", "001").startswith("【研究样例")
    assert "第七十九条" in loader.get_document_text("cisg", "cisg-art79-sample-001", "001")

    with pytest.raises(PackNotFoundError):
        loader.get_pack("enforcement", "does-not-exist")
    with pytest.raises(PackVersionMismatchError):
        loader.get_pack("cisg", "cisg-art79-sample-001", "9.9.9")


def test_enforcement_pack_six_columns_are_pending_draft():
    pack = _loader().get_pack("enforcement", "enf-cn-notice-001", "0.1.0-draft")
    for field in SIX_COLUMN_FIELDS:
        assert getattr(pack, field), field
    assert pack.review_state == "pending"
    assert pack.task_labels.task_type == "enforcement_nyc"
    assert pack.task_labels.enforcement_forum == "CN"
    assert pack.task_labels.procedure_type == "recognition_and_enforcement"
    assert pack.task_labels.convention_issues == ["nyc-v-1-b"]
    notice = next(item for item in pack.procedural_facts if item.field_key == "notice_of_proceedings")
    assert notice.value == UNKNOWN
    assert notice.missing_code == "UV"
    assert notice.speaker == "researcher"
    assert pack.court_findings[0].finding == UNKNOWN
    assert pack.court_findings[0].missing_code == "NR"
    assert [event.event_id for event in pack.task_labels.notice_events] == [
        "enf-notice-constitution",
        "enf-notice-hearing",
    ]
    assert pack.documents[0].original_ref is not None
    assert pack.documents[0].original_ref.raw_id == "B-SAMPLE-001"
    assert [row.argument_id for row in pack.argument_records] == [
        "enf-arg-applicant",
        "enf-arg-respondent",
    ]
    assert pack.argument_records[1].rebuttal_target == "enf-arg-applicant"
    assert any(link.relation == "rule_basis" for link in pack.evidence_links)
    assert all(item.review_state == "pending" for item in pack.procedural_facts)
    assert all(item.review_state == "pending" for item in pack.party_claims)
    assert pack.reference is not None
    assert "reference" not in pack.role_view()


def test_cisg_art79_sample_is_fully_annotated_with_four_review_states():
    pack = _loader().get_pack("cisg", "cisg-art79-sample-001", "0.1.0")
    for field in SIX_COLUMN_FIELDS:
        assert getattr(pack, field), field
    assert pack.task_labels.task_type == "cisg_article79"
    element_ids = [item.element_id for item in pack.task_labels.elements]
    assert tuple(element_ids) == CISG_ART79_ELEMENT_IDS
    states = {record.review_state for record in pack.review_records}
    assert states == set(REVIEW_STATES)
    assert pack.task_labels.conclusion_label == UNKNOWN
    assert pack.task_labels.original_label_relation == "incomparable"
    assert [row.judgment_id for row in pack.task_labels.judgments] == ["cisg-j-1"]
    assert all(item.judgment_id == "cisg-j-1" for item in pack.task_labels.elements)
    assert pack.reference is not None
    assert pack.reference.acceptable_paths
    assert pack.reference.acceptable_paths[0].path_id == "exempt-if-unforeseeable-and-noticed"
    assert pack.reference.acceptable_paths[0].requires
    assert [row.argument_id for row in pack.argument_records] == [
        "cisg-arg-seller",
        "cisg-arg-buyer",
    ]
    assert pack.argument_records[1].rebuttal_target == "cisg-arg-seller"
    assert "reference" not in pack.role_view()
    assert "gold_labels" not in json.dumps(pack.role_view())


def test_source_anchors_point_back_to_original_text():
    loader = _loader()
    for dataset_id, cluster_id in (
        ("enforcement", "enf-cn-notice-001"),
        ("cisg", "cisg-art79-sample-001"),
    ):
        pack = loader.get_pack(dataset_id, cluster_id)
        texts = {
            doc.document_id: loader.get_document_text(dataset_id, cluster_id, doc.document_id)
            for doc in pack.documents
        }
        for anchor in pack.source_anchors:
            body = texts[anchor.document_id]
            assert f"[{anchor.locator}]" in body
            assert anchor.quote in body
            if anchor.start_offset is not None:
                assert body[anchor.start_offset :].startswith(f"[{anchor.locator}]")


def test_task_types_cannot_be_swapped_across_datasets():
    pack = _loader().get_pack("enforcement", "enf-cn-notice-001")
    payload = pack.model_dump(mode="json")
    payload["task_type"] = "cisg_article79"
    payload["task_labels"] = {
        "task_type": "cisg_article79",
        "article": "79",
        "elements": [],
    }
    with pytest.raises(ValidationError):
        ResearchPack.model_validate(payload)


def test_historical_value_requires_source_or_unknown():
    InputContract.model_validate(
        {
            "dataset_id": "cisg",
            "cluster_id": "cisg-art79-sample-001",
            "pack_version": "0.1.0",
            "task_type": "cisg_article79",
            "visible_materials": {"claimant": VisibleMaterials().model_dump()},
            "experiment_conditions": ExperimentConditions().model_dump(),
            "model_config": ModelConfigSnapshot().model_dump(),
        }
    )
    with pytest.raises(ValidationError):
        AnnotatedValue(
            item_id="bad",
            field_key="award_seat",
            value="新加坡",
            source_ids=[],
            source_tier="historical",
        )
    ok = AnnotatedValue(
        item_id="ok",
        field_key="award_seat",
        value=UNKNOWN,
        source_ids=[],
        source_tier="historical",
        missing_code="UV",
    )
    assert ok.value == UNKNOWN
    assert ok.missing_code == "UV"
    with pytest.raises(ValidationError):
        AnnotatedValue(
            item_id="cf",
            field_key="award_seat",
            value=UNKNOWN,
            source_ids=["001:p1"],
            source_tier="researcher",
            missing_code="CF",
        )
    conflict = AnnotatedValue(
        item_id="cf-ok",
        field_key="award_seat",
        value=UNKNOWN,
        source_ids=["001:p1", "001:p2"],
        source_tier="researcher",
        missing_code="CF",
        conflict_values=["新加坡", "香港"],
    )
    assert conflict.conflict_values == ["新加坡", "香港"]


def test_field_key_dictionary_rejects_unknown_fact_and_gap_fields():
    pack = _loader().get_pack("enforcement", "enf-cn-notice-001")
    payload = pack.model_dump(mode="json")
    payload["procedural_facts"][0]["field_key"] = "not_a_dictionary_key"
    with pytest.raises(ValidationError):
        ResearchPack.model_validate(payload)
    with pytest.raises(ValidationError):
        MaterialGap(
            gap_id="bad",
            description="x",
            related_field="not_a_dictionary_key",
        )
    ok_gap = MaterialGap(
        gap_id="ok",
        description="x",
        related_field="notice_of_proceedings",
        missing_code="NR",
    )
    assert ok_gap.missing_code == "NR"


def test_experiment_hide_cannot_overlap_natural_missing():
    ExperimentConditions(
        hide_source_ids=["001:p2"],
        natural_missing_source_ids=["001:p3"],
    )
    with pytest.raises(ValidationError):
        ExperimentConditions(
            hide_source_ids=["001:p1"],
            natural_missing_source_ids=["001:p1"],
        )


def test_argument_graph_requires_known_ids():
    pack = _loader().get_pack("enforcement", "enf-cn-notice-001")
    payload = pack.model_dump(mode="json")
    payload["argument_records"][1]["rebuttal_target"] = "not-an-argument"
    with pytest.raises(ValidationError):
        ResearchPack.model_validate(payload)

    payload = pack.model_dump(mode="json")
    payload["evidence_links"][0]["evidence_id"] = "missing-id"
    with pytest.raises(ValidationError):
        ResearchPack.model_validate(payload)

    payload = pack.model_dump(mode="json")
    payload["argument_records"][0]["fact_ids"] = ["not-a-fact"]
    with pytest.raises(ValidationError):
        ResearchPack.model_validate(payload)
