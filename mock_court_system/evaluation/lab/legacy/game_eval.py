"""
博弈论评测模块

提供四项博弈论专属评测指标，用于衡量 LLM 智能体的博弈理性程度：
- 策略理性度 (Strategic Rationality, SR)
- 均衡趋近率 (Equilibrium Convergence Rate, ECR)
- 演化稳定性 (ESS-Score)
- NBS 偏离度 (NBS-Deviation)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple

from core.nash_equilibrium import (
    NashEquilibriumTracker,
    STRATEGY_NAMES,
    STRATEGY_INDEX,
    N_STRATEGIES,
)

logger = logging.getLogger("game_eval")


@dataclass
class GameTheoreticScores:
    """博弈论评测指标集合"""
    strategic_rationality: float
    equilibrium_convergence_rate: float
    ess_score: float
    nbs_deviation: float
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategic_rationality": round(self.strategic_rationality, 4),
            "equilibrium_convergence_rate": round(self.equilibrium_convergence_rate, 4),
            "ess_score": round(self.ess_score, 4),
            "nbs_deviation": round(self.nbs_deviation, 4),
            "details": self.details,
        }


class GameTheoreticEvaluator:
    """
    博弈论评测器。

    整合扩展式博弈、演化博弈和讨价还价博弈三个模块的分析结果，
    计算四项标准化评测指标。
    """

    def __init__(self, payoff_source: Optional[NashEquilibriumTracker] = None):
        self._payoff = payoff_source or NashEquilibriumTracker()

    def compute_strategic_rationality(
        self,
        strategy_history: List[Dict[str, str]],
    ) -> Tuple[float, Dict[str, Any]]:
        """策略理性度 (SR)：智能体策略选择与理论最优响应的一致率。

        SR = #{选择了最优响应的轮次} / N

        Args:
            strategy_history: [{"plaintiff": str, "defendant": str}, ...]
        """
        if not strategy_history:
            return 0.0, {"total_rounds": 0, "rational_rounds": 0}

        rational_count = 0
        details_list = []

        for h in strategy_history:
            p_strat = h.get("plaintiff", "compromising")
            d_strat = h.get("defendant", "compromising")

            p_br = self._payoff.best_response("plaintiff", d_strat)
            d_br = self._payoff.best_response("defendant", p_strat)

            p_rational = (p_strat == p_br)
            d_rational = (d_strat == d_br)

            if p_rational and d_rational:
                rational_count += 1

            details_list.append({
                "plaintiff_chose": p_strat,
                "plaintiff_br": p_br,
                "plaintiff_rational": p_rational,
                "defendant_chose": d_strat,
                "defendant_br": d_br,
                "defendant_rational": d_rational,
            })

        sr = rational_count / len(strategy_history)

        return sr, {
            "total_rounds": len(strategy_history),
            "rational_rounds": rational_count,
            "per_round": details_list[-5:],
        }

    def compute_equilibrium_convergence(
        self,
        strategy_history: List[Dict[str, str]],
        window: int = 3,
    ) -> Tuple[float, Dict[str, Any]]:
        """均衡趋近率 (ECR)：策略序列在窗口内处于均衡的比例。

        ECR = #{窗口内处于NE的轮次} / W
        """
        if len(strategy_history) < window:
            return 0.0, {"too_few_rounds": True}

        pure_eq = self._payoff.find_pure_nash()
        eq_pairs = {(e.plaintiff, e.defendant) for e in pure_eq}

        if not eq_pairs:
            return 0.0, {"no_pure_ne": True}

        recent = strategy_history[-window:]
        in_eq = sum(
            1 for h in recent
            if (h.get("plaintiff", ""), h.get("defendant", "")) in eq_pairs
        )

        ecr = in_eq / window

        return ecr, {
            "window": window,
            "recent_strategies": recent,
            "equilibria": [{"p": e.plaintiff, "d": e.defendant} for e in pure_eq],
            "in_equilibrium_count": in_eq,
        }

    def compute_ess_score(
        self,
        converged_distribution: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """演化稳定性 (ESS-Score)：收敛不动点满足 ESS 条件的程度。

        ESS-Score = min barrier / max possible barrier (归一化)
        若收敛分布的主导策略满足 ESS，score 接近 1；否则接近 0。
        """
        from core.evolutionary_dynamics import EvolutionaryDynamics

        evo = EvolutionaryDynamics(self._payoff)
        ess_result = evo.find_ess(converged_distribution)

        if not ess_result.is_ess:
            return 0.0, {
                "is_ess": False,
                "ess_strategy": None,
                "ne_consistent": ess_result.ne_consistent,
            }

        barriers = list(ess_result.invasion_barriers.values())
        if not barriers:
            return 0.0, {"is_ess": True, "no_barriers": True}

        min_barrier = min(barriers)
        max_barrier = max(barriers)
        normalized = min_barrier / max(max_barrier, 1e-10) if max_barrier > 0 else 0

        score = min(max(normalized, 0), 1.0)

        return score, {
            "is_ess": True,
            "ess_strategy": ess_result.ess_strategy,
            "min_invasion_barrier": round(min_barrier, 4),
            "max_invasion_barrier": round(max_barrier, 4),
            "ne_consistent": ess_result.ne_consistent,
            "invasion_barriers": ess_result.invasion_barriers,
        }

    def compute_nbs_deviation(
        self,
        actual_utility: Tuple[float, float],
        nbs_utility: Tuple[float, float],
    ) -> Tuple[float, Dict[str, Any]]:
        """NBS 偏离度：实际调解方案与纳什讨价还价解的欧氏距离。

        NBS-Dev = ||u_actual - u_NBS||_2
        """
        dev = (
            (actual_utility[0] - nbs_utility[0]) ** 2
            + (actual_utility[1] - nbs_utility[1]) ** 2
        ) ** 0.5

        return dev, {
            "actual": {"plaintiff": round(actual_utility[0], 4), "defendant": round(actual_utility[1], 4)},
            "nbs": {"plaintiff": round(nbs_utility[0], 4), "defendant": round(nbs_utility[1], 4)},
            "deviation_plaintiff": round(actual_utility[0] - nbs_utility[0], 4),
            "deviation_defendant": round(actual_utility[1] - nbs_utility[1], 4),
        }

    def evaluate(
        self,
        strategy_history: Optional[List[Dict[str, str]]] = None,
        converged_distribution: Optional[Dict[str, float]] = None,
        actual_mediation_utility: Optional[Tuple[float, float]] = None,
        nbs_utility: Optional[Tuple[float, float]] = None,
    ) -> GameTheoreticScores:
        """执行完整的博弈论评测。"""
        details: Dict[str, Any] = {}

        if strategy_history:
            sr, sr_details = self.compute_strategic_rationality(strategy_history)
            ecr, ecr_details = self.compute_equilibrium_convergence(strategy_history)
            details["strategic_rationality"] = sr_details
            details["equilibrium_convergence"] = ecr_details
        else:
            sr, ecr = 0.0, 0.0

        if converged_distribution:
            ess, ess_details = self.compute_ess_score(converged_distribution)
            details["ess"] = ess_details
        else:
            ess = 0.0

        if actual_mediation_utility and nbs_utility:
            nbs_dev, nbs_details = self.compute_nbs_deviation(
                actual_mediation_utility, nbs_utility,
            )
            details["nbs_deviation"] = nbs_details
        else:
            nbs_dev = 0.0

        return GameTheoreticScores(
            strategic_rationality=sr,
            equilibrium_convergence_rate=ecr,
            ess_score=ess,
            nbs_deviation=nbs_dev,
            details=details,
        )

    def generate_report(self, scores: GameTheoreticScores) -> str:
        """生成人类可读的博弈论评测报告。"""
        lines = [
            "=" * 50,
            "博弈论评测报告",
            "=" * 50,
            "",
            f"1. 策略理性度 (SR): {scores.strategic_rationality:.2%}",
            f"   智能体选择理论最优响应的比例。>80% 表示高度理性。",
            "",
            f"2. 均衡趋近率 (ECR): {scores.equilibrium_convergence_rate:.2%}",
            f"   近期策略序列处于纳什均衡的比例。=100% 表示已收敛。",
            "",
            f"3. 演化稳定性 (ESS-Score): {scores.ess_score:.4f}",
            f"   收敛策略抵抗突变入侵的能力。>0 表示存在 ESS。",
            "",
            f"4. NBS 偏离度 (NBS-Dev): {scores.nbs_deviation:.4f}",
            f"   调解方案与纳什讨价还价解的距离。越小越公平。",
            "",
            "=" * 50,
        ]

        ess_details = scores.details.get("ess", {})
        if ess_details.get("is_ess"):
            lines.append(f"ESS 策略: {ess_details.get('ess_strategy', '—')}")
            lines.append(f"与 NE 一致: {'是' if ess_details.get('ne_consistent') else '否'}")

        return "\n".join(lines)
