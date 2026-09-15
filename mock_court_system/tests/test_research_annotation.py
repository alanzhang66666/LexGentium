"""Annotation overlays must not overwrite pack.json; changelog records who/when."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.annotation import (  # noqa: E402
    AnnotationStore,
    InvalidReviewStateError,
    apply_overlays,
    get_annotated_pack,
    get_source_text,
    list_annotated_packs,
    list_change_log,
    patch_field,
    reset_annotation_store_cache,
)
from api.services.materials import get_loader  # noqa: E402


CISG = ("cisg", "cisg-art79-sample-001")
ENF = ("enforcement", "enf-cn-notice-001")


@pytest.fixture()
def annotation_db(tmp_path, monkeypatch):
    db_path = tmp_path / "research_annotations.sqlite3"
    monkeypatch.setenv("RESEARCH_ANNOTATION_DB", str(db_path))
    reset_annotation_store_cache()
    yield db_path
    reset_annotation_store_cache()


def test_list_includes_both_sample_packs(annotation_db):
    packs = list_annotated_packs()
    keys = {(item["dataset_id"], item["cluster_id"]) for item in packs}
    assert CISG in keys
    assert ENF in keys
    versions = {item["cluster_id"]: item["pack_version"] for item in packs}
    assert versions["cisg-art79-sample-001"] == "0.1.0"
    assert versions["enf-cn-notice-001"] == "0.1.0-draft"


def test_patch_does_not_rewrite_pack_json(annotation_db):
    loader = get_loader()
    pack_path = loader.pack_json_path(*CISG)
    before = pack_path.read_bytes()
    original = json.loads(before.decode("utf-8"))
    original_value = next(
        item["value"] for item in original["procedural_facts"] if item["item_id"] == "cisg-fact-parties"
    )

    result = patch_field(
        *CISG,
        field_path="procedural_facts/cisg-fact-parties",
        actor="reviewer-a",
        note="核对营业地表述",
        value="卖方 S（中国）；买方 B（德国）",
        review_state="tech_checked",
    )

    assert pack_path.read_bytes() == before
    assert result["pack_json_unmodified"] is True
    item = next(
        row for row in result["pack"]["procedural_facts"] if row["item_id"] == "cisg-fact-parties"
    )
    assert item["value"] == "卖方 S（中国）；买方 B（德国）"
    assert item["review_state"] == "tech_checked"
    assert original_value != item["value"]
    assert result["change"]["actor"] == "reviewer-a"
    assert result["change"]["note"] == "核对营业地表述"


def test_source_text_jumps_by_source_id(annotation_db):
    span = get_source_text(*CISG, "001:zh-1")
    assert span["source_id"] == "001:zh-1"
    assert span["document_id"] == "001"
    assert "非他所能控制的障碍" in (span["excerpt"] or span["quote"] or "")


def test_review_state_and_changelog(annotation_db):
    patch_field(
        *ENF,
        field_path="review_state",
        actor="law-reviewer",
        review_state="law_reviewed",
        note="整包法学复核",
    )
    bundle = get_annotated_pack(*ENF)
    assert bundle["pack"]["review_state"] == "law_reviewed"
    log = list_change_log(*ENF)
    assert log["entries"][0]["actor"] == "law-reviewer"
    assert log["entries"][0]["review_state"] == "law_reviewed"
    summaries = { (row["dataset_id"], row["cluster_id"]): row for row in list_annotated_packs() }
    assert summaries[ENF]["review_state"] == "law_reviewed"


def test_invalid_review_state_rejected(annotation_db):
    with pytest.raises(InvalidReviewStateError):
        patch_field(*CISG, field_path="review_state", review_state="approved")


def test_apply_overlays_merges_without_mutating_base():
    base = {
        "review_state": "pending",
        "procedural_facts": [{"item_id": "x", "value": "old", "review_state": "pending"}],
    }
    overlays = [
        {
            "field_path": "procedural_facts/x",
            "overlay": {"value": "new", "review_state": "disputed"},
        }
    ]
    merged = apply_overlays(base, overlays)
    assert merged["procedural_facts"][0]["value"] == "new"
    assert base["procedural_facts"][0]["value"] == "old"


def test_research_router_list_and_source(annotation_db):
    from fastapi.testclient import TestClient

    import api_server

    client = TestClient(api_server.app)
    listed = client.get("/research/packs")
    assert listed.status_code == 200
    keys = {(row["dataset_id"], row["cluster_id"]) for row in listed.json()["packs"]}
    assert CISG in keys
    bundle = client.get("/research/packs/cisg/cisg-art79-sample-001")
    assert bundle.status_code == 200
    assert bundle.json()["documents"]
    assert any(doc["document_id"] == "001" and doc["text"] for doc in bundle.json()["documents"])
    source = client.get(
        "/research/packs/cisg/cisg-art79-sample-001/source",
        params={"source_id": "002:p1"},
    )
    assert source.status_code == 200
    assert source.json()["document_id"] == "002"
    patched = client.patch(
        "/research/packs/cisg/cisg-art79-sample-001/fields",
        json={
            "field_path": "procedural_facts/cisg-fact-notice-date",
            "actor": "http-reviewer",
            "value": "unknown",
            "review_state": "tech_checked",
            "note": "通知日期仍未知",
        },
    )
    assert patched.status_code == 200
    log = client.get("/research/packs/cisg/cisg-art79-sample-001/changelog")
    assert log.status_code == 200
    assert log.json()["entries"][0]["actor"] == "http-reviewer"


def test_annotation_store_roundtrip(tmp_path):
    store = AnnotationStore(tmp_path / "ann.sqlite3")
    store.upsert_overlay(
        dataset_id="cisg",
        cluster_id="cisg-art79-sample-001",
        pack_version="0.1.0",
        field_path="review_state",
        item_id="review_state",
        overlay={"review_state": "disputed"},
        review_state="disputed",
        actor="tech",
    )
    store.append_changelog(
        dataset_id="cisg",
        cluster_id="cisg-art79-sample-001",
        pack_version="0.1.0",
        field_path="review_state",
        item_id="review_state",
        actor="tech",
        action="set_review_state",
        from_value="pending",
        to_value="disputed",
        review_state="disputed",
        note="争议",
    )
    overlays = store.list_overlays("cisg", "cisg-art79-sample-001", "0.1.0")
    assert overlays[0]["overlay"]["review_state"] == "disputed"
    log = store.list_changelog("cisg", "cisg-art79-sample-001", "0.1.0")
    assert log[0]["actor"] == "tech"
    assert log[0]["from_value"] == "pending"
