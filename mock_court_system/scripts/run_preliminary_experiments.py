"""
LexGentium 初步实验验证脚本

基于新修改的申请书方案，设计5组真实实验：
  预实验0: 管道冒烟测试（3案件 x 默认策略）
  实验1:   SPNE vs NE 对比（5案件 x 9策略组合，并发）
  实验2:   演化博弈动力学模拟（纯计算，基于实验1收益矩阵）
  实验3:   NBS 调解对比（3案件 x 2模式）
  实验4:   工程模块消融（3案件 x 4配置，并发）
  实验5:   博弈论评测指标汇总（纯计算）

耗时部分（实验1/4）使用 ThreadPoolExecutor 并发加速。

输出: experiments/results/prelim_*.json + prelim_*.png
"""
from __future__ import annotations

import sys
import os
import json
import time
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False

from config import settings
from core import LLMClient, CourtSimulatorClient
from core.nash_equilibrium import NashEquilibriumTracker, STRATEGY_NAMES, STRATEGY_INDEX
from core.extensive_form import ExtensiveFormGame
from core.evolutionary_dynamics import EvolutionaryDynamics
from core.nash_bargaining import NashBargainingEngine, BargainingOutcome
from core.progressive_rag import ProgressiveRAG
from core.dual_mode_reasoning import DualModeReasoner
from core.multi_judge import MultiJudgeEngine
from core.case_orchestrator import FullCaseOrchestrator
from core.mediation_engine import MediationEngine
from evaluation.lib.game_eval import GameTheoreticEvaluator
from agents import CDAgent, DDAgent, CIAgent, SimAgent

OUTPUT_DIR = PROJECT_ROOT / "experiments" / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("prelim_exp")

# 初步验证用的缩减策略集（3x3 = 9 组合）
CORE_STRATEGIES = ["competing", "collaborating", "compromising"]
CORE_STRATEGY_CN = {"competing": "竞争型", "collaborating": "合作型", "compromising": "妥协型"}
ALL_STRATEGY_CN = {
    "competing": "竞争型", "collaborating": "合作型", "compromising": "妥协型",
    "avoiding": "回避型", "accommodating": "迁就型",
}

# =====================================================================
# 数据加载
# =====================================================================

def load_test_cases(n: int = 5) -> List[Dict[str, Any]]:
    """从测试集按案由分层抽样选取案件。"""
    data_path = PROJECT_ROOT / "data" / "dataset_1000" / "test" / "case_info.jsonl"
    cases: List[Dict] = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    target_causes = ["民间借贷", "交通事故", "劳动", "合同纠纷", "房屋租赁"]
    selected: List[Dict] = []
    used_causes: set = set()

    for cause_kw in target_causes:
        for c in cases:
            if cause_kw in c.get("cause", "") and cause_kw not in used_causes:
                selected.append(c)
                used_causes.add(cause_kw)
                break
        if len(selected) >= n:
            break

    while len(selected) < n and len(selected) < len(cases):
        candidate = cases[len(selected)]
        if candidate not in selected:
            selected.append(candidate)

    logger.info(f"选取 {len(selected)} 个案件: {[c.get('case_id') for c in selected]}")
    return selected[:n]


# =====================================================================
# 基础设施：构建 Orchestrator + LLM 评分
# =====================================================================

def create_llm_client() -> LLMClient:
    return LLMClient(
        api_key=settings.llm.api_key,
        base_url=settings.llm.base_url,
        model=settings.llm.model,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        timeout=settings.llm.timeout,
        provider=settings.llm.provider,
    )


def create_orchestrator(llm: LLMClient) -> FullCaseOrchestrator:
    api_client = CourtSimulatorClient(
        base_url=settings.api.base_url,
        api_key=settings.api.api_key,
        scenario_prefix=settings.api.scenario_prefix,
        timeout=settings.api.timeout,
    )
    return FullCaseOrchestrator(
        llm_client=llm,
        cd_agent=CDAgent(api_client=api_client, llm=llm, max_turns=15, verbose=False),
        dd_agent=DDAgent(api_client=api_client, llm=llm, max_turns=15, verbose=False),
        ci_agent=CIAgent(api_client=api_client, llm=llm, max_turns=40, verbose=False),
        sim_agent=SimAgent(llm),
        max_turns_per_stage=15,
    )


