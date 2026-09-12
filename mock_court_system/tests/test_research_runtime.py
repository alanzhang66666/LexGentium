"""Research runtime: material views, derived runs, civil passthrough, claims."""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

_CORE_DIR = Path(__file__).resolve().parents[1] / "core"
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from research.runtime import (  # noqa: E402
    CACHE_MODE_INDEPENDENT,
    CACHE_MODE_REPLAY,
    bind_research_context,
    condition_fingerprint,
    conditions_changed,
    count_argument_turns,
    filter_materials_for_role,
    filter_retrieval_snippets,
    merge_condition_overrides,
    research_cache_namespace,
    research_llm_blocked,
    research_stop_notice,
    reset_research_context,
    resolve_visible_materials,
    role_model_input,
    session_stop_reason,
)


def _runtime_path(name: str) -> Path:
    base = Path(__file__).resolve().parent / "runtime_tmp"
    base.mkdir(exist_ok=True)
    return base / f"{name}-{uuid.uuid4().hex}.sqlite3"


def _load_api_server(monkeypatch, db_path, claims_path=None):
    monkeypatch.setenv("CONVERSATION_STORE", "sqlite")
    monkeypatch.setenv("CONVERSATION_DB_PATH", str(db_path))
    monkeypatch.setenv("RESEARCH_CLAIMS_DB", str(claims_path or _runtime_path("claims")))
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")

    stale = [
        m
        for m in list(sys.modules)
        if m == "api_server" or m == "api" or m.startswith("api.") or m in ("api_runtime", "config", "settings")
    ]
    for module_name in stale:
        sys.modules.pop(module_name, None)

    import api_server
    from api import state
    from api.services import claims as claim_service

    claim_service.reset_store_for_tests(claims_path or _runtime_path("claims-reset"))

    captured = {}

    def fake_run_agent_turn(*, scenario, case_id, dialog_history, input_json):
        captured["input_json"] = json.loads(json.dumps(input_json))
        return "Lawyer", f"offline reply for {scenario}:{case_id}", False

    state.run_agent_turn = fake_run_agent_turn
    return api_server, captured


HIDDEN = "本层不得写入角色可见快照"


def test_material_filter_strips_reference_and_hidden_docs():
    research = {
        "run_id": "run_filter",
        "dataset_id": "enforcement",
        "cluster_id": "enf-filter",
        "task_type": "enforcement_nyc",
        "materials_hash": "abc",
        "reference": {
            "reference_version": "x",
            "gold_labels": {"secret": HIDDEN},
            "notes": HIDDEN,
        },
        "gold_labels": {"secret": HIDDEN},
        "documents": [
            {"document_id": "001", "text": "visible notice narrative"},
            {"document_id": "002", "text": "hidden convention text"},
        ],
        "source_anchors": [
            {"source_id": "001:p1", "document_id": "001", "quote": "visible"},
            {"source_id": "002:zh", "document_id": "002", "quote": "hidden"},
        ],
        "procedural_facts": [
            {"item_id": "a", "value": "seat", "source_ids": ["001:p1"], "document_id": "001"},
            {"item_id": "b", "value": "secret-fact", "source_ids": ["002:zh"], "document_id": "002"},
        ],
        "rules": [
            {"rule_id": "nyc-v", "rule_version": "1958", "text": "visible rule"},
            {"rule_id": "hidden-rule", "rule_version": "x", "text": "no"},
        ],
        "visible_materials": {
            "applicant": {
                "document_ids": ["001"],
                "source_ids": ["001:p1"],
                "rule_ids": ["nyc-v"],
            }
        },
        "experiment_conditions": {"hide_source_ids": []},
    }

    view = filter_materials_for_role(research, "applicant")
    dumped = json.dumps(view, ensure_ascii=False)
    assert "reference" not in view
    assert "gold_labels" not in view
    assert HIDDEN not in dumped
    assert [doc["document_id"] for doc in view["documents"]] == ["001"]
    assert [row["source_id"] for row in view["source_anchors"]] == ["001:p1"]
    assert [row["item_id"] for row in view["procedural_facts"]] == ["a"]
    assert [row["rule_id"] for row in view["rules"]] == ["nyc-v"]

    model_input = role_model_input({"research": research, "reference": {"gold_labels": {"x": HIDDEN}}}, "applicant")
    assert "reference" not in model_input
    assert HIDDEN not in json.dumps(model_input, ensure_ascii=False)
    assert "visible notice narrative" in model_input["case_description"]
    assert "hidden convention text" not in model_input["case_description"]


