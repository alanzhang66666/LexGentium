import argparse
import hashlib
import json
import math
import random
import requests
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None


_LAB_DIR = Path(__file__).resolve().parent
_EVAL_DIR = _LAB_DIR.parent
_PROJECT_ROOT = _EVAL_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from evaluation.lab._paths import PROJECT_ROOT

from core.nash_equilibrium import NashEquilibriumTracker, STRATEGY_INDEX, STRATEGY_NAMES
from core.extensive_form import ExtensiveFormGame
from core.evolutionary_dynamics import EvolutionaryDynamics


def get_matplotlib_pyplot():
    global plt
    if plt is not None:
        return plt
    try:
        import matplotlib.pyplot as _plt
        plt = _plt
        return plt
    except Exception:
        plt = None
        return None


def parse_weights(text: str) -> Tuple[float, float, float]:
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) != 3:
        raise ValueError("weights must be three comma-separated numbers, e.g. 0.5,0.25,0.25")
    w = tuple(float(x) for x in parts)
    if abs(sum(w) - 1.0) > 1e-6:
        raise ValueError("weights must sum to 1.0")
    return w


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def stratified_sample(rows: List[Dict[str, Any]], n: int, seed: int) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        cat = str(row.get("sampled_category", "其他"))
        by_cat.setdefault(cat, []).append(row)

    categories = sorted(by_cat.keys())
    total = len(rows)
    if n >= total:
        sampled = rows[:]
        rng.shuffle(sampled)
        return sampled

    # Proportional allocation with remainder fill.
    alloc: Dict[str, int] = {}
    remainders: List[Tuple[float, str]] = []
    allocated = 0
    for cat in categories:
        raw = n * len(by_cat[cat]) / total
        k = int(math.floor(raw))
        k = min(k, len(by_cat[cat]))
        alloc[cat] = k
        allocated += k
        remainders.append((raw - k, cat))

    for _, cat in sorted(remainders, reverse=True):
        if allocated >= n:
            break
        if alloc[cat] < len(by_cat[cat]):
            alloc[cat] += 1
            allocated += 1

    sampled: List[Dict[str, Any]] = []
    for cat in categories:
        pool = by_cat[cat][:]
        rng.shuffle(pool)
        sampled.extend(pool[: alloc[cat]])

    rng.shuffle(sampled)
    return sampled[:n]


def list_categories(rows: List[Dict[str, Any]]) -> List[str]:
    cats = sorted({str(row.get("sampled_category", "其他")) for row in rows})
    return [cat for cat in cats if cat]


def parse_category_list(text: str) -> List[str]:
    return [x.strip() for x in text.split(",") if x.strip()]


def filter_rows_by_categories(rows: List[Dict[str, Any]], categories: List[str]) -> List[Dict[str, Any]]:
    if not categories:
        return rows
    allowed = {str(cat).strip() for cat in categories if str(cat).strip()}
    if not allowed:
        return rows
    filtered = [row for row in rows if str(row.get("sampled_category", "")).strip() in allowed]
    return filtered


def slugify_category(category: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in category).strip("_") or "category"


def choose_strategy(cause: str, role: str, case_id: str) -> str:
    # Base strategy preference by cause category.
    cause_text = (cause or "").lower()
    if "借贷" in cause_text or "借款" in cause_text:
        base = "competing" if role == "plaintiff" else "compromising"
    elif "交通" in cause_text or "机动车" in cause_text:
        base = "collaborating" if role == "plaintiff" else "avoiding"
    elif "劳动" in cause_text or "劳务" in cause_text:
        base = "compromising" if role == "plaintiff" else "collaborating"
    else:
        base = "compromising" if role == "plaintiff" else "compromising"

    # Deterministic small perturbation to avoid degenerate one-strategy traces.
    idx = STRATEGY_INDEX[base]
    h = int(hashlib.md5(f"{case_id}:{role}".encode("utf-8")).hexdigest()[:8], 16) % 100
    if h < 15:
        idx = (idx + 1) % len(STRATEGY_NAMES)
    elif h < 30:
        idx = (idx - 1) % len(STRATEGY_NAMES)
    return STRATEGY_NAMES[idx]


