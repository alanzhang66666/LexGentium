# -*- coding: utf-8 -*-
"""
导出动图（A 与 B 各一份 GIF+MP4）

A: 单次 full-simulation（CD→DD→CI）
B: tournament 多轮 full-simulation（每轮一帧趋势图）

数据：从 small_sample_100_three_causes.jsonl 里自动挑一个“较短”案件（运行更快）

输出目录：
  results/animations/<case_id>/
    A_frames/*.png + animation_A.gif + animation_A.mp4 + result_A.json
    B_frames/*.png + animation_B.gif + animation_B.mp4 + result_B.json

运行：
  python scripts/export_case_animations.py
"""

from __future__ import annotations

import json
import os
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import imageio.v2 as imageio


BACKEND_BASE = os.environ.get("COURT_API_BASE_URL", "http://127.0.0.1:8000")
JSONL = Path(__file__).resolve().parent.parent / "data" / "dataset_1000" / "small_sample_100_three_causes.jsonl"
OUTROOT = Path(__file__).resolve().parent.parent / "results" / "animations"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _setup_fonts() -> None:
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def pick_case(max_desc_len: int = 500) -> Dict[str, Any]:
    """
    从 jsonl 选择一个相对短的案件，减少运行时间。
    """
    best: Optional[Dict[str, Any]] = None
    best_len = 10**18
    with JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            desc = obj.get("case_description") or ""
            l = len(desc)
            if l < best_len and l <= max_desc_len:
                best = obj
                best_len = l
    if best is None:
        # fallback: 第一条
        with JSONL.open("r", encoding="utf-8") as f:
            best = json.loads(next(f))
    return best


