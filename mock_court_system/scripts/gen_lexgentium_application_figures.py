# -*- coding: utf-8 -*-
"""
LexGentium 申请书配图（北自然基金版）：图1–图5
输出目录：docs/figures/lexgentium_application/
运行：在 mock_court_system 根目录执行
  python scripts/gen_lexgentium_application_figures.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D

OUT = PROJECT_ROOT / "docs" / "figures" / "lexgentium_application"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"],
        "mathtext.fontset": "stix",
        "axes.unicode_minus": False,
        "font.size": 9,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.12,
    }
)

C = {
    "blue": "#2980B9",
    "lightblue": "#AED6F1",
    "red": "#C0392B",
    "orange": "#E67E22",
    "green": "#27AE60",
    "gray": "#7F8C8D",
    "lightgray": "#BDC3C7",
    "palegray": "#ECF0F1",
    "dark": "#2C3E50",
    "white": "#FFFFFF",
    "pipe": "#1F618D",
}


def _arrow(ax, x1, y1, x2, y2, color=C["dark"], lw=1.2, ls="-", style="-|>"):
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(arrowstyle=style, color=color, lw=lw, ls=ls, shrinkA=0, shrinkB=0),
    )


def _darrow(ax, x1, y1, x2, y2, color=C["gray"], lw=0.9):
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(arrowstyle="<->", color=color, lw=lw, ls="--"),
    )


def fig1_system_architecture():
    """图1 LexGentium 系统架构（CD→DD→CI 管道 + 引擎层 + 评测）"""
    fig, ax = plt.subplots(figsize=(10.5, 11))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12.2)
    ax.axis("off")

    ax.text(5, 11.75, "LexGentium 系统架构", ha="center", fontsize=14, fontweight="bold", color=C["dark"])

    def rbox(xy, w, h, text, ec, fc, lw=1.2, fs=8.5, bold=False):
        x, y = xy
        p = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.08,rounding_size=0.12",
            facecolor=fc,
            edgecolor=ec,
            linewidth=lw,
        )
        ax.add_patch(p)
        ax.text(
            x + w / 2,
            y + h / 2,
            text,
            ha="center",
            va="center",
            fontsize=fs,
            fontweight="bold" if bold else "normal",
            color=C["dark"],
            linespacing=1.35,
        )

    # 数据输入
    rbox(
        (0.55, 9.85),
        2.35,
        1.55,
        "数据输入\n案件事实\n\nLexGentium-1K\n(1000条/29案由)\nClaimGen-CN\n→ 三场景重构",
        C["blue"],
        C["lightblue"],
        fs=8,
    )
    _arrow(ax, 2.95, 10.6, 3.35, 10.6)

    # 多智能体管道外框
    pipe = FancyBboxPatch(
        (3.25, 7.05),
        6.2,
        3.65,
        boxstyle="round,pad=0.06,rounding_size=0.1",
        facecolor="#EBF5FB",
        edgecolor=C["pipe"],
        linewidth=2.2,
    )
    ax.add_patch(pipe)
    ax.text(6.35, 10.52, "多智能体协同管道 (CD→DD→CI)", ha="center", fontsize=10, fontweight="bold", color=C["pipe"])

    # 三主智能体
    y_ag = 9.35
    w_a, h_a = 1.75, 0.72
    rbox((3.45, y_ag), w_a, h_a, "CDAgent\n起诉律师", C["blue"], "#D6EAF8", fs=8)
    rbox((5.15, y_ag), w_a, h_a, "DDAgent\n答辩律师", C["blue"], "#D6EAF8", fs=8)
    rbox((6.85, y_ag), w_a, h_a, "CIAgent\n审判长", C["blue"], "#D6EAF8", fs=8)
    _arrow(ax, 5.2, y_ag + h_a / 2, 5.15, y_ag + h_a / 2)
    _arrow(ax, 6.9, y_ag + h_a / 2, 6.85, y_ag + h_a / 2)
    _arrow(ax, 3.35, 10.15, 4.3, y_ag + h_a)

    # SimAgent
    y_s = 8.05
    rbox(
        (3.45, y_s),
        3.45,
        0.78,
        "SimAgent  原告模拟\n(per-party)",
        C["blue"],
        "#A9CCE3",
        fs=8,
    )
    rbox(
        (6.95, y_s),
        2.35,
        0.78,
        "SimAgent  被告模拟\n(per-party)",
        C["blue"],
        "#A9CCE3",
        fs=8,
    )
    _darrow(ax, 4.3, y_ag, 4.3, y_s + 0.78)
    _darrow(ax, 6.05, y_ag, 6.05, y_s + 0.78)
    _arrow(ax, 5.0, 10.15, 8.1, y_ag + h_a)

    # 引擎层
    rbox(
        (0.55, 5.15),
        8.9,
        1.55,
        "",
        C["dark"],
        C["palegray"],
        lw=1.4,
    )
    ax.text(5, 6.48, "引擎层", ha="center", fontsize=10, fontweight="bold")
    rbox(
        (0.85, 5.35),
        2.45,
        1.05,
        "扩展式博弈\n引擎 (SPNE)",
        C["red"],
        "#FADBD8",
        lw=2.0,
        fs=8.5,
        bold=True,
    )
    rbox((3.55, 5.35), 2.35, 1.05, "演化博弈\n模拟器", C["gray"], "#E5E8E8", fs=8.5)
    rbox((6.15, 5.35), 2.85, 1.05, "P-RAG\n检索引擎", C["gray"], "#D4E6F1", fs=8.5)

    _arrow(ax, 5.0, 7.05, 5.0, 6.75, lw=1.6)
    _darrow(ax, 3.3, 8.4, 3.3, 6.4, color=C["gray"])

    # 评测输出
    rbox(
        (2.75, 3.35),
        4.5,
        1.25,
        "评测输出\nSR / ECR / PFS / LAW Recall",
        C["dark"],
        "#EAEDED",
        fs=9,
        bold=True,
    )
    _arrow(ax, 5.0, 5.15, 5.0, 4.62, lw=1.6)

    cap = (
        "图1 LexGentium系统架构。数据输入经三场景重构后进入扩展式博弈驱动的多智能体协同管道（CD→DD→CI），"
        "核心引擎基于SPNE建模序贯策略决策，辅以演化博弈模拟器和P-RAG渐进式法条检索，最终输出多维评测结果。"
    )
    ax.text(5, 0.35, cap, ha="center", va="top", fontsize=8, wrap=True, color=C["dark"])

    fig.savefig(OUT / "图1_LexGentium系统架构.png", facecolor="white")
    plt.close()
    print("[OK]", OUT / "图1_LexGentium系统架构.png")


def fig2_roadmap():
    """图2 技术路线总览：三步串行"""
    fig, ax = plt.subplots(figsize=(12, 7.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7.6)
    ax.axis("off")
    ax.text(6, 7.25, "技术路线总览", ha="center", fontsize=14, fontweight="bold")

    def step_box(x, y, w, h, title, body, border, lw=1.6):
        p = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.06",
            facecolor="white",
            edgecolor=border,
            linewidth=lw,
        )
        ax.add_patch(p)
        ax.text(x + w / 2, y + h - 0.35, title, ha="center", fontsize=9.5, fontweight="bold", color=border)
        ax.text(x + w / 2, y + h / 2 - 0.15, body, ha="center", va="center", fontsize=8, linespacing=1.42)

    y0, w, h = 2.15, 3.35, 4.35
    step_box(
        0.35,
        y0,
        w,
        h,
        "步骤一  收益矩阵构建",
        "5×5 TKI 策略组合\n     ↓\nCD→DD→CI\n全流程模拟\n     ↓\n双路校验\n     ↓\n5×5 收益矩阵\n\n输出：经验收益矩阵",
        C["blue"],
        lw=1.8,
    )
    step_box(
        4.15,
        y0,
        w,
        h,
        "步骤二（核心）\nSPNE vs NE 对照",
        "扩展式博弈树\n(反向归纳)\n     ↓\nSPNE 求解\n    对照\nNE 求解\n     ↓\n博弈锦标赛\n(实际收敛)\n\n输出：SPNE vs NE\n预测精度对比",
        C["red"],
        lw=3.2,
    )
    step_box(
        7.95,
        y0,
        w,
        h,
        "步骤三  ESS稳定性验证",
        "复制者动态\n方程模拟\n(50代)\n     ↓\nESS 收敛\n检验\n     ↓\nSPNE=ESS?\n\n输出：演化稳定性\n验证结论",
        C["blue"],
        lw=1.8,
    )

    for xa, xb in [(3.75, 4.15), (7.55, 7.95)]:
        _arrow(ax, xa, y0 + h * 0.55, xb, y0 + h * 0.55, lw=2.8, color=C["dark"])

    foot = FancyBboxPatch(
        (0.25, 0.45),
        11.5,
        1.35,
        boxstyle="round,pad=0.05",
        facecolor=C["palegray"],
        edgecolor=C["lightgray"],
        linewidth=1,
    )
    ax.add_patch(foot)
    ax.text(
        6,
        1.1,
        "底层支撑：LexGentium系统 (28模块/65端点) + LexGentium-1K数据集 + P-RAG法条检索 + 双路校验机制",
        ha="center",
        va="center",
        fontsize=8.5,
        color=C["dark"],
    )

    cap = (
        "图2 技术路线总览。三步串行：步骤一构建5×5经验收益矩阵（数据基础），步骤二将CD→DD建模为扩展式博弈并对照"
        "SPNE与NE的策略预测精度（核心实验），步骤三通过复制者动态方程检验SPNE均衡的演化稳定性（补充验证）。"
    )
    ax.text(6, 0.18, cap, ha="center", va="top", fontsize=8)

    fig.savefig(OUT / "图2_技术路线总览.png", facecolor="white")
    plt.close()
    print("[OK]", OUT / "图2_技术路线总览.png")


def _fig3_game_tree_variant(*, variant: str) -> None:
    """
    图3 CD→DD→CI 博弈树 + SPNE 路径（中文策略名）

    variant:
      - "half":   约 1/2 页高（更舒展）
      - "third":  约 1/3 页高（更紧凑）
    """
    if variant not in {"half", "third"}:
        raise ValueError(f"unknown variant: {variant}")

    # 版式参数：只调整“枝干长度/间距”，其余信息元素保持一致
    if variant == "half":
        fig, ax = plt.subplots(figsize=(13.6, 8.2))
        y_min, y_max = 0.6, 8.0
        root_y, dd_y, ci_y = 7.15, 4.95, 2.05
        span = 0.80
        root_from, root_to = 0.12, 0.22
        dd_from, ci_to = 0.12, 0.14
        node_scale = 1.00
        label_shift_on, label_shift_off = 0.28, 0.22
        dd_text_dy = 0.40
        ci_text_dy = 0.58
        # 公式框：放右上，减少干扰主路径
        formula_xy = (10.35, 6.55)
    else:  # "third"
        # 更扁平：减少高度并进一步缩短枝干
        fig, ax = plt.subplots(figsize=(13.6, 6.2))
        y_min, y_max = 1.2, 7.8
        root_y, dd_y, ci_y = 6.90, 5.15, 3.15
        span = 0.65
        root_from, root_to = 0.10, 0.18
        dd_from, ci_to = 0.10, 0.12
        node_scale = 0.92
        label_shift_on, label_shift_off = 0.22, 0.18
        dd_text_dy = 0.32
        ci_text_dy = 0.52
        # 公式框：放右上，减少干扰主路径
        formula_xy = (10.35, 6.55)

    ax.set_xlim(-0.5, 11.5)
    ax.set_ylim(y_min, y_max)
    ax.axis("off")

    labels = ["竞争型", "合作型", "妥协型", "回避型", "迁就型"]
    root_x = 5.5
    ax.plot(root_x, root_y, "o", color=C["blue"], markersize=18 * node_scale, zorder=6)
    ax.text(
        root_x,
        root_y + 0.45 * node_scale,
        "根节点\n原告 (CD阶段)",
        ha="center",
        fontsize=10.5 * node_scale,
        fontweight="bold",
        color=C["blue"],
    )

    xs = np.linspace(0.6, 10.4, 5)
    spne_i = 1

    for i, (dx, lab) in enumerate(zip(xs, labels)):
        on = i == spne_i
        lc = C["red"] if on else C["lightgray"]
        lw = 3.4 if on else 1.0
        ax.plot([root_x, dx], [root_y - root_from, dd_y + root_to], "-", color=lc, lw=lw, zorder=2)
        ax.text(
            (root_x + dx) / 2,
            (root_y + dd_y) / 2 + (label_shift_on if on else label_shift_off),
            lab,
            fontsize=8.8 * node_scale,
            ha="center",
            color=lc,
            fontweight="bold" if on else "normal",
        )

        nc = C["red"] if on else C["orange"]
        ax.plot(dx, dd_y, "s", color=nc, markersize=12.5 * node_scale, zorder=5)
        ax.text(dx, dd_y - dd_text_dy, "被告\n(DD阶段)", ha="center", fontsize=8.2 * node_scale, color=C["dark"])

        cxs = np.linspace(dx - span, dx + span, 3)
        for j, cx in enumerate(cxs):
            full = on and (j == 1)
            lw2 = 3.0 if full else 0.8
            c2 = C["red"] if full else "#D5D8DC"
            ax.plot([dx, cx], [dd_y - dd_from, ci_y + ci_to], "-", color=c2, lw=lw2, zorder=1)
            if full:
                ax.plot(cx, ci_y, "D", color="#27AE60", markersize=11.5 * node_scale, zorder=6)
                ax.text(
                    cx,
                    ci_y - ci_text_dy,
                    "终端收益\n(CI裁判)",
                    ha="center",
                    fontsize=8.2 * node_scale,
                    fontweight="bold",
                    color="#1E8449",
                )
            else:
                ax.plot(cx, ci_y, "D", color="#D5D8DC", markersize=6, zorder=3)

    ax.text(
        formula_xy[0],
        formula_xy[1],
        r"反向归纳：" "\n" r"$s_D^*(s_P)=\arg\max_{s_D} u_D(s_P,s_D)$",
        fontsize=8.6 * node_scale,
        ha="left",
        va="top",
        bbox=dict(boxstyle="round,pad=0.35", fc="#F8F9F9", ec=C["lightgray"]),
    )
    # 删除图底部字段内容（用于 PPT 干净展示）

    legend_elements = [
        Line2D([0], [0], color=C["red"], lw=3.4, label="SPNE 均衡路径"),
        Line2D([0], [0], color=C["lightgray"], lw=1, label="非均衡分支"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=C["blue"], markersize=10, label="原告决策点"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=C["orange"], markersize=9, label="被告决策点"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#27AE60", markersize=9, label="终端 (CI)"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=9.2, frameon=True, fancybox=True)

    # 同时输出：PNG（高 DPI）+ SVG（矢量，PPT 放大不糊）
    suffix = "半页高" if variant == "half" else "三分之一页高"
    fig.savefig(OUT / f"图3_扩展式博弈树与SPNE_{suffix}.png", facecolor="white", dpi=600)
    fig.savefig(OUT / f"图3_扩展式博弈树与SPNE_{suffix}.svg", facecolor="white", format="svg")
    plt.close()
    print("[OK]", OUT / f"图3_扩展式博弈树与SPNE_{suffix}.png")
    print("[OK]", OUT / f"图3_扩展式博弈树与SPNE_{suffix}.svg")


def fig3_game_tree():
    """图3：同时导出 1/2 高 与 1/3 高两版"""
    _fig3_game_tree_variant(variant="half")
    _fig3_game_tree_variant(variant="third")


def fig4_heatmap():
    """图4 5×5 收益矩阵热力图（原告视角，指定数值）"""
    strategies = ["竞争", "合作", "妥协", "回避", "迁就"]
    M = np.array(
        [
            [0.31, 0.42, 0.38, 0.35, 0.55],
            [0.58, 0.89, 0.72, 0.65, 0.78],
            [0.45, 0.71, 0.62, 0.55, 0.68],
            [0.28, 0.52, 0.45, 0.40, 0.48],
            [0.22, 0.65, 0.55, 0.42, 0.58],
        ]
    )

    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    im = ax.imshow(M, cmap="coolwarm", vmin=0.2, vmax=0.92, aspect="equal")
    ax.set_xticks(range(5))
    ax.set_yticks(range(5))
    ax.set_xticklabels(strategies, fontsize=9)
    ax.set_yticklabels(strategies, fontsize=9)
    ax.set_xlabel("被告策略", fontsize=10, fontweight="bold")
    ax.set_ylabel("原告策略", fontsize=10, fontweight="bold")
    ax.set_title("5×5 TKI 策略收益矩阵（原告视角）", fontsize=11, fontweight="bold", pad=10)

    for i in range(5):
        for j in range(5):
            v = M[i, j]
            tc = "white" if v < 0.45 or v > 0.82 else "black"
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=9, color=tc, fontweight="bold")

    ax.plot(1, 1, marker="*", markersize=22, color="gold", markeredgecolor="black", markeredgewidth=0.8, zorder=10)

    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("收益（低→高）", fontsize=9)

    ax.text(0.5, -0.12, "★ = NE点 (合作型, 合作型)", ha="center", va="top", transform=ax.transAxes, fontsize=9, color=C["dark"])

    cap = (
        "图4 5×5 TKI策略收益矩阵热力图（原告视角）。颜色从蓝（低收益）到红（高收益），★标记纯策略纳什均衡点"
        "(Collaborating, Collaborating)。该矩阵同时服务于SPNE博弈树终端收益和演化适应度计算。"
    )
    fig.text(0.5, 0.01, cap, ha="center", fontsize=7.8, wrap=True)

    plt.tight_layout(rect=[0, 0.14, 1, 1])
    fig.savefig(OUT / "图4_收益矩阵热力图.png", facecolor="white")
    plt.close()
    print("[OK]", OUT / "图4_收益矩阵热力图.png")


def fig5_expected():
    """图5 预期实验结果：(a) 对照表 (b) 复制者动态"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.2), gridspec_kw={"width_ratios": [1.05, 1.0]})

    # (a) 表格
    ax1.axis("off")
    rows = [
        ["案由", "NE预测", "SPNE预测", "实际收敛"],
        ["借贷", "(合,合)", "(合,妥)", "(合,妥)"],
        ["交通", "(合,合)", "(妥,合)", "(妥,合)"],
        ["劳动", "(合,合)", "(合,合)", "(合,合)"],
    ]
    table = ax1.table(
        cellText=rows[1:],
        colLabels=rows[0],
        loc="center",
        cellLoc="center",
        colColours=["#D6EAF8"] * 4,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.15, 1.85)
    ax1.set_title("(a) SPNE vs NE 策略预测对照", fontsize=11, fontweight="bold", pad=12)
    ax1.text(0.5, 0.18, "NE准确率:  33%\nSPNE准确率: 100%", ha="center", transform=ax1.transAxes, fontsize=10, fontweight="bold")
    ax1.text(
        0.5,
        0.06,
        "※ 示意数据，非正式实验结果",
        ha="center",
        transform=ax1.transAxes,
        fontsize=9,
        color=C["red"],
        fontweight="bold",
    )

    # (b) 复制者动态示意曲线
    gens = np.arange(0, 51)
    t = gens / 50.0
    coop = 0.22 + 0.73 * (1 - np.exp(-4 * t)) + 0.02 * np.sin(gens * 0.35)
    coop = np.clip(coop, 0, 1)
    comp = 0.35 * np.exp(-3.5 * t)
    compr = 0.28 * np.exp(-2.2 * t) + 0.02
    avoid = 0.18 * np.exp(-2.8 * t)
    accom = 0.12 * np.exp(-2.0 * t)
    s = coop + comp + compr + avoid + accom
    coop, comp, compr, avoid, accom = coop / s, comp / s, compr / s, avoid / s, accom / s

    styles = [
        ("合作型", coop, C["green"], "-"),
        ("妥协型", compr, C["orange"], "-"),
        ("竞争型", comp, C["red"], "--"),
        ("回避型", avoid, C["gray"], "-."),
        ("迁就型", accom, "#8E44AD", ":"),
    ]
    for name, y, col, ls in styles:
        ax2.plot(gens, y, label=name, color=col, ls=ls, lw=2)

    ax2.axvline(48, color=C["lightgray"], ls=":", lw=1.2)
    ax2.annotate(
        "ESS\n收敛",
        xy=(48, 0.92),
        xytext=(38, 0.72),
        arrowprops=dict(arrowstyle="->", color=C["dark"], lw=1),
        fontsize=8,
    )
    ax2.set_xlabel("演化代数", fontsize=10)
    ax2.set_ylabel("种群比例", fontsize=10)
    ax2.set_title("(b) 复制者动态演化轨迹", fontsize=11, fontweight="bold", pad=10)
    ax2.set_xlim(0, 50)
    ax2.set_ylim(0, 1.0)
    ax2.legend(loc="center right", fontsize=8, frameon=True, fancybox=True)
    ax2.grid(alpha=0.25, ls="--")

    cap = (
        "图5 预期实验结果示意。(a) SPNE与NE在不同案由类型上的策略预测对照——预期SPNE在序贯依赖较强的案由（如民间借贷）上"
        "预测精度显著优于NE；(b) 复制者动态下五种TKI策略的种群比例演化轨迹——预期合作型策略收敛为ESS，与SPNE均衡一致。"
        "注：图中数据为基于先验分析的示意，正式结果将在100条测试案件的端到端实验中获得。"
    )
    fig.text(0.5, 0.02, cap, ha="center", fontsize=7.8)

    plt.tight_layout(rect=[0, 0.12, 1, 1])
    fig.savefig(OUT / "图5_预期实验结果示意.png", facecolor="white")
    plt.close()
    print("[OK]", OUT / "图5_预期实验结果示意.png")


def main():
    fig1_system_architecture()
    fig2_roadmap()
    fig3_game_tree()
    fig4_heatmap()
    fig5_expected()
    print("全部完成，输出目录:", OUT)


if __name__ == "__main__":
    main()