_SCORING_PROMPT = """你是法学评测专家。请阅读以下判决书并从三个维度打分（0.0-1.0）：

【判决书】
{judgment}

请输出 JSON（不含其他文字）：
{{"plaintiff_win_rate": 0.0到1.0, "reasoning_quality": 0.0到1.0, "evidence_strength": 0.0到1.0}}"""


def score_judgment(llm: LLMClient, judgment_text: str) -> Dict[str, float]:
    """用 LLM-as-Judge 对判决书打分，返回三维分数。"""
    if not judgment_text or len(judgment_text) < 20:
        return {"plaintiff_win_rate": 0.5, "reasoning_quality": 0.3, "evidence_strength": 0.3}
    try:
        result = llm.chat_json(
            [{"role": "user", "content": _SCORING_PROMPT.format(judgment=judgment_text[:3000])}],
            temperature=0.1,
        )
        if isinstance(result, dict):
            return {
                "plaintiff_win_rate": float(result.get("plaintiff_win_rate", 0.5)),
                "reasoning_quality": float(result.get("reasoning_quality", 0.5)),
                "evidence_strength": float(result.get("evidence_strength", 0.5)),
            }
    except Exception as e:
        logger.warning(f"评分失败: {e}")
    return {"plaintiff_win_rate": 0.5, "reasoning_quality": 0.3, "evidence_strength": 0.3}


def compute_payoff(score: Dict[str, float]) -> Tuple[float, float]:
    """公式(1): u_P = 0.5*w + 0.25*q + 0.25*e; u_D = 1 - u_P（零和近似）。"""
    w = score.get("plaintiff_win_rate", 0.5)
    q = score.get("reasoning_quality", 0.5)
    e = score.get("evidence_strength", 0.5)
    u_p = 0.5 * w + 0.25 * q + 0.25 * e
    u_d = 1.0 - u_p
    return (round(u_p, 4), round(u_d, 4))


# =====================================================================
# 预实验0: 管道冒烟测试
# =====================================================================

def run_smoke_test(cases: List[Dict], llm: LLMClient) -> Dict[str, Any]:
    """3 个案件以默认策略运行全流程，验证管道端到端可通。"""
    logger.info("=" * 60)
    logger.info("[预实验0] 管道冒烟测试")
    logger.info("=" * 60)

    smoke_cases = cases[:3]
    orch = create_orchestrator(llm)
    results = []

    for case in smoke_cases:
        cid = case.get("case_id", "?")
        logger.info(f"  冒烟测试: {cid} ({case.get('cause', '')})")
        t0 = time.time()
        try:
            result = orch.run_full_case(
                case,
                plaintiff_strategy_type="compromising",
                defendant_strategy_type="compromising",
            )
            elapsed = round(time.time() - t0, 1)
            results.append({
                "case_id": cid,
                "cause": case.get("cause", ""),
                "elapsed_s": elapsed,
                "cd_turns": result.cd_result.metadata.get("turns", 0) if result.cd_result else 0,
                "dd_turns": result.dd_result.metadata.get("turns", 0) if result.dd_result else 0,
                "ci_turns": result.ci_result.metadata.get("turns", 0) if result.ci_result else 0,
                "cd_doc_len": len(result.cd_result.final_document) if result.cd_result else 0,
                "dd_doc_len": len(result.dd_result.final_document) if result.dd_result else 0,
                "ci_doc_len": len(result.ci_result.final_document) if result.ci_result else 0,
                "status": "ok",
            })
            logger.info(f"    OK  耗时={elapsed}s  CI文档长度={results[-1]['ci_doc_len']}")
        except Exception as e:
            logger.error(f"    FAIL: {e}")
            results.append({"case_id": cid, "status": "error", "error": str(e)})

    out = {"experiment": "smoke_test", "results": results}
    _save_json("prelim_exp0_smoke.json", out)
    return out


# =====================================================================
# 实验1: SPNE vs NE 对比（并发）
# =====================================================================

@dataclass
class StrategyRunResult:
    case_id: str
    plaintiff_strategy: str
    defendant_strategy: str
    judgment_text: str
    score: Dict[str, float]
    payoff: Tuple[float, float]
    elapsed_s: float
    error: Optional[str] = None


