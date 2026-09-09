"""评测任务：默认预测文件或现场会话。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import HTTPException

from api import state
from api.services.conversation import bind_session_link


def _write_session_predictions(session_id: str, scenarios: List[str]) -> Dict[str, str]:
    record = state.conversation_store.get(session_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")

    out_dir = state.project_root / "data" / "session_predictions"
    out_dir.mkdir(parents=True, exist_ok=True)
    files: Dict[str, str] = {}
    history = list(record.dialog_history)
    for scenario in scenarios:
        path = out_dir / f"{session_id}_{scenario}.jsonl"
        row = {
            "id": f"{scenario}-{session_id[:8]}",
            "scenario": scenario,
            "dialog_history": history,
            "input_json": record.input_json or {},
            "case_id": record.case_id,
        }
        path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        files[scenario] = str(path)
    return files


def start_evaluation_task(
    scenarios: List[str],
    prediction_files: Optional[Dict[str, str]],
    session_id: Optional[str],
    use_default_predictions: bool,
) -> tuple:
    report_id = f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    created_at = datetime.now().isoformat()
    files = prediction_files
    if session_id:
        files = _write_session_predictions(session_id, scenarios)
        bind_session_link(session_id, report_id=report_id)
    elif use_default_predictions:
        files = files or None

    state.evaluation_tasks[report_id] = {
        "status": "running",
        "message": "evaluation task started",
        "results": None,
        "report_path": None,
        "created_at": created_at,
        "session_id": session_id,
    }
    state.evaluation_task_store.upsert(
        state.EvaluationTaskRecord(
            report_id=report_id,
            status="running",
            message="evaluation task started",
            created_at=created_at,
            updated_at=created_at,
        )
    )
    return report_id, files
