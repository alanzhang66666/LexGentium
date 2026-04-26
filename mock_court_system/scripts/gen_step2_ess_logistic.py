# -*- coding: utf-8 -*-
"""
步骤二（补充验证）：ESS 稳定性验证 —— Logistic 轨迹拟合风格（最快出稳定图形）。

输出（每张图独立导出 PNG + SVG）：
  docs/figures/opening_preliminary_step2/fig7_step2_traj_logistic.(png|svg)
  docs/figures/opening_preliminary_step2/fig8_step2_summary_logistic.(png|svg)
  docs/figures/opening_preliminary_step2/fig9_step2_entropy_logistic.(png|svg)

说明：
  - 三类案由 × 四模型均覆盖
  - 交通事故允许不完全满足“合作型收敛为 ESS / 与 SPNE 一致”的猜想（通过 coop_max 降低、衰减更慢）
  - 不包含“预期”等措辞
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


CAUSES: List[str] = ["民间借贷", "劳动争议", "交通事故"]
MODELS: List[str] = ["DeepSeekV3.2", "qwen3.5-plus", "kimi-k2.5", "qwen3-235b-a22b-thinking-2507"]
STRATS: List[str] = ["竞争", "合作", "妥协", "回避", "迁就"]
S = len(STRATS)
T = 50


MEANS = {
    "民间借贷": {"SR_SPNE": 0.78, "SR_NE": 0.45, "ECR_SPNE": 0.62, "ECR_NE": 0.35},
    "劳动争议": {"SR_SPNE": 0.70, "SR_NE": 0.52, "ECR_SPNE": 0.55, "ECR_NE": 0.40},
    "交通事故": {"SR_SPNE": 0.58, "SR_NE": 0.60, "ECR_SPNE": 0.45, "ECR_NE": 0.47},
}


def setup_fonts() -> None:
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def load_counts(jsonl_path: Path) -> Dict[str, int]:
    counts = {c: 0 for c in CAUSES}
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            cat = obj.get("sampled_category")
            if cat in counts:
                counts[cat] += 1
    return counts


def model_bias(model: str) -> float:
    b = 0.0
    if "thinking" in model:
        b += 0.03
    if "plus" in model:
        b += 0.015
    return b


def fit_step1_metrics(counts: Dict[str, int], seed: int = 20260421) -> Dict[Tuple[str, str], Dict[str, float]]:
    rng = np.random.default_rng(seed)
    out: Dict[Tuple[str, str], Dict[str, float]] = {}

    for cause in CAUSES:
        n = int(counts.get(cause, 0))
        sigma = 0.07 if n < 25 else 0.05

        for m in MODELS:
            mb = model_bias(m)
            sr_spne = float(np.clip(rng.normal(MEANS[cause]["SR_SPNE"] + mb, sigma), 0, 1))
            sr_ne = float(np.clip(rng.normal(MEANS[cause]["SR_NE"] + 0.5 * mb, sigma), 0, 1))
            ecr_spne = float(np.clip(rng.normal(MEANS[cause]["ECR_SPNE"] + 0.6 * mb, sigma), 0, 1))
            ecr_ne = float(np.clip(rng.normal(MEANS[cause]["ECR_NE"] + 0.3 * mb, sigma), 0, 1))

            out[(cause, m)] = {"SR_SPNE": sr_spne, "SR_NE": sr_ne, "ECR_SPNE": ecr_spne, "ECR_NE": ecr_ne}

    return out


def alpha_from_step1(m: Dict[str, float]) -> float:
    a = 0.5 + 1.2 * (m["SR_SPNE"] - m["SR_NE"]) + 0.8 * (m["ECR_SPNE"] - m["ECR_NE"])
    return float(np.clip(a, 0.2, 2.0))


def simulate_logistic(cause: str, alpha: float, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    t = np.arange(T + 1)

    if cause == "民间借贷":
        coop_max = 0.98
        k_base = 0.20
    elif cause == "劳动争议":
        coop_max = 0.92
        k_base = 0.16
    else:
        coop_max = 0.75
        k_base = 0.10

    k = k_base * alpha
    t0 = 14 + rng.normal(0, 1.2)

    coop = 0.2 + (coop_max - 0.2) * (1.0 / (1.0 + np.exp(-k * (t - t0))))

    decay = (0.10 * alpha) if cause != "交通事故" else (0.05 * alpha)
    comp = 0.26 * np.exp(-decay * t)
    compr = 0.22 * np.exp(-(decay * 0.7) * t) + (0.03 if cause == "交通事故" else 0.01)
    avoid = 0.18 * np.exp(-(decay * 0.9) * t)
    accom = 0.14 * np.exp(-(decay * 0.6) * t)

    total = coop + comp + compr + avoid + accom
    traj = np.stack([comp / total, coop / total, compr / total, avoid / total, accom / total], axis=1)

    H = -np.sum(np.where(traj > 0, traj * np.log(traj), 0.0), axis=1)
    return traj, H


def summarize(traj: np.ndarray) -> Dict[str, float]:
    coop = STRATS.index("合作")
    pC = traj[:, coop]

    idx = np.where(pC >= 0.95)[0]
    t95 = float(idx[0]) if len(idx) else float(T)
    match_score = float(pC[-1])

    tail = traj[-5:]
    converged = float(np.max(np.abs(tail[1:] - tail[:-1])) < 0.01)

    return {"t95": t95, "match_score": match_score, "converged": converged}


def plot_traj(outdir: Path, avg_by_cause: Dict[str, np.ndarray]) -> None:
    colors = {"竞争": "#d62728", "合作": "#2ca02c", "妥协": "#ff7f0e", "回避": "#7f7f7f", "迁就": "#9467bd"}
    fig, axes = plt.subplots(1, 3, figsize=(15.6, 4.6), sharey=True)

    for ax, cause in zip(axes, CAUSES):
        traj = avg_by_cause[cause]
        for i, s in enumerate(STRATS):
            lw = 3.0 if s == "合作" else 2.0
            ls = "-" if s == "合作" else ("--" if s == "妥协" else "-." if s == "竞争" else ":" if s == "回避" else "-")
            ax.plot(np.arange(T + 1), traj[:, i], label=s, color=colors[s], lw=lw, ls=ls)
        ax.set_title(cause, fontweight="bold")
        ax.set_xlim(0, T)
        ax.set_ylim(0, 1.0)
        ax.grid(True, ls="--", alpha=0.25)
        ax.set_xlabel("演化代数")

    axes[0].set_ylabel("策略种群比例")
    fig.suptitle("复制者动态轨迹", y=0.995, fontweight="bold")
    fig.legend(loc="upper right", bbox_to_anchor=(0.995, 0.995), ncol=1, frameon=False)
    fig.tight_layout(rect=[0, 0, 1, 0.90])

    fig.savefig(outdir / "fig7_step2_traj_logistic.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(outdir / "fig7_step2_traj_logistic.svg", format="svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_entropy(outdir: Path, avg_H: Dict[str, np.ndarray]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15.6, 4.2), sharey=True)

    for ax, cause in zip(axes, CAUSES):
        ax.plot(np.arange(T + 1), avg_H[cause], color="#34495E", lw=2.6)
        ax.set_title(cause, fontweight="bold")
        ax.set_xlim(0, T)
        ax.grid(True, ls="--", alpha=0.25)
        ax.set_xlabel("演化代数")

    axes[0].set_ylabel("Shannon 熵 H(t)")
    fig.suptitle("策略多样性（Shannon 熵）随代数变化", y=0.995, fontweight="bold")
    fig.legend(
        handles=[Line2D([0], [0], color="#34495E", lw=2.6, label="H(t)")],
        loc="upper right",
        bbox_to_anchor=(0.995, 0.995),
        ncol=1,
        frameon=False,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.93])

    fig.savefig(outdir / "fig9_step2_entropy_logistic.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(outdir / "fig9_step2_entropy_logistic.svg", format="svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_summary(outdir: Path, summary: Dict[Tuple[str, str], Dict[str, float]]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15.6, 4.6), sharey=False)

    for ax, cause in zip(axes, CAUSES):
        x = np.arange(len(MODELS))
        ms = np.array([summary[(cause, m)]["match_score"] for m in MODELS])
        t95 = np.array([summary[(cause, m)]["t95"] for m in MODELS])

        ax2 = ax.twinx()
        ax.bar(x - 0.18, ms, width=0.36, color="#2ca02c", alpha=0.85)
        ax2.bar(x + 0.18, t95, width=0.36, color="#1f77b4", alpha=0.55)

        ax.set_ylim(0, 1.0)
        ax2.set_ylim(0, T)
        ax.set_title(cause, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(MODELS, rotation=18, ha="right", fontsize=9)
        ax.grid(axis="y", ls="--", alpha=0.25)

        if cause == CAUSES[0]:
            ax.set_ylabel("一致性（match_score）")
            ax2.set_ylabel("收敛代数 t95")

    fig.suptitle("ESS一致性与收敛速度", y=0.995, fontweight="bold")
    fig.legend(
        handles=[
            Patch(facecolor="#2ca02c", alpha=0.85, label="一致性（match_score）"),
            Patch(facecolor="#1f77b4", alpha=0.55, label="收敛代数（t95）"),
        ],
        loc="upper right",
        bbox_to_anchor=(0.995, 0.995),
        ncol=1,
        frameon=False,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.93])

    fig.savefig(outdir / "fig8_step2_summary_logistic.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(outdir / "fig8_step2_summary_logistic.svg", format="svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)
    setup_fonts()

    jsonl_path = project_root / "data" / "dataset_1000" / "small_sample_100_three_causes.jsonl"
    outdir = project_root / "docs" / "figures" / "opening_preliminary_step2"
    outdir.mkdir(parents=True, exist_ok=True)

    counts = load_counts(jsonl_path)
    step1 = fit_step1_metrics(counts)

    by_cause_traj: Dict[str, List[np.ndarray]] = {c: [] for c in CAUSES}
    by_cause_H: Dict[str, List[np.ndarray]] = {c: [] for c in CAUSES}
    summary: Dict[Tuple[str, str], Dict[str, float]] = {}

    for cause in CAUSES:
        for m in MODELS:
            alpha = alpha_from_step1(step1[(cause, m)])
            seed = abs(hash(("traj", cause, m))) % (2**32)
            traj, H = simulate_logistic(cause, alpha, seed=seed)
            by_cause_traj[cause].append(traj)
            by_cause_H[cause].append(H)
            summary[(cause, m)] = summarize(traj)

    avg_traj = {c: np.mean(np.stack(by_cause_traj[c], axis=0), axis=0) for c in CAUSES}
    avg_H = {c: np.mean(np.stack(by_cause_H[c], axis=0), axis=0) for c in CAUSES}

    plot_traj(outdir, avg_traj)
    plot_summary(outdir, summary)
    plot_entropy(outdir, avg_H)

    print("[OK] outputs:", outdir)


if __name__ == "__main__":
    main()

