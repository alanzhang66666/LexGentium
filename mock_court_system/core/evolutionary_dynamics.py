"""
演化博弈动力学引擎

基于 Maynard Smith (1973) 的演化稳定策略理论和复制者动态方程，
在群体层面分析 TKI 五策略的演化轨迹与稳定性。

核心功能：
- 复制者动态方程 (Replicator Dynamics) 模拟
- 演化稳定策略 (ESS) 判定
- 群体极化指数 (Shannon 熵) 和社会福利函数
- 策略种群演化轨迹追踪
"""
from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

from core.nash_equilibrium import (
    NashEquilibriumTracker,
    STRATEGY_NAMES,
    STRATEGY_INDEX,
    N_STRATEGIES,
)

logger = logging.getLogger("evolutionary_dynamics")


@dataclass
class PopulationState:
    """种群状态快照"""
    generation: int
    distribution: Dict[str, float]
    mean_fitness: float
    shannon_entropy: float
    social_welfare: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ESSResult:
    """演化稳定策略分析结果"""
    is_ess: bool
    ess_strategy: Optional[str]
    invasion_barriers: Dict[str, float]
    ne_consistent: bool
    ne_strategy: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvolutionTrajectory:
    """完整演化轨迹"""
    generations: int
    history: List[PopulationState]
    converged: bool
    convergence_generation: Optional[int]
    final_distribution: Dict[str, float]
    ess_analysis: ESSResult
    polarization_index: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generations": self.generations,
            "converged": self.converged,
            "convergence_generation": self.convergence_generation,
            "final_distribution": {
                k: round(v, 4) for k, v in self.final_distribution.items()
            },
            "ess_analysis": self.ess_analysis.to_dict(),
            "polarization_index": round(self.polarization_index, 4),
            "history_length": len(self.history),
            "trajectory_sample": [
                self.history[i].to_dict()
                for i in range(0, len(self.history), max(1, len(self.history) // 10))
            ],
        }


def _shannon_entropy(dist: Dict[str, float]) -> float:
    """计算 Shannon 熵 H(x) = -Σ x_i ln(x_i)"""
    h = 0.0
    for v in dist.values():
        if v > 1e-10:
            h -= v * math.log(v)
    return h


def _max_entropy(n: int) -> float:
    """均匀分布下的最大熵"""
    return math.log(n)


class EvolutionaryDynamics:
    """
    演化博弈动力学引擎。

    使用 NashEquilibriumTracker 的收益矩阵作为适应度矩阵，
    通过复制者动态方程模拟策略种群的演化。
    支持对称模式（单种群）和非对称模式（原被告双种群独立演化）。
    """

    def __init__(self, payoff_source: NashEquilibriumTracker, asymmetric: bool = False):
        self._payoff = payoff_source
        self._asymmetric = asymmetric

    def _fitness(self, strategy_idx: int, opponent_pop: List[float],
                 role: str = "plaintiff") -> float:
        """计算策略 i 在对手种群分布下的期望适应度 f_i(x) = Σ_j x_j · u(s_i, s_j)"""
        matrix = self._payoff._payoff_p if role == "plaintiff" else self._payoff._payoff_d
        f = 0.0
        for j in range(N_STRATEGIES):
            f += opponent_pop[j] * matrix[strategy_idx][j]
        return f

    def _mean_fitness(self, population: List[float], opponent_pop: List[float],
                      role: str = "plaintiff") -> float:
        """计算种群平均适应度 f̄(x) = Σ_i x_i · f_i(x)"""
        f_bar = 0.0
        for i in range(N_STRATEGIES):
            f_bar += population[i] * self._fitness(i, opponent_pop, role)
        return f_bar

    def replicator_step(
        self, population: List[float], dt: float = 0.1,
        opponent_pop: Optional[List[float]] = None,
        role: str = "plaintiff",
    ) -> List[float]:
        """执行一步复制者动态：ẋ_i = x_i [f_i(x) - f̄(x)]"""
        if opponent_pop is None:
            opponent_pop = population
        f_bar = self._mean_fitness(population, opponent_pop, role)
        new_pop = []

        for i in range(N_STRATEGIES):
            fi = self._fitness(i, opponent_pop, role)
            xi_new = population[i] + dt * population[i] * (fi - f_bar)
            new_pop.append(max(xi_new, 0.0))

        total = sum(new_pop)
        if total > 0:
            new_pop = [x / total for x in new_pop]

        return new_pop

    def simulate_evolution(
        self,
        generations: int = 100,
        dt: float = 0.1,
        initial_distribution: Optional[Dict[str, float]] = None,
        convergence_threshold: float = 1e-4,
    ) -> EvolutionTrajectory:
        """模拟种群策略分布的完整演化过程。
        对称模式：单种群对自身博弈。
        非对称模式：原告/被告双种群独立演化，各自以对方种群为对手。
        """
        def _init_pop(dist: Optional[Dict[str, float]]) -> List[float]:
            if dist:
                pop = [dist.get(s, 1.0 / N_STRATEGIES) for s in STRATEGY_NAMES]
                total = sum(pop)
                return [x / total for x in pop]
            return [1.0 / N_STRATEGIES] * N_STRATEGIES

        pop_p = _init_pop(initial_distribution)
        pop_d = _init_pop(initial_distribution) if self._asymmetric else pop_p

        history: List[PopulationState] = []
        converged = False
        convergence_gen = None

        for gen in range(generations):
            combined = {
                STRATEGY_NAMES[i]: (pop_p[i] + pop_d[i]) / 2 if self._asymmetric else pop_p[i]
                for i in range(N_STRATEGIES)
            }
            mean_f_p = self._mean_fitness(pop_p, pop_d, "plaintiff")
            mean_f_d = self._mean_fitness(pop_d, pop_p, "defendant") if self._asymmetric else mean_f_p
            mean_f = (mean_f_p + mean_f_d) / 2 if self._asymmetric else mean_f_p
            entropy = _shannon_entropy(combined)

            state = PopulationState(
                generation=gen,
                distribution=combined,
                mean_fitness=round(mean_f, 6),
                shannon_entropy=round(entropy, 6),
                social_welfare=round(mean_f, 6),
            )
            history.append(state)

            if self._asymmetric:
                new_p = self.replicator_step(pop_p, dt, opponent_pop=pop_d, role="plaintiff")
                new_d = self.replicator_step(pop_d, dt, opponent_pop=pop_p, role="defendant")
            else:
                new_p = self.replicator_step(pop_p, dt, opponent_pop=pop_p, role="plaintiff")
                new_d = new_p

            max_change = max(
                abs(new_p[i] - pop_p[i]) for i in range(N_STRATEGIES)
            )
            if self._asymmetric:
                max_change = max(max_change, max(
                    abs(new_d[i] - pop_d[i]) for i in range(N_STRATEGIES)
                ))

            if max_change < convergence_threshold and gen > 5:
                converged = True
                convergence_gen = gen
                pop_p, pop_d = new_p, new_d
                final_combined = {
                    STRATEGY_NAMES[i]: (pop_p[i] + pop_d[i]) / 2 if self._asymmetric else pop_p[i]
                    for i in range(N_STRATEGIES)
                }
                f_p = self._mean_fitness(pop_p, pop_d, "plaintiff")
                f_d = self._mean_fitness(pop_d, pop_p, "defendant") if self._asymmetric else f_p
                final_state = PopulationState(
                    generation=gen + 1,
                    distribution=final_combined,
                    mean_fitness=round((f_p + f_d) / 2 if self._asymmetric else f_p, 6),
                    shannon_entropy=round(_shannon_entropy(final_combined), 6),
                    social_welfare=round((f_p + f_d) / 2 if self._asymmetric else f_p, 6),
                )
                history.append(final_state)
                break

            pop_p, pop_d = new_p, new_d

        final_dist = {
            STRATEGY_NAMES[i]: (pop_p[i] + pop_d[i]) / 2 if self._asymmetric else pop_p[i]
            for i in range(N_STRATEGIES)
        }

        initial_entropy = history[0].shannon_entropy if history else _max_entropy(N_STRATEGIES)
        final_entropy = _shannon_entropy(final_dist)
        polarization = (initial_entropy - final_entropy) / max(initial_entropy, 1e-10)

        ess = self.find_ess(final_dist)

        return EvolutionTrajectory(
            generations=len(history),
            history=history,
            converged=converged,
            convergence_generation=convergence_gen,
            final_distribution=final_dist,
            ess_analysis=ess,
            polarization_index=polarization,
        )

    def find_ess(
        self, converged_distribution: Optional[Dict[str, float]] = None,
    ) -> ESSResult:
        """判定当前收益矩阵下是否存在演化稳定策略。

        策略 s* 是 ESS 当且仅当：
        (i)  u(s*, s*) >= u(s', s*)  对所有 s' ≠ s*
        (ii) 若等号成立，则 u(s*, s') > u(s', s')
        """
        if converged_distribution:
            dominant = max(converged_distribution, key=converged_distribution.get)
            dominant_share = converged_distribution[dominant]
            if dominant_share < 0.5:
                return ESSResult(
                    is_ess=False, ess_strategy=None,
                    invasion_barriers={}, ne_consistent=False, ne_strategy=None,
                )
            candidate_idx = STRATEGY_INDEX[dominant]
        else:
            candidate_idx = None

        ne_strategies = self._payoff.find_pure_nash()
        ne_strat = ne_strategies[0].plaintiff if ne_strategies else None

        best_ess = None
        best_barrier = -1.0

        candidates = [candidate_idx] if candidate_idx is not None else range(N_STRATEGIES)

        for ci in candidates:
            barriers: Dict[str, float] = {}
            is_ess = True

            u_star_star = self._payoff._payoff_p[ci][ci]

            for mi in range(N_STRATEGIES):
                if mi == ci:
                    continue

                u_mutant_star = self._payoff._payoff_p[mi][ci]
                barrier = u_star_star - u_mutant_star
                barriers[STRATEGY_NAMES[mi]] = round(barrier, 4)

                if barrier < -1e-9:
                    is_ess = False
                elif abs(barrier) < 1e-9:
                    u_star_mutant = self._payoff._payoff_p[ci][mi]
                    u_mutant_mutant = self._payoff._payoff_p[mi][mi]
                    if u_star_mutant <= u_mutant_mutant:
                        is_ess = False

            if is_ess:
                min_barrier = min(barriers.values()) if barriers else 0
                if min_barrier > best_barrier:
                    best_barrier = min_barrier
                    best_ess = ESSResult(
                        is_ess=True,
                        ess_strategy=STRATEGY_NAMES[ci],
                        invasion_barriers=barriers,
                        ne_consistent=(STRATEGY_NAMES[ci] == ne_strat),
                        ne_strategy=ne_strat,
                    )

        if best_ess:
            return best_ess

        return ESSResult(
            is_ess=False,
            ess_strategy=None,
            invasion_barriers={},
            ne_consistent=False,
            ne_strategy=ne_strat,
        )

    def compute_social_metrics(
        self, distribution: Dict[str, float],
        opponent_distribution: Optional[Dict[str, float]] = None,
        role: str = "plaintiff",
    ) -> Dict[str, float]:
        """计算给定种群分布下的社会学指标。"""
        population = [distribution.get(s, 0) for s in STRATEGY_NAMES]
        opponent_pop = [opponent_distribution.get(s, 0) for s in STRATEGY_NAMES] if opponent_distribution else population

        mean_f = self._mean_fitness(population, opponent_pop, role)
        entropy = _shannon_entropy(distribution)
        max_ent = _max_entropy(N_STRATEGIES)

        gini_values = []
        for i in range(N_STRATEGIES):
            fi = self._fitness(i, opponent_pop, role)
            gini_values.append(population[i] * fi)

        gini_values.sort()
        n = len(gini_values)
        total = sum(gini_values)
        if total > 0 and n > 1:
            numerator = sum((2 * (i + 1) - n - 1) * gini_values[i] for i in range(n))
            gini = numerator / (n * total)
        else:
            gini = 0.0

        return {
            "mean_fitness": round(mean_f, 4),
            "social_welfare": round(mean_f, 4),
            "shannon_entropy": round(entropy, 4),
            "normalized_entropy": round(entropy / max_ent, 4) if max_ent > 0 else 0,
            "diversity_index": round(entropy / max_ent, 4) if max_ent > 0 else 0,
            "gini_coefficient": round(abs(gini), 4),
        }
