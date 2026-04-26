"""
Dual-Mode Reasoning 快/慢双模式推理引擎
基于 LegalΔ (2508.12281) 的核心创新：

双模式：
- Fast Mode（快思考）：直接输出结论，不做显式推理
- Slow Mode（慢思考）：完整 Chain-of-Thought 推理

信息增益 = Slow 模式相对于 Fast 模式的额外信息量
- 高信息增益 → 推理有价值，判决需要深度论证
- 低信息增益 → 案件简单，快速判断即可信赖

同时输出推理质量的多维度奖励信号（结构连贯性 + 法律特异性）。
"""
from __future__ import annotations

import logging
import re
from typing import Dict, Any

logger = logging.getLogger("dual_mode_reasoning")

_FAST_MODE_PROMPT = """你是一位经验丰富的民事法官。请基于以下案件信息，快速给出判决结论。
不需要详细推理，只需给出判决主文（支持/驳回哪些诉讼请求，金额等）。

【案件信息】
{case_info}

【原告诉求】
{claims}

请直接输出判决结论（不超过200字）："""

_SLOW_MODE_PROMPT = """你是一位经验丰富的民事法官。请基于以下案件信息，进行完整的法律推理并给出判决。

【案件信息】
{case_info}

【原告诉求】
{claims}

请按以下步骤进行完整推理：

一、事实认定
（梳理查明的事实）

二、争议焦点
（归纳本案的争议焦点）

三、法律分析
（对每个争议焦点逐一进行法律分析，引用具体法条）

四、判决主文
（基于以上分析给出具体判决）

五、适用法条
（列出所有适用的法律条文）"""

_REASONING_QUALITY_PROMPT = """你是一位法学教授。请评估以下法律推理的质量。

【快速判断（无推理）】
{fast_output}

【完整推理】
{slow_output}

请评估完整推理相对于快速判断增加了多少有价值的内容：

1. 事实认定充分性（0-10）：推理是否充分梳理了案件事实？
2. 法律论证深度（0-10）：是否有逐条法条的分析论证？
3. 争议焦点覆盖（0-10）：是否识别并回应了所有争议焦点？
4. 结论一致性（0-10）：快速判断和完整推理的结论是否一致？
5. 推理不可替代性（0-10）：推理过程是否包含快速判断无法给出的关键洞察？

输出 JSON：
{{"fact_sufficiency": 0-10, "legal_depth": 0-10, "dispute_coverage": 0-10, "conclusion_consistency": 0-10, "reasoning_irreplaceability": 0-10, "overall_quality": 0-10, "key_insights": "完整推理中最关键的洞察", "information_gain_assessment": "高/中/低"}}"""


def _count_legal_elements(text: str) -> Dict[str, int]:
    """统计文本中的法律要素数量。"""
    law_citations = len(re.findall(r'第[\d零一二三四五六七八九十百千]+条', text))
    reasoning_steps = len(re.findall(r'[一二三四五六七八九十]\s*[、．.]', text))
    factual_claims = text.count("事实") + text.count("查明") + text.count("认定")
    legal_terms = sum(text.count(t) for t in ["根据", "依据", "适用", "规定", "法律", "条款"])
    return {
        "law_citations": law_citations,
        "reasoning_steps": reasoning_steps,
        "factual_claims": factual_claims,
        "legal_terms": legal_terms,
    }


def _compute_info_gain_heuristic(fast_output: str, slow_output: str) -> float:
    """启发式计算信息增益（不依赖 LLM）。"""
    fast_elems = _count_legal_elements(fast_output)
    slow_elems = _count_legal_elements(slow_output)

    len_ratio = len(slow_output) / max(len(fast_output), 1)
    law_delta = slow_elems["law_citations"] - fast_elems["law_citations"]
    step_delta = slow_elems["reasoning_steps"]
    term_delta = slow_elems["legal_terms"] - fast_elems["legal_terms"]

    gain = (
        min(len_ratio / 5, 1.0) * 0.2
        + min(law_delta / 3, 1.0) * 0.3
        + min(step_delta / 4, 1.0) * 0.3
        + min(term_delta / 10, 1.0) * 0.2
    )
    return round(max(0, min(gain, 1.0)), 4)


class DualModeReasoner:
    """快/慢双模式推理引擎。"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def fast_judgment(self, case_info: str, claims: str) -> str:
        """Fast Mode: 直接输出结论。"""
        prompt = _FAST_MODE_PROMPT.format(
            case_info=case_info[:2000], claims=claims[:500],
        )
        try:
            return self.llm.chat_completion(
                [{"role": "user", "content": prompt}], temperature=0.1,
            ).strip()
        except Exception as e:
            logger.warning(f"Fast mode failed: {e}")
            return ""

    def slow_judgment(self, case_info: str, claims: str) -> str:
        """Slow Mode: 完整 CoT 推理。"""
        prompt = _SLOW_MODE_PROMPT.format(
            case_info=case_info[:3000], claims=claims[:500],
        )
        try:
            return self.llm.chat_completion(
                [{"role": "user", "content": prompt}], temperature=0.1,
            ).strip()
        except Exception as e:
            logger.warning(f"Slow mode failed: {e}")
            return ""

    def compute_information_gain(
        self, fast_output: str, slow_output: str, use_llm: bool = True,
    ) -> Dict[str, Any]:
        """计算慢模式相对于快模式的信息增益。"""
        heuristic_gain = _compute_info_gain_heuristic(fast_output, slow_output)
        fast_elems = _count_legal_elements(fast_output)
        slow_elems = _count_legal_elements(slow_output)

        result: Dict[str, Any] = {
            "heuristic_gain": heuristic_gain,
            "fast_elements": fast_elems,
            "slow_elements": slow_elems,
            "length_ratio": round(len(slow_output) / max(len(fast_output), 1), 2),
        }

        if use_llm and self.llm:
            try:
                llm_eval = self.llm.chat_json(
                    [{"role": "user", "content": _REASONING_QUALITY_PROMPT.format(
                        fast_output=fast_output[:1500],
                        slow_output=slow_output[:3000],
                    )}],
                    temperature=0.1,
                )
                if isinstance(llm_eval, dict):
                    result["llm_evaluation"] = llm_eval
                    scores = [
                        llm_eval.get("fact_sufficiency", 5),
                        llm_eval.get("legal_depth", 5),
                        llm_eval.get("dispute_coverage", 5),
                        llm_eval.get("reasoning_irreplaceability", 5),
                    ]
                    result["llm_gain"] = round(sum(float(s) for s in scores) / 40, 4)
            except Exception as e:
                logger.warning(f"LLM info gain eval failed: {e}")

        final_gain = result.get("llm_gain", heuristic_gain)
        result["final_information_gain"] = final_gain
        result["confidence_level"] = (
            "high" if final_gain > 0.7 else "medium" if final_gain > 0.4 else "low"
        )
        return result

    def dual_mode_judgment(
        self, case_info: str, claims: str, use_llm_eval: bool = True,
    ) -> Dict[str, Any]:
        """执行完整的双模式推理流程。"""
        fast = self.fast_judgment(case_info, claims)
        slow = self.slow_judgment(case_info, claims)
        info_gain = self.compute_information_gain(fast, slow, use_llm=use_llm_eval)

        return {
            "fast_judgment": fast,
            "slow_judgment": slow,
            "information_gain": info_gain,
            "recommended_output": slow if info_gain["final_information_gain"] > 0.3 else fast,
            "reasoning_value": info_gain["confidence_level"],
        }
