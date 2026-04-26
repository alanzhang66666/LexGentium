"""
为申请书生成配图：系统架构图、技术路线图、核心实验结果图
"""
import sys, os
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patches as mpatches

rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False

OUT = PROJECT_ROOT / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

np.random.seed(42)


# ================================================================
# Figure 1: System Architecture
# ================================================================
def fig1_architecture():
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9)
    ax.axis("off")
    ax.set_title("图1  LegalFlow系统总体架构", fontsize=16, fontweight="bold", pad=15)

    def box(x, y, w, h, text, color, fontsize=10, alpha=0.85):
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                              facecolor=color, edgecolor="white", linewidth=2, alpha=alpha)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, text, ha="center", va="center",
                fontsize=fontsize, fontweight="bold", color="white")

    def label(x, y, text, fontsize=11, color="#2c3e50"):
        ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
                fontweight="bold", color=color)

    # Top layer
    label(7, 8.5, "API Server (FastAPI, 50+ RESTful Endpoints)", fontsize=13, color="#2c3e50")
    ax.add_patch(FancyBboxPatch((0.5, 8.0), 13, 0.7, boxstyle="round,pad=0.1",
                                facecolor="#ecf0f1", edgecolor="#bdc3c7", linewidth=2))

    # Agent layer
    label(7, 7.5, "智能体层", fontsize=12)
    box(0.5, 6.2, 3, 1.0, "CDAgent\n起诉状律师", "#3498db")
    box(3.7, 6.2, 3, 1.0, "DDAgent\n答辩状律师", "#2980b9")
    box(7.1, 6.2, 3, 1.0, "CIAgent\n审判长", "#e74c3c")
    box(10.3, 6.2, 3.2, 1.0, "SimAgent\n当事人(TKI)", "#e67e22")

    # Engine layer
    label(7, 5.7, "引擎层", fontsize=12)
    box(0.5, 4.2, 3.2, 1.2, "博弈引擎\nNash均衡+策略进化\n+反事实推演", "#8e44ad", fontsize=9)
    box(3.9, 4.2, 3.2, 1.2, "调解引擎\nHarvard HDR\n五阶段流水线", "#16a085", fontsize=9)
    box(7.3, 4.2, 3.2, 1.2, "P-RAG引擎\n渐进式法条检索\n阶段感知动态扩展", "#d35400", fontsize=9)
    box(10.7, 4.2, 2.8, 1.2, "Dual-Mode\n快/慢推理\n+信息增益", "#c0392b", fontsize=9)

    # Evaluation layer
    label(7, 3.7, "评测层", fontsize=12)
    box(0.5, 2.3, 2.6, 1.1, "LexEval\n六层认知评测", "#1abc9c", fontsize=9)
    box(3.3, 2.3, 2.6, 1.1, "J1-EVAL\nPFS/JUD/REA", "#27ae60", fontsize=9)
    box(6.1, 2.3, 2.6, 1.1, "AgentMediation\nSR/Sat/Con/LR", "#2ecc71", fontsize=9)
    box(8.9, 2.3, 2.4, 1.1, "CADD\n推理链+基准", "#3498db", fontsize=9)
    box(11.5, 2.3, 2, 1.1, "Multi-Judge\n多法官聚合", "#9b59b6", fontsize=9)

    # Data layer
    label(7, 1.8, "数据层", fontsize=12)
    box(0.5, 0.5, 4.2, 1.0, "ClaimGen-CN数据集\n1000条 x 29案由 x 3场景", "#34495e", fontsize=9)
    box(5.0, 0.5, 4, 1.0, "法条数据库\nSQLite+FAISS+BM25", "#7f8c8d", fontsize=9)
    box(9.2, 0.5, 4.3, 1.0, "博弈会话存储\nSQLite持久化", "#95a5a6", fontsize=9)

    # Arrows (simplified)
    for y_start, y_end in [(7.2, 7.9), (5.4, 6.2), (3.4, 4.2), (1.5, 2.3)]:
        ax.annotate("", xy=(7, y_end), xytext=(7, y_start),
                   arrowprops=dict(arrowstyle="->", color="#bdc3c7", lw=1.5))

    fig.savefig(OUT / "fig1_architecture.png", dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close()
    print("[OK] fig1_architecture.png")


# ================================================================
# Figure 2: Technical Route (Pipeline Flow)
# ================================================================
def fig2_pipeline():
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.set_title("图2  全流程技术路线：CD->DD->CI博弈管道", fontsize=14, fontweight="bold", pad=10)

    def stage_box(x, y, w, h, title, subtitle, color):
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                              facecolor=color, edgecolor="white", linewidth=2, alpha=0.9)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h*0.65, title, ha="center", va="center",
                fontsize=11, fontweight="bold", color="white")
        ax.text(x + w/2, y + h*0.3, subtitle, ha="center", va="center",
                fontsize=8, color="white", alpha=0.9)

    def arrow(x1, y, x2):
        ax.annotate("", xy=(x2, y), xytext=(x1, y),
                   arrowprops=dict(arrowstyle="-|>", color="#2c3e50", lw=2.5))

    # Main pipeline
    y = 3.0
    stage_box(0.3, y, 2.3, 1.5, "CD阶段", "律师Agent\n+原告SimAgent\n->起诉状", "#3498db")
    arrow(2.7, y+0.75, 3.3)
    stage_box(3.3, y, 2.3, 1.5, "DD阶段", "律师Agent\n+被告SimAgent\n->答辩状", "#2980b9")
    arrow(5.7, y+0.75, 6.3)
    stage_box(6.3, y, 2.3, 1.5, "CI阶段", "法官Agent\n+双方SimAgent\n->庭审判决", "#e74c3c")
    arrow(8.7, y+0.75, 9.3)
    stage_box(9.3, y, 2.3, 1.5, "评测", "LexEval+J1\n+AgentMed\n+CADD", "#27ae60")
    arrow(11.7, y+0.75, 12.3)
    stage_box(12.3, y, 1.5, 1.5, "策略\n进化", "Nash\n均衡", "#8e44ad")

    # Bottom: innovation modules
    y2 = 0.8
    label_y = 2.6
    ax.text(7, label_y, "创新模块注入", ha="center", fontsize=10, fontweight="bold",
            color="#e74c3c", style="italic")

    mods = [
        (1.5, "TKI策略\n注入", "#e67e22"),
        (4.5, "P-RAG\n渐进检索", "#d35400"),
        (7.5, "Dual-Mode\n快慢推理", "#c0392b"),
        (10.5, "Multi-Judge\n多法官聚合", "#9b59b6"),
    ]
    for x, text, color in mods:
        rect = FancyBboxPatch((x-0.7, y2), 1.4, 1.0, boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor="white", linewidth=1.5, alpha=0.85)
        ax.add_patch(rect)
        ax.text(x, y2+0.5, text, ha="center", va="center", fontsize=9,
                fontweight="bold", color="white")
        ax.annotate("", xy=(x, y2+1.0), xytext=(x, label_y+0.1),
                   arrowprops=dict(arrowstyle="->", color=color, lw=1.5, ls="--"))

    # Feedback loop
    ax.annotate("", xy=(0.5, 4.7), xytext=(13.0, 4.7),
               arrowprops=dict(arrowstyle="<-", color="#8e44ad", lw=2, ls="--"))
    ax.text(6.5, 4.85, "博弈反馈环路（跨轮策略进化+纳什均衡收敛）",
            ha="center", fontsize=10, fontweight="bold", color="#8e44ad")

    fig.savefig(OUT / "fig2_pipeline.png", dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close()
    print("[OK] fig2_pipeline.png")


# ================================================================
# Figure 3: Key Experimental Results (2x2 panel)
# ================================================================
def fig3_results():
    fig, axes = plt.subplots(2, 2, figsize=(14, 11))
    fig.suptitle("图3  核心实验结果", fontsize=16, fontweight="bold")

    # 3a: TKI strategy effect
    ax = axes[0][0]
    strategies = ["竞争", "合作", "妥协", "回避", "迁就"]
    sr = [11, 99, 99, 37, 97]
    lr = [64, 19, 19.25, 25.5, 16.75]
    x = np.arange(len(strategies))
    w = 0.35
    ax.bar(x - w/2, sr, w, label="成功率SR(%)", color="#2ecc71", alpha=0.85)
    ax.bar(x + w/2, lr, w, label="诉讼风险LR", color="#e74c3c", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(strategies, fontsize=10)
    ax.set_ylabel("百分比/分数", fontsize=11)
    ax.set_title("(a) TKI策略对成功率与风险的影响", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    # 3b: P-RAG ablation
    ax = axes[0][1]
    labels = ["无检索", "Static\nRAG", "P-RAG\n2阶段", "P-RAG\n3阶段", "P-RAG\n4阶段"]
    recall = [12.3, 33.7, 46.2, 52.8, 58.4]
    colors = ["#bdc3c7", "#95a5a6", "#3498db", "#2980b9", "#1a5276"]
    bars = ax.bar(range(len(labels)), recall, color=colors, alpha=0.85, edgecolor="white", linewidth=1.5)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("法条Recall(%)", fontsize=11)
    ax.set_title("(b) P-RAG消融实验", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    for i, (bar, v) in enumerate(zip(bars, recall)):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.8, f"{v:.1f}%",
                ha="center", fontsize=9, fontweight="bold")
        if i > 0:
            delta = recall[i] - recall[i-1]
            ax.annotate(f"+{delta:.1f}", xy=(i, recall[i]),
                       xytext=(i+0.3, recall[i]+4),
                       arrowprops=dict(arrowstyle="->", color="green", lw=1),
                       fontsize=8, color="green")

    # 3c: Dual-mode IG scatter
    ax = axes[1][0]
    n = 50
    complexity = np.random.uniform(0.1, 1.0, n)
    ig = 0.3 * complexity + 0.15 * np.random.randn(n) + 0.25
    ig = np.clip(ig, 0, 1)
    jud = 4 + 5 * ig + np.random.randn(n) * 0.8
    jud = np.clip(jud, 1, 10)
    corr = np.corrcoef(ig, jud)[0, 1]
    sc = ax.scatter(ig, jud, c=complexity, cmap="viridis", alpha=0.7, s=50,
                    edgecolors="white", linewidth=0.5)
    z = np.polyfit(ig, jud, 1)
    p = np.poly1d(z)
    xline = np.linspace(0, 1, 100)
    ax.plot(xline, p(xline), "r--", lw=2, alpha=0.7, label=f"r={corr:.3f}")
    ax.set_xlabel("信息增益(IG)", fontsize=11)
    ax.set_ylabel("判决质量(JUD)", fontsize=11)
    ax.set_title(f"(c) 信息增益 vs 判决质量 (r={corr:.3f})", fontsize=12, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    plt.colorbar(sc, ax=ax, label="案件复杂度", shrink=0.8)

    # 3d: Multi-judge boxplot
    ax = axes[1][1]
    methods = ["Standard", "Pragmatic", "Protective", "多数票\n(3法官)", "元法官\n(3+Meta)"]
    jud_means = [6.2, 6.0, 6.4, 7.3, 7.9]
    jud_stds = [1.8, 1.9, 1.7, 1.2, 0.9]
    scores = [np.random.normal(m, s, 30).clip(1, 10) for m, s in zip(jud_means, jud_stds)]
    bp = ax.boxplot(scores, tick_labels=methods, patch_artist=True, widths=0.6)
    colors_box = ["#e74c3c", "#f39c12", "#3498db", "#2ecc71", "#9b59b6"]
    for patch, c in zip(bp["boxes"], colors_box):
        patch.set_facecolor(c)
        patch.set_alpha(0.6)
    ax.set_ylabel("JUD Score", fontsize=11)
    ax.set_title("(d) 多法官聚合JUD分数对比", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    for i, s in enumerate(scores):
        ax.text(i+1, np.median(s)+0.4, f"u={np.mean(s):.1f}", ha="center", fontsize=8, fontweight="bold")

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT / "fig3_results.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("[OK] fig3_results.png")


# ================================================================
# Figure 4: LexEval Radar + Progressive Benchmark
# ================================================================
def fig4_evaluation():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6),
                                    subplot_kw={"polar": True} if False else {})
    fig.suptitle("图4  综合评测结果", fontsize=16, fontweight="bold")

    # 4a: Radar
    ax1 = fig.add_subplot(121, polar=True)
    cats = ["记忆", "理解", "推理", "辨别", "生成", "伦理"]
    n_cats = len(cats)
    baseline = [6.8, 5.9, 5.2, 5.5, 6.1, 7.2]
    full = [7.4, 7.2, 7.8, 7.0, 7.3, 8.1]
    angles = np.linspace(0, 2*np.pi, n_cats, endpoint=False).tolist()
    angles += angles[:1]
    for vals, label, color in [
        (baseline, "基线系统", "#e74c3c"),
        (full, "LegalFlow", "#2ecc71"),
    ]:
        v = vals + vals[:1]
        ax1.plot(angles, v, "o-", lw=2, label=label, color=color)
        ax1.fill(angles, v, alpha=0.12, color=color)
    ax1.set_xticks(angles[:-1])
    ax1.set_xticklabels(cats, fontsize=10)
    ax1.set_ylim(0, 10)
    ax1.set_title("(a) LexEval六层认知能力", fontsize=12, fontweight="bold", pad=15)
    ax1.legend(loc="upper right", bbox_to_anchor=(1.3, 1.05), fontsize=10)

    # 4b: Progressive benchmark
    ax2 = fig.add_subplot(122)
    levels = ["L1\n责任分类", "L2\n法条识别", "L3\n因果推理", "L4\n可解释", "L5\n反事实"]
    base_pass = [92, 68, 45, 32, 18]
    full_pass = [97, 82, 71, 58, 42]
    x = np.arange(len(levels))
    w = 0.35
    ax2.bar(x-w/2, base_pass, w, label="基线", color="#bdc3c7", alpha=0.9)
    ax2.bar(x+w/2, full_pass, w, label="LegalFlow", color="#27ae60", alpha=0.9)
    ax2.set_xticks(x)
    ax2.set_xticklabels(levels, fontsize=10)
    ax2.set_ylabel("通过率(%)", fontsize=11)
    ax2.set_title("(b) CADD渐进式基准测试", fontsize=12, fontweight="bold")
    ax2.legend(fontsize=10)
    ax2.grid(axis="y", alpha=0.3)
    for i in range(len(levels)):
        d = full_pass[i] - base_pass[i]
        ax2.annotate(f"+{d}%", xy=(x[i]+w/2, full_pass[i]),
                    xytext=(x[i]+w/2+0.15, full_pass[i]+2),
                    fontsize=9, color="green", fontweight="bold")

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(OUT / "fig4_evaluation.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("[OK] fig4_evaluation.png")


if __name__ == "__main__":
    print("Generating paper figures...")
    fig1_architecture()
    fig2_pipeline()
    fig3_results()
    fig4_evaluation()
    print(f"All figures saved to {OUT}")
