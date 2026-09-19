"""评测任务：默认预测文件或现场会话。

run_id 绑定顺序：
1. ``session.input_json.research.run_id``（若已有）
2. 本次请求的 ``run_id``
3. 在 evaluate 时 ``new_run_id()`` 生成

``start_session`` 目前不一定铸造 run_id；缺省时由本模块补发并写入任务表。
报告文件名必须含 UUID ``report_id``，禁止按「最新文件」认领结果。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from api import state
from api.services.conversation import bind_session_link
from core.research import (
    EvalContract,
    PackNotFoundError,
    PackVersionMismatchError,
    ResearchPackError,
    ResearchPackLoader,
    new_report_id,
    new_run_id,
)
from evaluation.run_evaluation import (
    EmptyEvaluationBodyError,
    EvaluationAttributionError,
    MissingReferenceError,
    MissingFinalOutputError,
    WrongClusterOrCaseError,
)
from evaluation.bodies import dialog_text, final_document, prediction_document


def resolve_evaluation_run_id(
    input_json: Optional[Dict[str, Any]],
    requested_run_id: Optional[str] = None,
) -> str:
    research = _research_block(input_json)
    existing = research.get("run_id")
    if existing:
        return str(existing).strip()
    if requested_run_id and str(requested_run_id).strip():
        return str(requested_run_id).strip()
    return new_run_id()


def _research_block(input_json: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = (input_json or {}).get("research")
    return raw if isinstance(raw, dict) else {}


def evaluation_report_filename(report_id: str) -> str:
    return f"evaluation_report_{report_id}.json"


def resolve_evaluation_report_path(results_dir: Path, report_id: str) -> Path:
    path = Path(results_dir) / evaluation_report_filename(report_id)
    if not path.is_file():
        raise FileNotFoundError(f"evaluation report not found for {report_id}")
    return path


def attach_evaluation_results(results_dir: Path, report_id: str) -> Dict[str, Any]:
    path = resolve_evaluation_report_path(results_dir, report_id)
    return json.loads(path.read_text(encoding="utf-8"))


def load_research_pack_for_eval(
    *,
    dataset_id: str,
    cluster_id: str,
    pack_version: Optional[str] = None,
):
    try:
        return ResearchPackLoader().get_pack(dataset_id, cluster_id, pack_version)
    except (PackNotFoundError, PackVersionMismatchError, ResearchPackError, ValueError) as exc:
        raise WrongClusterOrCaseError(
            f"unknown research cluster or case: {dataset_id}/{cluster_id}"
        ) from exc


def _dialog_text(dialog_history: Optional[List[Dict[str, Any]]]) -> str:
    return dialog_text(dialog_history)


def has_evaluation_body(
    dialog_history: Optional[List[Dict[str, Any]]] = None,
    prediction: Optional[Dict[str, Any]] = None,
) -> bool:
    return bool(prediction_document(prediction or {}) or final_document(dialog_history))


def _require_session_body(record) -> None:
    if not _dialog_text(record.dialog_history):
        raise EmptyEvaluationBodyError("evaluation body is empty")
    if not _is_research_session(record) and not final_document(record.dialog_history):
        raise MissingFinalOutputError("本场尚无已确认的最终文书，不能对用户发言或过程对话评分")


def _is_research_session(record) -> bool:
    research = _research_block(record.input_json)
    return bool(research.get("dataset_id") or research.get("cluster_id"))


def _require_research_reference(record) -> None:
    research = _research_block(record.input_json)
    dataset_id = research.get("dataset_id")
    cluster_id = research.get("cluster_id")
    if not dataset_id and not cluster_id:
        return
    if not dataset_id or not cluster_id:
        raise WrongClusterOrCaseError("research dataset_id/cluster_id incomplete")
    pack = load_research_pack_for_eval(
        dataset_id=str(dataset_id),
        cluster_id=str(cluster_id),
        pack_version=research.get("pack_version"),
    )
    if pack.reference is None:
        raise MissingReferenceError("research pack has no reference")


def _write_session_predictions(
    record,
    scenarios: List[str],
    *,
    report_id: str,
    run_id: str,
) -> Dict[str, str]:
    out_dir = state.project_root / "data" / "session_predictions" / report_id
    out_dir.mkdir(parents=True, exist_ok=False)
    files: Dict[str, str] = {}
    history = list(record.dialog_history)
    body = _dialog_text(history) if _is_research_session(record) else final_document(history)
    research = _research_block(record.input_json)
    for scenario in scenarios:
        path = out_dir / f"{scenario}.jsonl"
        if research.get("dataset_id") and research.get("cluster_id"):
            pred_id = str(research["cluster_id"])
        else:
            pred_id = record.case_id
        row: Dict[str, Any] = {
            "id": pred_id,
            "scenario": scenario,
            "dialog_history": history,
            "input_json": record.input_json or {},
            "case_id": record.case_id,
            "run_id": run_id,
            "report_id": report_id,
            "model_output": body,
            "generated_doc": body,
            "output_source": "research_transcript" if _is_research_session(record) else "session_final",
        }
        if isinstance((record.input_json or {}).get("civil_case"), dict):
            row["civil_case"] = record.input_json["civil_case"]
        if research.get("dataset_id"):
            row["dataset_id"] = research["dataset_id"]
        if research.get("cluster_id"):
            row["cluster_id"] = research["cluster_id"]
        if research.get("pack_version"):
            row["pack_version"] = research["pack_version"]
        row["input_hash"] = hashlib.sha256(
            json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        files[scenario] = str(path)
    return files


def start_evaluation_task(
    scenarios: List[str],
    prediction_files: Optional[Dict[str, str]],
    session_id: Optional[str],
    use_default_predictions: bool,
    run_id: Optional[str] = None,
) -> tuple:
    if not scenarios or any(s not in {"CD", "DD", "CI"} for s in scenarios):
        raise HTTPException(status_code=400, detail="select at least one valid scenario")
    scenarios = list(dict.fromkeys(scenarios))
    record = None
    if session_id:
        record = state.conversation_store.get(session_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
        if scenarios != [record.scenario]:
            raise HTTPException(status_code=400, detail="session evaluation must use its own scenario")
        _require_session_body(record)
        _require_research_reference(record)

    resolved_run_id = resolve_evaluation_run_id(
        record.input_json if record else None,
        run_id,
    )
    report_id = new_report_id()
    EvalContract(report_id=report_id, run_id=resolved_run_id)
    created_at = datetime.now().isoformat()

    files = prediction_files
    if record is not None:
        files = _write_session_predictions(
            record,
            scenarios,
            report_id=report_id,
            run_id=resolved_run_id,
        )
        bind_session_link(session_id, report_id=report_id)
    elif use_default_predictions:
        files = files or _default_prediction_files(scenarios)
    if not files:
        raise HTTPException(status_code=400, detail="evaluation requires prediction files or a session")

    state.evaluation_tasks[report_id] = {
        "status": "running",
        "message": "evaluation task started",
        "results": None,
        "report_path": None,
        "created_at": created_at,
        "session_id": session_id,
        "run_id": resolved_run_id,
    }
    state.evaluation_task_store.upsert(
        state.EvaluationTaskRecord(
            report_id=report_id,
            status="running",
            message="evaluation task started",
            created_at=created_at,
            updated_at=created_at,
            session_id=session_id,
            run_id=resolved_run_id,
        )
    )
    return report_id, files


def _default_prediction_files(scenarios: List[str]) -> Dict[str, str]:
    files: Dict[str, str] = {}
    for scenario in scenarios:
        default_paths = [
            state.project_root / "evaluation" / "data" / "real_test_pred" / f"{scenario}_prediction.jsonl",
            state.project_root / f"{scenario}_prediction.jsonl",
            state.project_root / "evaluation" / "data" / "test_run" / f"{scenario}_test_pred.jsonl",
        ]
        for path in default_paths:
            if path.exists():
                files[scenario] = str(path)
                break
    return files


def execute_evaluation_task(
    report_id: str,
    scenarios: List[str],
    prediction_files: Optional[Dict[str, str]],
) -> None:
    """Run scoring and attach the file named with this report_id only."""
    rec = state.evaluation_task_store.get(report_id)
    memory = state.evaluation_tasks.get(report_id) or {}
    session_id = (rec.session_id if rec else None) or memory.get("session_id")
    run_id = (rec.run_id if rec else None) or memory.get("run_id")
    created_at = memory.get("created_at") or (rec.created_at if rec else datetime.now().isoformat())

    def _persist(*, status: str, message: str, results: Any = None, report_path: Optional[str] = None) -> None:
        if report_id in state.evaluation_tasks:
            state.evaluation_tasks[report_id]["status"] = status
            state.evaluation_tasks[report_id]["message"] = message
            if results is not None:
                state.evaluation_tasks[report_id]["results"] = results
            if report_path is not None:
                state.evaluation_tasks[report_id]["report_path"] = report_path
        state.evaluation_task_store.upsert(
            state.EvaluationTaskRecord(
                report_id=report_id,
                status=status,
                message=message,
                created_at=created_at,
                updated_at=datetime.now().isoformat(),
                results_json=json.dumps(results, ensure_ascii=False) if results is not None else None,
                report_path=report_path,
                session_id=session_id,
                run_id=run_id,
            )
        )

    try:
        _persist(status="running", message="评测进行中...")
        from evaluation.run_evaluation import load_config, run_evaluation

        files = prediction_files
        if not files:
            if session_id:
                raise EmptyEvaluationBodyError(
                    "session evaluation is missing prediction files; refusing default paper"
                )
            raise EmptyEvaluationBodyError("evaluation is missing prediction files")

        config_path = state.project_root / "evaluation" / "eval_config.yaml"
        config = load_config(str(config_path))
        payload = run_evaluation(
            config,
            scenarios,
            files,
            report_id=report_id,
            run_id=run_id,
        )
        report_path = payload["report_path"]
        results = attach_evaluation_results(Path(report_path).parent, report_id)
        if results.get("report_id") != report_id or results.get("run_id") != run_id:
            raise EvaluationAttributionError("report identity does not match this task")
        _persist(status="completed", message="评测完成", results=results, report_path=str(report_path))
    except EvaluationAttributionError as exc:
        state.eval_logger.error(f"评测归属失败: {exc}", exc_info=True)
        _persist(status="failed", message=f"{exc.code}: {exc}")
    except Exception as exc:
        state.eval_logger.error(f"评测任务失败: {exc}", exc_info=True)
        _persist(status="failed", message=f"评测失败: {str(exc)}")
