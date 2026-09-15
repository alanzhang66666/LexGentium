"""Regression: selected pack / civil case materials hydrate into start_session."""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from core.research import ResearchPackLoader, new_run_id


def _runtime_path(name: str) -> Path:
    base = Path(__file__).resolve().parent / "runtime_tmp"
    base.mkdir(exist_ok=True)
    return base / f"{name}-{uuid.uuid4().hex}.sqlite3"


def _load_api_server(monkeypatch, db_path):
    monkeypatch.setenv("CONVERSATION_STORE", "sqlite")
    monkeypatch.setenv("CONVERSATION_DB_PATH", str(db_path))
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")

    stale = [
        m
        for m in list(sys.modules)
        if m == "api_server" or m == "api" or m.startswith("api.") or m in ("settings",)
    ]
    for module_name in stale:
        sys.modules.pop(module_name, None)

    import api_server
    from api import state

    def fake_run_agent_turn(*, scenario, case_id, dialog_history, input_json):
        return "Lawyer", f"offline reply for {scenario}:{case_id}", False

    state.run_agent_turn = fake_run_agent_turn
    return api_server


def _write_civil_row(root: Path, row: dict, split: str = "test") -> None:
    split_dir = root / "data" / "dataset_1000" / split
    split_dir.mkdir(parents=True, exist_ok=True)
    path = split_dir / "case_info.jsonl"
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


CIVIL_ROW = {
    "case_id": "CASE-0001",
    "cause": "民间借贷纠纷",
    "case_description": "原告主张被告借款未还，约定利息按月支付，到期后经催告仍未清偿。",
    "plaintiff_claims": ["偿还本金十万元", "支付约定利息"],
    "plaintiff_name": "张三",
    "defendant_name": "李四",
}


def test_research_pack_materials_hydrate_without_reference(monkeypatch):
    api_server = _load_api_server(monkeypatch, _runtime_path("hydrate-pack"))
    from api import state
    from api.services.conversation import start_session

    parent = new_run_id()
    result = start_session(
        "CI",
        "enf-cn-notice-001",
        dataset_id="enforcement",
        cluster_id="enf-cn-notice-001",
        pack_version="0.1.0-draft",
        derived_from=parent,
    )
    record = state.conversation_store.get(result["session_id"])
    assert record is not None
    research = record.input_json["research"]
    dumped = json.dumps(research, ensure_ascii=False)

    assert research["dataset_id"] == "enforcement"
    assert research["cluster_id"] == "enf-cn-notice-001"
    assert research["pack_version"] == "0.1.0-draft"
    assert research["task_type"] == "enforcement_nyc"
    assert research["run_id"].startswith("run_")
    assert research["derived_from"] == parent
    assert research["materials_hash"]
    assert "applicant" in research["visible_materials"]
    assert any(doc.get("document_id") == "001" for doc in research["documents"])
    assert any("研究样例" in str(doc.get("text") or "") for doc in research["documents"])
    assert any(item.get("field_key") == "notice_of_proceedings" for item in research["procedural_facts"])
    assert "reference" not in research
    assert "gold_labels" not in dumped
    assert "本层不得写入角色可见快照" not in dumped
    assert result["run_id"] == research["run_id"]


def test_cisg_pack_hydrates_article79_text(monkeypatch):
    api_server = _load_api_server(monkeypatch, _runtime_path("hydrate-cisg"))
    from api import state
    from api.services.conversation import start_session

    start_session(
        "CD",
        "cisg-art79-sample-001",
        dataset_id="cisg",
        cluster_id="cisg-art79-sample-001",
        pack_version="0.1.0",
    )
    sessions, _ = state.conversation_store.list(limit=1, offset=0)
    session_id = sessions[0]["session_id"]
    record = state.conversation_store.get(session_id)
    research = record.input_json["research"]
    texts = " ".join(str(doc.get("text") or "") for doc in research["documents"])
    assert "第七十九条" in texts
    assert research["task_type"] == "cisg_article79"
    assert "reference" not in research


