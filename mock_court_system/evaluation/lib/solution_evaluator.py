"""
AgentMediation Solution Evaluator + 争议原因分类体系 + 群体极化检测

基于 AgentMediation (2509.06586) 的 Solution Evaluator 和实验发现。

Solution Evaluator:
- 争议焦点识别质量（文本相似度评估）
- 法条引用召回率

争议原因分类体系:
- 5 大类 × 29 子类（论文 Figure 3 / Section 2, Appendix 2）

外部知识(EK)条件控制:
- 控制调解员/法官是否能访问法条检索系统

群体极化 & 表面共识检测:
- Group Polarization: NUM=ALL 时策略效果极化
- Surface-level Consensus: 高共识但低满意度模式
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger("solution_evaluator")

# ========== Solution Evaluator ==========

_SOLUTION_EVAL_PROMPT = """你是一位法律方案评测专家。请评估以下调解/判决方案的质量。

【案件争议焦点（参考标准）】
{reference_points}

【调解员/法官识别的争议焦点】
{predicted_points}

【参考法律依据】
{reference_laws}

【方案中引用的法律依据】
{predicted_laws}

请评估：
1. 争议焦点的识别准确性（与参考标准的匹配程度，0-10 分）
2. 争议焦点的覆盖完整性（是否遗漏关键焦点，0-10 分）
3. 法律依据的引用质量（是否援引了正确法条，0-10 分）
4. 方案的可行性和合理性（0-10 分）

输出 JSON：
{{"focus_accuracy": 0-10, "focus_coverage": 0-10, "legal_citation_quality": 0-10, "solution_feasibility": 0-10, "focus_matched": ["匹配的焦点"], "focus_missed": ["遗漏的焦点"], "laws_matched": ["匹配的法条"], "laws_missed": ["遗漏的法条"], "overall_score": 0-10, "reasoning": "评分依据"}}
"""


def compute_text_similarity_score(predicted: str, reference: str) -> float:
    """简化的文本相似度评分（字符级 ROUGE-L 近似）。"""
    if not predicted or not reference:
        return 0.0

    pred_chars = list(predicted.replace(" ", ""))
    ref_chars = list(reference.replace(" ", ""))

    if not pred_chars or not ref_chars:
        return 0.0

    # LCS 长度计算
    m, n = len(pred_chars), len(ref_chars)
    if m > 500:
        pred_chars = pred_chars[:500]
        m = 500
    if n > 500:
        ref_chars = ref_chars[:500]
        n = 500

    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if pred_chars[i - 1] == ref_chars[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    lcs_len = dp[m][n]
    precision = lcs_len / m if m > 0 else 0
    recall = lcs_len / n if n > 0 else 0

    if precision + recall == 0:
        return 0.0
    f1 = 2 * precision * recall / (precision + recall)
    return round(f1, 4)


def compute_law_recall(predicted_laws: List[str], reference_laws: List[str]) -> Dict[str, Any]:
    """法条引用召回率。"""
    if not reference_laws:
        return {"recall": None, "precision": None, "note": "无参考法条"}

    def _normalize(law: str) -> str:
        return re.sub(r'[\s　第条款项]', '', law).lower()

    ref_set = {_normalize(l) for l in reference_laws}
    pred_set = {_normalize(l) for l in predicted_laws}

    matched = {p for p in pred_set if any(p in r or r in p for r in ref_set)}

    recall = len(matched) / len(ref_set) if ref_set else 0
    precision = len(matched) / len(pred_set) if pred_set else 0

    return {
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "matched_count": len(matched),
        "reference_count": len(ref_set),
        "predicted_count": len(pred_set),
    }


class SolutionEvaluator:
    """AgentMediation Solution Evaluator。"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def evaluate(
        self,
        predicted_points: List[str],
        reference_points: List[str],
        predicted_laws: List[str],
        reference_laws: List[str],
    ) -> Dict[str, Any]:
        """完整方案质量评测。"""
        # 文本相似度
        pred_text = "；".join(predicted_points)
        ref_text = "；".join(reference_points)
        text_sim = compute_text_similarity_score(pred_text, ref_text)

        # 法条召回
        law_metrics = compute_law_recall(predicted_laws, reference_laws)

        # LLM 深度评估
        try:
            result = self.llm.chat_json(
                [{"role": "user", "content": _SOLUTION_EVAL_PROMPT.format(
                    reference_points="\n".join(f"- {p}" for p in reference_points) or "无参考",
                    predicted_points="\n".join(f"- {p}" for p in predicted_points) or "无",
                    reference_laws="\n".join(f"- {l}" for l in reference_laws) or "无参考",
                    predicted_laws="\n".join(f"- {l}" for l in predicted_laws) or "无",
                )}],
                temperature=0.1,
            )
        except Exception as e:
            logger.warning(f"Solution eval LLM 调用失败: {e}")
            result = {}

        if not isinstance(result, dict):
            result = {}

        return {
            "text_similarity_rouge_l": text_sim,
            "law_recall": law_metrics,
            "llm_evaluation": result,
            "composite_score": round(
                text_sim * 0.3
                + (law_metrics.get("recall") or 0) * 0.3
                + float(result.get("overall_score", 5)) / 10 * 0.4,
                4,
            ),
        }


# ========== 争议原因分类体系（29 子类） ==========

