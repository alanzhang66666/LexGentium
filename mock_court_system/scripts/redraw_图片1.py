# -*- coding: utf-8 -*-
"""
重绘 docs/figures/图片1.png（保留全部信息元素，提升清晰度；枝干可更紧凑）。

输出：
  - docs/figures/图片1.png  (高 DPI)
  - docs/figures/图片1.svg  (矢量，PPT 推荐)

运行（在 mock_court_system 根目录）：
  python scripts/redraw_图片1.py
"""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)

    out_dir = project_root / "docs" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    def render(*, variant: str) -> None:
        """
        variant:
          - normal: 原尺寸
          - narrow: 横向收紧（更适合 PPT 一栏/窄版）
          - narrow2: 更进一步横向收紧（更适合左右并排/更窄版）
        """
        if variant not in {"normal", "narrow", "narrow2"}:
            raise ValueError(f"unknown variant: {variant}")

        # 画布：窄版减少宽度，并配合更紧凑的 x_offsets
        if variant == "normal":
            fig, ax = plt.subplots(figsize=(12.8, 6.2))
            x_offsets = np.array([-0.36, -0.18, 0.0, 0.18, 0.36])
            root_x = 0.52
            formula_x, formula_y = 0.83, 0.64
            suffix = ""
        elif variant == "narrow":
            fig, ax = plt.subplots(figsize=(10.2, 6.2))
            x_offsets = np.array([-0.30, -0.15, 0.0, 0.15, 0.30])
            root_x = 0.50
            formula_x, formula_y = 0.80, 0.66
            suffix = "_窄版"
        else:  # narrow2
            fig, ax = plt.subplots(figsize=(8.9, 6.2))
            x_offsets = np.array([-0.26, -0.13, 0.0, 0.13, 0.26])
            root_x = 0.50
            # 公式框更靠右上，给右侧分支留空间
            formula_x, formula_y = 0.79, 0.70
            suffix = "_更窄版"

        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

        # 坐标（缩短枝干：level1 / level2 上移）
        root_y = 0.88
        level1_y = 0.56
        level2_y = 0.26
        leaf_y = 0.16

        strategies = ["竞争型", "合作型", "妥协型", "回避型", "迁就型"]

        # 颜色/样式（与原图一致的语义）
        col_spne = "#C0392B"
        col_off = "#D0D3D4"
        col_root = "#1F77B4"
        col_dd = "#E67E22"
        col_term = "#27AE60"
        col_text_g = "#7B7D7D"

        spne_idx = 1  # 合作型
        spne_l1_x = float(root_x + x_offsets[spne_idx])

        # 非均衡枝干（浅灰）
        for i, x_off in enumerate(x_offsets):
            l1_x = float(root_x + x_off)
            ax.plot([root_x, l1_x], [root_y, level1_y], color=col_off, lw=1.25, zorder=1)

            # 被告响应（每个被告节点下方三条支线 + 端点）
            # 窄版情况下，子分支也略收紧，减少横向占用
            j_span = 0.035 if variant == "normal" else (0.032 if variant == "narrow" else 0.028)
            for j in [-j_span, 0.0, j_span]:
                ax.plot([l1_x, l1_x + j], [level1_y, level2_y], color=col_off, lw=1.05, zorder=1)
                ax.plot(l1_x + j, leaf_y, marker="D", markersize=4.6, color=col_off, zorder=1)

            # 策略标签放在线上方
            mid_x = (root_x + l1_x) / 2
            mid_y = (root_y + level1_y) / 2
            ax.text(
                mid_x,
                mid_y + 0.035,
                strategies[i],
                ha="center",
                va="bottom",
                fontsize=10.2,
                color=col_spne if i == spne_idx else col_text_g,
                fontweight="bold" if i == spne_idx else "normal",
            )

        # SPNE 均衡路径（红色加粗）
        ax.plot([root_x, spne_l1_x], [root_y, level1_y], color=col_spne, lw=3.2, zorder=3)
        ax.plot([spne_l1_x, spne_l1_x], [level1_y, level2_y], color=col_spne, lw=3.2, zorder=3)

        # 根节点（原告）
        ax.scatter([root_x], [root_y], s=220, color=col_root, zorder=5)
        ax.text(
            root_x,
            root_y + 0.06,
            "根节点\n原告 (CD阶段)",
            ha="center",
            va="bottom",
            fontsize=11.5,
            fontweight="bold",
            color=col_root,
        )

        # 第一层节点（被告）
        for i, x_off in enumerate(x_offsets):
            l1_x = float(root_x + x_off)
            node_color = col_spne if i == spne_idx else col_dd
            ax.scatter([l1_x], [level1_y], s=130, marker="s", color=node_color, zorder=5)

        # 将“被告(DD阶段)”统一移到空白区域，避免在每个节点下方重复遮挡
        ax.text(
            0.10 if variant == "normal" else (0.09 if variant == "narrow" else 0.085),
            0.48,
            "被告（DD阶段）",
            ha="left",
            va="center",
            fontsize=11.0 if variant == "normal" else (10.6 if variant == "narrow" else 10.2),
            fontweight="bold",
            color="#2C3E50",
        )

        # 终端节点（CI）— 仅标注 SPNE 终端，与原图一致
        ax.scatter([spne_l1_x], [level2_y], s=120, marker="D", color=col_term, zorder=6)
        ax.text(
            spne_l1_x,
            level2_y - 0.06,
            "终端收益\n(CI裁判)",
            ha="center",
            va="top",
            fontsize=9.2,
            color=col_term,
            fontweight="bold",
        )

        # 反向归纳公式标注框（右侧）
        ax.text(
            formula_x,
            formula_y,
            "反向归纳：\n$s_D^*(s_P)=\\arg\\max_{s_D} u_D(s_P,s_D)$",
            ha="left",
            va="center",
            fontsize=10.0,
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#BFC9CA", lw=1.0),
            color="#2C3E50",
        )

        # 图例（左上）
        legend_elements = [
            Line2D([0], [0], color=col_spne, lw=3.0, label="SPNE  均衡路径"),
            Line2D([0], [0], color=col_off, lw=1.6, label="非均衡分支"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor=col_root, markersize=8, label="原告决策节点"),
            Line2D([0], [0], marker="s", color="w", markerfacecolor=col_dd, markersize=8, label="被告决策点"),
            Line2D([0], [0], marker="D", color="w", markerfacecolor=col_term, markersize=7, label="终端（CI）"),
        ]
        ax.legend(handles=legend_elements, loc="upper left", fontsize=9.0, frameon=True, fancybox=True, framealpha=0.95)

        # 底部红色说明（保留原图信息）
        ax.text(
            root_x,
            0.055,
            "原告选择合作型 → 被告选择合作型 → CI裁判 → 终端收益最优",
            ha="center",
            va="center",
            fontsize=10.4,
            fontweight="bold",
            color=col_spne,
        )
        ax.plot([root_x - 0.15, root_x + 0.15], [0.075, 0.075], color=col_spne, lw=1.2, alpha=0.6)

        fig.tight_layout()

        png_path = out_dir / f"图片1{suffix}.png"
        svg_path = out_dir / f"图片1{suffix}.svg"
        fig.savefig(png_path, dpi=600, facecolor="white", bbox_inches="tight", pad_inches=0.06)
        fig.savefig(svg_path, format="svg", facecolor="white", bbox_inches="tight", pad_inches=0.06)
        plt.close(fig)

        print("[OK]", png_path)
        print("[OK]", svg_path)

    render(variant="normal")
    render(variant="narrow")
    render(variant="narrow2")


if __name__ == "__main__":
    main()