def score_from_case(case: Dict[str, Any], rng: random.Random) -> Dict[str, float]:
    desc = str(case.get("case_description", ""))
    claims = case.get("plaintiff_claims", [])
    claim_n = len(claims) if isinstance(claims, list) else 1

    complexity = min(1.0, max(0.0, len(desc) / 1800.0))
    claim_factor = min(1.0, claim_n / 6.0)
    noise = rng.uniform(-0.04, 0.04)

    plaintiff_win_rate = max(0.2, min(0.9, 0.52 + 0.20 * complexity + 0.10 * claim_factor + noise))
    defendant_win_rate = max(0.1, min(0.8, 1.0 - plaintiff_win_rate + rng.uniform(-0.02, 0.02)))
    reasoning_quality = max(0.35, min(0.95, 0.55 + 0.30 * complexity + rng.uniform(-0.03, 0.03)))
    evidence_strength = max(0.30, min(0.95, 0.50 + 0.25 * claim_factor + rng.uniform(-0.03, 0.03)))

    return {
        "plaintiff_win_rate": round(plaintiff_win_rate, 4),
        "defendant_win_rate": round(defendant_win_rate, 4),
        "reasoning_quality": round(reasoning_quality, 4),
        "evidence_strength": round(evidence_strength, 4),
    }


def record_round_weighted(
    tracker: NashEquilibriumTracker,
    plaintiff_strategy: str,
    defendant_strategy: str,
    score: Dict[str, float],
    weights: Tuple[float, float, float],
) -> None:
    i = STRATEGY_INDEX.get(plaintiff_strategy)
    j = STRATEGY_INDEX.get(defendant_strategy)
    if i is None or j is None:
        return

    w_w, w_r, w_e = weights
    p_win = float(score.get("plaintiff_win_rate", 0.5))
    d_win = float(score.get("defendant_win_rate", 0.5))
    r_q = float(score.get("reasoning_quality", 0.5))
    e_s = float(score.get("evidence_strength", 0.5))

    p_pay = max(0.0, min(1.0, w_w * p_win + w_r * r_q + w_e * e_s))
    d_pay = max(0.0, min(1.0, w_w * d_win + w_r * r_q + w_e * e_s))

    n = tracker._counts[i][j]
    tracker._payoff_p[i][j] = (tracker._payoff_p[i][j] * n + p_pay) / (n + 1)
    tracker._payoff_d[i][j] = (tracker._payoff_d[i][j] * n + d_pay) / (n + 1)
    tracker._counts[i][j] = n + 1
    tracker._history.append(
        {
            "plaintiff_strategy": plaintiff_strategy,
            "defendant_strategy": defendant_strategy,
            "plaintiff_payoff": round(p_pay, 4),
            "defendant_payoff": round(d_pay, 4),
        }
    )


