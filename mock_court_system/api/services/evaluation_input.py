"""EvaluationInputBuilder：从已提交会话构造 immutable 评测输入（design §12，Task 8.2）。

- 输入模型只从 latest committed ordered dialog 派生，附 input_digest；
  全程在内存受管，不读写 ``data/session_predictions/``。
- legacy 文件接口：在 runtime data root 下创建 task-scoped 临时目录，
  任务结束由调用方 ``cleanup``；路径不在源码树，也不是持久输入。
- 缺失输入抛 ``MissingEvaluationInputError``（→422，field_errors），
  不创建 report。
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.fingerprint import canonical_digest
from core.store.registry import runtime_data_root


class MissingEvaluationInputError(Exception):
    """评测必需输入缺失；``field_errors`` 映射 422。"""

    code = "missing_evaluation_input"

    def __init__(self, field_errors: List[Dict[str, str]]):
        self.field_errors = field_errors
        super().__init__(
            "missing required evaluation input: "
            + ", ".join(e["path"] for e in field_errors)
        )


@dataclass(frozen=True)
class EvaluationInput:
    """单场景 immutable 评测输入。"""

    scenario: str
    prediction_identity: str
    normalized_dialog: Tuple[Dict[str, Any], ...]
    model_output: str
    input_digest: str
    session_id: Optional[str] = None
    run_id: Optional[str] = None
    case_id: Optional[str] = None
    dataset_id: Optional[str] = None
    cluster_id: Optional[str] = None
    pack_version: Optional[str] = None
    degraded: bool = False
    affected_metrics: Tuple[str, ...] = ()


def normalize_dialog(dialog_history: Optional[List[Dict[str, Any]]]) -> Tuple[Dict[str, Any], ...]:
    """latest committed ordered dialog → 规范化 (turn, role, message) 序列。"""
    rows: List[Dict[str, Any]] = []
    for idx, msg in enumerate(dialog_history or []):
        if not isinstance(msg, dict):
            continue
        text = msg.get("message") or msg.get("content") or msg.get("text") or ""
        if not str(text).strip():
            continue
        rows.append(
            {
                "turn": int(msg.get("turn", idx)),
                "role": str(msg.get("role", "")),
                "message": str(text).strip(),
            }
        )
    # turn 相同（异常输入）时用 (role, message) 确定性 tiebreak，
    # 保证 digest 与输入顺序无关
    rows.sort(key=lambda r: (r["turn"], r["role"], r["message"]))
    return tuple(rows)


def _dialog_text(normalized: Tuple[Dict[str, Any], ...]) -> str:
    return "\n".join(r["message"] for r in normalized)


def _research_block(input_json: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = (input_json or {}).get("research")
    return raw if isinstance(raw, dict) else {}


class EvaluationInputBuilder:
    """从已提交会话 record 构造每场景 EvaluationInput。"""

    def build_from_session(
        self,
        record,
        scenarios: List[str],
        *,
        run_id: str,
    ) -> List[EvaluationInput]:
        normalized = normalize_dialog(record.dialog_history)
        if not normalized:
            raise MissingEvaluationInputError(
                [{"path": "/dialog_history", "reason": "empty_committed_dialog"}]
            )
        if not getattr(record, "session_id", None):
            raise MissingEvaluationInputError(
                [{"path": "/session_id", "reason": "required"}]
            )

        research = _research_block(record.input_json)
        if research.get("dataset_id") and research.get("cluster_id"):
            prediction_identity = str(research["cluster_id"])
        else:
            prediction_identity = str(record.case_id or record.session_id)

        body = _dialog_text(normalized)
        digest = canonical_digest(
            {
                "session_id": record.session_id,
                "run_id": run_id,
                "dialog": list(normalized),
                "case_id": record.case_id,
                "dataset_id": research.get("dataset_id"),
                "cluster_id": research.get("cluster_id"),
                "pack_version": research.get("pack_version"),
            }
        )

        degraded = bool(
            (record.input_json or {}).get("degraded")
            or research.get("degraded")
        )
        affected = tuple((record.input_json or {}).get("affected_metrics") or ())

        inputs: List[EvaluationInput] = []
        for scenario in scenarios:
            inputs.append(
                EvaluationInput(
                    scenario=scenario,
                    prediction_identity=prediction_identity,
                    normalized_dialog=normalized,
                    model_output=body,
                    input_digest=digest,
                    session_id=record.session_id,
                    run_id=run_id,
                    case_id=record.case_id,
                    dataset_id=research.get("dataset_id"),
                    cluster_id=research.get("cluster_id"),
                    pack_version=research.get("pack_version"),
                    degraded=degraded,
                    affected_metrics=affected,
                )
            )
        return inputs


def materialize_legacy_files(
    inputs: List[EvaluationInput],
    task_scope: str,
    *,
    root: Optional[Path] = None,
) -> Tuple[Dict[str, str], Callable[[], None]]:
    """为仍要求文件接口的 legacy evaluator 落 task-scoped 临时 jsonl。

    目录在 runtime data root 下（``evaluation_inputs/<task_scope>/``），
    返回 (files, cleanup)；cleanup 删除整个 scope 目录。
    """
    base = (root or runtime_data_root()) / "evaluation_inputs" / task_scope
    base.mkdir(parents=True, exist_ok=True)
    files: Dict[str, str] = {}
    for inp in inputs:
        row: Dict[str, Any] = {
            "id": inp.prediction_identity,
            "scenario": inp.scenario,
            "dialog_history": list(inp.normalized_dialog),
            "model_output": inp.model_output,
            "generated_doc": inp.model_output,
            "input_digest": inp.input_digest,
        }
        for key in ("session_id", "run_id", "case_id", "dataset_id", "cluster_id", "pack_version"):
            value = getattr(inp, key)
            if value:
                row[key] = value
        if inp.degraded:
            row["degraded"] = True
            row["affected_metrics"] = list(inp.affected_metrics)
        path = base / f"{inp.session_id or 'input'}_{inp.scenario}.jsonl"
        fd, tmp_name = tempfile.mkstemp(dir=str(base), prefix=".in-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
        files[inp.scenario] = str(path)

    def cleanup() -> None:
        shutil.rmtree(base, ignore_errors=True)

    return files, cleanup


def cleanup_evaluation_inputs(task_scope: str, *, root: Optional[Path] = None) -> None:
    """按 task scope 清理遗留输入目录。"""
    shutil.rmtree(
        (root or runtime_data_root()) / "evaluation_inputs" / task_scope,
        ignore_errors=True,
    )