def test_civil_case_id_hydrates_full_text(monkeypatch, tmp_path):
    api_server = _load_api_server(monkeypatch, _runtime_path("hydrate-civil"))
    from api import state
    from api.services.cases import get_case_full
    from api.services.conversation import start_session

    _write_civil_row(tmp_path, CIVIL_ROW)
    state.project_root = tmp_path

    loaded = get_case_full("CASE-0001")
    assert loaded is not None
    assert "借款未还" in loaded["case_description"]

    result = start_session("CI", "CASE-0001")
    record = state.conversation_store.get(result["session_id"])
    assert record is not None
    assert record.input_json["case_description"] == CIVIL_ROW["case_description"]
    assert record.input_json["plaintiff_claims"] == CIVIL_ROW["plaintiff_claims"]
    assert record.input_json["plaintiff_name"] == "张三"
    assert record.input_json["complaint"]["plaintiff_case_description"] == CIVIL_ROW["case_description"]
    assert "research" not in record.input_json


def test_bad_cluster_id_errors(monkeypatch):
    api_server = _load_api_server(monkeypatch, _runtime_path("hydrate-bad-cluster"))
    client = TestClient(api_server.app)

    res = client.post(
        "/conversation/start",
        json={
            "scenario": "CI",
            "case_id": "missing",
            "dataset_id": "enforcement",
            "cluster_id": "does-not-exist",
            "pack_version": "0.1.0-draft",
        },
    )
    assert res.status_code == 404
    assert "does-not-exist" in res.json()["detail"]


def test_partial_research_ids_error(monkeypatch):
    api_server = _load_api_server(monkeypatch, _runtime_path("hydrate-partial"))
    from api.services.conversation import start_session

    with pytest.raises(HTTPException) as exc:
        start_session("CI", "x", dataset_id="enforcement")
    assert exc.value.status_code == 400
    assert "required together" in str(exc.value.detail)


def test_empty_pack_errors(monkeypatch):
    api_server = _load_api_server(monkeypatch, _runtime_path("hydrate-empty"))
    from api.services.conversation import start_session
    from api.services import materials

    pack = ResearchPackLoader().get_pack("enforcement", "enf-cn-notice-001", "0.1.0-draft")
    empty = pack.model_copy(update={"documents": []})
    monkeypatch.setattr(materials, "get_pack", lambda *args, **kwargs: empty)

    with pytest.raises(HTTPException) as exc:
        start_session(
            "CI",
            "enf-cn-notice-001",
            dataset_id="enforcement",
            cluster_id="enf-cn-notice-001",
            pack_version="0.1.0-draft",
        )
    assert exc.value.status_code == 400
    assert "empty pack" in str(exc.value.detail)


def test_reference_endpoints_list_and_get_pack(monkeypatch, tmp_path):
    api_server = _load_api_server(monkeypatch, _runtime_path("hydrate-ref"))
    client = TestClient(api_server.app)

    listed = client.get("/reference/research-packs")
    assert listed.status_code == 200
    identities = {
        (row["dataset_id"], row["cluster_id"], row["pack_version"])
        for row in listed.json()["packs"]
    }
    assert ("enforcement", "enf-cn-notice-001", "0.1.0-draft") in identities
    assert ("cisg", "cisg-art79-sample-001", "0.1.0") in identities

    detail = client.get(
        "/reference/research-packs/enforcement/enf-cn-notice-001",
        params={"pack_version": "0.1.0-draft"},
    )
    assert detail.status_code == 200
    body = detail.json()
    assert "reference" not in body
    assert body["cluster_id"] == "enf-cn-notice-001"
    assert any(doc.get("document_id") == "001" for doc in body["documents"])
    assert any(doc.get("text", "").startswith("【研究样例") for doc in body["documents"])
    assert body["source_anchors"]

    missing = client.get("/reference/research-packs/enforcement/does-not-exist")
    assert missing.status_code == 404

    from api import state

    _write_civil_row(tmp_path, CIVIL_ROW)
    state.project_root = tmp_path
    found = client.get("/reference/cases/CASE-0001")
    assert found.status_code == 200
    assert "借款未还" in found.json()["case"]["case_description"]
    assert client.get("/reference/cases/missing-case").status_code == 404
