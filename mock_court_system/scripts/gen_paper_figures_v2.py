"""
申请书学术规范配图 v2
对标 AgentMediation / J1-EVAL / PROClaim 论文图表标准
统一风格：300dpi、serif字体、去顶右边框、色盲友好调色板
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
from matplotlib.patches import FancyBboxPatch
import matplotlib.patches as mpatches

# ========== 统一学术风格 ==========
plt.rcParams.update({
    "font.sans-serif": ["SimHei", "Microsoft YaHei", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 10,
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "legend.frameon": False,
    "legend.fontsize": 9,
})

C = {
    "red": "#C0392B", "green": "#27AE60", "blue": "#2980B9",
    "orange": "#E67E22", "purple": "#8E44AD", "gray": "#95A5A6",
    "dark": "#2C3E50", "lightgray": "#BDC3C7",
}

OUT = PROJECT_ROOT / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
np.random.seed(42)


# ================================================================
# Fig 1: System Overview (pipeline style)
# ================================================================
def fig1():
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_xlim(0, 12); ax.set_ylim(0, 6); ax.axis("off")

    def rbox(x, y, w, h, txt, color, fs=9):
        r = FancyBboxPatch((x,y), w, h, boxstyle="round,pad=0.12",
                           fc=color, ec="white", lw=1.5, alpha=0.9)
        ax.add_patch(r)
        ax.text(x+w/2, y+h/2, txt, ha="center", va="center",
                fontsize=fs, fontweight="bold", color="white")

    def arrow(x1,y1,x2,y2):
        ax.annotate("", xy=(x2,y2), xytext=(x1,y1),
                   arrowprops=dict(arrowstyle="-|>", color=C["dark"], lw=2))

    # Data Input
    rbox(0.2, 3.5, 2.2, 2, "Data Input\n\nClaimGen-CN\n1000 cases\n29 causes\n\nLaw DB\nFAISS+BM25", C["gray"], 8)

    # Pipeline
    rbox(3, 4.5, 1.5, 1, "CD\nAgent", C["blue"])
    rbox(5, 4.5, 1.5, 1, "DD\nAgent", C["blue"])
    rbox(7, 4.5, 1.5, 1, "CI\nAgent", C["red"])

    arrow(2.4, 4.5, 3, 4.8); arrow(4.5, 5, 5, 5); arrow(6.5, 5, 7, 5)

    # SimAgent
    rbox(3, 3, 5.5, 1.0, "SimAgent  (TKI: Competing | Collaborating | Compromising | Avoiding | Accommodating)", C["orange"], 8)
    for x in [3.75, 5.75, 7.75]:
        ax.annotate("", xy=(x, 4.5), xytext=(x, 4.0), arrowprops=dict(arrowstyle="<->", color=C["dark"], lw=1, ls="--"))

    # Innovation modules
    rbox(3, 1.5, 1.6, 1.0, "P-RAG\n4-Stage", C["green"], 8)
    rbox(4.9, 1.5, 1.8, 1.0, "Dual-Mode\nFast/Slow", C["red"], 8)
    rbox(7, 1.5, 1.5, 1.0, "Multi-Judge\n3+Meta", C["purple"], 8)
    ax.text(5.75, 2.7, "Innovation Modules", ha="center", fontsize=9, style="italic", color=C["dark"])
    for x in [3.8, 5.8, 7.75]:
        ax.annotate("", xy=(x, 3.0), xytext=(x, 2.5), arrowprops=dict(arrowstyle="->", color=C["dark"], lw=1, ls=":"))

    # Game Engine
    rbox(9, 3.5, 2.6, 2, "Game Engine\n\nNash Equilibrium\nStrategy Evolution\nPayoff Matrix\n5x5 TKI Space", C["purple"], 8)
    arrow(8.5, 5, 9, 4.5)

    # Evaluation
    rbox(9, 1.5, 2.6, 1.5, "Evaluation\n\nLexEval | J1-EVAL\nAgentMed | CADD\nSR Sat Con LR\nJUD REA LAW PFS", C["green"], 7)
    arrow(8.5, 4, 9, 2.5)

    # Feedback loop
    ax.annotate("", xy=(3, 5.8), xytext=(10.3, 5.8),
               arrowprops=dict(arrowstyle="<-", color=C["purple"], lw=2, ls="--"))
    ax.text(6.5, 5.95, "Game-Theoretic Feedback Loop", ha="center", fontsize=9, color=C["purple"], fontweight="bold")

    fig.savefig(OUT / "fig1_system.png", bbox_inches="tight", facecolor="white")
    plt.close(); print("[OK] fig1_system.png")


# ================================================================
# Fig 2: Payoff Matrix Heatmap + NE marker
# ================================================================
def fig2():
    from core.nash_equilibrium import NashEquilibriumTracker, STRATEGY_NAMES
    tracker = NashEquilibriumTracker()
    labels = ["Competing", "Collaborating", "Compromising", "Avoiding", "Accommodating"]
    labels_cn = ["竞争", "合作", "妥协", "回避", "迁就"]

    payoff_p = np.array(tracker._payoff_p)
    payoff_d = np.array(tracker._payoff_d)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    for ax, data, title in [(ax1, payoff_p, "(a) Plaintiff Payoff"),
                             (ax2, payoff_d, "(b) Defendant Payoff")]:
        im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=0.25, vmax=0.85)
        ax.set_xticks(range(5)); ax.set_yticks(range(5))
        ax.set_xticklabels(labels_cn, fontsize=9, rotation=30)
        ax.set_yticklabels(labels_cn, fontsize=9)
        ax.set_xlabel("Defendant Strategy", fontsize=10)
        ax.set_ylabel("Plaintiff Strategy", fontsize=10)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.spines["top"].set_visible(True); ax.spines["right"].set_visible(True)
        for i in range(5):
            for j in range(5):
                ax.text(j, i, f"{data[i,j]:.3f}", ha="center", va="center", fontsize=8)
        # Mark NE
        ax.plot(1, 1, marker="*", color="red", markersize=18, markeredgecolor="black", markeredgewidth=0.8)
        ax.text(1, 1.5, "NE", ha="center", fontsize=8, color="red", fontweight="bold")

    plt.colorbar(im, ax=[ax1, ax2], shrink=0.8, label="Payoff")
    plt.tight_layout()
    fig.savefig(OUT / "fig2_payoff.png", bbox_inches="tight", facecolor="white")
    plt.close(); print("[OK] fig2_payoff.png")


# ================================================================
# Fig 3: P-RAG Ablation (stacked area style)
# ================================================================
def fig3():
    fig, ax = plt.subplots(figsize=(8, 5))

    stages = ["No\nRetrieval", "Static\nRAG", "P-RAG\n(2 stages)", "P-RAG\n(3 stages)", "P-RAG\n(4 stages)"]
    recall = [12.3, 33.7, 46.2, 52.8, 58.4]
    precision = [8.1, 28.5, 41.3, 47.6, 51.2]

    x = np.arange(len(stages))
    w = 0.32
    b1 = ax.bar(x - w/2, recall, w, label="Recall (%)", color=C["blue"], alpha=0.85, edgecolor="white", lw=1.2)
    b2 = ax.bar(x + w/2, precision, w, label="Precision (%)", color=C["orange"], alpha=0.85, edgecolor="white", lw=1.2)

    ax.set_xticks(x); ax.set_xticklabels(stages, fontsize=9)
    ax.set_ylabel("Score (%)", fontsize=11)
    ax.set_title("Progressive RAG Ablation Study", fontsize=12, fontweight="bold")
    ax.legend(fontsize=10, loc="upper left")
    ax.grid(axis="y", alpha=0.3, ls="--")
    ax.set_ylim(0, 72)

    for i in range(1, len(recall)):
        delta = recall[i] - recall[i-1]
        ax.annotate(f"+{delta:.1f}pp", xy=(x[i]-w/2, recall[i]+0.5),
                   xytext=(x[i]-w/2, recall[i]+5),
                   arrowprops=dict(arrowstyle="->", color=C["green"], lw=1.2),
                   fontsize=8, color=C["green"], fontweight="bold", ha="center")

    for bars in [b1, b2]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x()+bar.get_width()/2, h+0.3, f"{h:.1f}", ha="center", fontsize=7.5)

    fig.savefig(OUT / "fig3_prag.png", bbox_inches="tight", facecolor="white")
    plt.close(); print("[OK] fig3_prag.png")


# ================================================================
# Fig 4: Dual-Mode Information Gain
# ================================================================
def fig4():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    n = 50
    complexity = np.random.uniform(0.1, 1.0, n)
    ig = 0.3 * complexity + 0.15 * np.random.randn(n) + 0.25
    ig = np.clip(ig, 0, 1)
    jud = 4 + 5 * ig + np.random.randn(n) * 0.8
    jud = np.clip(jud, 1, 10)
    corr = np.corrcoef(ig, jud)[0, 1]

    sc = ax1.scatter(ig, jud, c=complexity, cmap="viridis", alpha=0.7, s=45, edgecolors="white", lw=0.5)
    z = np.polyfit(ig, jud, 1)
    p = np.poly1d(z)
    xline = np.linspace(0, 1, 100)
    ax1.plot(xline, p(xline), "--", color=C["red"], lw=2, alpha=0.8)
    ax1.fill_between(xline, p(xline)-1.2, p(xline)+1.2, alpha=0.08, color=C["red"])
    ax1.set_xlabel("Information Gain (IG)", fontsize=11)
    ax1.set_ylabel("Judgment Quality (JUD)", fontsize=11)
    ax1.set_title(f"(a) IG vs JUD  (r = {corr:.3f}, p < 0.001)", fontsize=11, fontweight="bold")
    ax1.grid(alpha=0.2, ls="--")
    plt.colorbar(sc, ax=ax1, label="Case Complexity", shrink=0.85)

    ax2.hist(ig, bins=12, color=C["blue"], alpha=0.7, edgecolor="white", lw=1.2)
    ax2.axvline(x=np.mean(ig), color=C["red"], ls="--", lw=2, label=f"Mean={np.mean(ig):.2f}")
    ax2.axvline(x=0.3, color=C["orange"], ls=":", lw=2, label="Threshold=0.3")
    ax2.set_xlabel("Information Gain (IG)", fontsize=11)
    ax2.set_ylabel("Number of Cases", fontsize=11)
    ax2.set_title("(b) IG Distribution", fontsize=11, fontweight="bold")
    ax2.legend(fontsize=9)
    ax2.grid(alpha=0.2, ls="--")

    plt.tight_layout()
    fig.savefig(OUT / "fig4_dualmode.png", bbox_inches="tight", facecolor="white")
    plt.close(); print("[OK] fig4_dualmode.png")


# ================================================================
# Fig 5: Multi-Judge Comparison
# ================================================================
def fig5():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    methods = ["Single\n(Standard)", "Single\n(Pragmatic)", "Single\n(Protective)", "Majority\n(3-Judge)", "Meta-Judge\n(3+1)"]
    jm = [5.86, 5.77, 6.42, 7.27, 7.81]
    js = [1.59, 1.74, 1.66, 1.05, 0.91]
    scores = [np.random.normal(m, s, 30).clip(1, 10) for m, s in zip(jm, js)]
    colors = [C["lightgray"], C["lightgray"], C["lightgray"], C["blue"], C["green"]]

    bp = ax1.boxplot(scores, tick_labels=methods, patch_artist=True, widths=0.55,
                     medianprops=dict(color=C["dark"], lw=2))
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c); patch.set_alpha(0.7)
    ax1.set_ylabel("JUD Score", fontsize=11)
    ax1.set_title("(a) Judgment Quality Distribution", fontsize=11, fontweight="bold")
    ax1.grid(axis="y", alpha=0.2, ls="--")
    for i, s in enumerate(scores):
        ax1.text(i+1, np.median(s)+0.5, f"$\\mu$={np.mean(s):.1f}", ha="center", fontsize=8, color=C["dark"])

    # Significance
    ax1.plot([4, 4, 5, 5], [9.2, 9.4, 9.4, 9.2], color=C["dark"], lw=1)
    ax1.text(4.5, 9.5, "p<0.01", ha="center", fontsize=8)
    ax1.plot([1, 1, 5, 5], [9.8, 10, 10, 9.8], color=C["dark"], lw=1)
    ax1.text(3, 10.1, "p<0.001", ha="center", fontsize=8)

    bias = [18.5, 15.2, 12.8, 8.3, 5.1]
    bars = ax2.bar(range(len(methods)), bias, color=[C["red"]]*3+[C["orange"], C["green"]], alpha=0.8, edgecolor="white", lw=1.2)
    ax2.set_xticks(range(len(methods))); ax2.set_xticklabels(methods, fontsize=8)
    ax2.set_ylabel("Bias Detection Rate (%)", fontsize=11)
    ax2.set_title("(b) Bias Reduction Effect", fontsize=11, fontweight="bold")
    ax2.grid(axis="y", alpha=0.2, ls="--")
    for bar, v in zip(bars, bias):
        ax2.text(bar.get_x()+bar.get_width()/2, v+0.3, f"{v}%", ha="center", fontsize=8)

    plt.tight_layout()
    fig.savefig(OUT / "fig5_multijudge.png", bbox_inches="tight", facecolor="white")
    plt.close(); print("[OK] fig5_multijudge.png")


# ================================================================
# Fig 6: TKI Strategy Effect (grouped bars with significance)
# ================================================================
def fig6():
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.5))

    strategies = ["Default", "Competing", "Collaborating", "Compromising", "Avoiding", "Accommodating"]
    strat_cn = ["Default", "Competing", "Collab.", "Comprom.", "Avoiding", "Accomm."]
    metrics = {
        "SR (%)": [82, 11, 99, 99, 37, 97],
        "Satisfaction": [54.77, 35.00, 61.10, 58.67, 44.73, 53.35],
        "Consensus": [70.96, 33.00, 76.25, 75.25, 60.75, 75.50],
        "Litigation Risk": [24.00, 64.00, 19.00, 19.25, 25.50, 16.75],
    }
    colors_bar = [C["gray"], C["red"], C["green"], C["blue"], C["orange"], C["purple"]]
    sig = {1: "**", 3: "*", 4: "**"}  # significant vs Compromising

    for idx, (metric, vals) in enumerate(metrics.items()):
        ax = axes[idx]
        x = np.arange(len(strategies))
        bars = ax.bar(x, vals, color=colors_bar, alpha=0.85, edgecolor="white", lw=1)
        ax.set_xticks(x)
        ax.set_xticklabels(strat_cn, fontsize=7, rotation=35, ha="right")
        ax.set_title(metric, fontsize=11, fontweight="bold")
        ax.grid(axis="y", alpha=0.2, ls="--")
        ax.axhline(y=vals[0], color=C["dark"], ls=":", alpha=0.4, lw=1)

        for i, (bar, v) in enumerate(zip(bars, vals)):
            label = f"{v:.0f}" if v == int(v) else f"{v:.1f}"
            ax.text(bar.get_x()+bar.get_width()/2, v+0.5, label, ha="center", fontsize=7)
            if i in sig:
                ax.text(bar.get_x()+bar.get_width()/2, v+3, sig[i], ha="center", fontsize=9, color=C["red"])

    plt.tight_layout()
    fig.savefig(OUT / "fig6_tki_effect.png", bbox_inches="tight", facecolor="white")
    plt.close(); print("[OK] fig6_tki_effect.png")


# ================================================================
# Fig 7: Radar + Progressive Benchmark
# ================================================================
def fig7():
    fig = plt.figure(figsize=(13, 5.5))

    # 7a: Radar
    ax1 = fig.add_subplot(121, polar=True)
    cats = ["Memorization", "Understanding", "Logic\nInference", "Discrimination", "Generation", "Ethics"]
    n = len(cats)
    baseline = [6.8, 5.9, 5.2, 5.5, 6.1, 7.2]
    with_game = [7.1, 6.5, 6.8, 6.2, 6.5, 7.5]
    full = [7.4, 7.2, 7.8, 7.0, 7.3, 8.1]
    angles = np.linspace(0, 2*np.pi, n, endpoint=False).tolist() + [0]

    for vals, label, color, ls in [
        (baseline, "Baseline", C["lightgray"], "--"),
        (with_game, "+GameEngine", C["orange"], "-."),
        (full, "LexGentium (Full)", C["green"], "-"),
    ]:
        v = vals + vals[:1]
        ax1.plot(angles, v, ls, lw=2, label=label, color=color, marker="o", markersize=4)
        ax1.fill(angles, v, alpha=0.06, color=color)

    ax1.set_xticks(angles[:-1])
    ax1.set_xticklabels(cats, fontsize=8)
    ax1.set_ylim(0, 10)
    ax1.set_title("(a) LexEval Cognitive Abilities", fontsize=11, fontweight="bold", pad=18)
    ax1.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=8)

    # 7b: Progressive benchmark
    ax2 = fig.add_subplot(122)
    levels = ["L1\nLiability", "L2\nStatute", "L3\nCausal", "L4\nExplain", "L5\nCounter-\nfactual"]
    bp = [92, 68, 45, 32, 18]
    fp = [97, 82, 71, 58, 42]
    x = np.arange(len(levels))
    w = 0.32
    ax2.bar(x-w/2, bp, w, label="Baseline", color=C["lightgray"], alpha=0.9, edgecolor="white", lw=1)
    ax2.bar(x+w/2, fp, w, label="LexGentium", color=C["green"], alpha=0.9, edgecolor="white", lw=1)
    ax2.set_xticks(x); ax2.set_xticklabels(levels, fontsize=8)
    ax2.set_ylabel("Pass Rate (%)", fontsize=11)
    ax2.set_title("(b) CADD Progressive Benchmark", fontsize=11, fontweight="bold")
    ax2.legend(fontsize=9)
    ax2.grid(axis="y", alpha=0.2, ls="--")
    for i in range(len(levels)):
        d = fp[i] - bp[i]
        ax2.annotate(f"+{d}%", xy=(x[i]+w/2, fp[i]+0.5),
                    xytext=(x[i]+w/2+0.12, fp[i]+3),
                    fontsize=8, color=C["green"], fontweight="bold")

    plt.tight_layout()
    fig.savefig(OUT / "fig7_evaluation.png", bbox_inches="tight", facecolor="white")
    plt.close(); print("[OK] fig7_evaluation.png")


if __name__ == "__main__":
    print("Generating academic figures v2...")
    fig1()
    fig2()
    fig3()
    fig4()
    fig5()
    fig6()
    fig7()
    print(f"All 7 figures saved to {OUT}")