DISPUTE_CAUSES_TAXONOMY = {
    "information_conflict": {
        "label": "信息冲突",
        "subcategories": {
            "missing_info": "信息缺失",
            "false_info": "虚假信息",
            "misunderstood_info": "信息误解",
            "other_info": "其他信息问题",
        },
    },
    "resource_conflict": {
        "label": "资源冲突",
        "subcategories": {
            "economic": "经济资源",
            "time": "时间资源",
            "public_resources": "公共资源",
            "land_real_estate": "土地/不动产",
            "family_rights": "家庭权利",
            "ip_intangible": "知识产权/无形资产",
            "education_academia": "教育/学术",
            "other_resources": "其他资源",
        },
    },
    "behavioral_misconduct": {
        "label": "行为不端",
        "subcategories": {
            "dishonesty": "不诚信行为",
            "illegal_acts": "违法行为",
            "gov_admin_misconduct": "政府/行政不当",
            "negligence": "疏忽",
            "financial_issues": "财务问题",
            "interpersonal": "人际冲突",
            "other_misconduct": "其他不当行为",
        },
    },
    "legal_issue": {
        "label": "法律问题",
        "subcategories": {
            "outdated_laws": "法律过时",
            "unclear_rules": "规则不明确",
            "inconsistent_judgments": "判决不一致",
            "lack_of_regulation": "监管缺失",
            "legal_loopholes": "法律漏洞",
            "other_legal": "其他法律问题",
        },
    },
    "external_factor": {
        "label": "外部因素",
        "subcategories": {
            "market_changes": "市场变化",
            "policy_shifts": "政策变动",
            "natural_disasters": "自然灾害",
            "other_external": "其他外部因素",
        },
    },
}


def get_dispute_cause_instruction(
    cause_type: str,
    subcategory: Optional[str] = None,
    detail: Optional[str] = None,
) -> str:
    """构建争议原因注入指令（包含子类）。"""
    cat = DISPUTE_CAUSES_TAXONOMY.get(cause_type)
    if not cat:
        return ""

    parts = [f"【争议原因类别】{cat['label']}"]

    if subcategory and subcategory in cat.get("subcategories", {}):
        parts.append(f"【细分原因】{cat['subcategories'][subcategory]}")

    if detail:
        parts.append(f"【具体描述】{detail}")

    return "\n".join(parts)


# ========== 外部知识 (EK) 条件控制 ==========

class ExternalKnowledgeController:
    """控制调解员/法官是否能访问法条检索系统。"""

    def __init__(self, law_retriever=None):
        self._retriever = law_retriever
        self._enabled = law_retriever is not None
        self._access_log: List[Dict] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        """有条件地执行法条检索。"""
        if not self._enabled or not self._retriever:
            self._access_log.append({"query": query, "result": "blocked", "reason": "EK disabled"})
            return []

        try:
            results = self._retriever.search(query, top_k)
            self._access_log.append({"query": query, "result": "success", "count": len(results)})
            return results
        except Exception as e:
            self._access_log.append({"query": query, "result": "error", "reason": str(e)})
            return []

    def get_access_log(self) -> List[Dict]:
        return list(self._access_log)


# ========== 群体极化 & 表面共识检测 ==========

def detect_group_polarization(
    single_strategy_results: Dict[str, Any],
    all_strategy_results: Dict[str, Any],
) -> Dict[str, Any]:
    """检测群体极化现象。

    比较 NUM=1（仅一方采用策略）和 NUM=ALL（所有方采用策略）的结果差异。
    如果 NUM=ALL 下效果显著放大（正向或负向），则存在群体极化。
    """
    def _get(d, key, default=0):
        return float(d.get(key, default))

    sr_single = _get(single_strategy_results, "success_rate", 0.5)
    sr_all = _get(all_strategy_results, "success_rate", 0.5)
    sat_single = _get(single_strategy_results, "satisfaction", 50)
    sat_all = _get(all_strategy_results, "satisfaction", 50)
    con_single = _get(single_strategy_results, "consensus", 50)
    con_all = _get(all_strategy_results, "consensus", 50)
    lr_single = _get(single_strategy_results, "litigation_risk", 25)
    lr_all = _get(all_strategy_results, "litigation_risk", 25)

    polarization_indicators = {
        "success_rate_delta": round(sr_all - sr_single, 4),
        "satisfaction_delta": round(sat_all - sat_single, 2),
        "consensus_delta": round(con_all - con_single, 2),
        "litigation_risk_delta": round(lr_all - lr_single, 2),
    }

    magnitude = sum(abs(v) for v in polarization_indicators.values()) / 4
    is_polarized = magnitude > 10

    direction = "positive" if (sr_all > sr_single and sat_all > sat_single) else "negative"
    if not is_polarized:
        direction = "neutral"

    return {
        "is_polarized": is_polarized,
        "polarization_direction": direction,
        "polarization_magnitude": round(magnitude, 2),
        "indicators": polarization_indicators,
    }


def detect_surface_consensus(
    consensus_score: float,
    satisfaction_scores: Dict[str, float],
    threshold_gap: float = 20.0,
) -> Dict[str, Any]:
    """检测表面共识现象。

    表面共识 = 高共识度 + 低满意度（各方表面同意但内心不满）。
    参考 AgentMediation Table 5 中 Accommodating 策略的发现。
    """
    avg_satisfaction = sum(satisfaction_scores.values()) / max(len(satisfaction_scores), 1)
    gap = consensus_score - avg_satisfaction

    is_surface = gap > threshold_gap and consensus_score > 60

    most_dissatisfied = min(satisfaction_scores.items(), key=lambda x: x[1]) if satisfaction_scores else ("", 0)

    return {
        "is_surface_consensus": is_surface,
        "consensus_score": round(consensus_score, 2),
        "average_satisfaction": round(avg_satisfaction, 2),
        "gap": round(gap, 2),
        "threshold": threshold_gap,
        "most_dissatisfied_party": most_dissatisfied[0],
        "most_dissatisfied_score": round(most_dissatisfied[1], 2),
        "interpretation": (
            "存在表面共识：各方表面达成一致但内心仍不满意，可能导致执行困难或后续诉讼"
            if is_surface else "共识与满意度较为一致"
        ),
    }
