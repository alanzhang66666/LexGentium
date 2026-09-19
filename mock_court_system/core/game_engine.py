"""
博弈引擎（增强版）
基于 FullCaseOrchestrator 运行多轮对抗博弈。

增强内容（基于 AgentMediation 2509.06586 + J1-EVAL 2507.04037）：
- 纳什均衡追踪器集成：每轮自动更新收益矩阵，分析均衡收敛
- Per-party 独立策略管理：原被告策略独立设置、独立进化
- 多变量交互支持：策略 × 争议原因注入
- 策略进化方法：LLM 反思 / 最佳响应 / 虚拟博弈
- 反事实推演：给定假设策略，预测可能结果
"""
from __future__ import annotations

import json
import math
import re
import time
import random
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Callable

from core import LLMClient
from core.case_orchestrator import FullCaseOrchestrator, FullCaseResult, StageResult
from core.llm_client import is_degraded_json
from core.nash_bargaining import NashBargainingEngine
from core.nash_equilibrium import (
    NashEquilibriumTracker,
    EquilibriumAnalysis,
    STRATEGY_NAMES,
    STRATEGY_INDEX,
)

logger = logging.getLogger("game_engine")


@dataclass
class GameScore:
    plaintiff_win_rate: float = 0.0
    defendant_win_rate: float = 0.0
    reasoning_quality: float = 0.0
    evidence_strength: float = 0.0
    degraded: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def offline(cls, reason: str = "llm_unavailable") -> "GameScore":
        """Return an explicit non-score that cannot be mistaken for real output."""
        return cls(details={"reason": reason or "llm_unavailable"}, degraded=True)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "GameScore":
        """Restore current and legacy score payloads with bounded numeric fields."""
        if not isinstance(payload, dict):
            return cls.offline("invalid_score_snapshot")
        try:
            values = {
                key: float(payload[key]) if not isinstance(payload[key], bool) else float("nan")
                for key in (
                    "plaintiff_win_rate",
                    "defendant_win_rate",
                    "reasoning_quality",
                    "evidence_strength",
                )
            }
        except (KeyError, TypeError, ValueError, OverflowError):
            return cls.offline("invalid_score_snapshot")
        if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in values.values()):
            return cls.offline("invalid_score_snapshot")
        details = payload.get("details")
        if not isinstance(details, dict):
            details = {}
        degraded = bool(payload.get("degraded", False))
        if degraded and not details.get("reason"):
            details = {**details, "reason": "degraded_score"}
        return cls(**values, details=dict(details), degraded=degraded)


def _stage_result_from_dict(payload: Any) -> Optional[StageResult]:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("invalid stage result in game snapshot")
    history = payload.get("dialog_history")
    if not isinstance(history, list):
        history = []
    extracted = payload.get("extracted_info")
    metadata = payload.get("metadata")
    return StageResult(
        scenario=str(payload.get("scenario") or ""),
        dialog_history=[dict(item) for item in history if isinstance(item, dict)],
        final_document=str(payload.get("final_document") or ""),
        extracted_info=dict(extracted) if isinstance(extracted, dict) else {},
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


def _case_result_from_dict(payload: Any) -> FullCaseResult:
    if not isinstance(payload, dict):
        raise ValueError("invalid case result in game snapshot")
    judgment_score = payload.get("judgment_score")
    return FullCaseResult(
        case_id=str(payload.get("case_id") or ""),
        cd_result=_stage_result_from_dict(payload.get("cd_result")),
        dd_result=_stage_result_from_dict(payload.get("dd_result")),
        ci_result=_stage_result_from_dict(payload.get("ci_result")),
        judgment_score=(dict(judgment_score) if isinstance(judgment_score, dict) else None),
        elapsed_seconds=float(payload.get("elapsed_seconds") or 0.0),
    )


@dataclass
class GameRound:
    round_index: int
    cd_strategy: Optional[str]
    dd_strategy: Optional[str]
    case_result: FullCaseResult
    score: GameScore
    elapsed_seconds: float = 0.0
    equilibrium_snapshot: Optional[Dict[str, Any]] = None
    strategy_switch_log: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_index": self.round_index,
            "cd_strategy": self.cd_strategy,
            "dd_strategy": self.dd_strategy,
            "score": self.score.to_dict(),
            "elapsed_seconds": self.elapsed_seconds,
            "case_result": self.case_result.to_dict(),
            "equilibrium_snapshot": self.equilibrium_snapshot,
            "strategy_switch_log": self.strategy_switch_log,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "GameRound":
        if not isinstance(payload, dict):
            raise ValueError("invalid round in game snapshot")
        equilibrium = payload.get("equilibrium_snapshot")
        switches = payload.get("strategy_switch_log")
        return cls(
            round_index=int(payload.get("round_index", 0)),
            cd_strategy=payload.get("cd_strategy"),
            dd_strategy=payload.get("dd_strategy"),
            case_result=_case_result_from_dict(payload.get("case_result")),
            score=GameScore.from_dict(payload.get("score")),
            elapsed_seconds=float(payload.get("elapsed_seconds") or 0.0),
            equilibrium_snapshot=(dict(equilibrium) if isinstance(equilibrium, dict) else None),
            strategy_switch_log=(
                [dict(item) for item in switches if isinstance(item, dict)]
                if isinstance(switches, list) else None
            ),
        )


@dataclass
class TournamentResult:
    case_id: str
    total_rounds: int
    rounds: List[GameRound]
    elapsed_seconds: float = 0.0
    final_equilibrium: Optional[Dict[str, Any]] = None
    strategy_evolution: Optional[List[Dict[str, Any]]] = None
    payoff_matrix: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "total_rounds": self.total_rounds,
            "rounds": [r.to_dict() for r in self.rounds],
            "elapsed_seconds": self.elapsed_seconds,
            "final_equilibrium": self.final_equilibrium,
            "strategy_evolution": self.strategy_evolution,
            "payoff_matrix": self.payoff_matrix,
        }


