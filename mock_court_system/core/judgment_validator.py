"""
判决 JSON 校验器：区分"语义有效"与"仅 HTTP 成功"。

背景：llm_client.chat_json 在 LLM 失败时返回 {}，GameEngine 评分把缺失
字段默认为 0.5，导致技术成功但语义失败的样本污染实验与前端展示。
本模块显式定义结构化判决的必需字段，校验失败打上 degraded/failed 标记。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# 结构化判决必需的顶层字段（judgment_chain 的输出契约）
REQUIRED_FIELDS = ("fact_finding", "dispute_focus", "legal_analysis", "judgment_result")
# 建议字段：缺失时降级但不阻断
OPTIONAL_FIELDS = ("applicable_laws", "liability_mapping")


def validate_judgment(judgment: Any) -> Tuple[str, List[str]]:
    """校验判决 JSON。

    Returns:
        (status, missing) — status 为 "ok" | "degraded" | "failed"：
        - ok:       全部必需字段存在且非空；
        - degraded: 缺少建议字段或个别必需字段为空，但有部分有效内容；
        - failed:   不是 dict，或全部必需字段缺失。
    """
    if not isinstance(judgment, dict) or not judgment:
        return "failed", list(REQUIRED_FIELDS)

    missing_required = [
        f for f in REQUIRED_FIELDS
        if not str(judgment.get(f) or "").strip()
        and not (isinstance(judgment.get(f), list) and judgment.get(f))
    ]
    missing_optional = [
        f for f in OPTIONAL_FIELDS
        if not judgment.get(f)
    ]

    if len(missing_required) == len(REQUIRED_FIELDS):
        return "failed", missing_required + missing_optional
    if missing_required:
        return "degraded", missing_required + missing_optional
    if missing_optional:
        return "degraded", missing_optional
    return "ok", []


def judgment_status_label(judgment: Any) -> str:
    """简短标签：ok / degraded / failed（用于响应与日志）。"""
    return validate_judgment(judgment)[0]


# ---------- 法条回查（Verified RAG 最小版） ----------

_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def cn_to_int(text: str) -> int:
    """中文数字转整数（支持 第X条 / 第X百X十X条 常见形态）。"""
    text = text.strip().replace("两", "二")
    total, current = 0, 0
    for ch in text:
        if ch in _CN_DIGITS:
            current = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            total += (current or 1) * unit
            current = 0
        else:
            return -1
    return total + current


def _parse_citation(law_ref: str) -> "tuple[str | None, int | None]":
    """从 '《中华人民共和国民法典》第676条' 解析 (法律名, 条号)。"""
    import re
    name = None
    m = re.search(r"《([^》]+)》", law_ref)
    if m:
        name = m.group(1)
    article = None
    m = re.search(r"第([\d零一二三四五六七八九十百千两]+)条", law_ref)
    if m:
        raw = m.group(1)
        article = int(raw) if raw.isdigit() else (cn_to_int(raw) or None)
    return name, article


def verify_citations(judgment: Dict[str, Any], law_db_path: str) -> Dict[str, Any]:
    """回查判决引用的法条是否在法条库中真实存在。

    对 judgment["applicable_laws"] 中每条引用解析法律名+条号，
    与 legal_articles.db 的 articles(law_name, article_number) 比对。
    未命中的引用标记 unverified——防止模型编造法条编号。
    """
    import re
    import sqlite3

    laws = (judgment or {}).get("applicable_laws") or []
    if not isinstance(laws, list) or not laws:
        return {"checked": 0, "verified": 0, "unverified": []}

    # 预载库内 (law_name, article_number) 集合
    try:
        conn = sqlite3.connect(law_db_path)
        rows = conn.execute("SELECT law_name, article_number FROM articles").fetchall()
        conn.close()
    except Exception:
        return {"checked": 0, "verified": 0, "unverified": [], "error": "law db unavailable"}
    known = {(str(r[0]), str(r[1])) for r in rows}
    # 同名法律的条号集合（处理法条名不带书名号的情况）
    by_name: Dict[str, set] = {}
    for ln, an in known:
        by_name.setdefault(ln, set()).add(str(an))

    checked = verified = 0
    unverified: List[Dict[str, Any]] = []
    for item in laws:
        ref = str((item or {}).get("law", ""))
        if not ref:
            continue
        checked += 1
        name, article = _parse_citation(ref)
        hit = False
        if article is not None:
            art = str(article)
            if name and (name, art) in known:
                hit = True
            elif name:
                # 条号在同一名称下存在即认可（编号书写差异兜底）
                hit = art in by_name.get(name, set())
            else:
                hit = any(art in s for s in by_name.values())
        if hit:
            verified += 1
            if isinstance(item, dict):
                item["verified"] = True
        else:
            unverified.append(ref)
            if isinstance(item, dict):
                item["verified"] = False

    return {"checked": checked, "verified": verified, "unverified": unverified}
