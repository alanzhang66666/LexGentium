# -*- coding: utf-8 -*-
"""
三场景录制（前端风格）并导出 10-15s MP4

特点：
- 只录制 CD→DD→CI
- 读取 mock_court_system/.env 的后端与 LLM 配置
- 通过后端 /config/llm 应用 LLM 配置后，调用 /case/full-simulation 获取三阶段结果
- 以“前端卡片式UI”风格渲染 1920x1080 画面，按时间轴合成约 12s 的 MP4
- 三个场景的数据与画面生成分开（cd/dd/ci 三张主画面 + 统一合成）

运行：
  python scripts/record_scheme_A_frontend_like.py

输出：
  results/recordings/<case_id>/schemeA_frontend_like.mp4
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


ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
JSONL = ROOT / "data" / "dataset_1000" / "small_sample_100_three_causes.jsonl"
OUTROOT = ROOT / "results" / "recordings"


def _setup_fonts() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def _read_dotenv(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def pick_case(max_desc_len: int = 420) -> Dict[str, Any]:
    best: Optional[Dict[str, Any]] = None
    best_len = 10**18
    with JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            desc = obj.get("case_description") or ""
            l = len(desc)
            if l <= max_desc_len and l < best_len:
                best = obj
                best_len = l
    if best is None:
        with JSONL.open("r", encoding="utf-8") as f:
            best = json.loads(next(f))
    return best


def _wrap(s: str, width: int = 58, max_lines: int = 16) -> str:
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


def _llm_base_url(env: Dict[str, str]) -> str:
    base = (env.get("LLM_BASE_URL") or "").strip()
    if not base:
        raise RuntimeError("缺少 LLM_BASE_URL")
    return base.rstrip("/")


def _llm_headers(env: Dict[str, str]) -> Dict[str, str]:
    key = (env.get("LLM_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("检测到 .env 中 LLM_API_KEY 为空：无法调用大模型。")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _llm_chat(env: Dict[str, str], messages: List[Dict[str, str]], *, temperature: float = 0.2, max_tokens: int = 900) -> str:
    """
    直接调用 OpenAI 兼容 chat/completions（用于硅基流动等网关），避免 full-simulation 卡住。
    """
    url = f"{_llm_base_url(env)}/chat/completions"
    payload = {
        "model": env.get("LLM_MODEL") or "gpt-4o-mini",
        "messages": messages,
        "temperature": float(env.get("LLM_TEMPERATURE") or temperature),
        "max_tokens": int(env.get("LLM_MAX_TOKENS") or max_tokens),
    }
    timeout_s = int(env.get("LLM_TIMEOUT") or 180)
    last_err: Optional[Exception] = None
    for _attempt in range(3):
        try:
            r = requests.post(url, headers=_llm_headers(env), json=payload, timeout=timeout_s)
            r.raise_for_status()
            data = r.json()
            return (data.get("choices", [{}])[0].get("message", {}) or {}).get("content", "") or ""
        except Exception as e:
            last_err = e
            time.sleep(1.2)
    raise RuntimeError(f"LLM 请求失败（重试后仍失败）: {last_err}")


def gen_cd_doc(env: Dict[str, str], case_info: Dict[str, Any]) -> str:
    sys = (
        "你是一名中国民事律师。请根据案件信息直接生成一份完整、规范的《民事起诉状》。"
        "必须满足：第一行标题严格为“民事起诉状”（不加案号、不加空格）。"
        "请控制全文在 600-900 字以内，信息齐全但不冗长。"
    )
    user = f"案件信息(JSON)：\n{json.dumps(case_info, ensure_ascii=False, indent=2)}"
    return _llm_chat(env, [{"role": "system", "content": sys}, {"role": "user", "content": user}], temperature=0.2, max_tokens=1800)


def gen_dd_doc(env: Dict[str, str], case_info: Dict[str, Any], cd_doc: str) -> str:
    sys = (
        "你是一名中国民事律师（被告代理人）。请根据案件信息与起诉状内容，直接生成一份完整、规范的《民事答辩状》。"
        "必须满足：第一行标题严格为“民事答辩状”（不加案号、不加空格）。"
        "请控制全文在 500-800 字以内。"
    )
    user = f"案件信息(JSON)：\n{json.dumps(case_info, ensure_ascii=False, indent=2)}\n\n起诉状：\n{cd_doc}"
    return _llm_chat(env, [{"role": "system", "content": sys}, {"role": "user", "content": user}], temperature=0.2, max_tokens=1800)


def gen_ci_doc(env: Dict[str, str], case_info: Dict[str, Any], cd_doc: str, dd_doc: str) -> str:
    sys = (
        "你是一名中国民事法官。请根据案件信息、起诉状与答辩状，生成一份简洁但结构完整的民事判决书。"
        "必须包含“【判决结果】”字段，并在开头包含“案号：”。"
        "请控制全文在 700-1100 字以内。"
    )
    user = (
        f"案件信息(JSON)：\n{json.dumps(case_info, ensure_ascii=False, indent=2)}\n\n"
        f"起诉状：\n{cd_doc}\n\n答辩状：\n{dd_doc}"
    )
    return _llm_chat(env, [{"role": "system", "content": sys}, {"role": "user", "content": user}], temperature=0.2, max_tokens=1800)


# -------------------- 渲染（前端趋同风格） --------------------

COL = {
    "bg": "#0B1220",
    "card": "#0F172A",  # slate-900
    "card2": "#0B1324",
    "border": "#1F2937",  # gray-800
    "muted": "#94A3B8",  # slate-400
    "text": "#E5E7EB",  # gray-200
    "title": "#F8FAFC",  # slate-50
    "blue": "#60A5FA",
    "green": "#34D399",
    "amber": "#FBBF24",
    "red": "#F87171",
}


def _card(ax, x: float, y: float, w: float, h: float, title: str, subtitle: str) -> None:
    from matplotlib.patches import FancyBboxPatch

    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.012,rounding_size=16",
            facecolor=COL["card"],
            edgecolor=COL["border"],
            linewidth=1.2,
        )
    )
    ax.text(x + 0.03 * w, y + h - 0.10 * h, title, fontsize=20, fontweight="bold", color=COL["title"], va="top")
    ax.text(x + 0.03 * w, y + h - 0.18 * h, subtitle, fontsize=12.5, color=COL["muted"], va="top")


def _render_scene(case_obj: Dict[str, Any], stage_label: str, stage_key: str, doc_text: str, out_path: Path) -> None:
    """
    生成单场景主画面（1920x1080），内容与前端卡片式布局接近。
    """
    fig = plt.figure(figsize=(19.2, 10.8), facecolor=COL["bg"])  # 1920x1080 @100dpi
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # 顶部信息条，并给正文留足空间避免遮挡
    badge_color = {"CD": COL["blue"], "DD": COL["amber"], "CI": COL["green"]}.get(stage_key, COL["blue"])
    sys_name = "legaflow｜基于扩展式博弈建模的多智能体协同模拟法庭系统"
    ax.text(0.04, 0.965, sys_name, fontsize=13, color=COL["muted"], va="top")
    ax.text(
        0.78,
        0.965,
        f"{stage_key}｜{stage_label}",
        fontsize=13,
        color=badge_color,
        va="top",
        ha="left",
        bbox=dict(boxstyle="round,pad=0.30", fc=COL["card2"], ec=COL["border"]),
    )

    # 左：案件卡
    _card(ax, 0.04, 0.10, 0.40, 0.78, "案件信息", "结构化字段摘要")
    case_id = str(case_obj.get("case_id", "CASE"))
    cause = str(case_obj.get("sampled_category", ""))
    desc = _wrap(str(case_obj.get("case_description", "")), width=40, max_lines=18)
    plaintiff = str(case_obj.get("plaintiff_name", "原告"))
    defendant = str(case_obj.get("defendant_name", "被告"))
    claims = case_obj.get("plaintiff_claims") or []
    claims_txt = "\n".join([f"- {c}" for c in claims[:4]])
    left_txt = f"case_id: {case_id}\n案由: {cause}\n原告: {plaintiff}\n被告: {defendant}\n\n【事实摘要】\n{desc}\n\n【诉请（节选）】\n{_wrap(claims_txt, width=40, max_lines=10)}"
    ax.text(0.06, 0.74, left_txt, fontsize=12.5, color=COL["text"], va="top", family="sans-serif")

    # 右：文书卡
    _card(ax, 0.48, 0.10, 0.48, 0.78, "文书内容", "模型生成（节选）")
    doc = _wrap(str(doc_text or ""), width=52, max_lines=26)
    if not doc:
        doc = "（暂无内容）"
    ax.text(0.50, 0.74, doc, fontsize=12.5, color=COL["text"], va="top", family="sans-serif")

    fig.savefig(out_path, dpi=100, facecolor=COL["bg"])
    plt.close(fig)


def _export_mp4_hold(frames: List[Tuple[Path, float]], out_mp4: Path, fps: int = 24) -> None:
    """
    frames: [(image_path, hold_seconds), ...]
    """
    writer = imageio.get_writer(out_mp4, fps=fps, codec="libx264", quality=8)
    try:
        for p, hold_s in frames:
            img = imageio.imread(p)
            n = max(1, int(round(hold_s * fps)))
            for _ in range(n):
                writer.append_data(img)
    finally:
        writer.close()

def _export_gif_hold(frames: List[Tuple[Path, float]], out_gif: Path, fps: int = 10) -> None:
    """
    导出 GIF（体积更敏感，默认用更低 fps）。
    frames: [(image_path, hold_seconds), ...]
    """
    imgs: List[np.ndarray] = []
    for p, hold_s in frames:
        img = imageio.imread(p)
        n = max(1, int(round(hold_s * fps)))
        for _ in range(n):
            imgs.append(img)
    # duration 是每帧秒数
    imageio.mimsave(out_gif, imgs, duration=1.0 / fps)

def _export_gif_single(image_path: Path, out_gif: Path, *, hold_s: float = 4.0, fps: int = 10) -> None:
    """
    将单张场景图导出为 GIF（通过重复帧实现停留时长）。
    """
    img = imageio.imread(image_path)
    n = max(1, int(round(hold_s * fps)))
    imgs = [img] * n
    imageio.mimsave(out_gif, imgs, duration=1.0 / fps)


def main() -> None:
    _setup_fonts()
    OUTROOT.mkdir(parents=True, exist_ok=True)

    env = _read_dotenv(ENV_PATH)
    backend = (env.get("COURT_API_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")

    # 强制要求真正调用大模型：必须在 .env 中配置 LLM_API_KEY
    if not (env.get("LLM_API_KEY") or "").strip():
        raise RuntimeError(
            "检测到 .env 中 LLM_API_KEY 为空：无法调用大模型。\n"
            "请将 Key 写入 mock_court_system/.env 的 LLM_API_KEY=... 后重试（不要在聊天里发送 Key）。"
        )

    # 可选：确认后端在线（用于“前后端适配录制”的环境一致性检查）
    try:
        requests.get(f"{backend}/health", timeout=2).raise_for_status()
    except Exception:
        pass

    case_obj = pick_case()
    case_info = {
        "case_id": case_obj.get("case_id"),
        "case_description": case_obj.get("case_description"),
        "plaintiff_name": case_obj.get("plaintiff_name"),
        "defendant_name": case_obj.get("defendant_name"),
        "plaintiff_claims": case_obj.get("plaintiff_claims"),
    }

    # 三个场景数据分开生成（避免 full-simulation 卡住）
    cd_doc = gen_cd_doc(env, case_info)
    dd_doc = gen_dd_doc(env, case_info, cd_doc)
    ci_doc = gen_ci_doc(env, case_info, cd_doc, dd_doc)

    case_id = str(case_obj.get("case_id", "CASE"))
    out_dir = OUTROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "schemeA_result.json").write_text(
        json.dumps(
            {"case_id": case_id, "CD": cd_doc, "DD": dd_doc, "CI": ci_doc},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # 三个场景画面分开生成
    cd_png = out_dir / "scene_CD.png"
    dd_png = out_dir / "scene_DD.png"
    ci_png = out_dir / "scene_CI.png"
    _render_scene(case_obj, "起诉状生成", "CD", cd_doc, cd_png)
    _render_scene(case_obj, "答辩状生成", "DD", dd_doc, dd_png)
    _render_scene(case_obj, "裁判文书生成", "CI", ci_doc, ci_png)

    # 合成 10-15 秒左右：总时长约 12 秒
    timeline = [
        (cd_png, 4.0),
        (dd_png, 4.0),
        (ci_png, 4.0),
    ]
    out_mp4 = out_dir / "schemeA_frontend_like.mp4"
    _export_mp4_hold(timeline, out_mp4, fps=24)
    out_gif = out_dir / "schemeA_frontend_like.gif"
    _export_gif_hold(timeline, out_gif, fps=10)

    # 额外：三个场景分别导出为独立 GIF（方便分别插入 PPT）
    _export_gif_single(cd_png, out_dir / "scene_CD.gif", hold_s=4.0, fps=10)
    _export_gif_single(dd_png, out_dir / "scene_DD.gif", hold_s=4.0, fps=10)
    _export_gif_single(ci_png, out_dir / "scene_CI.gif", hold_s=4.0, fps=10)

    print("[OK]", out_mp4)
    print("[OK]", out_gif)
    print("[OK]", out_dir / "scene_CD.gif")
    print("[OK]", out_dir / "scene_DD.gif")
    print("[OK]", out_dir / "scene_CI.gif")


if __name__ == "__main__":
    main()

