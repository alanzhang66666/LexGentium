"""Regression tests for evaluation attribution (report_id / run_id / files / errors)."""
from __future__ import annotations

import json
import sqlite3
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

_ROOT = Path(__file__).resolve().parents[1]
_CORE_DIR = _ROOT / "core"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_CORE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_DIR))

from research import EvalContract, new_report_id, new_run_id  # noqa: E402
from research.ids import validate_report_id  # noqa: E402

from core.store.conversation_store import MemoryConversationStore  # noqa: E402
from core.store.evaluation_task_store import (  # noqa: E402
    EvaluationTaskRecord,
    SqliteEvaluationTaskStore,
)
from evaluation.run_evaluation import run_evaluation  # noqa: E402


PROJECT = _ROOT
TEST_RUN = PROJECT / "evaluation" / "data" / "test_run"


def _civil_config(output_root: Path) -> dict:
    return {
        "evaluation": {
            "paths": {
                "ground_truth": {
                    "cd": str(TEST_RUN / "CD_test_gt.jsonl"),
                    "dd": str(TEST_RUN / "DD_test_gt.jsonl"),
                    "ci": str(TEST_RUN / "CI_test_gt.jsonl"),
                },
                "output": {"root": str(output_root)},
            },
            "scenarios": {
                "CD": {"enabled": True},
                "DD": {"enabled": True},
                "CI": {"enabled": True},
            },
        }
    }


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _old_schema_db(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as conn:
        conn.execute(
            """
            CREATE TABLE evaluation_tasks (
              report_id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              message TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              results_json TEXT,
              report_path TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO evaluation_tasks(
              report_id, status, message, created_at, updated_at, results_json, report_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-report",
                "completed",
                "old row",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
                json.dumps({"score": 1}),
                "evaluation/results/old.json",
            ),
        )
    return path


def test_timestamp_report_id_fails_eval_contract():
    with pytest.raises((ValueError, ValidationError)):
        validate_report_id(f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    with pytest.raises(ValidationError):
        EvalContract(report_id="eval_20260912_112700", run_id=new_run_id())


def test_new_report_id_is_uuid_and_binds_run():
    report_id = new_report_id()
    run_id = new_run_id()
    UUID(report_id)
    contract = EvalContract(report_id=report_id, run_id=run_id, reference_version="0.1.0")
    assert contract.report_id == report_id
    assert contract.run_id == run_id


def test_task_store_persists_session_id_and_run_id(tmp_path):
    store = SqliteEvaluationTaskStore(str(tmp_path / "eval.sqlite3"))
    report_id = new_report_id()
    run_id = new_run_id()
    store.upsert(
        EvaluationTaskRecord(
            report_id=report_id,
            status="running",
            message="started",
            created_at="2026-09-12T00:00:00Z",
            updated_at="2026-09-12T00:00:00Z",
            session_id="sess-attr-1",
            run_id=run_id,
        )
    )
    loaded = store.get(report_id)
    assert loaded is not None
    assert loaded.session_id == "sess-attr-1"
    assert loaded.run_id == run_id
    assert store.list_recent(limit=1)[0].session_id == "sess-attr-1"


def test_task_store_migrates_legacy_schema_without_dropping_rows(tmp_path):
    db = _old_schema_db(tmp_path / "legacy.sqlite3")
    store = SqliteEvaluationTaskStore(str(db))
    legacy = store.get("legacy-report")
    assert legacy is not None
    assert legacy.results() == {"score": 1}
    assert legacy.session_id is None
    assert legacy.run_id is None

    report_id = new_report_id()
    store.upsert(
        EvaluationTaskRecord(
            report_id=report_id,
            status="completed",
            message="migrated",
            created_at="2026-09-12T01:00:00Z",
            updated_at="2026-09-12T01:00:00Z",
            session_id="sess-migrated",
            run_id="run_migrated",
        )
    )
    loaded = store.get(report_id)
    assert loaded is not None
    assert loaded.session_id == "sess-migrated"
    assert loaded.run_id == "run_migrated"
    assert store.get("legacy-report") is not None


def test_start_evaluation_mints_uuid_and_binds_session_run_id(tmp_path, monkeypatch):
    from api.services import evaluation as ev

    conv = MemoryConversationStore()
    run_id = new_run_id()
    record = conv.create(
        session_id="sess-bind-run",
        scenario="CD",
        case_id="CD-Test",
        input_json={"research": {"run_id": run_id}},
    )
    record.dialog_history = [
        {"turn": 0, "role": "Client", "message": "请帮我起草民事起诉状，原告李婷琳。"}
    ]
    conv.save(record)

    store = SqliteEvaluationTaskStore(str(tmp_path / "tasks.sqlite3"))
    monkeypatch.setattr(ev.state, "conversation_store", conv)
    monkeypatch.setattr(ev.state, "evaluation_task_store", store)
    ev.state.evaluation_tasks.clear()
    monkeypatch.setattr(ev, "bind_session_link", lambda *a, **k: None)

    report_id, files = ev.start_evaluation_task(
        ["CD"],
        None,
        "sess-bind-run",
        False,
    )
    UUID(report_id)
    with pytest.raises((ValueError, ValidationError)):
        validate_report_id("eval_20260912_112700")
    EvalContract(report_id=report_id, run_id=run_id)

    persisted = store.get(report_id)
    assert persisted is not None
    assert persisted.session_id == "sess-bind-run"
    assert persisted.run_id == run_id
    assert files is not None and "CD" in files
    pred = json.loads(Path(files["CD"]).read_text(encoding="utf-8").splitlines()[0])
    assert pred["id"] == "CD-Test"
    assert pred["run_id"] == run_id


def test_start_evaluation_accepts_or_mints_run_id_when_session_has_none(tmp_path, monkeypatch):
    from api.services import evaluation as ev

    conv = MemoryConversationStore()
    record = conv.create(
        session_id="sess-mint-run",
        scenario="CD",
        case_id="CD-Test",
        input_json={},
    )
    record.dialog_history = [{"turn": 0, "role": "Client", "message": "起诉借款纠纷"}]
    conv.save(record)

    store = SqliteEvaluationTaskStore(str(tmp_path / "tasks.sqlite3"))
    monkeypatch.setattr(ev.state, "conversation_store", conv)
    monkeypatch.setattr(ev.state, "evaluation_task_store", store)
    ev.state.evaluation_tasks.clear()
    monkeypatch.setattr(ev, "bind_session_link", lambda *a, **k: None)

    requested = new_run_id()
    report_id, _ = ev.start_evaluation_task(
        ["CD"],
        None,
        "sess-mint-run",
        False,
        run_id=requested,
    )
    assert store.get(report_id).run_id == requested

    record2 = conv.create(
        session_id="sess-gen-run",
        scenario="CD",
        case_id="CD-Test",
        input_json={},
    )
    record2.dialog_history = [{"turn": 0, "role": "Client", "message": "另一起借款纠纷"}]
    conv.save(record2)
    report_b, _ = ev.start_evaluation_task(["CD"], None, "sess-gen-run", False)
    generated = store.get(report_b).run_id
    assert generated
    assert generated.startswith("run_")
    assert generated != requested


def test_empty_body_wrong_cluster_missing_reference_are_distinct(tmp_path, monkeypatch):
    from api.services import evaluation as ev
    from api.services.evaluation import (
        EmptyEvaluationBodyError,
        MissingReferenceError,
        WrongClusterOrCaseError,
    )

    conv = MemoryConversationStore()
    store = SqliteEvaluationTaskStore(str(tmp_path / "tasks.sqlite3"))
    monkeypatch.setattr(ev.state, "conversation_store", conv)
    monkeypatch.setattr(ev.state, "evaluation_task_store", store)
    ev.state.evaluation_tasks.clear()
    monkeypatch.setattr(ev, "bind_session_link", lambda *a, **k: None)

    empty = conv.create(session_id="sess-empty", scenario="CD", case_id="CD-Test", input_json={})
    empty.dialog_history = []
    conv.save(empty)
    with pytest.raises(EmptyEvaluationBodyError):
        ev.start_evaluation_task(["CD"], None, "sess-empty", True)

    wrong = conv.create(
        session_id="sess-wrong",
        scenario="CD",
        case_id="does-not-exist",
        input_json={
            "research": {
                "dataset_id": "enforcement",
                "cluster_id": "does-not-exist",
                "pack_version": "0.1.0-draft",
                "run_id": new_run_id(),
            }
        },
    )
    wrong.dialog_history = [{"turn": 0, "role": "Client", "message": "承认与执行抗辩"}]
    conv.save(wrong)
    with pytest.raises(WrongClusterOrCaseError):
        ev.start_evaluation_task(["CD"], None, "sess-wrong", False)

    missing_ref = conv.create(
        session_id="sess-noref",
        scenario="CD",
        case_id="pack-without-reference",
        input_json={
            "research": {
                "dataset_id": "cisg",
                "cluster_id": "pack-without-reference",
                "pack_version": "0.1.0",
                "run_id": new_run_id(),
            }
        },
    )
    missing_ref.dialog_history = [{"turn": 0, "role": "Claimant", "message": "主张第79条免责"}]
    conv.save(missing_ref)

    class _NoRef:
        reference = None
        cluster_id = "pack-without-reference"
        dataset_id = "cisg"

    monkeypatch.setattr(ev, "load_research_pack_for_eval", lambda **kw: _NoRef())
    with pytest.raises(MissingReferenceError):
        ev.start_evaluation_task(["CD"], None, "sess-noref", False)

    assert store.list_recent(limit=20) == []
    assert ev.state.evaluation_tasks == {}


def test_civil_contrast_without_research_pack(tmp_path):
    out = tmp_path / "civil-out"
    report_id = new_report_id()
    run_id = new_run_id()
    result = run_evaluation(
        _civil_config(out),
        scenarios=["CD"],
        prediction_files={"CD": str(TEST_RUN / "CD_test_pred.jsonl")},
        report_id=report_id,
        run_id=run_id,
    )
    report_path = Path(result["report_path"])
    assert report_path.name == f"evaluation_report_{report_id}.json"
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    cd_rows = payload.get("CD") or result.get("results", {}).get("CD")
    if cd_rows is None and isinstance(payload.get("scenarios"), dict):
        cd_rows = payload["scenarios"].get("CD")
    assert cd_rows, payload
    assert any(row.get("case_id") == "CD-Test" for row in cd_rows)
    assert "CD-1" not in json.dumps(cd_rows)
    dumped = json.dumps(payload)
    assert "pack.reference" not in dumped or "CD-Test" in dumped


def test_research_pack_uses_pack_reference_not_cd1_gt(tmp_path):
    out = tmp_path / "research-out"
    report_id = new_report_id()
    run_id = new_run_id()
    pred = tmp_path / "cisg_pred.jsonl"
    _write_jsonl(
        pred,
        [
            {
                "id": "cisg-art79-sample-001",
                "scenario": "CD",
                "cluster_id": "cisg-art79-sample-001",
                "dataset_id": "cisg",
                "pack_version": "0.1.0",
                "run_id": run_id,
                "dialog_history": [
                    {"turn": 0, "role": "Claimant", "message": "卖方主张 CISG 第79条免责。"}
                ],
                "input_json": {
                    "research": {
                        "dataset_id": "cisg",
                        "cluster_id": "cisg-art79-sample-001",
                        "pack_version": "0.1.0",
                        "run_id": run_id,
                    }
                },
            }
        ],
    )
    result = run_evaluation(
        _civil_config(out),
        scenarios=["CD"],
        prediction_files={"CD": str(pred)},
        report_id=report_id,
        run_id=run_id,
    )
    payload = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))
    blob = json.dumps(payload, ensure_ascii=False)
    assert "cisg-art79-sample-001" in blob
    assert "0.1.0" in blob
    assert "CD-1" not in blob
    assert "CD-Test" not in blob
    assert "exempt-if-unforeseeable-and-noticed" in blob or "gold_labels" in blob


def test_result_file_named_with_report_id_never_picks_latest(tmp_path):
    from api.services.evaluation import attach_evaluation_results, resolve_evaluation_report_path

    out = tmp_path / "named-out"
    out.mkdir()
    report_id = new_report_id()
    decoy = {
        "CD": [{"case_id": "CD-DECOY", "score": {"score": 0.99}}],
        "winner": "latest",
    }
    decoy_path = out / "evaluation_report_99999999_999999.json"
    decoy_path.write_text(json.dumps(decoy), encoding="utf-8")

    run_evaluation(
        _civil_config(out),
        scenarios=["CD"],
        prediction_files={"CD": str(TEST_RUN / "CD_test_pred.jsonl")},
        report_id=report_id,
        run_id=new_run_id(),
    )
    expected = out / f"evaluation_report_{report_id}.json"
    assert expected.exists()
    resolved = resolve_evaluation_report_path(out, report_id)
    assert Path(resolved) == expected
    attached = attach_evaluation_results(out, report_id)
    blob = json.dumps(attached)
    assert "CD-Test" in blob
    assert "CD-DECOY" not in blob
    assert "latest" not in blob


def test_concurrent_evaluations_do_not_cross_attach(tmp_path):
    from api.services.evaluation import attach_evaluation_results

    out = tmp_path / "concurrent-out"
    pred_a = tmp_path / "pred_a.jsonl"
    pred_b = tmp_path / "pred_b.jsonl"
    _write_jsonl(
        pred_a,
        [
            {
                "id": "CD-Test",
                "model_output": "民事起诉状 原告 被告 诉讼请求 事实 证据 专属报告A",
            }
        ],
    )
    _write_jsonl(
        pred_b,
        [
            {
                "id": "CD-Test",
                "model_output": "民事起诉状 原告 被告 诉讼请求 事实 证据 专属报告B",
            }
        ],
    )
    report_a = new_report_id()
    report_b = new_report_id()
    barrier = threading.Barrier(2)

    def _run(report_id: str, pred: Path) -> dict:
        barrier.wait()
        return run_evaluation(
            _civil_config(out),
            scenarios=["CD"],
            prediction_files={"CD": str(pred)},
            report_id=report_id,
            run_id=new_run_id(),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_a = pool.submit(_run, report_a, pred_a)
        fut_b = pool.submit(_run, report_b, pred_b)
        out_a = fut_a.result()
        out_b = fut_b.result()

    assert out_a["report_id"] == report_a
    assert out_b["report_id"] == report_b
    assert Path(out_a["report_path"]).name == f"evaluation_report_{report_a}.json"
    assert Path(out_b["report_path"]).name == f"evaluation_report_{report_b}.json"
    text_a = Path(out_a["report_path"]).read_text(encoding="utf-8")
    text_b = Path(out_b["report_path"]).read_text(encoding="utf-8")
    assert "专属报告A" in text_a
    assert "专属报告B" in text_b
    assert "专属报告B" not in text_a
    assert "专属报告A" not in text_b
    assert "专属报告B" not in json.dumps(attach_evaluation_results(out, report_a), ensure_ascii=False)
    assert "专属报告A" not in json.dumps(attach_evaluation_results(out, report_b), ensure_ascii=False)


def test_router_does_not_fallback_to_latest_file(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from tests.test_offline_governance import _load_api_server, _runtime_path

    api_server = _load_api_server(monkeypatch, _runtime_path("eval-attr-router"))
    from api import state

    report_id = str(uuid.uuid4())
    results_dir = state.project_root / "evaluation" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    decoy = results_dir / "evaluation_report_99999999_999999.json"
    owned = results_dir / f"evaluation_report_{report_id}.json"
    decoy.write_text(json.dumps({"CD": [{"case_id": "DECOY"}]}), encoding="utf-8")
    owned.write_text(json.dumps({"CD": [{"case_id": "OWNED"}]}), encoding="utf-8")
    try:
        client = TestClient(api_server.app)
        res = client.get(f"/evaluation/reports/{report_id}")
        assert res.status_code == 200
        assert res.json()["results"]["CD"][0]["case_id"] == "OWNED"
    finally:
        decoy.unlink(missing_ok=True)
        owned.unlink(missing_ok=True)
