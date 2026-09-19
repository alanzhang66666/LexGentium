"""Regression tests for the final role-specific research input boundary."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.research.runtime import role_model_input


PACKS = (
    Path(__file__).parents[1] / "data/research_packs/enforcement/enf-cn-notice-001/pack.json",
    Path(__file__).parents[1] / "data/research_packs/cisg/cisg-art79-sample-001/pack.json",
)


def _pack(path: Path) -> dict:
    research = json.loads(path.read_text(encoding="utf-8"))
    research.update(run_id="run-test", materials_hash="test")
    return research


def _ids(research: dict) -> dict[str, list[str]]:
    return {
        "document_ids": [str(row["document_id"]) for row in research.get("documents", [])],
        "source_ids": [str(row["source_id"]) for row in research.get("source_anchors", [])],
        "rule_ids": [str(row["rule_id"]) for row in research.get("rules", [])],
    }


def _input(research: dict, role: str = "applicant") -> dict:
    return role_model_input({"research": research}, role)


@pytest.mark.parametrize("path", PACKS, ids=["enforcement-sample", "cisg-sample"])
def test_unconfigured_and_explicit_empty_allowlists_fail_closed(path: Path):
    research = _pack(path)
    unconfigured = _input(research)["research"]
    assert unconfigured["documents"] == []
    assert unconfigured["source_anchors"] == []
    assert unconfigured["procedural_facts"] == []
    assert unconfigured["party_claims"] == []

    research["visible_materials"] = {"applicant": {"document_ids": [], "source_ids": [], "rule_ids": []}}
    empty = _input(research)["research"]
    assert all(not empty.get(key) for key in ("documents", "source_anchors", "procedural_facts", "party_claims", "rules"))


@pytest.mark.parametrize("path", PACKS, ids=["enforcement-sample", "cisg-sample"])
def test_single_source_allowlist_filters_derived_facts_claims_and_labels(path: Path):
    research = _pack(path)
    ids = _ids(research)
    chosen_source = ids["source_ids"][0]
    chosen_anchor = next(row for row in research["source_anchors"] if row["source_id"] == chosen_source)
    chosen_doc = chosen_anchor.get("document_id")
    research["visible_materials"] = {
        "applicant": {
            "document_ids": [chosen_doc] if chosen_doc else [],
            "source_ids": [chosen_source],
            "rule_ids": [],
        }
    }
    visible = _input(research)["research"]
    assert all(row["source_id"] == chosen_source for row in visible["source_anchors"])
    for field in ("procedural_facts", "party_claims", "court_findings", "legal_bases", "argument_records"):
        for row in visible.get(field, []):
            assert set(row.get("source_ids", [])) <= {chosen_source}
    for value in visible.get("task_labels", {}).values():
        if isinstance(value, list):
            for row in value:
                if isinstance(row, dict) and row.get("source_ids"):
                    assert set(row["source_ids"]) <= {chosen_source}


@pytest.mark.parametrize("path", PACKS, ids=["enforcement-sample", "cisg-sample"])
def test_full_allowlist_preserves_all_materials_and_hidden_source_is_removed(path: Path):
    research = _pack(path)
    research["visible_materials"] = {"applicant": _ids(research)}
    full = _input(research)["research"]
    assert len(full["documents"]) == len(research["documents"])
    assert len(full["source_anchors"]) == len(research["source_anchors"])

    hidden = research["source_anchors"][0]["source_id"]
    research["experiment_conditions"] = {"hide_source_ids": [hidden]}
    filtered = _input(research)["research"]
    assert hidden not in {row["source_id"] for row in filtered["source_anchors"]}
    for field in ("procedural_facts", "party_claims", "court_findings", "legal_bases", "argument_records"):
        assert all(hidden not in row.get("source_ids", []) for row in filtered.get(field, []))


def test_stage_grant_adds_only_material_authorized_for_that_stage():
    research = _pack(PACKS[0])
    anchor = research["source_anchors"][1]
    source_id = anchor["source_id"]
    document_id = anchor.get("document_id")
    research["visible_materials"] = {"applicant": {"document_ids": [], "source_ids": [], "rule_ids": []}}
    research["visibility_grants"] = [{
        "grant_id": "hearing-only", "role": "applicant", "stage": "hearing",
        "visibility": "stage_open", "source_id": source_id, "document_id": document_id,
    }]
    # final input helper currently resolves the default stage; exercise the final filter directly via context pack stage.
    research["experiment_conditions"] = {"stage": "hearing"}
    visible = _input(research)["research"]
    assert source_id in visible["visible_materials"]["applicant"]["source_ids"]
    assert {row["source_id"] for row in visible["source_anchors"]} == {source_id}


def test_retrieval_snippets_fail_closed_for_empty_visibility_context():
    from core.research.runtime import ResearchCallContext, filter_retrieval_snippets

    context = ResearchCallContext(
        run_id="run-test", role="applicant", materials_hash="test",
        visible_document_ids=frozenset(), visible_source_ids=frozenset(), visible_rule_ids=frozenset(),
    )
    snippets = [
        {"source_id": "001:p1", "quote": "known source"},
        {"document_id": "001", "text": "known document"},
        {"text": "unanchored text"},
    ]
    assert filter_retrieval_snippets(snippets, context) == []


def _empty_research_context_pack() -> dict:
    return {
        "run_id": "run-empty-context", "dataset_id": "enforcement",
        "cluster_id": "cluster-empty", "task_type": "enforcement_nyc",
        "materials_hash": "empty", "visible_materials": {
            "applicant": {"document_ids": [], "source_ids": [], "rule_ids": []}
        },
    }


def test_run_agent_turn_binds_empty_research_visibility_through_process_turn(monkeypatch):
    from api import state
    from core.research.runtime import filter_retrieval_snippets, current_research_context

    class StubAgent:
        def process_turn(self, dialog_history, case_id, input_json, **kwargs):
            assert current_research_context() is not None
            self.visible = filter_retrieval_snippets([
                {"source_id": "001:p1", "quote": "must be hidden"},
                {"text": "unanchored retrieval"},
            ])
            return "continuing"

        class StateMachine:
            @staticmethod
            def export_state():
                return {"is_finished": False}

        state_machine = StateMachine()

    agent = StubAgent()
    monkeypatch.setattr(state, "_ci_final", lambda _text: False)
    assert state.run_agent_turn(
        scenario="CI", case_id="cluster-empty", dialog_history=[{"role": "applicant", "message": "claim"}],
        input_json={"research": _empty_research_context_pack()}, ci_agent=agent,
    ) == ("Judge", "continuing", False)
    assert agent.visible == []
    assert current_research_context() is None


def test_run_agent_turn_resets_research_context_when_agent_raises():
    from api import state
    from core.research.runtime import current_research_context

    class BrokenAgent:
        state_machine = None

        def process_turn(self, *args, **kwargs):
            assert current_research_context() is not None
            raise RuntimeError("stub failure")

    with pytest.raises(RuntimeError, match="stub failure"):
        state.run_agent_turn(
            scenario="CI", case_id="cluster-empty", dialog_history=[{"role": "applicant", "message": "claim"}],
            input_json={"research": _empty_research_context_pack()}, ci_agent=BrokenAgent(),
        )
    assert current_research_context() is None


def test_run_agent_turn_keeps_civil_retrieval_without_research_context(monkeypatch):
    from api import state
    from core.research.runtime import current_research_context, filter_retrieval_snippets

    class CivilStub:
        def process_turn(self, dialog_history, case_id, input_json):
            assert input_json == {"ordinary": "civil"}
            assert current_research_context() is None
            self.visible = filter_retrieval_snippets(["ordinary civil retrieval"])
            return "draft"

    agent = CivilStub()
    monkeypatch.setattr(state, "cd_agent", agent)
    result = state.run_agent_turn(
        scenario="CD", case_id="civil-1", dialog_history=[{"role": "user", "message": "start"}],
        input_json={"ordinary": "civil"},
    )
    assert result == ("Lawyer", "draft", False)
    assert agent.visible == ["ordinary civil retrieval"]


def test_material_context_uses_active_respondent_role_duties():
    from core.research.runtime import material_context_message

    research = {
        **_empty_research_context_pack(),
        "documents": [{"document_id": "001", "text": "visible case text"}],
        "visible_materials": {
            role: {"document_ids": ["001"], "source_ids": [], "rule_ids": []}
            for role in ("applicant", "respondent")
        },
    }
    applicant_view = _input(research, "applicant")
    respondent_view = _input(research, "respondent")
    applicant_prompt = material_context_message(applicant_view)["message"]
    respondent_prompt = material_context_message(respondent_view)["message"]
    assert "主张承认与执行" in applicant_prompt
    assert "针对申请提出抗辩" not in applicant_prompt
    assert "针对申请提出抗辩" in respondent_prompt
    assert "主张承认与执行" not in respondent_prompt


def test_research_context_and_final_role_input_use_same_experiment_stage():
    from core.research.runtime import bind_research_context, current_research_context, reset_research_context

    research = {
        **_empty_research_context_pack(),
        "documents": [{"document_id": "001", "text": "visible"}],
        "source_anchors": [
            {"source_id": "001:p1", "document_id": "001", "quote": "base"},
            {"source_id": "001:p2", "document_id": "001", "quote": "hearing"},
        ],
        "visible_materials": {
            "applicant": {"document_ids": ["001"], "source_ids": ["001:p1"], "rule_ids": []}
        },
        "visibility_grants": [{
            "grant_id": "hearing", "role": "applicant", "stage": "hearing",
            "visibility": "stage_open", "document_id": "001", "source_id": "001:p2",
        }],
        "experiment_conditions": {"stage": "hearing"},
    }
    role_input = _input(research, "applicant")
    role_ids = role_input["research"]["visible_materials"]["applicant"]
    token = bind_research_context({"research": research}, "applicant")
    try:
        context = current_research_context()
        assert sorted(context.visible_document_ids) == role_ids["document_ids"]
        assert sorted(context.visible_source_ids) == role_ids["source_ids"]
        assert sorted(context.visible_rule_ids) == role_ids["rule_ids"]
        assert "001:p2" in context.visible_source_ids
    finally:
        reset_research_context(token)


def test_state_dispatch_injects_active_role_material_context_for_research(monkeypatch):
    from api import state

    research = {
        **_empty_research_context_pack(),
        "documents": [{"document_id": "001", "text": "respondent-visible text"}],
        "visible_materials": {
            "respondent": {"document_ids": ["001"], "source_ids": [], "rule_ids": []}
        },
    }
    filtered = _input(research, "respondent")

    class StubCivilAgent:
        def process_turn(self, dialog_history, case_id, input_json):
            assert dialog_history[0]["role"] == "System"
            assert "针对申请提出抗辩" in dialog_history[0]["message"]
            assert "respondent-visible text" in dialog_history[0]["message"]
            return "draft"

    monkeypatch.setattr(state, "cd_agent", StubCivilAgent())
    result = state.run_agent_turn(
        scenario="CD", case_id="cluster-empty", dialog_history=[{"role": "respondent", "message": "defend"}],
        input_json=filtered,
    )
    assert result == ("Lawyer", "draft", False)


def test_law_retriever_search_filters_research_results_at_real_exit(monkeypatch):
    from core.law_retriever import LawRetriever
    from core.research.runtime import bind_research_context, reset_research_context

    retriever = LawRetriever.__new__(LawRetriever)
    results = [
        {"law_id": 1, "content": "law id is not a pack authorization"},
        {"law_id": 2, "source_id": "source-allowed", "content": "authorized"},
        {"law_id": 3, "source_id": "source-hidden", "content": "hidden"},
    ]
    monkeypatch.setattr(retriever, "_vector_search", lambda query, top_k: [])
    monkeypatch.setattr(retriever, "_bm25_search", lambda query, top_k: [])
    monkeypatch.setattr(retriever, "_rrf_fusion", lambda vector, bm25: [{"law_id": i} for i in (1, 2, 3)])
    monkeypatch.setattr(retriever, "_rerank_model", lambda query, candidates, top_k: results)

    research = {
        **_empty_research_context_pack(),
        "visible_materials": {
            "applicant": {"document_ids": [], "source_ids": ["source-allowed"], "rule_ids": []}
        },
    }
    token = bind_research_context({"research": research}, "applicant")
    try:
        assert retriever.search("query") == [results[1]]
    finally:
        reset_research_context(token)

    # With no research context, the existing civil retrieval result shape is unchanged.
    assert retriever.search("query") == results