_EVALUATE_PROMPT = """你是一位资深的法律分析专家。请分析以下判决书，从博弈角度对原告和被告的表现进行评分。

【判决书】
{judgment_text}

请输出严格的 JSON，格式如下：
{{
  "plaintiff_win_rate": 0.0到1.0之间的数字，表示原告诉请被支持的比例,
  "defendant_win_rate": 0.0到1.0之间的数字，表示被告抗辩成功的比例,
  "reasoning_quality": 0.0到1.0之间的数字，表示双方论证的整体质量,
  "evidence_strength": 0.0到1.0之间的数字，表示证据被采信的程度,
  "analysis": "简要分析判决要点和双方表现"
}}
"""

_EVOLVE_STRATEGY_PROMPT = """你是一位顶尖的诉讼策略专家。请根据上一轮博弈的结果，为{role_name}制定改进后的策略。

【当前策略类型】{current_strategy_type}（{strategy_label}）
【上一轮策略指令】
{current_strategy}

【上一轮判决结果】
{judgment_summary}

【上一轮得分】
- 原告胜率: {plaintiff_score}
- 被告胜率: {defendant_score}
- 论证质量: {reasoning_quality}
- 证据强度: {evidence_strength}

【法院推理要点】
{court_reasoning}

【纳什均衡分析】
- 当前均衡距离: {equilibrium_distance}
- 对方最佳响应策略: {opponent_best_response}
- 建议策略方向: {suggested_direction}

请分析：
1. 上一轮中哪些论点被法院采纳了？
2. 哪些论点被法院驳回了？
3. 对方使用了哪些有效策略？
4. 基于博弈论分析，应如何调整策略？

输出格式（JSON）：
{{
  "recommended_strategy_type": "从 competing/collaborating/compromising/avoiding/accommodating 中选择",
  "strategy_instruction": "改进后的策略指令（不超过 500 字）",
  "reasoning": "策略调整的理由"
}}
"""

_COUNTERFACTUAL_PROMPT = """你是一位法律博弈分析专家。请基于以下案件信息和历史博弈数据，推演如果{party}采用{hypothetical_strategy}策略会产生什么结果。

【案件背景】
{case_summary}

【历史博弈轮次总结】
{history_summary}

【当前收益矩阵先验】
原告策略 {current_plaintiff_strategy} vs 被告策略 {current_defendant_strategy}:
- 原告收益: {current_p_payoff}
- 被告收益: {current_d_payoff}

假设策略变化: {party} 从 {current_strategy} 切换到 {hypothetical_strategy}

请预测：
{{
  "predicted_plaintiff_win_rate": 0.0-1.0,
  "predicted_defendant_win_rate": 0.0-1.0,
  "predicted_reasoning_quality": 0.0-1.0,
  "key_impact": "该策略变化对博弈结果的核心影响",
  "risk_assessment": "切换策略的风险评估",
  "recommendation": "是否建议切换"
}}
"""

# TKI 策略标签映射
_STRATEGY_LABELS = {
    "competing": "竞争型（高主张/低合作）",
    "collaborating": "合作型（高主张/高合作）",
    "compromising": "妥协型（中主张/中合作）",
    "avoiding": "回避型（低主张/低合作）",
    "accommodating": "迁就型（低主张/高合作）",
}


def _sample_strategy_from_distribution(
    dist: Dict[str, float], rng: random.Random,
) -> str:
    """按分布对 TKI 策略做一次多项式抽样。"""
    weights = [max(0.0, float(dist.get(s, 0.0))) for s in STRATEGY_NAMES]
    total = sum(weights)
    if total <= 0:
        return "compromising"
    r = rng.random() * total
    c = 0.0
    for s, w in zip(STRATEGY_NAMES, weights):
        c += w
        if r <= c:
            return s
    return STRATEGY_NAMES[-1]


