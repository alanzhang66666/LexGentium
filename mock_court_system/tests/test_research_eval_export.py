"""Research rubric penalties and export bundle identity."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.lib.research_rubric import REASONING_INDEPENDENCE_CAP, score_research_output  # noqa: E402


def test_rubric_penalty_wrong_reasons():
    result = score_research_output(
        output={
            "conclusion": "refuse_enforcement",
            "reasons": ["public policy / 公共政策"],
            "text": "应拒绝承认，依据公共政策。",
        },
        claims=[
            {
                "claim_id": "c1",
                "status": "assert",
                "fact": "award exists",
                "norm": "public policy",
                "reasoning": "public policy only",
                "events": [
                    {
                        "action": "assert",
                        "fact": "award exists",
                        "norm": "public policy",
                        "reasoning": "public policy only",
                    }
                ],
            }
        ],
        reference={
            "reference_version": "test",
            "gold_labels": {
                "outcome": "refuse_enforcement",
                "reasons": ["nyc-v-1-b", "proper notice"],
                "convention_issue": "nyc-v-1-b",
            },
        },
    )
    assert result["legal_quality"]["wrong_reasons"] is True
    assert result["legal_quality"]["overall"] <= REASONING_INDEPENDENCE_CAP
    assert result["penalties"]["reasoning_independence"]["applied"] is True
    assert any(item.get("code") == "wrong_reasons" for item in result["failures"])


def test_rubric_acceptable_path_can_pass():
    result = score_research_output(
        output={
            "conclusion": "undecidable",
            "reasons": ["notice arrival is unknown", "admit material insufficient"],
            "unknown_marked": True,
            "citations_ok": True,
            "rebuttal_response": True,
            "facts_supported": True,
        },
        claims=[
            {
                "claim_id": "c1",
                "status": "admit_insufficient",
                "fact": "arrival unknown",
                "norm": "nyc-v-1-b",
                "reasoning": "cannot prove proper notice from the pack",
                "source_ids": ["001:p3"],
                "events": [
                    {
                        "action": "admit_insufficient",
                        "fact": "arrival unknown",
                        "norm": "nyc-v-1-b",
                        "reasoning": "cannot prove proper notice from the pack",
                        "source_ids": ["001:p3"],
                    }
                ],
            }
        ],
        reference={
            "gold_labels": {"outcome": "refuse_enforcement", "reasons": ["nyc-v-1-b"]},
            "acceptable_paths": [
                {
                    "path_id": "unknown-notice",
                    "conclusion_label": "undecidable",
                    "requires_any": ["unknown", "insufficient", "admit"],
                }
            ],
        },
    )
    assert result["legal_quality"]["acceptable_path"] == "unknown-notice"
    assert result["legal_quality"]["passed_review_gate"] is True
    assert any(item.get("code") == "acceptable_path" for item in result["disagreements"])


def test_export_contains_run_id_materials_hash_eval(monkeypatch, tmp_path):
    import uuid

    claims_db = tmp_path / f"export-claims-{uuid.uuid4().hex}.sqlite3"
    conv_db = tmp_path / f"export-conv-{uuid.uuid4().hex}.sqlite3"
    monkeypatch.setenv("CONVERSATION_STORE", "sqlite")
    monkeypatch.setenv("CONVERSATION_DB_PATH", str(conv_db))
    monkeypatch.setenv("RESEARCH_CLAIMS_DB", str(claims_db))
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

    import api_server  # noqa: F401
    from api.services import claims as claim_service
    from api.services.conversation import start_session
    from api.services.research_eval import export_bundle

    claim_service.reset_store_for_tests(claims_db)
    started = start_session(
        "CI",
        "enf-cn-notice-001",
        dataset_id="enforcement",
        cluster_id="enf-cn-notice-001",
        pack_version="0.1.0-draft",
    )
    run_id = started["run_id"]
    claim_service.append_claim_event(
        run_id=run_id,
        session_id=started["session_id"],
        role="applicant",
        action="assert",
        fact="组庭与开庭通知原件未收录",
        norm="nyc-v-1-b",
        reasoning="送达到达为 unknown，不能认定已获适当通知",
        source_ids=["001:p3"],
    )
    bundle = export_bundle(run_id)
    assert bundle["run_id"] == run_id
    assert bundle["materials_hash"]
    assert bundle["materials_hash"] == started["materials_hash"]
    assert bundle["eval"]["run_id"] == run_id
    assert bundle["eval"]["rubric"]["dimensions"]
    assert "disclaimer" in bundle
    assert bundle["claims"]