def run_tournament_rounds(
    tracker: NashEquilibriumTracker,
    sampled: List[Dict[str, Any]],
    rounds: int,
    seed: int,
    execution_mode: str = "local",
    api_base: str = "http://127.0.0.1:8000",
    max_api_calls_per_round: int = 3,
    api_timeout: int = 180,
    evolution_method: str = "best_response",
    weights: Tuple[float, float, float] = (0.5, 0.25, 0.25),
) -> List[Dict[str, Any]]:
    """Run iterative strategy tournament and return last-round case records.

    Players use cause-based priors plus best-response adaptation with small exploration.
    """
    rng = random.Random(seed)
    last_round_records: List[Dict[str, Any]] = []
    api_stats = {
        "mode": execution_mode,
        "base_url": api_base,
        "health_ok": False,
        "api_calls": 0,
        "api_success": 0,
        "api_fallback_local": 0,
    }

    def _api_health_check() -> bool:
        try:
            resp = requests.get(f"{api_base.rstrip('/')}/health", timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def _build_case_info(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "case_id": str(row.get("case_id", "")),
            "cause": str(row.get("cause", "")),
            "case_description": str(row.get("case_description", "")),
            "plaintiff_claims": row.get("plaintiff_claims", []),
            "plaintiff_name": str(row.get("plaintiff_name", "原告")),
            "defendant_name": str(row.get("defendant_name", "被告")),
        }

    def _api_run_one_round(
        row: Dict[str, Any],
        p_s: str,
        d_s: str,
        evolution_method: str,
    ) -> Dict[str, Any]:
        base = api_base.rstrip("/")
        case_info = _build_case_info(row)

        create_payload = {
            "case_info": case_info,
            "plaintiff_strategy": p_s,
            "defendant_strategy": d_s,
            "max_rounds": 1,
            "convergence_threshold": 0.05,
            "evolution_method": evolution_method,
            "enable_dynamic_strategy": False,
            "dispute_cause": "legal_issue",
            "dispute_cause_detail": str(row.get("cause", "")),
        }
        cr = requests.post(f"{base}/game/create", json=create_payload, timeout=api_timeout)
        cr.raise_for_status()
        game_id = cr.json().get("game_id")
        if not game_id:
            raise RuntimeError("game/create missing game_id")

        rr = requests.post(
            f"{base}/game/{game_id}/round",
            json={"evolution_method": evolution_method},
            timeout=api_timeout,
        )
        rr.raise_for_status()
        round_data = rr.json()

        # Best-effort cleanup.
        try:
            requests.delete(f"{base}/game/{game_id}", timeout=10)
        except Exception:
            pass

        return round_data

    if execution_mode in ("api", "api_hybrid"):
        api_stats["health_ok"] = _api_health_check()
        if execution_mode == "api" and not api_stats["health_ok"]:
            raise RuntimeError(f"API backend unavailable: {api_base}")

    for r in range(rounds):
        round_records: List[Dict[str, Any]] = []
        api_indices = set()
        if execution_mode == "api":
            api_indices = set(range(len(sampled)))
        elif execution_mode == "api_hybrid" and api_stats["health_ok"] and max_api_calls_per_round > 0:
            pool = list(range(len(sampled)))
            rng.shuffle(pool)
            api_indices = set(pool[: min(max_api_calls_per_round, len(pool))])

        for idx, row in enumerate(sampled):
            case_id = str(row.get("case_id", ""))
            cause = str(row.get("cause", ""))
            cat = str(row.get("sampled_category", "其他"))

            # Cause-driven initial strategy.
            p_prior = choose_strategy(cause, "plaintiff", case_id)
            d_prior = choose_strategy(cause, "defendant", case_id)

            # Adaptive best response to prior strategies.
            p_br = tracker.best_response("plaintiff", d_prior)
            d_br = tracker.best_response("defendant", p_prior)

            # Annealed exploration to avoid early collapse.
            eps = max(0.05, 0.25 - 0.01 * r)
            p_s = p_br if rng.random() > eps else p_prior
            d_s = d_br if rng.random() > eps else d_prior

            # Add small deterministic perturbation for diversity.
            h = int(hashlib.md5(f"{case_id}:{r}".encode("utf-8")).hexdigest()[:8], 16) % 100
            if h < 8:
                p_s = STRATEGY_NAMES[(STRATEGY_INDEX[p_s] + 1) % len(STRATEGY_NAMES)]
            if h >= 92:
                d_s = STRATEGY_NAMES[(STRATEGY_INDEX[d_s] - 1) % len(STRATEGY_NAMES)]

            score = None
            round_score_payload = None
            if idx in api_indices:
                api_stats["api_calls"] += 1
                try:
                    round_resp = _api_run_one_round(
                        row=row,
                        p_s=p_s,
                        d_s=d_s,
                        evolution_method=evolution_method,
                    )
                    api_stats["api_success"] += 1
                    round_score_payload = round_resp.get("score", {})
                    score = {
                        "plaintiff_win_rate": float(round_score_payload.get("plaintiff_win_rate", 0.5)),
                        "defendant_win_rate": float(round_score_payload.get("defendant_win_rate", 0.5)),
                        "reasoning_quality": float(round_score_payload.get("reasoning_quality", 0.5)),
                        "evidence_strength": float(round_score_payload.get("evidence_strength", 0.5)),
                    }
                except Exception:
                    if execution_mode == "api":
                        raise
                    api_stats["api_fallback_local"] += 1

            if score is None:
                rng_seed = int(hashlib.md5(f"{case_id}:{r}:score".encode("utf-8")).hexdigest()[:8], 16)
                score = score_from_case(row, random.Random(rng_seed))

            record_round_weighted(tracker, p_s, d_s, score, weights)

            round_records.append(
                {
                    "round": r + 1,
                    "case_id": case_id,
                    "cause": cause,
                    "sampled_category": cat,
                    "plaintiff_strategy": p_s,
                    "defendant_strategy": d_s,
                    "plaintiff_prior": p_prior,
                    "defendant_prior": d_prior,
                    "api_score_used": round_score_payload is not None,
                }
            )

        last_round_records = round_records

    return last_round_records, api_stats


def build_initial_distributions() -> Dict[str, Dict[str, float]]:
    return {
        "uniform": {s: 1.0 / len(STRATEGY_NAMES) for s in STRATEGY_NAMES},
        "cooperative_bias": {
            "competing": 0.10,
            "collaborating": 0.35,
            "compromising": 0.20,
            "avoiding": 0.10,
            "accommodating": 0.25,
        },
        "competitive_bias": {
            "competing": 0.40,
            "collaborating": 0.10,
            "compromising": 0.25,
            "avoiding": 0.15,
            "accommodating": 0.10,
        },
        "compromise_bias": {
            "competing": 0.10,
            "collaborating": 0.15,
            "compromising": 0.45,
            "avoiding": 0.15,
            "accommodating": 0.15,
        },
    }


def compute_sr_ecr(
    history: List[Dict[str, Any]],
    payoff_p: List[List[float]],
    payoff_d: List[List[float]],
    window: int,
) -> Dict[str, float]:
    if not history:
        return {"sr": 0.0, "ecr": 0.0, "window": float(window)}

    eq_pairs = set()
    for i in range(len(STRATEGY_NAMES)):
        for j in range(len(STRATEGY_NAMES)):
            p_br = max(range(len(STRATEGY_NAMES)), key=lambda k: payoff_p[k][j])
            d_br = max(range(len(STRATEGY_NAMES)), key=lambda k: payoff_d[i][k])
            if p_br == i and d_br == j:
                eq_pairs.add((STRATEGY_NAMES[i], STRATEGY_NAMES[j]))

    sr_scores: List[float] = []
    in_eq = 0
    for row in history:
        p = row["plaintiff_strategy"]
        d = row["defendant_strategy"]
        i = STRATEGY_INDEX[p]
        j = STRATEGY_INDEX[d]

        p_opt = STRATEGY_NAMES[max(range(len(STRATEGY_NAMES)), key=lambda k: payoff_p[k][j])]
        d_opt = STRATEGY_NAMES[max(range(len(STRATEGY_NAMES)), key=lambda k: payoff_d[i][k])]
        hit = 0.5 * (1.0 if p == p_opt else 0.0) + 0.5 * (1.0 if d == d_opt else 0.0)
        sr_scores.append(hit)
        if (p, d) in eq_pairs:
            in_eq += 1

    ecr = in_eq / len(history)
    return {
        "sr": round(sum(sr_scores) / len(sr_scores), 4),
        "ecr": round(ecr, 4),
        "window": float(window),
    }


def permutation_pvalue(spne_hits: List[int], ne_hits: List[int], seed: int, n_perm: int = 5000) -> float:
    rng = random.Random(seed)
    diffs = [a - b for a, b in zip(spne_hits, ne_hits)]
    observed = abs(sum(diffs) / len(diffs)) if diffs else 0.0
    if not diffs:
        return 1.0

    count = 0
    for _ in range(n_perm):
        signed = [d if rng.random() < 0.5 else -d for d in diffs]
        stat = abs(sum(signed) / len(signed))
        if stat >= observed:
            count += 1
    return (count + 1) / (n_perm + 1)


def bootstrap_ci_delta(spne_hits: List[int], ne_hits: List[int], seed: int, n_boot: int = 2000) -> Tuple[float, float]:
    rng = random.Random(seed)
    n = len(spne_hits)
    if n == 0:
        return (0.0, 0.0)
    deltas: List[float] = []
    for _ in range(n_boot):
        idxs = [rng.randrange(n) for _ in range(n)]
        s = sum(spne_hits[i] for i in idxs) / n
        q = sum(ne_hits[i] for i in idxs) / n
        deltas.append(s - q)
    deltas.sort()
    lo = deltas[int(0.025 * n_boot)]
    hi = deltas[int(0.975 * n_boot)]
    return (round(lo, 4), round(hi, 4))


def save_plots(out_dir: Path, step1: Dict[str, Any], step2: Dict[str, Any]) -> List[str]:
    plt_mod = get_matplotlib_pyplot()
    if plt_mod is None:
        return []

    created: List[str] = []

    # Plot 1: SPNE vs NE accuracy by cause.
    cause_rows = step1["by_cause"]
    labels = list(cause_rows.keys())
    spne_vals = [cause_rows[k]["spne_acc"] for k in labels]
    ne_vals = [cause_rows[k]["ne_acc"] for k in labels]
    x = list(range(len(labels)))
    width = 0.35

    fig, ax = plt_mod.subplots(figsize=(9, 4.8))
    ax.bar([i - width / 2 for i in x], spne_vals, width=width, label="SPNE")
    ax.bar([i + width / 2 for i in x], ne_vals, width=width, label="NE")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Accuracy")
    ax.set_title("Step 1: SPNE vs NE Accuracy by Cause")
    ax.legend()
    fig.tight_layout()
    p1 = out_dir / "step1_spne_vs_ne_accuracy.png"
    fig.savefig(p1, dpi=180)
    plt_mod.close(fig)
    created.append(str(p1))

    # Plot 2: Replicator trajectory.
    hist = step2["overall_evolution"]["history"]
    gens = [h["generation"] for h in hist]
    fig, ax = plt_mod.subplots(figsize=(9, 5))
    for s in STRATEGY_NAMES:
        ys = [h["distribution"].get(s, 0.0) for h in hist]
        ax.plot(gens, ys, label=s)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Population Share")
    ax.set_ylim(0, 1)
    ax.set_title("Step 2: Replicator Dynamics Trajectory")
    ax.legend(fontsize=8)
    fig.tight_layout()
    p2 = out_dir / "step2_replicator_trajectory.png"
    fig.savefig(p2, dpi=180)
    plt_mod.close(fig)
    created.append(str(p2))

    # Plot 3: Shannon entropy.
    ent = [h["shannon_entropy"] for h in hist]
    fig, ax = plt_mod.subplots(figsize=(8.5, 4.5))
    ax.plot(gens, ent, color="#3366cc")
    ax.set_xlabel("Generation")
    ax.set_ylabel("Shannon Entropy")
    ax.set_title("Step 2: Shannon Entropy over Generations")
    fig.tight_layout()
    p3 = out_dir / "step2_shannon_entropy.png"
    fig.savefig(p3, dpi=180)
    plt_mod.close(fig)
    created.append(str(p3))

    return created


def run_experiment(
    args: argparse.Namespace,
    rows: List[Dict[str, Any]],
    out_dir: Path,
    *,
    cause_filters: Optional[List[str]] = None,
    input_path: Path,
) -> Path:
    project_root = PROJECT_ROOT
    sampled = stratified_sample(rows, n=args.n, seed=args.seed)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: SPNE vs NE comparison.
    tracker = NashEquilibriumTracker()
    case_records: List[Dict[str, Any]] = []
    by_cause_cases: Dict[str, List[Dict[str, Any]]] = {}

    # Run iterative tournament and evaluate on last-round realized strategies.
    weights = parse_weights(args.payoff_weights)
    case_records, api_stats = run_tournament_rounds(
        tracker=tracker,
        sampled=sampled,
        rounds=args.rounds,
        seed=args.seed,
        execution_mode=args.execution_mode,
        api_base=args.api_base,
        max_api_calls_per_round=args.max_api_calls_per_round,
        api_timeout=args.api_timeout,
        evolution_method=args.evolution_method,
        weights=weights,
    )
    for rec in case_records:
        by_cause_cases.setdefault(rec["sampled_category"], []).append(rec)

    ef = ExtensiveFormGame(tracker)
    ef_res = ef.full_analysis().to_dict()
    ne_pair = (
        ef_res["ne"]["plaintiff_strategy"],
        ef_res["ne"]["defendant_strategy"],
    )
    spne_pair = (
        ef_res["spne"]["plaintiff_strategy"],
        ef_res["spne"]["defendant_best_responses"][ef_res["spne"]["plaintiff_strategy"]],
    )

    spne_hits: List[int] = []
    ne_hits: List[int] = []
    for rec in case_records:
        p_obs = rec["plaintiff_strategy"]
        d_obs = rec["defendant_strategy"]
        # Sequential (SPNE-like): evaluate defendant response conditioned on observed plaintiff action.
        d_spne_pred = ef_res["spne"]["defendant_best_responses"].get(p_obs, spne_pair[1])
        # Static (NE-like): evaluate against one static equilibrium response.
        d_ne_pred = ne_pair[1]
        spne_hits.append(1 if d_obs == d_spne_pred else 0)
        ne_hits.append(1 if d_obs == d_ne_pred else 0)

    overall_sr_ecr = compute_sr_ecr(tracker._history, tracker._payoff_p, tracker._payoff_d, window=args.window)
    p_value = permutation_pvalue(spne_hits, ne_hits, seed=args.seed)
    ci_low, ci_high = bootstrap_ci_delta(spne_hits, ne_hits, seed=args.seed)

    by_cause: Dict[str, Any] = {}
    for cat, arr in by_cause_cases.items():
        ch_spne = []
        ch_ne = []
        ch_hist = []
        for rec in arr:
            p_obs = rec["plaintiff_strategy"]
            d_obs = rec["defendant_strategy"]
            d_spne_pred = ef_res["spne"]["defendant_best_responses"].get(p_obs, spne_pair[1])
            d_ne_pred = ne_pair[1]
            ch_spne.append(1 if d_obs == d_spne_pred else 0)
            ch_ne.append(1 if d_obs == d_ne_pred else 0)
            ch_hist.append({
                "plaintiff_strategy": rec["plaintiff_strategy"],
                "defendant_strategy": rec["defendant_strategy"],
            })
        ch_metrics = compute_sr_ecr(ch_hist, tracker._payoff_p, tracker._payoff_d, window=args.window)
        by_cause[cat] = {
            "n": len(arr),
            "spne_acc": round(sum(ch_spne) / len(ch_spne), 4) if ch_spne else 0.0,
            "ne_acc": round(sum(ch_ne) / len(ch_ne), 4) if ch_ne else 0.0,
            "delta": round((sum(ch_spne) - sum(ch_ne)) / len(ch_spne), 4) if ch_spne else 0.0,
            "sr": ch_metrics["sr"],
            "ecr": ch_metrics["ecr"],
        }

    step1 = {
        "sample_size": len(sampled),
        "rounds": args.rounds,
        "predictions": {
            "spne_pair": {"plaintiff": spne_pair[0], "defendant": spne_pair[1]},
            "ne_pair": {"plaintiff": ne_pair[0], "defendant": ne_pair[1]},
        },
        "overall": {
            "spne_acc": round(sum(spne_hits) / len(spne_hits), 4) if spne_hits else 0.0,
            "ne_acc": round(sum(ne_hits) / len(ne_hits), 4) if ne_hits else 0.0,
            "delta_spne_minus_ne": round((sum(spne_hits) - sum(ne_hits)) / len(spne_hits), 4) if spne_hits else 0.0,
            "sr": overall_sr_ecr["sr"],
            "ecr": overall_sr_ecr["ecr"],
            "permutation_pvalue": round(p_value, 6),
            "delta_95ci": [ci_low, ci_high],
        },
        "by_cause": by_cause,
        "analysis": ef_res,
        "case_records": case_records,
    }

    # Step 2: ESS stability verification.
    evo = EvolutionaryDynamics(tracker, asymmetric=True)
    evo_res = evo.simulate_evolution(generations=args.evo_generations, dt=0.15, convergence_threshold=5e-4)
    overall_ess = evo_res.ess_analysis.to_dict()

    init_sets = build_initial_distributions()
    multi_init: Dict[str, Any] = {}
    for name, dist in init_sets.items():
        r = EvolutionaryDynamics(tracker, asymmetric=True).simulate_evolution(
            generations=args.evo_generations,
            dt=0.15,
            convergence_threshold=5e-4,
            initial_distribution=dist,
        )
        multi_init[name] = {
            "converged": r.converged,
            "convergence_generation": r.convergence_generation,
            "ess_strategy": r.ess_analysis.ess_strategy,
            "final_distribution": {k: round(v, 4) for k, v in r.final_distribution.items()},
        }

    by_cause_evolution: Dict[str, Any] = {}
    for cat, arr in by_cause_cases.items():
        c_tracker = NashEquilibriumTracker()
        for rec in arr:
            rng_seed = int(hashlib.md5(rec["case_id"].encode("utf-8")).hexdigest()[:8], 16)
            rng = random.Random(rng_seed)
            row = next((x for x in sampled if str(x.get("case_id", "")) == rec["case_id"]), None)
            if row is None:
                continue
            c_tracker.record_round(
                rec["plaintiff_strategy"],
                rec["defendant_strategy"],
                score_from_case(row, rng),
            )
        c_ef = ExtensiveFormGame(c_tracker).full_analysis().to_dict()
        c_spne = c_ef["spne"]["plaintiff_strategy"]
        c_evo = EvolutionaryDynamics(c_tracker, asymmetric=True).simulate_evolution(
            generations=args.evo_generations,
            dt=0.15,
            convergence_threshold=5e-4,
        )
        c_ess = c_evo.ess_analysis.to_dict()
        by_cause_evolution[cat] = {
            "n": len(arr),
            "converged": c_evo.converged,
            "convergence_generation": c_evo.convergence_generation,
            "ess_strategy": c_ess.get("ess_strategy"),
            "spne_plaintiff_strategy": c_spne,
            "ess_consistent_with_spne": c_ess.get("ess_strategy") == c_spne,
            "final_distribution": {k: round(v, 4) for k, v in c_evo.final_distribution.items()},
        }

    step2 = {
        "overall_evolution": {
            "converged": evo_res.converged,
            "convergence_generation": evo_res.convergence_generation,
            "final_distribution": {k: round(v, 4) for k, v in evo_res.final_distribution.items()},
            "ess": overall_ess,
            "shannon_entropy_initial": evo_res.history[0].shannon_entropy if evo_res.history else None,
            "shannon_entropy_final": evo_res.history[-1].shannon_entropy if evo_res.history else None,
            "history": [h.to_dict() for h in evo_res.history],
        },
        "multi_initial_distributions": multi_init,
        "spne_consistency": overall_ess.get("ess_strategy") == spne_pair[0],
        "by_cause": by_cause_evolution,
    }

    plots = save_plots(out_dir, step1, step2)

    (out_dir / "step1_spne_vs_ne.json").write_text(
        json.dumps(step1, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "step2_ess_validation.json").write_text(
        json.dumps(step2, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = {
        "input": str(input_path),
        "input_total_rows": len(rows),
        "cause_filters": cause_filters or [],
        "available_categories": list_categories(rows),
        "sample_size": len(sampled),
        "rounds": args.rounds,
        "execution_mode": args.execution_mode,
        "evolution_method": args.evolution_method,
        "payoff_weights": {
            "win": weights[0],
            "reason": weights[1],
            "evidence": weights[2],
        },
        "api_integration": api_stats,
        "seed": args.seed,
        "window": args.window,
        "evo_generations": args.evo_generations,
        "step1_overall": step1["overall"],
        "step2_overall": {
            "converged": step2["overall_evolution"]["converged"],
            "convergence_generation": step2["overall_evolution"]["convergence_generation"],
            "ess_strategy": step2["overall_evolution"]["ess"].get("ess_strategy"),
            "spne_consistency": step2["spne_consistency"],
        },
        "plots": plots,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return out_dir


def run(args: argparse.Namespace) -> Path:
    project_root = PROJECT_ROOT
    input_path = project_root / args.input
    all_rows = load_jsonl(input_path)
    cause_filters = parse_category_list(args.cause_categories) if getattr(args, "cause_categories", "") else []

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    root_dir = project_root / "evaluation" / "results" / f"two_step_small_sample_{timestamp}"

    if args.split_by_cause:
        categories = cause_filters or list_categories(all_rows)
        root_dir.mkdir(parents=True, exist_ok=True)
        manifest: Dict[str, Any] = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "input": str(input_path),
            "mode": "split_by_cause",
            "categories": categories,
            "runs": [],
        }
        for category in categories:
            filtered_rows = filter_rows_by_categories(all_rows, [category])
            out_dir = root_dir / slugify_category(category)
            run_out = run_experiment(
                args,
                filtered_rows,
                out_dir,
                cause_filters=[category],
                input_path=input_path,
            )
            manifest["runs"].append(
                {
                    "category": category,
                    "row_count": len(filtered_rows),
                    "output_dir": str(run_out),
                    "summary_path": str((run_out / "summary.json").as_posix()),
                }
            )

        manifest_path = root_dir / "split_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"root_dir": str(root_dir.as_posix()), "manifest": str(manifest_path.as_posix())}, ensure_ascii=False, indent=2))
        return root_dir

    rows = filter_rows_by_categories(all_rows, cause_filters)
    if cause_filters and not rows:
        raise ValueError(f"No rows matched cause filters: {cause_filters}")
    return run_experiment(
        args,
        rows,
        root_dir,
        cause_filters=cause_filters,
        input_path=input_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run two-step experiment on prepared small sample dataset")
    parser.add_argument(
        "--input",
        default="data/dataset_1000/small_sample_100_three_causes.jsonl",
        help="jsonl input path relative to project root",
    )
    parser.add_argument("--n", type=int, default=100, help="sample size to run")
    parser.add_argument("--rounds", type=int, default=12, help="iterative tournament rounds")
    parser.add_argument(
        "--execution-mode",
        choices=["local", "api", "api_hybrid"],
        default="api_hybrid",
        help="execution backend mode",
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="mock court system API base URL")
    parser.add_argument("--max-api-calls-per-round", type=int, default=3, help="max API-backed cases per round")
    parser.add_argument("--api-timeout", type=int, default=180, help="API timeout seconds")
    parser.add_argument(
        "--evolution-method",
        choices=["best_response", "fictitious_play", "llm_reflection"],
        default="best_response",
        help="strategy evolution method passed to API per round",
    )
    parser.add_argument(
        "--payoff-weights",
        default="0.5,0.25,0.25",
        help="payoff weights for win,reason,evidence (sum=1), e.g. 0.5,0.25,0.25",
    )
    parser.add_argument("--seed", type=int, default=20260419, help="random seed")
    parser.add_argument("--window", type=int, default=3, help="ECR window size")
    parser.add_argument("--evo-generations", type=int, default=50, help="replicator generations")
    parser.add_argument(
        "--cause-categories",
        default="",
        help="comma-separated sampled_category values to keep, e.g. 民间借贷,劳动争议,交通事故",
    )
    parser.add_argument(
        "--split-by-cause",
        action="store_true",
        help="run one experiment per cause category and write a split manifest",
    )
    args = parser.parse_args()
    out_dir = run(args)
    print(f"two-step experiment completed: {out_dir}")


if __name__ == "__main__":
    main()