def test_retrieval_and_cache_namespace_distinguish_replay():
    research = {
        "run_id": "run_cache",
        "dataset_id": "enforcement",
        "cluster_id": "enf-cache",
        "task_type": "enforcement_nyc",
        "materials_hash": "hash-1",
        "visible_materials": {
            "applicant": {"document_ids": ["001"], "source_ids": ["001:p1"], "rule_ids": []},
        },
        "experiment_conditions": {"hide_source_ids": ["002:zh"]},
        "documents": [],
    }
    snippets = [
        {"document_id": "001", "source_id": "001:p1", "content": "ok"},
        {"document_id": "002", "source_id": "002:zh", "content": "hidden"},
        {"content": 'gold_labels leaked "reference"'},
    ]
    token = bind_research_context({"research": research}, "applicant", cache_mode=CACHE_MODE_REPLAY)
    try:
        kept = filter_retrieval_snippets(snippets)
        assert [row.get("source_id") for row in kept] == ["001:p1"]
        replay = dict(research_cache_namespace())
        reset_research_context(token)
        token = bind_research_context(
            {"research": research},
            "applicant",
            cache_mode=CACHE_MODE_INDEPENDENT,
            attempt_id="attempt-2",
        )
        independent = dict(research_cache_namespace())
        assert replay["cache_mode"] == CACHE_MODE_REPLAY
        assert independent["cache_mode"] == CACHE_MODE_INDEPENDENT
        assert replay != independent
        assert "attempt_id" in independent
    finally:
        reset_research_context(token)


def test_new_conditions_create_derived_run(monkeypatch):
    api_server, _ = _load_api_server(monkeypatch, _runtime_path("derive-run"), _runtime_path("derive-claims"))
    from api import state
    from api.services.conversation import derive_session, start_session

    first = start_session(
        "CI",
        "enf-cn-notice-001",
        dataset_id="enforcement",
        cluster_id="enf-cn-notice-001",
        pack_version="0.1.0-draft",
    )
    parent = state.conversation_store.get(first["session_id"])
    parent_research = parent.input_json["research"]
    with pytest.raises(HTTPException) as unchanged:
        derive_session(first["session_id"])
    assert unchanged.value.status_code == 400

    derived = derive_session(
        first["session_id"],
        experiment_conditions={"hide_source_ids": ["001:p1"], "enable_source_audit": True},
    )
    assert derived["run_id"] != first["run_id"]
    assert derived["derived_from"] == first["run_id"]
    child = state.conversation_store.get(derived["session_id"])
    child_research = child.input_json["research"]
    assert child_research["derived_from"] == parent_research["run_id"]
    assert child_research["experiment_conditions"]["hide_source_ids"] == ["001:p1"]
    assert conditions_changed(parent_research, child_research)
    proposed = merge_condition_overrides(
        parent_research,
        experiment_conditions={"hide_source_ids": ["001:p1"], "enable_source_audit": True},
    )
    assert condition_fingerprint(parent_research) != condition_fingerprint(proposed)


def test_civil_path_unchanged(monkeypatch, tmp_path):
    api_server, captured = _load_api_server(monkeypatch, _runtime_path("civil-runtime"), _runtime_path("civil-claims"))
    from api import state
    from api.services.conversation import send_message, start_session

    split_dir = tmp_path / "data" / "dataset_1000" / "test"
    split_dir.mkdir(parents=True)
    row = {
        "case_id": "CASE-CIVIL-1",
        "cause": "民间借贷纠纷",
        "case_description": "原告主张被告借款未还。",
        "plaintiff_claims": ["偿还本金"],
        "plaintiff_name": "张三",
        "defendant_name": "李四",
    }
    (split_dir / "case_info.jsonl").write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    state.project_root = tmp_path

    result = start_session("CI", "CASE-CIVIL-1")
    record = state.conversation_store.get(result["session_id"])
    assert "research" not in record.input_json
    assert record.input_json["case_description"] == row["case_description"]
    send_message(result["session_id"], "到庭", "Plaintiff")
    assert "research" not in captured["input_json"]
    assert captured["input_json"]["case_description"] == row["case_description"]
    assert "reference" not in captured["input_json"]