def _run_single_strategy_combo(
    case: Dict, p_strat: str, d_strat: str, llm: LLMClient,
) -> StrategyRunResult:
    """单次策略组合的全流程运行（线程安全：每次创建独立 orchestrator）。"""
    cid = case.get("case_id", "?")
    t0 = time.time()
    try:
        orch = create_orchestrator(llm)
        result = orch.run_full_case(
            case,
            plaintiff_strategy_type=p_strat,
            defendant_strategy_type=d_strat,
        )
        judgment = result.ci_result.final_document if result.ci_result else ""
        score = score_judgment(llm, judgment)
        payoff = compute_payoff(score)
        elapsed = round(time.time() - t0, 1)
        logger.info(f"    [{cid}] {p_strat[:4]}x{d_strat[:4]} → u=({payoff[0]:.3f},{payoff[1]:.3f})  {elapsed}s")
        return StrategyRunResult(cid, p_strat, d_strat, judgment[:500], score, payoff, elapsed)
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        logger.error(f"    [{cid}] {p_strat[:4]}x{d_strat[:4]} FAIL: {e}")
        return StrategyRunResult(cid, p_strat, d_strat, "", {}, (0.5, 0.5), elapsed, str(e))


def run_exp1_spne_vs_ne(
    cases: List[Dict], llm: LLMClient, max_workers: int = 4,
) -> Dict[str, Any]:
    """实验1: 遍历策略组合、构建真实收益矩阵、求解 SPNE vs NE。"""
    logger.info("=" * 60)
    logger.info(f"[实验1] SPNE vs NE（{len(cases)}案件 x {len(CORE_STRATEGIES)}^2策略，并发={max_workers}）")
    logger.info("=" * 60)

    all_runs: List[StrategyRunResult] = []
    tasks = []
    for case in cases:
        for ps in CORE_STRATEGIES:
            for ds in CORE_STRATEGIES:
                tasks.append((case, ps, ds))

    logger.info(f"  共 {len(tasks)} 个任务，启动 {max_workers} 线程并发执行...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_run_single_strategy_combo, c, ps, ds, llm): (c["case_id"], ps, ds)
            for c, ps, ds in tasks
        }
        for future in as_completed(future_map):
            tag = future_map[future]
            try:
                run_result = future.result()
                all_runs.append(run_result)
            except Exception as e:
                cid, ps, ds = tag
                logger.error(f"    线程异常 [{cid}] {ps}x{ds}: {e}")
                all_runs.append(StrategyRunResult(cid, ps, ds, "", {}, (0.5, 0.5), 0, str(e)))

    # 汇总: 对所有案件的收益取均值，填入 3x3 → 映射回 5x5 收益矩阵
    tracker = NashEquilibriumTracker()
    payoff_sums: Dict[Tuple[str, str], List[Tuple[float, float]]] = {}

    for r in all_runs:
        key = (r.plaintiff_strategy, r.defendant_strategy)
        payoff_sums.setdefault(key, []).append(r.payoff)

    for (ps, ds), payoffs in payoff_sums.items():
        avg_p = sum(p[0] for p in payoffs) / len(payoffs)
        avg_d = sum(p[1] for p in payoffs) / len(payoffs)
        pi, di = STRATEGY_INDEX[ps], STRATEGY_INDEX[ds]
        tracker._payoff_p[pi][di] = round(avg_p, 4)
        tracker._payoff_d[pi][di] = round(avg_d, 4)
        tracker._counts[pi][di] = len(payoffs)

    # SPNE vs NE 分析
    efg = ExtensiveFormGame(tracker)
    analysis = efg.full_analysis()

    # 按案件分组的 SPNE/NE 分析
    per_case_analysis = {}
    for case in cases:
        cid = case["case_id"]
        case_tracker = NashEquilibriumTracker()
        for r in all_runs:
            if r.case_id == cid and r.error is None:
                pi, di = STRATEGY_INDEX[r.plaintiff_strategy], STRATEGY_INDEX[r.defendant_strategy]
                case_tracker._payoff_p[pi][di] = r.payoff[0]
                case_tracker._payoff_d[pi][di] = r.payoff[1]
                case_tracker._counts[pi][di] = 1
        case_efg = ExtensiveFormGame(case_tracker)
        try:
            case_analysis = case_efg.full_analysis()
            per_case_analysis[cid] = case_analysis.to_dict()
        except Exception as e:
            per_case_analysis[cid] = {"error": str(e)}

    result = {
        "experiment": "exp1_spne_vs_ne",
        "n_cases": len(cases),
        "n_strategies": len(CORE_STRATEGIES),
        "total_runs": len(all_runs),
        "errors": sum(1 for r in all_runs if r.error),
        "aggregate_analysis": analysis.to_dict(),
        "per_case_analysis": per_case_analysis,
        "payoff_matrix": {
            "plaintiff": [[tracker._payoff_p[i][j] for j in range(5)] for i in range(5)],
            "defendant": [[tracker._payoff_d[i][j] for j in range(5)] for i in range(5)],
        },
        "raw_runs": [
            {"case_id": r.case_id, "ps": r.plaintiff_strategy, "ds": r.defendant_strategy,
             "payoff": r.payoff, "elapsed_s": r.elapsed_s, "error": r.error}
            for r in all_runs
        ],
    }

    _save_json("prelim_exp1_spne_vs_ne.json", result)
    _plot_exp1(tracker, analysis)
    return result