class GameEngine:
    """增强版博弈引擎：纳什均衡追踪 + per-party 策略管理 + 反事实推演。"""

    def __init__(
        self,
        orchestrator: FullCaseOrchestrator,
        llm_client: LLMClient,
        *,
        prior_strategy_distribution: Optional[Dict[str, float]] = None,
        ess_random_seed: Optional[int] = None,
    ):
        self.orchestrator = orchestrator
        self.llm = llm_client
        self.strategy_history: List[GameRound] = []
        self.nash_tracker = NashEquilibriumTracker()
        self._ess_seed = ess_random_seed if ess_random_seed is not None else 42
        self._nbs_engine = NashBargainingEngine(
            self.nash_tracker, llm_client, use_spne_disagreement=True,
        )
        self._nbs_engine.refresh_spne_disagreement_point()

        # per-party 策略状态
        self._plaintiff_strategy_type: str = "compromising"
        self._defendant_strategy_type: str = "compromising"
        self._plaintiff_strategy_text: Optional[str] = None
        self._defendant_strategy_text: Optional[str] = None

        if prior_strategy_distribution:
            rng = random.Random(self._ess_seed)
            self._plaintiff_strategy_type = _sample_strategy_from_distribution(
                prior_strategy_distribution, rng,
            )
            self._defendant_strategy_type = _sample_strategy_from_distribution(
                prior_strategy_distribution, rng,
            )

        # AgentMediation 争议原因注入
        self._dispute_cause: Optional[str] = None
        self._dispute_cause_detail: Optional[str] = None

        self._evolution_log: List[Dict[str, Any]] = []

    # ================================================================
    # Per-party 策略管理
    # ================================================================

    def set_strategy(self, party: str, strategy_type: str, custom_instruction: Optional[str] = None):
        """设置指定方的 TKI 策略类型。"""
        if strategy_type not in STRATEGY_NAMES:
            raise ValueError(f"Unknown strategy: {strategy_type}. Options: {STRATEGY_NAMES}")

        if party == "plaintiff":
            self._plaintiff_strategy_type = strategy_type
            self._plaintiff_strategy_text = custom_instruction
        elif party == "defendant":
            self._defendant_strategy_type = strategy_type
            self._defendant_strategy_text = custom_instruction
        else:
            raise ValueError(f"Unknown party: {party}. Options: plaintiff, defendant")

        self._evolution_log.append({
            "event": "strategy_set",
            "party": party,
            "strategy_type": strategy_type,
            "has_custom_instruction": custom_instruction is not None,
            "timestamp": time.time(),
        })

    def get_strategy_state(self) -> Dict[str, Any]:
        """获取当前双方策略状态。"""
        return {
            "plaintiff": {
                "strategy_type": self._plaintiff_strategy_type,
                "strategy_label": _STRATEGY_LABELS.get(self._plaintiff_strategy_type, ""),
                "has_custom_instruction": self._plaintiff_strategy_text is not None,
            },
            "defendant": {
                "strategy_type": self._defendant_strategy_type,
                "strategy_label": _STRATEGY_LABELS.get(self._defendant_strategy_type, ""),
                "has_custom_instruction": self._defendant_strategy_text is not None,
            },
            "evolution_log_count": len(self._evolution_log),
        }

    def get_strategy_history(self) -> List[Dict[str, Any]]:
        """获取策略演化历史。"""
        return list(self._evolution_log)

    def export_snapshot(self) -> Dict[str, Any]:
        """Serialize the state required to continue a game after process restart."""
        return {
            "snapshot_version": 1,
            "strategies": {
                "plaintiff": {
                    "type": self._plaintiff_strategy_type,
                    "instruction": self._plaintiff_strategy_text,
                },
                "defendant": {
                    "type": self._defendant_strategy_type,
                    "instruction": self._defendant_strategy_text,
                },
            },
            "dispute": {
                "cause": self._dispute_cause,
                "detail": self._dispute_cause_detail,
            },
            "ess_seed": self._ess_seed,
            "evolution_log": [dict(item) for item in self._evolution_log],
            "nash_tracker": self.nash_tracker.export_state(),
            "rounds": [item.to_dict() for item in self.strategy_history],
        }

    def import_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Restore a v1 snapshot; accept the old rounds-only shape for compatibility."""
        if not isinstance(snapshot, dict):
            raise ValueError("game snapshot must be an object")
        version = snapshot.get("snapshot_version")
        if version not in (None, 1):
            raise ValueError(f"unsupported game snapshot version: {version}")

        strategies = snapshot.get("strategies")
        if isinstance(strategies, dict):
            for party in ("plaintiff", "defendant"):
                entry = strategies.get(party)
                if not isinstance(entry, dict):
                    continue
                strategy_type = entry.get("type")
                if strategy_type not in STRATEGY_NAMES:
                    raise ValueError(f"invalid {party} strategy in game snapshot")
                instruction = entry.get("instruction")
                if instruction is not None and not isinstance(instruction, str):
                    raise ValueError(f"invalid {party} instruction in game snapshot")
                if party == "plaintiff":
                    self._plaintiff_strategy_type = strategy_type
                    self._plaintiff_strategy_text = instruction
                else:
                    self._defendant_strategy_type = strategy_type
                    self._defendant_strategy_text = instruction

        dispute = snapshot.get("dispute")
        if isinstance(dispute, dict):
            self._dispute_cause = dispute.get("cause")
            self._dispute_cause_detail = dispute.get("detail")

        seed = snapshot.get("ess_seed")
        if seed is not None:
            self._ess_seed = int(seed)
        evolution = snapshot.get("evolution_log")
        if evolution is not None:
            if not isinstance(evolution, list):
                raise ValueError("invalid evolution log in game snapshot")
            self._evolution_log = [dict(item) for item in evolution if isinstance(item, dict)]
        tracker = snapshot.get("nash_tracker")
        if tracker is not None:
            if not isinstance(tracker, dict):
                raise ValueError("invalid Nash state in game snapshot")
            self.nash_tracker.import_state(tracker)
        rounds = snapshot.get("rounds", [])
        if not isinstance(rounds, list):
            raise ValueError("invalid rounds in game snapshot")
        self.strategy_history = [GameRound.from_dict(item) for item in rounds]
        self._nbs_engine.refresh_spne_disagreement_point()

    def get_nash_bargaining_engine(self) -> NashBargainingEngine:
        """供调解 API 等外部模块读取与当前收益矩阵一致的 NBS 引擎。"""
        return self._nbs_engine

    def apply_ess_prior(
        self, generations: int = 80, asymmetric: bool = False,
    ) -> Dict[str, Any]:
        """基于复制者动态不动点分布抽样初始原被告策略（ESS 先验注入单案件）。"""
        from core.evolutionary_dynamics import EvolutionaryDynamics

        evo = EvolutionaryDynamics(self.nash_tracker, asymmetric=asymmetric)
        traj = evo.simulate_evolution(generations=generations)
        rng = random.Random(self._ess_seed)
        self._plaintiff_strategy_type = _sample_strategy_from_distribution(
            traj.final_distribution, rng,
        )
        self._defendant_strategy_type = _sample_strategy_from_distribution(
            traj.final_distribution, rng,
        )
        self._nbs_engine.refresh_spne_disagreement_point()
        return {
            "plaintiff_strategy": self._plaintiff_strategy_type,
            "defendant_strategy": self._defendant_strategy_type,
            "final_distribution": traj.final_distribution,
            "converged": traj.converged,
        }

    @staticmethod
    def _rule_claim_alignment(judgment: str, case_info: Dict[str, Any]) -> Optional[float]:
        """规则侧：诉请在判决主文中的字面覆盖度，用于缓解纯 LLM 评分的自证循环。"""
        claims = case_info.get("plaintiff_claims") or case_info.get("claims")
        if not claims or not judgment:
            return None
        if isinstance(claims, str):
            claims = [claims]
        hits = 0
        for c in claims:
            c = str(c).strip()
            if len(c) < 4:
                continue
            snippet = c[: min(40, len(c))]
            if snippet and snippet in judgment:
                hits += 1
        if not claims:
            return None
        return min(1.0, hits / max(1, len([x for x in claims if len(str(x).strip()) >= 4])))

    # ================================================================
    # 评分
    # ================================================================

    def evaluate_judgment(
        self,
        ci_result,
        case_info: Optional[Dict[str, Any]] = None,
    ) -> GameScore:
        """从判决书中提取博弈评分；若提供 case_info 则与诉请覆盖规则分混合。"""
        if not ci_result or not ci_result.final_document or not ci_result.final_document.strip():
            return GameScore.offline("missing_judgment")

        judgment_text = ci_result.final_document[:3000]

        try:
            result = self.llm.chat_json(
                [{"role": "user", "content": _EVALUATE_PROMPT.format(
                    judgment_text=judgment_text
                )}],
                temperature=0.1,
            )
        except Exception as e:
            logger.warning(f"评分 LLM 调用失败: {e}")
            return GameScore.offline("scoring_request_failed")

        if is_degraded_json(result):
            reason = result.get("reason") if isinstance(result, dict) else None
            return GameScore.offline(str(reason or "invalid_score_payload"))

        required = (
            "plaintiff_win_rate",
            "defendant_win_rate",
            "reasoning_quality",
            "evidence_strength",
        )
        if any(key not in result for key in required):
            return GameScore.offline("incomplete_score_payload")
        if any(isinstance(result[key], bool) for key in required):
            return GameScore.offline("invalid_score_payload")
        try:
            p_win, d_win, q, e = (float(result[key]) for key in required)
        except (TypeError, ValueError, OverflowError):
            return GameScore.offline("invalid_score_payload")
        if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in (p_win, d_win, q, e)):
            return GameScore.offline("invalid_score_payload")

        align = None
        if case_info:
            align = self._rule_claim_alignment(judgment_text, case_info)
        if align is not None:
            p_win = max(0.0, min(1.0, 0.62 * p_win + 0.38 * align))
            d_win = max(0.0, min(1.0, 0.62 * d_win + 0.38 * (1.0 - align) * 0.85))

        return GameScore(
            plaintiff_win_rate=p_win,
            defendant_win_rate=d_win,
            reasoning_quality=q,
            evidence_strength=e,
            details={"analysis": result.get("analysis", ""), "rule_claim_alignment": align},
        )

    # ================================================================
    # 策略进化（增强版：基于均衡分析）
    # ================================================================

    def evolve_both_strategies(
        self, last_round: GameRound, method: str = "llm_reflection",
    ) -> None:
        """按原告、被告顺序更新策略，保留交替更新的博弈语义。"""
        # 对方策略和进化历史会在更新期间改变，不能把两侧当作独立任务并行。
        for party in ("plaintiff", "defendant"):
            self.evolve_strategy(party, last_round, method=method)

    def evolve_strategy(
        self,
        party: str,
        last_round: GameRound,
        method: str = "llm_reflection",
    ) -> str:
        """策略进化，支持多种方法。"""
        if last_round.score.degraded:
            return self._plaintiff_strategy_type if party == "plaintiff" else self._defendant_strategy_type
        if method == "best_response":
            return self._evolve_best_response(party)
        elif method == "fictitious_play":
            return self._evolve_fictitious_play(party)
        return self._evolve_llm_reflection(party, last_round)

    def _evolve_best_response(self, party: str) -> str:
        """最佳响应策略进化。"""
        if party == "plaintiff":
            opponent_strat = self._defendant_strategy_type
            new_type = self.nash_tracker.best_response("plaintiff", opponent_strat)
            self._plaintiff_strategy_type = new_type
        else:
            opponent_strat = self._plaintiff_strategy_type
            new_type = self.nash_tracker.best_response("defendant", opponent_strat)
            self._defendant_strategy_type = new_type

        self._evolution_log.append({
            "event": "evolve_best_response",
            "party": party,
            "new_strategy_type": new_type,
            "opponent_strategy": opponent_strat,
            "timestamp": time.time(),
        })
        return new_type

    def _evolve_fictitious_play(self, party: str) -> str:
        """虚拟博弈策略进化：基于对手历史策略分布的最佳响应。"""
        if not self._evolution_log:
            return self._plaintiff_strategy_type if party == "plaintiff" else self._defendant_strategy_type

        opponent_key = "defendant" if party == "plaintiff" else "plaintiff"
        opponent_history = [
            h.get("new_strategy_type") or h.get("strategy_type", "compromising")
            for h in self._evolution_log
            if h.get("party") == opponent_key
        ]
        if not opponent_history:
            return "compromising"

        # 计算对手策略频率分布
        freq = {s: 0 for s in STRATEGY_NAMES}
        for s in opponent_history:
            if s in freq:
                freq[s] += 1
        total = sum(freq.values()) or 1

        # 对每个己方策略计算期望收益
        best_strat = "compromising"
        best_payoff = -1
        for i, ps in enumerate(STRATEGY_NAMES):
            expected = 0.0
            for j, ds in enumerate(STRATEGY_NAMES):
                prob = freq[ds] / total
                if party == "plaintiff":
                    expected += prob * self.nash_tracker._payoff_p[i][j]
                else:
                    expected += prob * self.nash_tracker._payoff_d[i][j]
            if expected > best_payoff:
                best_payoff = expected
                best_strat = ps

        if party == "plaintiff":
            self._plaintiff_strategy_type = best_strat
        else:
            self._defendant_strategy_type = best_strat

        self._evolution_log.append({
            "event": "evolve_fictitious_play",
            "party": party,
            "new_strategy_type": best_strat,
            "expected_payoff": round(best_payoff, 4),
            "opponent_distribution": {k: round(v / total, 3) for k, v in freq.items()},
            "timestamp": time.time(),
        })
        return best_strat

    def _evolve_llm_reflection(self, party: str, last_round: GameRound) -> str:
        """LLM 反思式策略进化（增强版：注入均衡分析信息）。"""
        role_name = "原告律师" if party == "plaintiff" else "被告律师"
        current_type = self._plaintiff_strategy_type if party == "plaintiff" else self._defendant_strategy_type
        current_text = self._plaintiff_strategy_text if party == "plaintiff" else self._defendant_strategy_text

        ci_doc = ""
        if last_round.case_result.ci_result:
            ci_doc = last_round.case_result.ci_result.final_document[:2000]

        # 获取均衡分析
        eq_analysis = self.nash_tracker.analyze(
            self._plaintiff_strategy_type,
            self._defendant_strategy_type,
        )
        opponent_br = eq_analysis.best_response_defendant if party == "plaintiff" else eq_analysis.best_response_plaintiff
        suggested = eq_analysis.best_response_plaintiff if party == "plaintiff" else eq_analysis.best_response_defendant

        prompt = _EVOLVE_STRATEGY_PROMPT.format(
            role_name=role_name,
            current_strategy_type=current_type,
            strategy_label=_STRATEGY_LABELS.get(current_type, ""),
            current_strategy=current_text or "（无自定义指令，使用默认策略）",
            judgment_summary=ci_doc[:1500],
            plaintiff_score=f"{last_round.score.plaintiff_win_rate:.2f}",
            defendant_score=f"{last_round.score.defendant_win_rate:.2f}",
            reasoning_quality=f"{last_round.score.reasoning_quality:.2f}",
            evidence_strength=f"{last_round.score.evidence_strength:.2f}",
            court_reasoning=last_round.score.details.get("analysis", "无"),
            equilibrium_distance=f"{1 - eq_analysis.convergence_rate:.2f}",
            opponent_best_response=opponent_br,
            suggested_direction=suggested,
        )

        try:
            result = self.llm.chat_json(
                [{"role": "user", "content": prompt}],
                temperature=0.3,
            )
        except Exception as e:
            logger.warning(f"策略进化 LLM 调用失败: {e}")
            result = {}

        if not isinstance(result, dict):
            result = {}

        new_type = result.get("recommended_strategy_type", current_type)
        if new_type not in STRATEGY_NAMES:
            new_type = current_type
        new_instruction = result.get("strategy_instruction", "")[:2000]

        if party == "plaintiff":
            self._plaintiff_strategy_type = new_type
            self._plaintiff_strategy_text = new_instruction or self._plaintiff_strategy_text
        else:
            self._defendant_strategy_type = new_type
            self._defendant_strategy_text = new_instruction or self._defendant_strategy_text

        self._evolution_log.append({
            "event": "evolve_llm_reflection",
            "party": party,
            "old_strategy_type": current_type,
            "new_strategy_type": new_type,
            "reasoning": result.get("reasoning", ""),
            "timestamp": time.time(),
        })
        return new_type

    # ================================================================
    # 反事实推演
    # ================================================================

    def counterfactual_analysis(
        self,
        party: str,
        hypothetical_strategy: str,
        case_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """反事实推演：如果某方切换策略会怎样。"""
        if hypothetical_strategy not in STRATEGY_NAMES:
            return {"error": f"Unknown strategy: {hypothetical_strategy}"}

        current_p = self._plaintiff_strategy_type
        current_d = self._defendant_strategy_type
        current_strat = current_p if party == "plaintiff" else current_d

        # 先查收益矩阵的先验数据
        if party == "plaintiff":
            hi = STRATEGY_INDEX[hypothetical_strategy]
            dj = STRATEGY_INDEX[current_d]
            ci = STRATEGY_INDEX[current_p]
            current_payoff_p = self.nash_tracker._payoff_p[ci][dj]
            current_payoff_d = self.nash_tracker._payoff_d[ci][dj]
            hypo_payoff_p = self.nash_tracker._payoff_p[hi][dj]
            hypo_payoff_d = self.nash_tracker._payoff_d[hi][dj]
        else:
            hi = STRATEGY_INDEX[hypothetical_strategy]
            pi = STRATEGY_INDEX[current_p]
            ci_idx = STRATEGY_INDEX[current_d]
            current_payoff_p = self.nash_tracker._payoff_p[pi][ci_idx]
            current_payoff_d = self.nash_tracker._payoff_d[pi][ci_idx]
            hypo_payoff_p = self.nash_tracker._payoff_p[pi][hi]
            hypo_payoff_d = self.nash_tracker._payoff_d[pi][hi]

        # 用历史数据做定量估计
        history_summary = ""
        for i, h in enumerate(self._evolution_log[-5:]):
            history_summary += f"轮次{i}: {h.get('event', '')} party={h.get('party', '')} -> {h.get('new_strategy_type', '')}\n"

        case_summary = ""
        if case_info:
            case_summary = json.dumps(
                {k: str(v)[:200] for k, v in case_info.items() if k != "dialog_history"},
                ensure_ascii=False,
            )[:800]

        try:
            result = self.llm.chat_json(
                [{"role": "user", "content": _COUNTERFACTUAL_PROMPT.format(
                    party="原告" if party == "plaintiff" else "被告",
                    hypothetical_strategy=_STRATEGY_LABELS.get(hypothetical_strategy, hypothetical_strategy),
                    case_summary=case_summary or "无额外案件信息",
                    history_summary=history_summary or "尚无历史轮次",
                    current_plaintiff_strategy=_STRATEGY_LABELS.get(current_p, current_p),
                    current_defendant_strategy=_STRATEGY_LABELS.get(current_d, current_d),
                    current_p_payoff=f"{current_payoff_p:.4f}",
                    current_d_payoff=f"{current_payoff_d:.4f}",
                    current_strategy=_STRATEGY_LABELS.get(current_strat, current_strat),
                )}],
                temperature=0.2,
            )
        except Exception as e:
            logger.warning(f"反事实推演 LLM 调用失败: {e}")
            result = {}

        if not isinstance(result, dict):
            result = {}

        return {
            "party": party,
            "current_strategy": current_strat,
            "hypothetical_strategy": hypothetical_strategy,
            "matrix_prediction": {
                "current_payoff": {"plaintiff": round(current_payoff_p, 4), "defendant": round(current_payoff_d, 4)},
                "hypothetical_payoff": {"plaintiff": round(hypo_payoff_p, 4), "defendant": round(hypo_payoff_d, 4)},
                "payoff_delta": {
                    "plaintiff": round(hypo_payoff_p - current_payoff_p, 4),
                    "defendant": round(hypo_payoff_d - current_payoff_d, 4),
                },
            },
            "llm_prediction": result,
        }

    # ================================================================
    # 博弈轮次 & 锦标赛
    # ================================================================

    def _build_previous_round_summary(self) -> Optional[str]:
        """从上一轮结果构建跨轮记忆摘要。"""
        if not self.strategy_history:
            return None
        last = self.strategy_history[-1]
        parts = [f"上一轮博弈（第{last.round_index + 1}轮）结果摘要："]
        parts.append(f"原告策略: {_STRATEGY_LABELS.get(last.cd_strategy, last.cd_strategy)}")
        parts.append(f"被告策略: {_STRATEGY_LABELS.get(last.dd_strategy, last.dd_strategy)}")
        if last.score.degraded:
            parts.append("上一轮评分不可用，不作为收益或策略调整依据。")
            return "\n".join(parts)
        parts.append(f"原告胜率: {last.score.plaintiff_win_rate:.0%}")
        parts.append(f"被告胜率: {last.score.defendant_win_rate:.0%}")
        analysis = last.score.details.get("analysis", "")
        if analysis:
            parts.append(f"法院分析要点: {analysis[:500]}")
        return "\n".join(parts)

    def run_game_round(
        self,
        case_info: Dict[str, Any],
        round_index: int,
        *,
        on_progress: Optional[Callable] = None,
        evolution_method: str = "llm_reflection",
    ) -> GameRound:
        """运行一轮博弈（策略类型和文本均注入到编排器和 SimAgent）。"""
        t0 = time.time()

        prev_summary = self._build_previous_round_summary()

        case_result = self.orchestrator.run_full_case(
            case_info,
            cd_strategy=self._plaintiff_strategy_text,
            dd_strategy=self._defendant_strategy_text,
            plaintiff_strategy_type=self._plaintiff_strategy_type,
            defendant_strategy_type=self._defendant_strategy_type,
            previous_round_summary=prev_summary,
            dispute_cause=self._dispute_cause,
            dispute_cause_detail=self._dispute_cause_detail,
            on_progress=on_progress,
        )

        score = self.evaluate_judgment(case_result.ci_result, case_info)
        case_result.judgment_score = score.to_dict()

        # 只有真实评分可更新收益矩阵；降级结果仅供界面说明。
        if not score.degraded:
            self.nash_tracker.record_round(
                self._plaintiff_strategy_type,
                self._defendant_strategy_type,
                score.to_dict(),
            )

            try:
                self._nbs_engine.refresh_spne_disagreement_point()
            except Exception as e:
                logger.debug("SPNE 破裂点刷新跳过: %s", e)

        eq_snapshot = self.nash_tracker.analyze(
            self._plaintiff_strategy_type,
            self._defendant_strategy_type,
        ).to_dict()

        game_round = GameRound(
            round_index=round_index,
            cd_strategy=self._plaintiff_strategy_type,
            dd_strategy=self._defendant_strategy_type,
            case_result=case_result,
            score=score,
            elapsed_seconds=round(time.time() - t0, 2),
            equilibrium_snapshot=eq_snapshot,
        )
        self.strategy_history.append(game_round)
        return game_round

    def run_tournament(
        self,
        case_info: Dict[str, Any],
        rounds: int = 3,
        *,
        on_progress: Optional[Callable] = None,
        evolution_method: str = "llm_reflection",
        convergence_threshold: float = 0.05,
        ess_warm_start: bool = False,
    ) -> TournamentResult:
        """运行多轮锦标赛：每轮双方策略根据上轮结果独立进化。"""
        t0 = time.time()
        case_id = case_info.get("case_id", "auto")
        completed_rounds: List[GameRound] = []

        if ess_warm_start:
            warm = self.apply_ess_prior()
            logger.info("ESS 先验初始化: %s", warm)

        for i in range(rounds):
            logger.info(
                f"锦标赛第 {i + 1}/{rounds} 轮 | "
                f"原告={self._plaintiff_strategy_type} 被告={self._defendant_strategy_type}"
            )

            game_round = self.run_game_round(
                case_info, i,
                on_progress=on_progress,
                evolution_method=evolution_method,
            )
            completed_rounds.append(game_round)

            if on_progress:
                on_progress("TOURNAMENT", i, "round_complete", False)

            # 检查收敛
            conv = self.nash_tracker.compute_convergence()
            if not game_round.score.degraded and conv >= (1 - convergence_threshold) and i >= 1:
                logger.info(f"策略已收敛（收敛率={conv:.2f}），提前终止")
                break

            # 策略进化（最后一轮不需要进化）
            if i < rounds - 1 and not game_round.score.degraded:
                self.evolve_both_strategies(game_round, method=evolution_method)
                logger.info(
                    f"第 {i + 1} 轮策略进化完成 -> "
                    f"原告={self._plaintiff_strategy_type} 被告={self._defendant_strategy_type}"
                )

        final_eq = self.nash_tracker.analyze(
            self._plaintiff_strategy_type,
            self._defendant_strategy_type,
        )

        return TournamentResult(
            case_id=case_id,
            total_rounds=len(completed_rounds),
            rounds=completed_rounds,
            elapsed_seconds=round(time.time() - t0, 2),
            final_equilibrium=final_eq.to_dict(),
            strategy_evolution=self._evolution_log.copy(),
            payoff_matrix=self.nash_tracker.get_payoff_matrix_display(),
        )

    # ================================================================
    # 查询接口
    # ================================================================

    def get_equilibrium_analysis(self) -> Dict[str, Any]:
        """获取当前均衡分析。"""
        return self.nash_tracker.analyze(
            self._plaintiff_strategy_type,
            self._defendant_strategy_type,
        ).to_dict()

    def get_payoff_matrix(self) -> Dict[str, Any]:
        """获取收益矩阵。"""
        return self.nash_tracker.get_payoff_matrix_display()

    # ================================================================
    # 会话快照（重启/换引擎恢复）
    # ================================================================

    def export_snapshot(self) -> Dict[str, Any]:
        """导出可序列化的博弈会话快照。"""
        return {
            "schema_version": "game_snapshot.v1",
            "plaintiff_strategy_type": self._plaintiff_strategy_type,
            "defendant_strategy_type": self._defendant_strategy_type,
            "plaintiff_strategy_text": self._plaintiff_strategy_text,
            "defendant_strategy_text": self._defendant_strategy_text,
            "dispute_cause": self._dispute_cause,
            "dispute_cause_detail": self._dispute_cause_detail,
            "strategy_history": [r.to_dict() for r in self.strategy_history],
            "evolution_log": list(self._evolution_log),
        }

    def import_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """从快照恢复策略状态与历史；未知/缺省字段安全忽略。"""
        if not isinstance(snapshot, dict):
            return
        self._plaintiff_strategy_type = snapshot.get(
            "plaintiff_strategy_type", self._plaintiff_strategy_type
        )
        self._defendant_strategy_type = snapshot.get(
            "defendant_strategy_type", self._defendant_strategy_type
        )
        self._plaintiff_strategy_text = snapshot.get("plaintiff_strategy_text")
        self._defendant_strategy_text = snapshot.get("defendant_strategy_text")
        self._dispute_cause = snapshot.get("dispute_cause")
        self._dispute_cause_detail = snapshot.get("dispute_cause_detail")
        self._evolution_log = list(snapshot.get("evolution_log") or [])
        self.strategy_history = [
            _game_round_from_dict(item)
            for item in snapshot.get("strategy_history") or []
            if isinstance(item, dict)
        ]


def _stage_result_from_dict(data: Optional[Dict[str, Any]]) -> Optional[StageResult]:
    if not data:
        return None
    return StageResult(
        scenario=str(data.get("scenario") or ""),
        dialog_history=list(data.get("dialog_history") or []),
        final_document=str(data.get("final_document") or ""),
        extracted_info=dict(data.get("extracted_info") or {}),
        metadata=dict(data.get("metadata") or {}),
    )


def _full_case_result_from_dict(data: Optional[Dict[str, Any]]) -> FullCaseResult:
    data = data or {}
    return FullCaseResult(
        case_id=str(data.get("case_id") or ""),
        cd_result=_stage_result_from_dict(data.get("cd_result")),
        dd_result=_stage_result_from_dict(data.get("dd_result")),
        ci_result=_stage_result_from_dict(data.get("ci_result")),
        judgment_score=data.get("judgment_score"),
        elapsed_seconds=float(data.get("elapsed_seconds", 0.0)),
    )


def _game_round_from_dict(data: Dict[str, Any]) -> GameRound:
    return GameRound(
        round_index=int(data.get("round_index", 0)),
        cd_strategy=data.get("cd_strategy"),
        dd_strategy=data.get("dd_strategy"),
        case_result=_full_case_result_from_dict(data.get("case_result")),
        score=GameScore.from_dict(data.get("score")),
        elapsed_seconds=float(data.get("elapsed_seconds", 0.0)),
        equilibrium_snapshot=data.get("equilibrium_snapshot"),
        strategy_switch_log=data.get("strategy_switch_log"),
    )