def test_claims_append_only_and_require_triad(monkeypatch):
    db = _runtime_path("claim-events")
    monkeypatch.setenv("RESEARCH_CLAIMS_DB", str(db))
    from api.services import claims as claim_service

    store = claim_service.reset_store_for_tests(db)
    with pytest.raises(claim_service.ClaimIncompleteError):
        claim_service.append_claim_event(
            run_id="run_claim",
            session_id="s1",
            role="applicant",
            action="assert",
            fact="only fact",
        )
    first = claim_service.append_claim_event(
        run_id="run_claim",
        session_id="s1",
        role="applicant",
        action="assert",
        fact="notice unknown",
        norm="NYC V(1)(b)",
        reasoning="arrival is unknown so the notice element is not proven",
    )
    claim_service.append_claim_event(
        run_id="run_claim",
        session_id="s1",
        role="respondent",
        action="rebut",
        reasoning="applicant has not produced the original notice",
        target_claim_id=first["claim_id"],
        claim_id=first["claim_id"],
    )
    with pytest.raises(claim_service.ClaimActionError):
        claim_service.append_claim_event(
            run_id="run_claim",
            session_id="s1",
            role="applicant",
            action="assert",
            fact="again",
            norm="x",
            reasoning="y",
            claim_id=first["claim_id"],
        )
    claim_service.append_claim_event(
        run_id="run_claim",
        session_id="s1",
        role="applicant",
        action="admit_insufficient",
        reasoning="notice originals are not in the pack",
        claim_id=first["claim_id"],
    )
    events = store.list_events("run_claim")
    assert [item["seq"] for item in events] == [1, 2, 3]
    resumed = claim_service.list_claim_events("run_claim")
    assert [item["event_id"] for item in resumed] == [item["event_id"] for item in events]
    chain = claim_service.claim_chain("run_claim")
    assert chain[0]["status"] == "admit_insufficient"
    assert len(chain[0]["events"]) == 3


def _visibility_fixture() -> dict:
    return {
        "run_id": "run_vis",
        "dataset_id": "enforcement",
        "cluster_id": "enf-vis",
        "task_type": "enforcement_nyc",
        "materials_hash": "vis",
        "documents": [
            {"document_id": "001", "text": "notice narrative"},
            {"document_id": "002", "text": "evaluator convention text"},
        ],
        "source_anchors": [
            {"source_id": "001:p1", "document_id": "001", "quote": "filing"},
            {"source_id": "001:p2", "document_id": "001", "quote": "hearing"},
            {"source_id": "001:p3", "document_id": "001", "quote": "natural gap"},
            {"source_id": "002:zh", "document_id": "002", "quote": "eval only"},
        ],
        "argument_records": [
            {
                "argument_id": "arg-a",
                "source_ids": ["001:p1"],
                "document_id": "001",
                "claim": "notice sent",
            },
            {
                "argument_id": "arg-b",
                "source_ids": ["002:zh"],
                "document_id": "002",
                "claim": "hidden from applicant",
            },
        ],
        "evidence_links": [
            {
                "link_id": "l-a",
                "object_id": "arg-a",
                "relation": "source_support",
                "evidence_id": "001:p1",
            },
            {
                "link_id": "l-b",
                "object_id": "arg-b",
                "relation": "source_support",
                "evidence_id": "002:zh",
            },
        ],
        "visible_materials": {
            "applicant": {
                "document_ids": ["001"],
                "source_ids": ["001:p1", "001:p3"],
                "rule_ids": [],
            },
            "auditor": {
                "document_ids": ["001", "002"],
                "source_ids": ["001:p1", "001:p2", "002:zh"],
                "rule_ids": [],
            },
        },
        "visibility_grants": [
            {
                "grant_id": "g-stage",
                "role": "applicant",
                "stage": "hearing",
                "visibility": "stage_open",
                "document_id": "001",
                "source_id": "001:p2",
            },
            {
                "grant_id": "g-eval",
                "role": "applicant",
                "visibility": "evaluator_only",
                "document_id": "002",
                "source_id": "002:zh",
            },
        ],
        "experiment_conditions": {
            "stage": "filing",
            "hide_source_ids": [],
            "natural_missing_source_ids": ["001:p3"],
        },
    }