def _plot_exp1(tracker: NashEquilibriumTracker, analysis):
    """生成实验1的收益矩阵热力图。"""
    payoff_p = np.array(tracker._payoff_p)
    labels = [ALL_STRATEGY_CN.get(s, s) for s in STRATEGY_NAMES]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("实验1：真实运行收益矩阵 (SPNE vs NE)", fontsize=14, fontweight="bold")

    for ax, data, title in [
        (ax1, np.array(tracker._payoff_p), "原告收益"),
        (ax2, np.array(tracker._payoff_d), "被告收益"),
    ]:
        im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=0.1, vmax=0.9)
        ax.set_title(title, fontsize=12)
        ax.set_xticks(range(5)); ax.set_yticks(range(5))
        ax.set_xticklabels(labels, fontsize=8, rotation=45)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel("被告策略"); ax.set_ylabel("原告策略")
        for i in range(5):
            for j in range(5):
                ax.text(j, i, f"{data[i, j]:.3f}", ha="center", va="center", fontsize=7)
        plt.colorbar(im, ax=ax, shrink=0.8)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(OUTPUT_DIR / "prelim_exp1_payoff.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("  [OK] 图: prelim_exp1_payoff.png")


# =====================================================================
# 实验2: 演化博弈动力学模拟（纯计算）
# =====================================================================

def run_exp2_evolution(tracker: NashEquilibriumTracker) -> Dict[str, Any]:
    """基于实验1的真实收益矩阵运行演化动力学。"""
    logger.info("=" * 60)
    logger.info("[实验2] 演化博弈动力学模拟")
    logger.info("=" * 60)

    evo = EvolutionaryDynamics(tracker)
    trajectory = evo.simulate_evolution(generations=100, dt=0.1)

    social_metrics = evo.compute_social_metrics(trajectory.final_distribution)

    result = {
        "experiment": "exp2_evolution",
        "trajectory": trajectory.to_dict(),
        "social_metrics": social_metrics,
    }
    _save_json("prelim_exp2_evolution.json", result)
    _plot_exp2(trajectory)
    return result


def _plot_exp2(trajectory):
    """绘制演化轨迹图。"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("实验2：复制者动态下的策略种群演化", fontsize=14, fontweight="bold")

    gens = [s.generation for s in trajectory.history]
    colors = ["#e74c3c", "#2ecc71", "#3498db", "#f39c12", "#9b59b6"]

    for i, strat in enumerate(STRATEGY_NAMES):
        values = [s.distribution.get(strat, 0) for s in trajectory.history]
        ax1.plot(gens, values, "-", color=colors[i], linewidth=2,
                 label=ALL_STRATEGY_CN.get(strat, strat))
    ax1.set_xlabel("演化代数"); ax1.set_ylabel("种群比例")
    ax1.set_title("策略分布演化轨迹"); ax1.legend(fontsize=9); ax1.grid(alpha=0.3)

    entropies = [s.shannon_entropy for s in trajectory.history]
    welfares = [s.social_welfare for s in trajectory.history]
    ax2.plot(gens, entropies, "b-", linewidth=2, label="Shannon熵")
    ax2r = ax2.twinx()
    ax2r.plot(gens, welfares, "r--", linewidth=2, label="社会福利")
    ax2.set_xlabel("演化代数"); ax2.set_ylabel("Shannon熵", color="b")
    ax2r.set_ylabel("社会福利", color="r")
    ax2.set_title("熵与福利变化"); ax2.grid(alpha=0.3)
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2r.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, fontsize=9)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(OUTPUT_DIR / "prelim_exp2_evolution.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("  [OK] 图: prelim_exp2_evolution.png")


# =====================================================================
# 实验3: NBS 调解对比
# =====================================================================

def run_exp3_bargaining(
    cases: List[Dict], llm: LLMClient, tracker: NashEquilibriumTracker,
) -> Dict[str, Any]:
    """NBS 增强 vs 基线调解对比。"""
    logger.info("=" * 60)
    logger.info("[实验3] NBS 调解对比")
    logger.info("=" * 60)

    nbs_engine = NashBargainingEngine(payoff_source=tracker, llm_client=llm)
    mediation_engine = MediationEngine(llm)
    mediation_cases = cases[:3]
    results = []

    for idx, case in enumerate(mediation_cases):
        cid = case.get("case_id", "?")
        cause = case.get("cause", "")
        logger.info(f"  调解案件: {cid} ({cause})")

        # (A) 基线调解
        t0 = time.time()
        try:
            base_sid = f"base_{cid}_{idx}"
            base_result = mediation_engine.run_full_mediation(base_sid, case)
            base_elapsed = round(time.time() - t0, 1)
            base_outcome = base_result.outcome if base_result else "error"
        except Exception as e:
            logger.warning(f"    基线调解失败: {e}")
            base_result = None
            base_outcome = "error"
            base_elapsed = round(time.time() - t0, 1)

        # (B) NBS 增强调解：先计算 NBS 参考点，注入到 case_info
        d_point = nbs_engine.compute_disagreement_point("compromising", "compromising")
        feasible_set = nbs_engine._default_feasible_set()
        nbs_solution = nbs_engine.compute_nbs(feasible_set, d_point)
        nbs_ref_text = nbs_engine.generate_nbs_reference_text(nbs_solution, case)

        enhanced_case = dict(case)
        existing_desc = enhanced_case.get("case_description", "")
        enhanced_case["case_description"] = f"{existing_desc}\n\n{nbs_ref_text}"

        t0 = time.time()
        try:
            nbs_sid = f"nbs_{cid}_{idx}"
            nbs_result = mediation_engine.run_full_mediation(nbs_sid, enhanced_case)
            nbs_elapsed = round(time.time() - t0, 1)
            nbs_outcome = nbs_result.outcome if nbs_result else "error"
        except Exception as e:
            logger.warning(f"    NBS调解失败: {e}")
            nbs_result = None
            nbs_outcome = "error"
            nbs_elapsed = round(time.time() - t0, 1)

        results.append({
            "case_id": cid,
            "cause": cause,
            "baseline": {
                "outcome": base_outcome,
                "elapsed_s": base_elapsed,
                "solution": base_result.final_solution[:300] if base_result else "",
            },
            "nbs_enhanced": {
                "outcome": nbs_outcome,
                "elapsed_s": nbs_elapsed,
                "solution": nbs_result.final_solution[:300] if nbs_result else "",
                "disagreement_point": {"plaintiff": d_point[0], "defendant": d_point[1]},
                "nbs": {"plaintiff": nbs_solution.nbs_plaintiff, "defendant": nbs_solution.nbs_defendant},
                "nash_product": nbs_solution.nash_product,
            },
        })
        logger.info(f"    基线={base_outcome}({base_elapsed}s) NBS={nbs_outcome}({nbs_elapsed}s)")

    out = {"experiment": "exp3_bargaining", "results": results}
    _save_json("prelim_exp3_bargaining.json", out)
    return out


# =====================================================================
# 实验4: 工程模块消融（并发）
# =====================================================================

@dataclass
class AblationRunResult:
    case_id: str
    config_name: str
    judgment_text: str
    jud_score: float
    law_count: int
    elapsed_s: float
    error: Optional[str] = None


def _run_ablation_config(
    case: Dict, config_name: str, llm: LLMClient,
) -> AblationRunResult:
    """运行单个消融配置。"""
    cid = case.get("case_id", "?")
    t0 = time.time()

    try:
        case_desc = case.get("case_description", "")
        claims = ", ".join(case.get("plaintiff_claims", []))

        if config_name == "baseline":
            # 直接用 LLM 生成判决（无增强）
            prompt = f"你是民事法官，基于以下案件直接判决：\n{case_desc[:2000]}\n诉求：{claims[:500]}\n请输出判决："
            judgment = llm.chat_completion([{"role": "user", "content": prompt}], temperature=0.1)

        elif config_name == "+P-RAG":
            from core.law_retriever import LawRetriever
            try:
                retriever = LawRetriever()
                prag = ProgressiveRAG(retriever, llm)
                prag.retrieve_opening(case_desc, claims)
                prag.retrieve_investigation(claims, "被告不同意原告诉求")
                laws = prag.get_accumulated_laws(top_k=5)
                law_text = "\n".join(f"- {l.get('content', '')[:100]}" for l in laws)
            except Exception:
                law_text = ""
            prompt = (
                f"你是民事法官，基于以下案件和检索到的法条判决：\n{case_desc[:2000]}\n"
                f"诉求：{claims[:500]}\n相关法条：\n{law_text}\n请输出判决："
            )
            judgment = llm.chat_completion([{"role": "user", "content": prompt}], temperature=0.1)

        elif config_name == "+DualMode":
            dm = DualModeReasoner(llm)
            dm_result = dm.dual_mode_judgment(case_desc[:2000], claims[:500], use_llm_eval=False)
            judgment = dm_result.get("recommended_output", "")

        elif config_name == "full":
            dm = DualModeReasoner(llm)
            dm_result = dm.dual_mode_judgment(case_desc[:2000], claims[:500], use_llm_eval=False)
            slow_judgment = dm_result.get("slow_judgment", "")

            mj = MultiJudgeEngine(llm)
            agg = mj.run(case_desc[:2000], claims[:500], slow_judgment[:1500], num_judges=3)
            judgment = agg.final_judgment

        else:
            judgment = ""

        elapsed = round(time.time() - t0, 1)
        score = score_judgment(llm, judgment)
        jud = round(score.get("reasoning_quality", 0) * 10, 2)
        import re
        law_count = len(re.findall(r'第[\d零一二三四五六七八九十百千]+条', judgment))
        logger.info(f"    [{cid}] {config_name}: JUD={jud}  laws={law_count}  {elapsed}s")
        return AblationRunResult(cid, config_name, judgment[:500], jud, law_count, elapsed)

    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        logger.error(f"    [{cid}] {config_name} FAIL: {e}")
        return AblationRunResult(cid, config_name, "", 0, 0, elapsed, str(e))


def run_exp4_ablation(
    cases: List[Dict], llm: LLMClient, max_workers: int = 4,
) -> Dict[str, Any]:
    """工程模块消融实验（并发）。"""
    logger.info("=" * 60)
    logger.info(f"[实验4] 工程模块消融（{len(cases[:3])}案件 x 4配置，并发={max_workers}）")
    logger.info("=" * 60)

    configs = ["baseline", "+P-RAG", "+DualMode", "full"]
    ablation_cases = cases[:3]
    tasks = [(case, cfg) for case in ablation_cases for cfg in configs]

    all_results: List[AblationRunResult] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_run_ablation_config, c, cfg, llm): (c["case_id"], cfg)
            for c, cfg in tasks
        }
        for future in as_completed(future_map):
            try:
                all_results.append(future.result())
            except Exception as e:
                tag = future_map[future]
                logger.error(f"    消融线程异常 {tag}: {e}")

    # 按配置汇总
    summary: Dict[str, Dict[str, Any]] = {}
    for cfg in configs:
        cfg_results = [r for r in all_results if r.config_name == cfg and r.error is None]
        if cfg_results:
            avg_jud = round(sum(r.jud_score for r in cfg_results) / len(cfg_results), 2)
            avg_laws = round(sum(r.law_count for r in cfg_results) / len(cfg_results), 1)
        else:
            avg_jud, avg_laws = 0, 0
        summary[cfg] = {"avg_jud": avg_jud, "avg_law_count": avg_laws, "n": len(cfg_results)}

    result = {
        "experiment": "exp4_ablation",
        "summary": summary,
        "raw": [
            {"case_id": r.case_id, "config": r.config_name, "jud": r.jud_score,
             "laws": r.law_count, "elapsed_s": r.elapsed_s, "error": r.error}
            for r in all_results
        ],
    }
    _save_json("prelim_exp4_ablation.json", result)
    _plot_exp4(summary)
    return result


def _plot_exp4(summary: Dict):
    """消融实验柱状图。"""
    configs = list(summary.keys())
    juds = [summary[c]["avg_jud"] for c in configs]
    laws = [summary[c]["avg_law_count"] for c in configs]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("实验4：工程模块消融", fontsize=14, fontweight="bold")
    x = np.arange(len(configs))
    colors = ["#bdc3c7", "#3498db", "#f39c12", "#2ecc71"]

    ax1.bar(x, juds, color=colors, alpha=0.85)
    ax1.set_xticks(x); ax1.set_xticklabels(configs, fontsize=10)
    ax1.set_ylabel("JUD Score"); ax1.set_title("判决质量"); ax1.grid(axis="y", alpha=0.3)
    for i, v in enumerate(juds):
        ax1.text(i, v + 0.1, f"{v:.1f}", ha="center", fontsize=9)

    ax2.bar(x, laws, color=colors, alpha=0.85)
    ax2.set_xticks(x); ax2.set_xticklabels(configs, fontsize=10)
    ax2.set_ylabel("法条引用数"); ax2.set_title("法条覆盖"); ax2.grid(axis="y", alpha=0.3)
    for i, v in enumerate(laws):
        ax2.text(i, v + 0.1, f"{v:.1f}", ha="center", fontsize=9)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(OUTPUT_DIR / "prelim_exp4_ablation.png", dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("  [OK] 图: prelim_exp4_ablation.png")


# =====================================================================
# 实验5: 博弈论评测指标汇总（纯计算）
# =====================================================================

def run_exp5_game_eval(
    exp1_result: Dict, exp2_result: Dict, exp3_result: Dict,
    tracker: NashEquilibriumTracker,
) -> Dict[str, Any]:
    """汇总前序实验数据，计算四项博弈论评测指标。"""
    logger.info("=" * 60)
    logger.info("[实验5] 博弈论评测指标汇总")
    logger.info("=" * 60)

    evaluator = GameTheoreticEvaluator(tracker)

    # 从实验1提取策略历史
    strategy_history = []
    for run in exp1_result.get("raw_runs", []):
        strategy_history.append({
            "plaintiff": run.get("ps", "compromising"),
            "defendant": run.get("ds", "compromising"),
        })

    # 从实验2提取演化分布
    traj = exp2_result.get("trajectory", {})
    converged_dist = traj.get("final_distribution", None)

    # 从实验3提取 NBS 偏离
    nbs_results = exp3_result.get("results", [])
    actual_u: Optional[Tuple[float, float]] = None
    nbs_u: Optional[Tuple[float, float]] = None
    if nbs_results:
        first = nbs_results[0]
        nbs_data = first.get("nbs_enhanced", {})
        if nbs_data.get("nbs"):
            nbs_u = (nbs_data["nbs"]["plaintiff"], nbs_data["nbs"]["defendant"])
            # 实际收益用 disagreement point 近似（调解结果的精确收益需要进一步解析）
            dp = nbs_data.get("disagreement_point", {})
            actual_u = (dp.get("plaintiff", 0.5), dp.get("defendant", 0.5))

    scores = evaluator.evaluate(
        strategy_history=strategy_history if strategy_history else None,
        converged_distribution=converged_dist,
        actual_mediation_utility=actual_u,
        nbs_utility=nbs_u,
    )

    report = evaluator.generate_report(scores)
    logger.info("\n" + report)

    result = {
        "experiment": "exp5_game_eval",
        "scores": scores.to_dict(),
        "report": report,
    }
    _save_json("prelim_exp5_game_eval.json", result)
    return result


# =====================================================================
# 综合报告
# =====================================================================

def generate_summary_report(all_results: Dict[str, Any]) -> Dict[str, Any]:
    """生成最终综合摘要。"""
    logger.info("=" * 60)
    logger.info("生成综合报告")
    logger.info("=" * 60)

    smoke = all_results.get("smoke", {})
    exp1 = all_results.get("exp1", {})
    exp2 = all_results.get("exp2", {})
    exp3 = all_results.get("exp3", {})
    exp4 = all_results.get("exp4", {})
    exp5 = all_results.get("exp5", {})

    summary = {
        "title": "LexGentium 初步实验验证报告",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sections": {
            "smoke_test": {
                "status": "pass" if all(
                    r.get("status") == "ok" for r in smoke.get("results", [])
                ) else "partial",
                "cases_tested": len(smoke.get("results", [])),
            },
            "exp1_spne_vs_ne": {
                "total_runs": exp1.get("total_runs", 0),
                "errors": exp1.get("errors", 0),
                "spne_ne_match": exp1.get("aggregate_analysis", {}).get("spne_ne_match"),
            },
            "exp2_evolution": {
                "converged": exp2.get("trajectory", {}).get("converged"),
                "ess": exp2.get("trajectory", {}).get("ess_analysis", {}).get("ess_strategy"),
                "polarization": exp2.get("trajectory", {}).get("polarization_index"),
            },
            "exp3_bargaining": {
                "cases": len(exp3.get("results", [])),
                "results": [
                    {"case": r.get("case_id"), "base": r.get("baseline", {}).get("outcome"),
                     "nbs": r.get("nbs_enhanced", {}).get("outcome")}
                    for r in exp3.get("results", [])
                ],
            },
            "exp4_ablation": exp4.get("summary", {}),
            "exp5_game_eval": exp5.get("scores", {}),
        },
    }

    _save_json("prelim_summary_report.json", summary)
    logger.info("  [OK] prelim_summary_report.json")
    return summary


# =====================================================================
# 工具函数
# =====================================================================

def _save_json(filename: str, data: Any):
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"  [OK] 保存: {path.name}")


# =====================================================================
# 主入口
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="LexGentium 初步实验验证")
    parser.add_argument("--cases", type=int, default=5, help="选取案件数量（默认5）")
    parser.add_argument("--workers", type=int, default=4, help="并发线程数（默认4）")
    parser.add_argument("--skip-smoke", action="store_true", help="跳过冒烟测试")
    parser.add_argument("--only", type=str, default=None,
                        help="仅运行指定实验（smoke/exp1/exp2/exp3/exp4/exp5）")
    args = parser.parse_args()

    t_global = time.time()
    logger.info("=" * 60)
    logger.info("LexGentium 初步实验验证 v1.0")
    logger.info(f"案件数={args.cases}  并发线程={args.workers}")
    logger.info("=" * 60)

    llm = create_llm_client()
    cases = load_test_cases(args.cases)
    all_results: Dict[str, Any] = {}

    # 预实验0
    if args.only in (None, "smoke") and not args.skip_smoke:
        all_results["smoke"] = run_smoke_test(cases, llm)

    # 实验1: SPNE vs NE
    if args.only in (None, "exp1"):
        all_results["exp1"] = run_exp1_spne_vs_ne(cases, llm, max_workers=args.workers)

    # 从实验1提取收益矩阵给后续实验用
    tracker = NashEquilibriumTracker()
    if "exp1" in all_results:
        pm = all_results["exp1"].get("payoff_matrix", {})
        if pm.get("plaintiff"):
            tracker._payoff_p = pm["plaintiff"]
            tracker._payoff_d = pm["defendant"]

    # 实验2: 演化动力学（纯计算）
    if args.only in (None, "exp2"):
        all_results["exp2"] = run_exp2_evolution(tracker)

    # 实验3: NBS 调解对比
    if args.only in (None, "exp3"):
        all_results["exp3"] = run_exp3_bargaining(cases, llm, tracker)

    # 实验4: 工程消融（并发）
    if args.only in (None, "exp4"):
        all_results["exp4"] = run_exp4_ablation(cases, llm, max_workers=args.workers)

    # 实验5: 博弈论指标汇总
    if args.only in (None, "exp5"):
        all_results["exp5"] = run_exp5_game_eval(
            all_results.get("exp1", {}),
            all_results.get("exp2", {}),
            all_results.get("exp3", {}),
            tracker,
        )

    # 综合报告
    if args.only is None:
        generate_summary_report(all_results)

    elapsed = time.time() - t_global
    logger.info(f"\n全部完成！总耗时 {elapsed:.0f}s ({elapsed/60:.1f}min)")
    logger.info(f"结果目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
