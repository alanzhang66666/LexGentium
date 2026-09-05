# -*- coding: utf-8 -*-
"""
根据用户给定代码生成博弈树配图（PDF + PNG）。

运行（在 mock_court_system 根目录）：
  python scripts/gen_game_tree_from_snippet.py
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

    out_dir = project_root / "docs" / "figures" / "lexgentium_application"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 设置全局字体，确保中文正常显示（Windows常用SimHei，Mac常用Arial Unicode MS）
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis("off")  # 隐藏坐标轴

    # 节点坐标定义
    root_x, root_y = 0.5, 0.9
    level1_y = 0.5
    level2_y = 0.1
    x_offsets = [-0.35, -0.15, 0.05, 0.25, 0.45]
    strategies = ["竞争型", "合作型", "妥协型", "回避型", "迁就型"]

    # 绘制非均衡路径（浅灰色）
    for i, x_off in enumerate(x_offsets):
        l1_x = root_x + x_off
        # 根节点到第一层的连线
        ax.plot([root_x, l1_x], [root_y, level1_y], color="lightgray", zorder=1)

        # 第一层到第二层的次级连线（模拟多个响应）
        for j in [-0.04, 0.0, 0.04]:
            ax.plot([l1_x, l1_x + j], [level1_y, level2_y], color="lightgray", linewidth=1, zorder=1)

    # 绘制 SPNE 均衡路径（红色加粗）
    spne_idx = 1  # 假设“合作型”是均衡路径
    spne_l1_x = root_x + x_offsets[spne_idx]
    spne_l2_x = spne_l1_x + 0.0
    ax.plot([root_x, spne_l1_x], [root_y, level1_y], color="#d62728", linewidth=3, zorder=2)
    ax.plot([spne_l1_x, spne_l2_x], [level1_y, level2_y], color="#d62728", linewidth=3, zorder=2)

    # 绘制节点
    # 根节点（原告）
    ax.scatter(root_x, root_y, s=300, color="#1f77b4", zorder=3)
    ax.text(
        root_x,
        root_y + 0.05,
        "原告 (CD阶段)\n根节点",
        ha="center",
        va="bottom",
        fontsize=12,
        color="#1f77b4",
        fontweight="bold",
    )

    # 第一层节点（被告）
    for i, x_off in enumerate(x_offsets):
        l1_x = root_x + x_off
        color = "#d62728" if i == spne_idx else "#ff7f0e"
        ax.scatter(l1_x, level1_y, s=200, marker="s", color=color, zorder=3)
        ax.text(l1_x, level1_y - 0.05, "被告\n(DD阶段)", ha="center", va="top", fontsize=10)

        # 在连线上方标注策略
        mid_x, mid_y = (root_x + l1_x) / 2, (root_y + level1_y) / 2
        ax.text(
            mid_x - 0.02,
            mid_y + 0.02,
            strategies[i],
            ha="right",
            fontsize=10,
            color="#d62728" if i == spne_idx else "gray",
            fontweight="bold" if i == spne_idx else "normal",
        )

    # 终端节点
    ax.scatter(spne_l2_x, level2_y, s=200, marker="D", color="#2ca02c", zorder=3)
    ax.text(
        spne_l2_x,
        level2_y - 0.05,
        "终端收益\n(CI裁判)",
        ha="center",
        va="top",
        fontsize=10,
        color="#2ca02c",
        fontweight="bold",
    )

    # SPNE 标注说明
    ax.text(root_x, 0.0, "—— SPNE均衡路径 (反向归纳求解) ——", ha="center", color="#d62728", fontsize=12, fontweight="bold")

    plt.tight_layout()

    pdf_path = out_dir / "game_tree.pdf"
    png_path = out_dir / "game_tree.png"
    svg_path = out_dir / "game_tree.svg"
    plt.savefig(pdf_path, format="pdf", dpi=300)
    plt.savefig(png_path, format="png", dpi=300)
    plt.savefig(svg_path, format="svg")
    plt.close()

    print("[OK]", pdf_path)
    print("[OK]", png_path)
    print("[OK]", svg_path)


if __name__ == "__main__":
    main()