def test_stage_grants_and_evaluator_only_are_role_specific():
    research = _visibility_fixture()
    filing = resolve_visible_materials(research, "applicant")
    assert "001:p2" not in filing["source_ids"]
    assert "002:zh" not in filing["source_ids"]
    assert "001:p3" not in filing["source_ids"]

    hearing = resolve_visible_materials(research, "applicant", stage="hearing")
    assert "001:p2" in hearing["source_ids"]
    assert "002:zh" not in hearing["source_ids"]

    evaluator = resolve_visible_materials(research, "evaluator")
    assert "002:zh" in evaluator["source_ids"]
    assert "001:p2" in evaluator["source_ids"]

    applicant_view = filter_materials_for_role(research, "applicant")
    assert [row["argument_id"] for row in applicant_view["argument_records"]] == ["arg-a"]
    assert [row["link_id"] for row in applicant_view["evidence_links"]] == ["l-a"]
    assert "002" not in [doc["document_id"] for doc in applicant_view["documents"]]
    assert "001:p3" not in applicant_view["visible_materials"]["applicant"]["source_ids"]


def test_natural_missing_and_experimental_hide_both_leave_role_view():
    research = _visibility_fixture()
    research["experiment_conditions"] = {
        "stage": "filing",
        "hide_source_ids": ["001:p1"],
        "natural_missing_source_ids": ["001:p3"],
    }
    view = filter_materials_for_role(research, "applicant")
    sources = {row["source_id"] for row in view["source_anchors"]}
    assert "001:p1" not in sources
    assert "001:p3" not in sources
    assert view["argument_records"] == []
    assert view["evidence_links"] == []


def test_frozen_snapshot_keeps_argument_graph(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    from api.services.materials import freeze_role_snapshot

    research = freeze_role_snapshot("enforcement", "enf-cn-notice-001", "0.1.0-draft")
    assert "reference" not in research
    assert [row["argument_id"] for row in research["argument_records"]] == [
        "enf-arg-applicant",
        "enf-arg-respondent",
    ]
    assert any(link["relation"] == "rule_basis" for link in research["evidence_links"])
    grants = [
        {
            "grant_id": "g1",
            "role": "applicant",
            "visibility": "hidden",
            "source_id": "001:p3",
        }
    ]
    proposed = merge_condition_overrides(research, visibility_grants=grants)
    assert conditions_changed(research, proposed)


def _research_input(task_type: str = "enforcement_nyc") -> dict:
    dataset = "cisg" if task_type == "cisg_article79" else "enforcement"
    return {
        "research": {
            "run_id": "run-stop",
            "dataset_id": dataset,
            "cluster_id": "cluster-stop",
            "task_type": task_type,
        }
    }


def test_count_argument_turns_skips_judge_and_lawyer():
    history = [
        {"role": "Judge", "message": "开庭"},
        {"role": "Lawyer", "message": "代理词"},
        {"role": "Plaintiff", "message": "主张一"},
        {"role": "Defendant", "message": "抗辩一"},
        {"role": "applicant", "message": "补充"},
        {"role": "Final", "message": "停止"},
    ]
    assert count_argument_turns(history) == 3


def test_research_stop_caps_enforcement_at_12_and_cisg_at_10():
    nyc = [{"role": "Plaintiff", "message": str(i)} for i in range(12)]
    cisg = [{"role": "Plaintiff", "message": str(i)} for i in range(10)]
    assert session_stop_reason(task_type="enforcement_nyc", dialog_history=nyc[:11]) is None
    assert session_stop_reason(task_type="enforcement_nyc", dialog_history=nyc) == "max_turns"
    assert session_stop_reason(task_type="cisg_article79", dialog_history=cisg[:9]) is None
    assert session_stop_reason(task_type="cisg_article79", dialog_history=cisg) == "max_turns"
    assert (
        session_stop_reason(task_type="enforcement_nyc", claim_actions=["admit_insufficient"])
        == "material_insufficient"
    )


def test_research_llm_blocked_is_noop_for_civil():
    party_heavy = [{"role": "Plaintiff", "message": str(i)} for i in range(20)]
    assert research_llm_blocked({"case_id": "civil"}, party_heavy) is None
    assert research_llm_blocked(_research_input(), party_heavy[:11]) is None
    assert research_llm_blocked(_research_input(), party_heavy[:12]) == "max_turns"
    assert research_llm_blocked(_research_input("cisg_article79"), party_heavy[:10]) == "max_turns"
    lawyers = [{"role": "Lawyer", "message": str(i)} for i in range(20)]
    assert research_llm_blocked(_research_input(), lawyers) is None
    assert "上限" in research_stop_notice("max_turns")
