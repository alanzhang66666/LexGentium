"""
AgentMediation 风格的调解/庭审结果多维评测

基于 AgentMediation (2509.06586) 的 Outcome Evaluator 和 Solution Evaluator。
使用 LLM-as-a-judge 范式评测四个核心维度：
1. Success Rate (SR) —— 调解/审判成功率
2. Satisfaction (Sat) —— 各方主观满意度（Likert 五级）
3. Consensus (Con) —— 共识程度
4. Litigation Risk (LR) —— 诉讼风险 / 冲突升级风险

Prompt 设计直接参考论文 Table 18-21 的中文本地化版本。
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger("outcome_evaluator")

# ============================================================
# Prompt 模板（基于 AgentMediation Table 18-21 的中文本地化）
# ============================================================

_SATISFACTION_PROMPT = """请你扮演当事人「{party_name}」。根据以下调解/庭审对话和最终方案，请表达你真实的满意程度。

【案件背景】
{case_background}

【对话历史】
{dialog_history}

【最终方案/判决】
{final_proposal}

你是「{party_name}」。请基于以上调解/庭审对话和最终方案，表达你真实的满意水平。这不是为了取悦他人，而是你内心的真实感受：
• 我是否在这次过程中充分表达了我真正的关切？
• 我最重要的需求是否被直接回应了？
• 最终方案在多大程度上满足了我的核心期望？

请从以下五个等级中选择最能代表你真实感受的一个，并简要说明原因：
• 非常低：我没有表达真正的关切，或者它们被忽视、拒绝或压制。核心需求未被满足，过程让我感到无力。
• 低：我表达了一些观点，但重要关切被压制或忽略。表面上的合作主要是为了避免冲突。
• 中等：我能够表达立场，部分关切得到回应。有些核心问题没有被深入探讨。结果可以接受但仍有犹豫。
• 高：我清楚地表达了立场，对方和调解人/法官积极回应。虽有让步但在合理范围内。
• 非常高：我充分表达了想法，核心需求被理解和回应。方案符合我的主要关切，过程让我感到受尊重。

请严格按照以下 JSON 格式输出：
{{"satisfaction_level": "非常低/低/中等/高/非常高", "reason": "简要说明"}}
"""

_CONSENSUS_PROMPT = """请评估以下调解/庭审对话中各方达成的共识程度，并从五个等级中选择一个。请提供简要说明。

【案件背景】
{case_background}

【对话历史】
{dialog_history}

【最终方案/判决】
{final_proposal}

评分标准：
• 非常低：各方几乎没有有意义的表达或回应。沉默、回避或敌对语言常见。关键问题被回避，对话停留在表面。
• 低：存在一些倾听和理解的意愿，但互动主要停留在态度层面，没有深入具体问题。
• 中等：共识的初步迹象正在出现。双方显示出解决问题的意愿，在部分问题上立场趋于一致。但关键问题仍未解决。
• 高：主要问题上正在形成初步协议。语言具体，互动具有建设性。共同解决框架基本建立。
• 非常高：各方已就主要问题达成明确协议。合作积极，解决方向明确且可执行。

请严格按照以下 JSON 格式输出：
{{"consensus_level": "非常低/低/中等/高/非常高", "reason": "简要说明"}}
"""

_LITIGATION_RISK_PROMPT = """请根据以下调解/庭审对话，评估当前的冲突升级/诉讼风险水平，并从五个等级中选择一个。

【案件背景】
{case_background}

【对话历史】
{dialog_history}

【最终方案/判决】
{final_proposal}

评分标准：
• 非常低：沟通顺畅，情绪平静。观点被充分理性表达，分歧很小或已达成初步共识。
• 低：虽然存在分歧，但各方开放沟通，语言温和。有明确的谈判意愿，互动具有建设性。
• 中等：存在明显分歧或调解进展缓慢。表述模糊，频繁让步，回避实质问题，或过度迁就导致核心诉求被压制。
• 高：对抗性语言频繁，沟通接近崩溃。调解基本停滞或被抵制，部分当事人开始倾向诉讼。
• 非常高：情绪严重失控，沟通已崩溃。部分当事人明确表示将诉诸法律或外部手段。

请严格按照以下 JSON 格式输出：
{{"risk_level": "非常低/低/中等/高/非常高", "reason": "简要说明"}}
"""

_ACCEPTANCE_PROMPT = """你是「{party_name}」。根据以上调解/庭审对话和最终方案，请做出你是否接受该方案的真实决定。

【案件背景】
{case_background}

【对话历史】
{dialog_history}

【最终方案/判决】
{final_proposal}

请不要急于下结论，而是仔细反思你真正的关切和利益。

