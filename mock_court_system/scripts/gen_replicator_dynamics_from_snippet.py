# -*- coding: utf-8 -*-
"""
根据用户给定代码生成复制者动态配图（PDF + PNG）。

运行（在 mock_court_system 根目录）：
  python scripts/gen_replicator_dynamics_from_snippet.py
"""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)

    out_dir = project_root / "docs" / "figures" / "legalflow_application"
    out_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(8, 6))

    # 模拟演化代数
    generations = np.linspace(0, 50, 200)

    # 模拟各策略的种群比例变化 (使用 Logistic 函数及其变体模拟)
    # 合作型 (最终收敛为 ESS)
    coop_prop = 0.2 + 0.75 * (1 / (1 + np.exp(-0.15 * (generations - 15))))
    # 其他策略衰减
    comp_prop = 0.3 * np.exp(-0.08 * generations)
    comprm_prop = 0.25 * np.exp(-0.05 * generations)
    avoid_prop = 0.15 * np.exp(-0.06 * generations)
    accom_prop = 0.1 * np.exp(-0.04 * generations)

    # 归一化处理以保证总和接近1（为绘图平滑进行轻微调整）
    total = coop_prop + comp_prop + comprm_prop + avoid_prop + accom_prop
    coop_prop /= total
    comp_prop /= total
    comprm_prop /= total
    avoid_prop /= total
    accom_prop /= total

    # 绘制折线
    ax.plot(generations, coop_prop, label="合作型 (ESS)", color="#2ca02c", linewidth=3.5, linestyle="-")
    ax.plot(generations, comprm_prop, label="妥协型", color="#ff7f0e", linewidth=2.5, linestyle="--")
    ax.plot(generations, comp_prop, label="竞争型", color="#d62728", linewidth=2.5, linestyle="-.")
    ax.plot(generations, avoid_prop, label="回避型", color="#7f7f7f", linewidth=2.5, linestyle=":")
    ax.plot(generations, accom_prop, label="迁就型", color="#9467bd", linewidth=2, linestyle="-")

    # 图表美化
    ax.set_xlim(0, 50)
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("演化代数 (Generations)", fontsize=12, fontweight="bold")
    ax.set_ylabel("种群比例 (Population Proportion)", fontsize=12, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.6, color="lightgray")

    # 添加 ESS 收敛标注
    ax.annotate(
        "ESS\n收敛",
        xy=(45, coop_prop[180]),
        xytext=(35, 0.75),
        arrowprops=dict(facecolor="black", shrink=0.05, width=1.5, headwidth=8),
        fontsize=12,
        fontweight="bold",
        ha="center",
        va="center",
    )

    # 图例设置
    ax.legend(loc="center right", fontsize=11, frameon=True, shadow=True)

    plt.tight_layout()

    pdf_path = out_dir / "replicator_dynamics.pdf"
    png_path = out_dir / "replicator_dynamics.png"
    svg_path = out_dir / "replicator_dynamics.svg"
    plt.savefig(pdf_path, format="pdf", dpi=300)
    plt.savefig(png_path, format="png", dpi=300)
    plt.savefig(svg_path, format="svg")
    plt.close()

    print("[OK]", pdf_path)
    print("[OK]", png_path)
    print("[OK]", svg_path)


if __name__ == "__main__":
    main()

