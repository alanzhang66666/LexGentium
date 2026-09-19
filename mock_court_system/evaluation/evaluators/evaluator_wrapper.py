from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class EvaluationOutcome:
    score: float
    details: Dict[str, Any]


class EvaluatorWrapper:
    """
    Minimal runnable evaluator wrapper for local demos.

    Notes:
    - The repository currently ships evaluation adapters + datasets, but does not ship
      the original J1Bench evaluator implementation.
    - For "system runnable" purposes, we provide lightweight heuristic scoring so that
      `/evaluate` can execute end-to-end without external dependencies.
    """

    def __init__(self, scenario: str, gt_path: str, output_dir: str):
        self.scenario = (scenario or "").upper()
        self.gt_path = gt_path
        self.output_dir = output_dir

    def evaluate_one(self, adapted_pred: Dict[str, Any], gt: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return a dict score payload (kept JSON-serializable).
        """
        if self.scenario == "CD":
            out = self._eval_cd(adapted_pred, gt)
        elif self.scenario == "DD":
            out = self._eval_dd(adapted_pred, gt)
        elif self.scenario == "CI":
            out = self._eval_ci(adapted_pred, gt)
        else:
            out = EvaluationOutcome(score=0.0, details={"reason": f"unknown scenario {self.scenario}"})

        return {
            "score": out.score,
            "details": out.details,
            "method": "structure_check",
            "label": "文书结构检查",
            "limitation": "仅检查结构关键词，不代表法律正确性、证据支持或参考答案一致性",
        }

    def _get_text(self, adapted_pred: Dict[str, Any]) -> str:
        return (
            (adapted_pred.get("model_output") or "")
            or (adapted_pred.get("generated_doc") or "")
            or ""
        )

    def _eval_cd(self, adapted_pred: Dict[str, Any], gt: Dict[str, Any]) -> EvaluationOutcome:
        text = self._get_text(adapted_pred)
        t = text.replace(" ", "").replace("*", "").strip()

        # Heuristic: structure markers
        must = ["民事起诉状", "原告", "被告", "诉讼请求", "事实", "证据"]
        hit = sum(1 for k in must if k in t)
        score = hit / len(must)
        return EvaluationOutcome(score=float(score), details={"hits": hit, "must": must})

    def _eval_dd(self, adapted_pred: Dict[str, Any], gt: Dict[str, Any]) -> EvaluationOutcome:
        text = self._get_text(adapted_pred)
        t = text.replace(" ", "").replace("*", "").strip()

        must = ["民事答辩状", "答辩人", "答辩", "事实", "证据"]
        hit = sum(1 for k in must if k in t)
        score = hit / len(must)
        return EvaluationOutcome(score=float(score), details={"hits": hit, "must": must})

    def _eval_ci(self, adapted_pred: Dict[str, Any], gt: Dict[str, Any]) -> EvaluationOutcome:
        text = self._get_text(adapted_pred)
        t = text.replace(" ", "").replace("*", "").strip()

        must = ["案号", "本院认为", "判决", "适用法律"]
        hit = sum(1 for k in must if k in t)
        score = hit / len(must)
        return EvaluationOutcome(score=float(score), details={"hits": hit, "must": must})
