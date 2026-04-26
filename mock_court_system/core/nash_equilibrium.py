"""
纳什均衡追踪引擎
基于 AgentMediation (2509.06586) 的 TKI 策略空间和博弈实验发现，
实现收益矩阵构建、纳什均衡求解与收敛分析。

核心思想：
- 5×5 策略空间（TKI 五策略 × 原被告双方）
- 从历史博弈轮次中构建经验收益矩阵
- 支持 support enumeration 求解混合策略纳什均衡
- 追踪策略演化的收敛趋势
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("nash_equilibrium")

STRATEGY_NAMES = ["competing", "collaborating", "compromising", "avoiding", "accommodating"]
STRATEGY_INDEX = {s: i for i, s in enumerate(STRATEGY_NAMES)}
N_STRATEGIES = len(STRATEGY_NAMES)

# AgentMediation Table 5 的经验先验（NUM=ALL 设定下的成功率 / 满意度 / 共识 / 诉讼风险）
# 用作没有实际博弈历史时的 fallback 先验
_PRIOR_PAYOFFS = {
    "competing":      {"sr": 0.11, "sat": 35.00, "con": 33.00, "lr": 64.00},
    "collaborating":  {"sr": 0.99, "sat": 61.10, "con": 76.25, "lr": 19.00},
    "compromising":   {"sr": 0.99, "sat": 58.67, "con": 75.25, "lr": 19.25},
    "avoiding":       {"sr": 0.37, "sat": 44.73, "con": 60.75, "lr": 25.50},
    "accommodating":  {"sr": 0.97, "sat": 53.35, "con": 75.50, "lr": 16.75},
}


@dataclass
class StrategyProfile:
    """策略组合"""
    plaintiff: str
    defendant: str
    profile_type: str = "pure"  # "pure" | "mixed"
    plaintiff_mix: Optional[Dict[str, float]] = None
    defendant_mix: Optional[Dict[str, float]] = None


@dataclass
class PayoffEntry:
    """收益矩阵中的一个条目"""
    plaintiff_strategy: str
    defendant_strategy: str
    plaintiff_payoff: float
    defendant_payoff: float
    sample_count: int = 0


@dataclass
class EquilibriumAnalysis:
    """均衡分析结果"""
    pure_equilibria: List[StrategyProfile]
    mixed_equilibria: List[StrategyProfile]
    current_profile: StrategyProfile
    convergence_rate: float
    payoff_matrix_plaintiff: List[List[float]]
    payoff_matrix_defendant: List[List[float]]
    best_response_plaintiff: str
    best_response_defendant: str
    rounds_to_convergence_estimate: int
    strategy_labels: List[str] = field(default_factory=lambda: list(STRATEGY_NAMES))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pure_equilibria": [asdict(e) for e in self.pure_equilibria],
            "mixed_equilibria": [asdict(e) for e in self.mixed_equilibria],
            "current_profile": asdict(self.current_profile),
            "convergence_rate": self.convergence_rate,
            "payoff_matrix_plaintiff": self.payoff_matrix_plaintiff,
            "payoff_matrix_defendant": self.payoff_matrix_defendant,
            "best_response_plaintiff": self.best_response_plaintiff,
            "best_response_defendant": self.best_response_defendant,
            "rounds_to_convergence_estimate": self.rounds_to_convergence_estimate,
            "strategy_labels": self.strategy_labels,
        }


def _compute_payoff(score_dict: Dict[str, Any]) -> Tuple[float, float]:
    """从 GameScore 字典计算原被告的标量收益。"""
    p_win = float(score_dict.get("plaintiff_win_rate", 0.5))
    d_win = float(score_dict.get("defendant_win_rate", 0.5))
    quality = float(score_dict.get("reasoning_quality", 0.5))
    evidence = float(score_dict.get("evidence_strength", 0.5))

    p_payoff = p_win * 0.5 + quality * 0.25 + evidence * 0.25
    d_payoff = d_win * 0.5 + quality * 0.25 + evidence * 0.25
    return p_payoff, d_payoff


def _scalar_from_metrics(row: Dict[str, Any]) -> float:
    """将单策略行的 SR/Sat/Con/LR 压成标量效用（与 _compute_payoff 量纲一致）。"""
    return (
        float(row["sr"]) * 0.3
        + float(row["sat"]) / 100 * 0.3
        + float(row["con"]) / 100 * 0.2
        + (1.0 - float(row["lr"]) / 100) * 0.2
    )


def _prior_payoff(p_strat: str, d_strat: str) -> Tuple[float, float]:
    """基于 AgentMediation 经验数据的先验收益（含双方策略交互项）。

    旧版仅把原告收益写成 p 自身指标、被告收益写成 d 自身指标，导致矩阵对 j/i 不变，
    失去博弈意义。此处加入双边的 SR×Con 交叉项与联合诉讼风险摩擦项，使 (i,j) 格点
    随对手策略变化。
    """
    p_data = _PRIOR_PAYOFFS.get(p_strat, _PRIOR_PAYOFFS["compromising"])
    d_data = _PRIOR_PAYOFFS.get(d_strat, _PRIOR_PAYOFFS["compromising"])

    u_p_own = _scalar_from_metrics(p_data)
    u_d_own = _scalar_from_metrics(d_data)
    # 交叉：一方成功率与另一方共识度的互补；对称化第二项
    cross_p = (
        float(p_data["sr"]) * float(d_data["con"])
        + float(p_data["con"]) * float(d_data["sr"])
    ) / 200.0
    cross_d = (
        float(d_data["sr"]) * float(p_data["con"])
        + float(d_data["con"]) * float(p_data["sr"])
    ) / 200.0
    joint_sr = min(float(p_data["sr"]), float(d_data["sr"]))
    # 双方诉讼风险均高 → 摩擦（调解更难、诉讼成本意象）
    friction = max(0.0, (float(p_data["lr"]) + float(d_data["lr"])) / 200.0 - 0.19) * 0.1

    p_payoff = 0.52 * u_p_own + 0.33 * cross_p + 0.15 * joint_sr - friction
    d_payoff = 0.52 * u_d_own + 0.33 * cross_d + 0.15 * joint_sr - friction

    p_payoff = max(0.0, min(1.0, p_payoff))
    d_payoff = max(0.0, min(1.0, d_payoff))
    return round(p_payoff, 4), round(d_payoff, 4)


class NashEquilibriumTracker:
    """
    纳什均衡追踪器。
    维护一张 5×5 经验收益矩阵，并在每轮博弈后更新。
    """

    def __init__(self):
        self._payoff_p = [[0.0] * N_STRATEGIES for _ in range(N_STRATEGIES)]
        self._payoff_d = [[0.0] * N_STRATEGIES for _ in range(N_STRATEGIES)]
        self._counts = [[0] * N_STRATEGIES for _ in range(N_STRATEGIES)]
        self._history: List[Dict[str, Any]] = []
        self._init_prior()

    def _init_prior(self):
        """用 AgentMediation 经验先验初始化矩阵。"""
        for i, ps in enumerate(STRATEGY_NAMES):
            for j, ds in enumerate(STRATEGY_NAMES):
                pp, dp = _prior_payoff(ps, ds)
                self._payoff_p[i][j] = pp
                self._payoff_d[i][j] = dp

    def record_round(
        self,
        plaintiff_strategy: str,
        defendant_strategy: str,
        score: Dict[str, Any],
    ):
        """记录一轮博弈结果并更新收益矩阵。"""
        i = STRATEGY_INDEX.get(plaintiff_strategy)
        j = STRATEGY_INDEX.get(defendant_strategy)
        if i is None or j is None:
            logger.warning(f"Unknown strategy pair: {plaintiff_strategy}/{defendant_strategy}")
            return

        p_pay, d_pay = _compute_payoff(score)
        n = self._counts[i][j]
        # 增量更新均值
        self._payoff_p[i][j] = (self._payoff_p[i][j] * n + p_pay) / (n + 1)
        self._payoff_d[i][j] = (self._payoff_d[i][j] * n + d_pay) / (n + 1)
        self._counts[i][j] = n + 1

        self._history.append({
            "plaintiff_strategy": plaintiff_strategy,
            "defendant_strategy": defendant_strategy,
            "plaintiff_payoff": round(p_pay, 4),
            "defendant_payoff": round(d_pay, 4),
        })

    def best_response(self, player: str, opponent_strategy: str) -> str:
        """给定对手策略，返回玩家的纯策略最佳响应。"""
        j = STRATEGY_INDEX.get(opponent_strategy, 2)

        if player == "plaintiff":
            payoffs = [self._payoff_p[i][j] for i in range(N_STRATEGIES)]
        else:
            payoffs = [self._payoff_d[j][i] for i in range(N_STRATEGIES)]

        best_idx = max(range(N_STRATEGIES), key=lambda k: payoffs[k])
        return STRATEGY_NAMES[best_idx]

    def find_pure_nash(self) -> List[StrategyProfile]:
        """求解纯策略纳什均衡。"""
        equilibria = []
        for i in range(N_STRATEGIES):
            for j in range(N_STRATEGIES):
                p_br = max(range(N_STRATEGIES), key=lambda k: self._payoff_p[k][j])
                d_br = max(range(N_STRATEGIES), key=lambda k: self._payoff_d[i][k])
                if p_br == i and d_br == j:
                    equilibria.append(StrategyProfile(
                        plaintiff=STRATEGY_NAMES[i],
                        defendant=STRATEGY_NAMES[j],
                        profile_type="pure",
                    ))
        return equilibria

    def find_mixed_nash_2x2(self, p_strategies: List[str], d_strategies: List[str]) -> Optional[StrategyProfile]:
        """在给定的 2×2 子博弈中求解混合策略纳什均衡（解析解）。"""
        if len(p_strategies) != 2 or len(d_strategies) != 2:
            return None

        i0, i1 = STRATEGY_INDEX[p_strategies[0]], STRATEGY_INDEX[p_strategies[1]]
        j0, j1 = STRATEGY_INDEX[d_strategies[0]], STRATEGY_INDEX[d_strategies[1]]

        # 被告的混合概率使原告无差异
        a = self._payoff_p[i0][j0] - self._payoff_p[i1][j0]
        b = self._payoff_p[i1][j1] - self._payoff_p[i0][j1]
        denom_q = a + b
        if abs(denom_q) < 1e-9:
            return None
        q = a / denom_q  # 被告选 d_strategies[0] 的概率

        # 原告的混合概率使被告无差异
        c = self._payoff_d[i0][j0] - self._payoff_d[i0][j1]
        d_val = self._payoff_d[i1][j1] - self._payoff_d[i1][j0]
        denom_p = c + d_val
        if abs(denom_p) < 1e-9:
            return None
        p = c / denom_p  # 原告选 p_strategies[0] 的概率

        if not (0 <= p <= 1 and 0 <= q <= 1):
            return None

        return StrategyProfile(
            plaintiff="mixed",
            defendant="mixed",
            profile_type="mixed",
            plaintiff_mix={p_strategies[0]: round(p, 4), p_strategies[1]: round(1 - p, 4)},
            defendant_mix={d_strategies[0]: round(q, 4), d_strategies[1]: round(1 - q, 4)},
        )

    def find_mixed_nash_support_enum(self) -> List[StrategyProfile]:
        """通过支撑枚举法求解所有可能的混合策略纳什均衡（2×2 子博弈）。"""
        results = []
        for i0 in range(N_STRATEGIES):
            for i1 in range(i0 + 1, N_STRATEGIES):
                for j0 in range(N_STRATEGIES):
                    for j1 in range(j0 + 1, N_STRATEGIES):
                        eq = self.find_mixed_nash_2x2(
                            [STRATEGY_NAMES[i0], STRATEGY_NAMES[i1]],
                            [STRATEGY_NAMES[j0], STRATEGY_NAMES[j1]],
                        )
                        if eq:
                            results.append(eq)
        return results

    def compute_convergence(self) -> float:
        """计算当前策略序列到均衡的收敛率（0-1，1=完全收敛）。"""
        if len(self._history) < 2:
            return 0.0

        pure_eq = self.find_pure_nash()
        if not pure_eq:
            return 0.0

        eq_pairs = {(e.plaintiff, e.defendant) for e in pure_eq}

        recent = self._history[-3:] if len(self._history) >= 3 else self._history
        in_eq = sum(
            1 for h in recent
            if (h["plaintiff_strategy"], h["defendant_strategy"]) in eq_pairs
        )
        return round(in_eq / len(recent), 4)

    def estimate_rounds_to_convergence(self) -> int:
        """估算距离均衡还需多少轮。"""
        conv = self.compute_convergence()
        if conv >= 0.95:
            return 0
        if conv <= 0:
            return 10
        return max(1, int((1 - conv) / max(conv, 0.1) * 3))

    def analyze(
        self,
        current_plaintiff_strategy: str = "compromising",
        current_defendant_strategy: str = "compromising",
    ) -> EquilibriumAnalysis:
        """执行完整均衡分析。"""
        pure_eq = self.find_pure_nash()
        mixed_eq = self.find_mixed_nash_support_enum()
        convergence = self.compute_convergence()

        d_strat = current_defendant_strategy
        p_strat = current_plaintiff_strategy
        br_p = self.best_response("plaintiff", d_strat)
        br_d = self.best_response("defendant", p_strat)

        return EquilibriumAnalysis(
            pure_equilibria=pure_eq,
            mixed_equilibria=mixed_eq[:5],
            current_profile=StrategyProfile(
                plaintiff=p_strat,
                defendant=d_strat,
            ),
            convergence_rate=convergence,
            payoff_matrix_plaintiff=[
                [round(self._payoff_p[i][j], 4) for j in range(N_STRATEGIES)]
                for i in range(N_STRATEGIES)
            ],
            payoff_matrix_defendant=[
                [round(self._payoff_d[i][j], 4) for j in range(N_STRATEGIES)]
                for i in range(N_STRATEGIES)
            ],
            best_response_plaintiff=br_p,
            best_response_defendant=br_d,
            rounds_to_convergence_estimate=self.estimate_rounds_to_convergence(),
        )

    def get_payoff_matrix_display(self) -> Dict[str, Any]:
        """返回人类可读的收益矩阵。"""
        rows = []
        for i, ps in enumerate(STRATEGY_NAMES):
            row = {}
            for j, ds in enumerate(STRATEGY_NAMES):
                row[ds] = {
                    "plaintiff": round(self._payoff_p[i][j], 4),
                    "defendant": round(self._payoff_d[i][j], 4),
                    "samples": self._counts[i][j],
                }
            rows.append({"strategy": ps, "vs": row})
        return {"strategies": STRATEGY_NAMES, "matrix": rows}