请严格按照以下 JSON 格式输出：
{{"accept_or_not": "接受/拒绝/犹豫", "reason": "简要说明"}}
"""

# Likert 五级量化映射
_SATISFACTION_MAP = {"非常低": 0, "低": 1, "中等": 2, "高": 3, "非常高": 4}
_CONSENSUS_MAP = {"非常低": 0, "低": 1, "中等": 2, "高": 3, "非常高": 4}
_RISK_MAP = {"非常低": 0, "低": 1, "中等": 2, "高": 3, "非常高": 4}
_ACCEPT_MAP = {"接受": 1.0, "犹豫": 0.5, "拒绝": 0.0}


def _format_dialog(dialog_history: List[Dict[str, Any]], max_turns: int = 30) -> str:
    """格式化对话历史为可读文本。"""
    recent = dialog_history[-max_turns:] if len(dialog_history) > max_turns else dialog_history
    lines = []
    for item in recent:
        role = item.get("role", "?")
        msg = item.get("message", "")[:500]
        lines.append(f"{role}: {msg}")
    return "\n".join(lines)


def _extract_json(text: str) -> Dict:
    """从 LLM 输出中提取 JSON。"""
    try:
        match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
        if match:
            import json
            return json.loads(match.group())
    except Exception:
        pass
    return {}


class OutcomeEvaluator:
    """AgentMediation 风格的 LLM-as-a-judge 结果评测器。"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def _call_llm(self, prompt: str) -> Dict:
        try:
            response = self.llm.chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            return _extract_json(response or "")
        except Exception as e:
            logger.warning(f"LLM-as-a-judge 调用失败: {e}")
            return {}

    # ----------------------------------------------------------------
    # 满意度评测（per-party）
    # ----------------------------------------------------------------

    def evaluate_satisfaction(
        self,
        party_name: str,
        case_background: str,
        dialog_history: List[Dict[str, Any]],
        final_proposal: str,
    ) -> Dict[str, Any]:
        prompt = _SATISFACTION_PROMPT.format(
            party_name=party_name,
            case_background=case_background[:2000],
            dialog_history=_format_dialog(dialog_history),
            final_proposal=final_proposal[:2000],
        )
        result = self._call_llm(prompt)
        level = result.get("satisfaction_level", "中等")
        score = _SATISFACTION_MAP.get(level, 2)
        return {
            "party": party_name,
            "level": level,
            "score": score,
            "normalized": round(score / 4 * 100, 2),
            "reason": result.get("reason", ""),
        }

    # ----------------------------------------------------------------
    # 共识度评测
    # ----------------------------------------------------------------

    def evaluate_consensus(
        self,
        case_background: str,
        dialog_history: List[Dict[str, Any]],
        final_proposal: str,
    ) -> Dict[str, Any]:
        prompt = _CONSENSUS_PROMPT.format(
            case_background=case_background[:2000],
            dialog_history=_format_dialog(dialog_history),
            final_proposal=final_proposal[:2000],
        )
        result = self._call_llm(prompt)
        level = result.get("consensus_level", "中等")
        score = _CONSENSUS_MAP.get(level, 2)
        return {
            "level": level,
            "score": score,
            "normalized": round(score / 4 * 100, 2),
            "reason": result.get("reason", ""),
        }

    # ----------------------------------------------------------------
    # 诉讼风险评测
    # ----------------------------------------------------------------

    def evaluate_litigation_risk(
        self,
        case_background: str,
        dialog_history: List[Dict[str, Any]],
        final_proposal: str,
    ) -> Dict[str, Any]:
        prompt = _LITIGATION_RISK_PROMPT.format(
            case_background=case_background[:2000],
            dialog_history=_format_dialog(dialog_history),
            final_proposal=final_proposal[:2000],
        )
        result = self._call_llm(prompt)
        level = result.get("risk_level", "中等")
        score = _RISK_MAP.get(level, 2)
        return {
            "level": level,
            "score": score,
            "normalized": round(score / 4 * 100, 2),
            "reason": result.get("reason", ""),
        }

    # ----------------------------------------------------------------
    # 接受度评测（per-party）
    # ----------------------------------------------------------------

    def evaluate_acceptance(
        self,
        party_name: str,
        case_background: str,
        dialog_history: List[Dict[str, Any]],
        final_proposal: str,
    ) -> Dict[str, Any]:
        prompt = _ACCEPTANCE_PROMPT.format(
            party_name=party_name,
            case_background=case_background[:2000],
            dialog_history=_format_dialog(dialog_history),
            final_proposal=final_proposal[:2000],
        )
        result = self._call_llm(prompt)
        decision = result.get("accept_or_not", "犹豫")
        return {
            "party": party_name,
            "decision": decision,
            "score": _ACCEPT_MAP.get(decision, 0.5),
            "reason": result.get("reason", ""),
        }

    # ----------------------------------------------------------------
    # 综合结果评测（四指标 + 成功率）
    # ----------------------------------------------------------------

    def evaluate_outcome(
        self,
        case_background: str,
        dialog_history: List[Dict[str, Any]],
        final_proposal: str,
        party_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """执行完整的 AgentMediation 四指标评测。"""
        if not party_names:
            party_names = ["原告", "被告"]

        # 满意度（per-party）
        satisfactions = {}
        for name in party_names:
            satisfactions[name] = self.evaluate_satisfaction(
                name, case_background, dialog_history, final_proposal,
            )

        avg_satisfaction = sum(s["normalized"] for s in satisfactions.values()) / max(len(satisfactions), 1)

        # 共识度
        consensus = self.evaluate_consensus(case_background, dialog_history, final_proposal)

        # 诉讼风险
        litigation_risk = self.evaluate_litigation_risk(case_background, dialog_history, final_proposal)

        # 接受度 -> 成功率
        acceptances = {}
        for name in party_names:
            acceptances[name] = self.evaluate_acceptance(
                name, case_background, dialog_history, final_proposal,
            )

        all_accepted = all(a["decision"] == "接受" for a in acceptances.values())
        success_rate = 1.0 if all_accepted else 0.0

        return {
            "success_rate": success_rate,
            "satisfaction": {
                "per_party": satisfactions,
                "average_normalized": round(avg_satisfaction, 2),
            },
            "consensus": consensus,
            "litigation_risk": litigation_risk,
            "acceptance": {
                "per_party": acceptances,
                "all_accepted": all_accepted,
            },
            "composite_score": round(
                success_rate * 0.25
                + avg_satisfaction / 100 * 0.25
                + consensus["normalized"] / 100 * 0.25
                + (1 - litigation_risk["normalized"] / 100) * 0.25,
                4,
            ),
        }
