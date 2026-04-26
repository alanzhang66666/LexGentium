"""
扩展式博弈建模与子博弈精炼纳什均衡（SPNE）求解

将 CD→DD→CI 三阶段管道建模为完美信息扩展式博弈 Γ = ⟨N, H, P, u⟩：
- N = {Plaintiff, Defendant}
- H = 博弈历史集合，每个节点对应一个阶段的策略选择
- P: H → N，行动人函数
- u: 终端节点 → R²，收益函数

通过反向归纳法（Backward Induction）求解 SPNE，并与正规形式 NE 进行对比。
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

logger = logging.getLogger("extensive_form")


@dataclass
class GameTreeNode:
    """扩展式博弈树节点"""
    stage: str
    player: str  # "plaintiff" / "defendant" / "terminal"
    action: Optional[str] = None  # 到达此节点所选的策略
    children: Dict[str, "GameTreeNode"] = field(default_factory=dict)
    payoff: Optional[Tuple[float, float]] = None  # 终端节点 (p_payoff, d_payoff)
    spne_action: Optional[str] = None  # 反向归纳选出的最优行动

    def is_terminal(self) -> bool:
        return self.player == "terminal"

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "stage": self.stage,
            "player": self.player,
            "action": self.action,
        }
        if self.is_terminal():
            result["payoff"] = self.payoff
        else:
            result["spne_action"] = self.spne_action
            result["children"] = {k: v.to_dict() for k, v in self.children.items()}
        return result


@dataclass
class SPNEResult:
    """子博弈精炼纳什均衡求解结果"""
    plaintiff_strategy: str
    defendant_best_responses: Dict[str, str]
    spne_payoff: Tuple[float, float]
    game_tree_summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plaintiff_strategy": self.plaintiff_strategy,
            "defendant_best_responses": self.defendant_best_responses,
            "spne_payoff": {
                "plaintiff": round(self.spne_payoff[0], 4),
                "defendant": round(self.spne_payoff[1], 4),
            },
            "game_tree_summary": self.game_tree_summary,
        }


@dataclass
class ExtensiveFormAnalysis:
    """扩展式博弈完整分析结果"""
    spne_profile: SPNEResult
    ne_profile: Dict[str, str]
    ne_payoff: Tuple[float, float]
    spne_ne_match: bool
    prediction_comparison: Dict[str, Any]
    payoff_matrix_used: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spne": self.spne_profile.to_dict(),
            "ne": {
                "plaintiff_strategy": self.ne_profile.get("plaintiff", ""),
                "defendant_strategy": self.ne_profile.get("defendant", ""),
                "payoff": {
                    "plaintiff": round(self.ne_payoff[0], 4),
                    "defendant": round(self.ne_payoff[1], 4),
                },
            },
            "spne_ne_match": self.spne_ne_match,
            "prediction_comparison": self.prediction_comparison,
        }


class ExtensiveFormGame:
    """
    扩展式博弈引擎。

    将 CD→DD→CI 管道建模为两阶段序贯博弈：
    Stage 1: 原告选择 CD 策略 (s_P)
    Stage 2: 被告观察原告策略后选择 DD 策略 (s_D)
    Terminal: 根据 (s_P, s_D) 运行 CI 阶段得到收益

    使用 NashEquilibriumTracker 的收益矩阵作为终端节点收益。
    """

    def __init__(self, payoff_source: NashEquilibriumTracker):
        self._payoff = payoff_source
        self._tree: Optional[GameTreeNode] = None

    def build_game_tree(self) -> GameTreeNode:
        """构建完整的扩展式博弈树。"""
        root = GameTreeNode(stage="CD", player="plaintiff")

        for p_strat in STRATEGY_NAMES:
            p_idx = STRATEGY_INDEX[p_strat]
            dd_node = GameTreeNode(
                stage="DD", player="defendant", action=p_strat,
            )

            for d_strat in STRATEGY_NAMES:
                d_idx = STRATEGY_INDEX[d_strat]
                p_pay = self._payoff._payoff_p[p_idx][d_idx]
                d_pay = self._payoff._payoff_d[p_idx][d_idx]

                terminal = GameTreeNode(
                    stage="CI",
                    player="terminal",
                    action=d_strat,
                    payoff=(p_pay, d_pay),
                )
                dd_node.children[d_strat] = terminal

            root.children[p_strat] = dd_node

        self._tree = root
        return root

    def backward_induction(self, node: Optional[GameTreeNode] = None) -> Tuple[float, float]:
        """反向归纳法求解 SPNE。

        从终端节点反向推导每个决策节点的最优行动。
        返回该节点（子博弈）的均衡收益。
        """
        if node is None:
            if self._tree is None:
                self.build_game_tree()
            node = self._tree

        if node.is_terminal():
            return node.payoff

        best_action = None
        best_payoff: Optional[Tuple[float, float]] = None

        for action, child in node.children.items():
            child_payoff = self.backward_induction(child)

            if best_payoff is None:
                best_action = action
                best_payoff = child_payoff
            else:
                if node.player == "plaintiff":
                    if child_payoff[0] > best_payoff[0]:
                        best_action = action
                        best_payoff = child_payoff
                else:
                    if child_payoff[1] > best_payoff[1]:
                        best_action = action
                        best_payoff = child_payoff

        node.spne_action = best_action
        return best_payoff

    def solve_spne(self) -> SPNEResult:
        """求解子博弈精炼纳什均衡。"""
        if self._tree is None:
            self.build_game_tree()

        spne_payoff = self.backward_induction()
        plaintiff_strat = self._tree.spne_action

        defendant_brs: Dict[str, str] = {}
        for p_strat, dd_node in self._tree.children.items():
            defendant_brs[p_strat] = dd_node.spne_action

        tree_summary = {
            "total_terminal_nodes": N_STRATEGIES * N_STRATEGIES,
            "plaintiff_spne_action": plaintiff_strat,
            "defendant_spne_responses": defendant_brs,
        }

        return SPNEResult(
            plaintiff_strategy=plaintiff_strat,
            defendant_best_responses=defendant_brs,
            spne_payoff=spne_payoff,
            game_tree_summary=tree_summary,
        )

    def solve_ne(self) -> Tuple[Dict[str, str], Tuple[float, float]]:
        """从同一收益矩阵求解正规形式纯策略 NE（用于对比）。"""
        pure_eq = self._payoff.find_pure_nash()
        if pure_eq:
            eq = pure_eq[0]
            pi = STRATEGY_INDEX[eq.plaintiff]
            di = STRATEGY_INDEX[eq.defendant]
            return (
                {"plaintiff": eq.plaintiff, "defendant": eq.defendant},
                (self._payoff._payoff_p[pi][di], self._payoff._payoff_d[pi][di]),
            )
        return (
            {"plaintiff": "compromising", "defendant": "compromising"},
            (self._payoff._payoff_p[2][2], self._payoff._payoff_d[2][2]),
        )

    def full_analysis(self) -> ExtensiveFormAnalysis:
        """执行完整的扩展式博弈分析：SPNE vs NE 对比。"""
        spne = self.solve_spne()
        ne_profile, ne_payoff = self.solve_ne()

        spne_p = spne.plaintiff_strategy
        spne_d = spne.defendant_best_responses.get(spne_p, "compromising")

        match = (
            spne_p == ne_profile.get("plaintiff")
            and spne_d == ne_profile.get("defendant")
        )

        comparison: Dict[str, Any] = {
            "spne_plaintiff": spne_p,
            "spne_defendant_on_path": spne_d,
            "ne_plaintiff": ne_profile.get("plaintiff"),
            "ne_defendant": ne_profile.get("defendant"),
            "match": match,
            "payoff_diff": {
                "plaintiff": round(spne.spne_payoff[0] - ne_payoff[0], 4),
                "defendant": round(spne.spne_payoff[1] - ne_payoff[1], 4),
            },
        }

        if not match:
            comparison["divergence_reason"] = self._explain_divergence(
                spne, ne_profile,
            )

        return ExtensiveFormAnalysis(
            spne_profile=spne,
            ne_profile=ne_profile,
            ne_payoff=ne_payoff,
            spne_ne_match=match,
            prediction_comparison=comparison,
            payoff_matrix_used=self._payoff.get_payoff_matrix_display(),
        )

    def _explain_divergence(
        self, spne: SPNEResult, ne_profile: Dict[str, str],
    ) -> str:
        """解释 SPNE 与 NE 不一致的原因。"""
        ne_d = ne_profile.get("defendant", "")
        spne_d_for_ne_p = spne.defendant_best_responses.get(
            ne_profile.get("plaintiff", ""), "",
        )

        if ne_d != spne_d_for_ne_p:
            return (
                f"NE 中被告选择 {ne_d}，但在扩展式博弈中，"
                f"给定原告选择 {ne_profile.get('plaintiff')}，"
                f"被告的子博弈最优响应为 {spne_d_for_ne_p}。"
                f"NE 中被告的策略构成不可信威胁。"
            )
        return "原告在预期被告最优响应后选择了不同的全局最优策略。"

    def update_terminal_payoff(
        self,
        plaintiff_strategy: str,
        defendant_strategy: str,
        payoff: Tuple[float, float],
    ):
        """用实际模拟结果更新终端节点收益（增量学习）。"""
        pi = STRATEGY_INDEX.get(plaintiff_strategy)
        di = STRATEGY_INDEX.get(defendant_strategy)
        if pi is None or di is None:
            return

        n = self._payoff._counts[pi][di]
        self._payoff._payoff_p[pi][di] = (
            self._payoff._payoff_p[pi][di] * n + payoff[0]
        ) / (n + 1)
        self._payoff._payoff_d[pi][di] = (
            self._payoff._payoff_d[pi][di] * n + payoff[1]
        ) / (n + 1)
        self._payoff._counts[pi][di] = n + 1

        self._tree = None

    def get_strategy_path(self) -> List[Dict[str, str]]:
        """获取 SPNE 均衡路径上的策略序列。"""
        if self._tree is None:
            self.build_game_tree()
            self.backward_induction()

        path = []
        node = self._tree
        while node and not node.is_terminal():
            path.append({
                "stage": node.stage,
                "player": node.player,
                "action": node.spne_action,
            })
            node = node.children.get(node.spne_action)

        if node and node.is_terminal():
            path.append({
                "stage": node.stage,
                "player": "terminal",
                "payoff_plaintiff": round(node.payoff[0], 4),
                "payoff_defendant": round(node.payoff[1], 4),
            })

        return path