def start_full_simulation(case_info: Dict[str, Any], mode: str, tournament_rounds: int = 3) -> str:
    payload: Dict[str, Any] = {"case_info": case_info, "mode": mode, "tournament_rounds": tournament_rounds}
    r = requests.post(f"{BACKEND_BASE}/case/full-simulation", json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    task_id = data.get("task_id") or data.get("taskId") or data.get("id")
    if not task_id:
        raise RuntimeError(f"无法从响应中获取 task_id: {data}")
    return str(task_id)

def _read_env_llm_config() -> Dict[str, str]:
    """
    读取 .env 中的 LLM 配置（用于导出后恢复）。
    不会打印密钥。
    """
    cfg = {"provider": "", "api_key": "", "base_url": "", "model": "", "temperature": "0.1", "max_tokens": "4096", "timeout": "60"}
    if not ENV_PATH.exists():
        return cfg
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k == "LLM_PROVIDER":
            cfg["provider"] = v
        elif k == "LLM_API_KEY":
            cfg["api_key"] = v
        elif k == "LLM_BASE_URL":
            cfg["base_url"] = v
        elif k == "LLM_MODEL":
            cfg["model"] = v
    return cfg


def _set_backend_llm_config(cfg: Dict[str, Any]) -> None:
    """
    调用后端 /config/llm 更新配置（会持久化到 .env）。
    """
    payload = {
        "provider": cfg.get("provider") or "deepseek",
        "api_key": cfg.get("api_key", ""),
        "base_url": cfg.get("base_url") or "http://localhost",
        "model": cfg.get("model") or "deepseek-chat",
        "temperature": float(cfg.get("temperature", 0.1)),
        "max_tokens": int(cfg.get("max_tokens", 4096)),
        "timeout": int(cfg.get("timeout", 60)),
    }
    r = requests.post(f"{BACKEND_BASE}/config/llm", json=payload, timeout=60)
    r.raise_for_status()


def poll_task(task_id: str, poll_s: float = 1.5, timeout_s: int = 1200) -> Dict[str, Any]:
    start = time.time()
    last = None
    while True:
        r = requests.get(f"{BACKEND_BASE}/case/full-simulation/{task_id}", timeout=60)
        r.raise_for_status()
        data = r.json()
        last = data
        status = data.get("status")
        if status == "completed":
            return data
        if status == "failed":
            raise RuntimeError(f"任务失败: {data.get('message') or data}")
        if time.time() - start > timeout_s:
            raise TimeoutError(f"超时未完成: {task_id}")
        time.sleep(poll_s)


def _wrap(s: str, width: int = 52, max_lines: int = 14) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    lines: List[str] = []
    for para in s.splitlines():
        para = para.strip()
        if not para:
            continue
        lines.extend(textwrap.wrap(para, width=width))
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + ["…"]
    return "\n".join(lines)


def _frame_card(title: str, subtitle: str, body: str, out_path: Path) -> None:
    fig = plt.figure(figsize=(12.8, 7.2))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    ax.text(0.04, 0.93, title, fontsize=20, fontweight="bold", ha="left", va="top", color="#1F2937")
    ax.text(0.04, 0.885, subtitle, fontsize=12.5, ha="left", va="top", color="#4B5563")

    ax.add_patch(plt.Rectangle((0.04, 0.08), 0.92, 0.76, facecolor="#F8FAFC", edgecolor="#E5E7EB", linewidth=1.2))
    ax.text(0.06, 0.80, body, fontsize=12.5, ha="left", va="top", color="#111827", family="sans-serif")

    fig.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def render_A_frames(case_obj: Dict[str, Any], result: Dict[str, Any], out_dir: Path) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    frames: List[Path] = []

    case_id = str(case_obj.get("case_id", "case"))
    cause = str(case_obj.get("sampled_category", ""))
    desc = _wrap(str(case_obj.get("case_description", "")), width=58, max_lines=16)
    claims = case_obj.get("plaintiff_claims") or []
    claims_txt = "\n".join([f"- {c}" for c in claims[:4]])

    intro = f"案号：{case_id}\n案由：{cause}\n\n【事实摘要】\n{desc}\n\n【诉请（节选）】\n{_wrap(claims_txt, width=58, max_lines=10)}"
    p = out_dir / "000_intro.png"
    _frame_card("A｜同案三场景：CD→DD→CI", "输入案件信息", intro, p)
    frames.append(p)

    sim = result.get("result") or {}
    for idx, key, label in [
        (10, "cd_result", "CD：起诉状生成"),
        (20, "dd_result", "DD：答辩状生成"),
        (30, "ci_result", "CI：裁判文书生成"),
    ]:
        stage = sim.get(key) or {}
        doc = _wrap(str(stage.get("final_document", "")), width=58, max_lines=22)
        turns = stage.get("dialog_history") or []
        meta = stage.get("metadata") or {}
        meta_keys = list(meta.keys())[:6]
        meta_txt = ", ".join(meta_keys) if meta_keys else "-"
        body = f"【文书预览】\n{doc}\n\n【对话轮次】{len(turns)}\n【metadata字段】{meta_txt}"
        fp = out_dir / f"{idx:03d}_{key}.png"
        _frame_card("A｜同案三场景：CD→DD→CI", label, body, fp)
        frames.append(fp)

    elapsed = sim.get("elapsed_seconds")
    summary = f"三场景已完成。\n\n- elapsed_seconds: {elapsed}\n- 返回字段: {', '.join([k for k in sim.keys() if k.endswith('_result')])}"
    sp = out_dir / "040_summary.png"
    _frame_card("A｜同案三场景：CD→DD→CI", "汇总", summary, sp)
    frames.append(sp)
    return frames


def render_B_frames(case_obj: Dict[str, Any], result: Dict[str, Any], out_dir: Path) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    frames: List[Path] = []

    sim = result.get("result") or {}
    rounds = sim.get("rounds") or []
    if not rounds:
        # fallback: 单帧提示
        fp = out_dir / "000_no_rounds.png"
        _frame_card("B｜锦标赛演化（按轮次）", "未返回 rounds 字段", "请确认 mode=tournament 且后端正常返回 rounds[]。", fp)
        return [fp]

    # 累计曲线：用 score 中的四个字段
    keys = ["plaintiff_win_rate", "defendant_win_rate", "reasoning_quality", "evidence_strength"]
    colors = ["#2563EB", "#DC2626", "#059669", "#7C3AED"]

    def get_score(rnd: Dict[str, Any], k: str) -> float:
        try:
            return float(((rnd.get("score") or {}).get(k)) or 0.0)
        except Exception:
            return 0.0

    for i in range(len(rounds)):
        xs = np.arange(i + 1)
        ys = {k: [get_score(rounds[j], k) for j in range(i + 1)] for k in keys}

        fig, ax = plt.subplots(figsize=(12.8, 7.2))
        ax.set_title("B｜锦标赛演化：轮次趋势（同一案件）", fontsize=18, fontweight="bold")
        for k, c in zip(keys, colors):
            ax.plot(xs, ys[k], marker="o", lw=2.6, color=c, label=k)
        ax.set_xlabel("round_index")
        ax.set_ylabel("score")
        ax.grid(True, ls="--", alpha=0.25)
        ax.legend(loc="upper left")

        # 右侧信息卡
        rnd = rounds[i]
        ridx = rnd.get("round_index", i)
        elapsed = rnd.get("elapsed_seconds")
        case_id = case_obj.get("case_id")
        cause = case_obj.get("sampled_category")
        info = f"case_id: {case_id}\n案由: {cause}\nround_index: {ridx}\nelapsed_seconds: {elapsed}"
        fig.text(0.72, 0.78, info, ha="left", va="top", fontsize=12, bbox=dict(boxstyle="round,pad=0.4", fc="#F8FAFC", ec="#E5E7EB"))

        fp = out_dir / f"{i:03d}_round.png"
        fig.savefig(fp, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        frames.append(fp)

    return frames


def export_gif(frames: List[Path], out_path: Path, fps: float = 1.0) -> None:
    imgs = [imageio.imread(p) for p in frames]
    imageio.mimsave(out_path, imgs, duration=1.0 / fps)


def export_mp4(frames: List[Path], out_path: Path, fps: float = 1.0) -> None:
    writer = imageio.get_writer(out_path, fps=fps, codec="libx264", quality=8)
    try:
        for p in frames:
            writer.append_data(imageio.imread(p))
    finally:
        writer.close()


def main() -> None:
    _setup_fonts()
    OUTROOT.mkdir(parents=True, exist_ok=True)

    # 为避免外部 LLM 连接失败，临时切换后端到“离线回显模式”（LLM_API_KEY 置空）
    # 导出完成后恢复原配置（从 .env 读取）。
    original_llm = _read_env_llm_config()
    offline_llm = dict(original_llm)
    offline_llm["api_key"] = ""  # 触发 LLMClient 的回显模拟回复模式（不出网）

    case_obj = pick_case(max_desc_len=420)
    case_info = {
        "case_id": case_obj.get("case_id"),
        "case_description": case_obj.get("case_description"),
        "plaintiff_name": case_obj.get("plaintiff_name"),
        "defendant_name": case_obj.get("defendant_name"),
        "plaintiff_claims": case_obj.get("plaintiff_claims"),
    }

    case_id = str(case_obj.get("case_id", "case"))
    base_dir = OUTROOT / case_id
    base_dir.mkdir(parents=True, exist_ok=True)

    try:
        _set_backend_llm_config(offline_llm)

        # A: single
        taskA = start_full_simulation(case_info, mode="single", tournament_rounds=3)
        dataA = poll_task(taskA)
        (base_dir / "result_A.json").write_text(json.dumps(dataA, ensure_ascii=False, indent=2), encoding="utf-8")
        framesA = render_A_frames(case_obj, dataA, base_dir / "A_frames")
        export_gif(framesA, base_dir / "animation_A.gif", fps=1.0)
        export_mp4(framesA, base_dir / "animation_A.mp4", fps=1.0)

        # B: tournament（轮数略降，保证导出更稳）
        taskB = start_full_simulation(case_info, mode="tournament", tournament_rounds=8)
        dataB = poll_task(taskB)
        (base_dir / "result_B.json").write_text(json.dumps(dataB, ensure_ascii=False, indent=2), encoding="utf-8")
        framesB = render_B_frames(case_obj, dataB, base_dir / "B_frames")
        export_gif(framesB, base_dir / "animation_B.gif", fps=2.0)
        export_mp4(framesB, base_dir / "animation_B.mp4", fps=2.0)

        print("[OK] exported to:", base_dir)
    finally:
        # 恢复后端 LLM 配置（避免影响后续正常使用）
        try:
            if original_llm.get("api_key"):
                _set_backend_llm_config(original_llm)
        except Exception:
            pass


if __name__ == "__main__":
    main()

