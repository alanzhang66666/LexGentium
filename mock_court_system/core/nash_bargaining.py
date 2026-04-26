"""
纳什讨价还价博弈引擎

基于 Nash (1950) 的公理化讨价还价解和 Rubinstein (1982) 的轮流出价模型，
为调解引擎提供博弈论基础的"公平参考点"。

核心概念：
- 可行收益集 F ⊂ R²：调解可能达成的方案对应的收益对
- 谈判破裂点 d = (d_P, d_D)：调解失败后走诉讼的预期收益
- NBS: argmax_{(x,y)∈F, x≥d_P, y≥d_D} (x - d_P)(y - d_D)

满足四条公理：帕累托最优、对称性、独立于无关选项、仿射不变性。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

from core.nash_equilibrium import (
    NashEquilibriumTracker,
    STRATEGY_NAMES,
    STRATEGY_INDEX,
    N_STRATEGIES,
)

logger = logging.getLogger("nash_bargaining")


@dataclass
class BargainingOutcome:
    """单个可行方案的收益"""
    description: str
    plaintiff_utility: float
    defendant_utility: float
    source: str = "llm_generated"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NashBargainingSolution:
    """纳什讨价还价解"""
    nbs_plaintiff: float
    nbs_defendant: float
    disagreement_point: Tuple[float, float]
    nash_product: float
    selected_outcome: Optional[BargainingOutcome]
    all_outcomes: List[BargainingOutcome]
    rubinstein_prediction: Optional[Dict[str, float]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nbs": {
                "plaintiff": round(self.nbs_plaintiff, 4),
                "defendant": round(self.nbs_defendant, 4),
            },
            "disagreement_point": {
                "plaintiff": round(self.disagreement_point[0], 4),
                "defendant": round(self.disagreement_point[1], 4),
            },
            "nash_product": round(self.nash_product, 6),
            "selected_outcome": self.selected_outcome.to_dict() if self.selected_outcome else None,
            "num_feasible_outcomes": len(self.all_outcomes),
            "rubinstein_prediction": self.rubinstein_prediction,
        }


@dataclass
class BargainingAnalysis:
    """讨价还价博弈分析结果"""
    nbs: NashBargainingSolution
    actual_outcome: Optional[BargainingOutcome]
    nbs_deviation: float
    fairness_score: float
    pareto_optimal: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nbs": self.nbs.to_dict(),
            "actual_outcome": self.actual_outcome.to_dict() if self.actual_outcome else None,
            "nbs_deviation": round(self.nbs_deviation, 4),
            "fairness_score": round(self.fairness_score, 4),
            "pareto_optimal": self.pareto_optimal,
        }


class NashBargainingEngine:
    """
    纳什讨价还价博弈引擎。

    与 MediationEngine 配合使用：
    1. 从博弈引擎获取谈判破裂点（诉讼预期收益）
    2. 从 LLM 生成的候选方案构建可行集
    3. 计算 NBS 作为调解的"公平参考点"
    4. 注入到调解引擎的方案生成阶段
    """

    def __init__(
        self,
        payoff_source: Optional[NashEquilibriumTracker] = None,
        llm_client=None,
        use_spne_disagreement: bool = True,
    ):
        self._payoff = payoff_source
        self.llm = llm_client
        # True：破裂点取扩展式博弈 SPNE 路径终端收益（全局诉讼理性基准）
        # False：破裂点取当前策略格点 (pi,di) 的收益（局部 BATNA）
        self.use_spne_disagreement = use_spne_disagreement
        self._spne_disagreement: Optional[Tuple[float, float]] = None

    def refresh_spne_disagreement_point(self) -> Optional[Tuple[float, float]]:
        """根据当前收益矩阵重算 SPNE 终端收益，并缓存为调解破裂点。"""
        if self._payoff is None:
            self._spne_disagreement = None
            return None
        from core.extensive_form import ExtensiveFormGame

        efg = ExtensiveFormGame(self._payoff)
        spne = efg.solve_spne()
        self._spne_disagreement = (
            round(float(spne.spne_payoff[0]), 4),
            round(float(spne.spne_payoff[1]), 4),
        )
        return self._spne_disagreement

    def compute_disagreement_point(
        self,
        plaintiff_strategy: str = "compromising",
        defendant_strategy: str = "compromising",
    ) -> Tuple[float, float]:
        """计算谈判破裂点 d = (d_P, d_D)。

        调解失败 → 走诉讼：若 ``use_spne_disagreement`` 为真，则取扩展式博弈 SPNE
        路径上的终端收益；否则取当前策略组合在正规形式矩阵中的格点收益。
        """
        if self._payoff is None:
            return (0.5, 0.5)

        if self.use_spne_disagreement:
            if self._spne_disagreement is None:
                self.refresh_spne_disagreement_point()
            if self._spne_disagreement is not None:
                return self._spne_disagreement

        pi = STRATEGY_INDEX.get(plaintiff_strategy, 2)
        di = STRATEGY_INDEX.get(defendant_strategy, 2)

        d_p = self._payoff._payoff_p[pi][di]
        d_d = self._payoff._payoff_d[pi][di]

        return (d_p, d_d)

    def compute_nbs(
        self,
        feasible_outcomes: List[BargainingOutcome],
        disagreement_point: Tuple[float, float],
    ) -> NashBargainingSolution:
        """计算纳什讨价还价解。

        NBS = argmax (x - d_P)(y - d_D) s.t. (x,y) ∈ F, x ≥ d_P, y ≥ d_D
        """
        d_p, d_d = disagreement_point

        valid = [
            o for o in feasible_outcomes
            if o.plaintiff_utility >= d_p and o.defendant_utility >= d_d
        ]

        if not valid:
            valid = feasible_outcomes

        if not valid:
            return NashBargainingSolution(
                nbs_plaintiff=d_p,
                nbs_defendant=d_d,
                disagreement_point=disagreement_point,
                nash_product=0.0,
                selected_outcome=None,
                all_outcomes=[],
                rubinstein_prediction=None,
            )

        best_outcome = None
        best_product = -float("inf")

        for outcome in valid:
            surplus_p = max(outcome.plaintiff_utility - d_p, 0)
            surplus_d = max(outcome.defendant_utility - d_d, 0)
            product = surplus_p * surplus_d

            if product > best_product:
                best_product = product
                best_outcome = outcome

        rubinstein = self._rubinstein_prediction(disagreement_point, valid)

        return NashBargainingSolution(
            nbs_plaintiff=best_outcome.plaintiff_utility,
            nbs_defendant=best_outcome.defendant_utility,
            disagreement_point=disagreement_point,
            nash_product=best_product,
            selected_outcome=best_outcome,
            all_outcomes=feasible_outcomes,
            rubinstein_prediction=rubinstein,
        )

    def _rubinstein_prediction(
        self,
        disagreement_point: Tuple[float, float],
        outcomes: List[BargainingOutcome],
        discount_factor: float = 0.9,
    ) -> Dict[str, float]:
        """Rubinstein 轮流出价模型的均衡预测。

        在对称折现因子 δ 下，先出价方获得的份额为 1/(1+δ)。
        """
        if not outcomes:
            return {"plaintiff_share": 0.5, "defendant_share": 0.5}

        total_surplus_p = sum(o.plaintiff_utility for o in outcomes) / len(outcomes)
        total_surplus_d = sum(o.defendant_utility for o in outcomes) / len(outcomes)
        total = total_surplus_p + total_surplus_d

        if total < 1e-10:
            return {"plaintiff_share": 0.5, "defendant_share": 0.5}

        first_mover_share = 1.0 / (1.0 + discount_factor)
        second_mover_share = discount_factor / (1.0 + discount_factor)

        return {
            "plaintiff_share": round(first_mover_share, 4),
            "defendant_share": round(second_mover_share, 4),
            "discount_factor": discount_factor,
            "first_mover_advantage": round(first_mover_share - 0.5, 4),
        }

    def generate_feasible_set_from_scores(
        self,
        case_info: Dict[str, Any],
        candidate_solutions: List[str],
    ) -> List[BargainingOutcome]:
        """通过 LLM 为候选调解方案评分，构建可行收益集。"""
        if not self.llm or not candidate_solutions:
            return self._default_feasible_set()

        outcomes = []
        for i, solution in enumerate(candidate_solutions):
            prompt = (
                f"请评估以下调解方案对原告和被告的公平性。\n\n"
                f"【调解方案】\n{solution[:500]}\n\n"
                f"请输出 JSON：\n"
                f'{{"plaintiff_satisfaction": 0.0到1.0, '
                f'"defendant_satisfaction": 0.0到1.0, '
                f'"rationale": "简要理由"}}'
            )

            try:
                result = self.llm.chat_json(
                    [{"role": "user", "content": prompt}],
                    temperature=0.1,
                )
                if isinstance(result, dict):
                    outcomes.append(BargainingOutcome(
                        description=solution[:200],
                        plaintiff_utility=float(result.get("plaintiff_satisfaction", 0.5)),
                        defendant_utility=float(result.get("defendant_satisfaction", 0.5)),
                        source="llm_scored",
                    ))
            except Exception as e:
                logger.warning(f"方案评分失败: {e}")

        if not outcomes:
            return self._default_feasible_set()
        return outcomes

    def default_feasible_outcomes(self) -> List[BargainingOutcome]:
        """默认可行集（对外 API，供调解路由等使用）。"""
        return self._default_feasible_set()

    def _default_feasible_set(self) -> List[BargainingOutcome]:
        """默认可行集：基于收益矩阵的典型收益对。"""
        outcomes = []
        if self._payoff:
            for i, ps in enumerate(STRATEGY_NAMES):
                for j, ds in enumerate(STRATEGY_NAMES):
                    outcomes.append(BargainingOutcome(
                        description=f"策略组合({ps},{ds})对应的预期收益",
                        plaintiff_utility=self._payoff._payoff_p[i][j],
                        defendant_utility=self._payoff._payoff_d[i][j],
                        source="payoff_matrix",
                    ))
        else:
            outcomes = [
                BargainingOutcome("全额支持原告", 0.9, 0.2, "synthetic"),
                BargainingOutcome("部分支持原告", 0.7, 0.5, "synthetic"),
                BargainingOutcome("对半分担", 0.5, 0.5, "synthetic"),
                BargainingOutcome("部分支持被告", 0.3, 0.7, "synthetic"),
                BargainingOutcome("驳回原告请求", 0.1, 0.9, "synthetic"),
            ]
        return outcomes

    def analyze(
        self,
        feasible_outcomes: List[BargainingOutcome],
        actual_outcome: Optional[BargainingOutcome] = None,
        plaintiff_strategy: str = "compromising",
        defendant_strategy: str = "compromising",
    ) -> BargainingAnalysis:
        """执行完整的讨价还价博弈分析。"""
        d = self.compute_disagreement_point(plaintiff_strategy, defendant_strategy)
        nbs = self.compute_nbs(feasible_outcomes, d)

        deviation = 0.0
        fairness = 0.5
        pareto = False

        if actual_outcome:
            deviation = (
                (actual_outcome.plaintiff_utility - nbs.nbs_plaintiff) ** 2
                + (actual_outcome.defendant_utility - nbs.nbs_defendant) ** 2
            ) ** 0.5

            ratio_diff = abs(
                actual_outcome.plaintiff_utility - actual_outcome.defendant_utility
            )
            fairness = max(0, 1.0 - ratio_diff)

            pareto = not any(
                o.plaintiff_utility >= actual_outcome.plaintiff_utility
                and o.defendant_utility >= actual_outcome.defendant_utility
                and (o.plaintiff_utility > actual_outcome.plaintiff_utility
                     or o.defendant_utility > actual_outcome.defendant_utility)
                for o in feasible_outcomes
            )

        return BargainingAnalysis(
            nbs=nbs,
            actual_outcome=actual_outcome,
            nbs_deviation=deviation,
            fairness_score=fairness,
            pareto_optimal=pareto,
        )

    def generate_nbs_reference_text(
        self,
        nbs: NashBargainingSolution,
        case_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """生成注入调解引擎的 NBS 公平参考点文本。"""
        parts = ["【博弈论公平参考点（纳什讨价还价解）】"]

        parts.append(
            f"基于博弈论分析，调解失败后双方转入诉讼的预期收益分别为："
            f"原告 {nbs.disagreement_point[0]:.2f}、被告 {nbs.disagreement_point[1]:.2f}。"
        )

        parts.append(
            f"在满足帕累托最优和对称性的公理化框架下，"
            f"纳什讨价还价解建议的最优方案应使原告获得约 {nbs.nbs_plaintiff:.2f} 的满意度、"
            f"被告获得约 {nbs.nbs_defendant:.2f} 的满意度。"
        )

        if nbs.selected_outcome:
            parts.append(
                f"对应的具体方案方向为：{nbs.selected_outcome.description[:200]}"
            )

        if nbs.rubinstein_prediction:
            fma = nbs.rubinstein_prediction.get("first_mover_advantage", 0)
            if abs(fma) > 0.05:
                parts.append(
                    f"注意：Rubinstein轮流出价模型预测先提方案者有约 {fma:.1%} 的优势，"
                    f"调解员应注意平衡双方的发言顺序。"
                )

        parts.append(
            "请参考以上分析结果，在保证公平性的前提下制定调解方案。"
        )

        return "\n".join(parts)
