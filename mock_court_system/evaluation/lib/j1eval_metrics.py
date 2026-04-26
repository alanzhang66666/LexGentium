"""
J1-EVAL 细粒度法律评测指标
基于 J1-ENVS (2507.04037v2) 的评测框架。

Level III 评测指标：
- PFS (Procedural-Following Score) —— 程序合规分（已在 state_machine 实现）
- JUD (Judgment Score) —— 判决质量评分
- REA (Reason Score) —— 裁判理由质量
- LAW (Law Accuracy) —— 法条引用准确率

Level II 评测指标：
- FOR (Format-Following Score) —— 文书格式合规分
- DOC (Document Score) —— 文书内容质量分

附加：
- Big Five 人格特质模型用于角色多样性
- 行为一致性检测
"""
from __future__ import annotations

import re
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("j1eval_metrics")

# ========== Level III: 判决评测 ==========

_JUD_PROMPT = """你是一位资深法官。请对以下判决书的判决质量进行评分。

【判决书】
{judgment_text}

{ground_truth_section}

请从以下维度评估（每项 1-10 分）：
1. 判决主文的明确性和具体性
2. 判决结果与查明事实的一致性
3. 判决结果的合理性和公正性
4. 判决结果的可执行性

输出 JSON：
{{"jud_score": 1-10, "specificity": 1-10, "consistency": 1-10, "fairness": 1-10, "enforceability": 1-10, "reasoning": "评分依据"}}
"""

_REA_PROMPT = """你是一位法学教授。请对以下判决书的裁判理由质量进行评分。

【判决书】
{judgment_text}

{ground_truth_section}

请从以下维度评估（每项 1-10 分）：
1. 法律观点的准确性
2. 逻辑推理的严密性
3. 事实认定的充分性

输出 JSON：
{{"rea_score": 1-10, "legal_accuracy": 1-10, "logic_rigor": 1-10, "fact_sufficiency": 1-10, "reasoning": "评分依据"}}
"""


def evaluate_law_accuracy(
    predicted_laws: List[str],
    ground_truth_laws: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """LAW: 法条引用准确率（基于精确匹配）。"""
    if not predicted_laws:
        return {"law_accuracy": 0.0, "predicted_count": 0, "matched": []}

    if ground_truth_laws is None:
        return {
            "law_accuracy": None,
            "predicted_count": len(predicted_laws),
            "note": "无 ground truth，无法计算准确率",
        }

    def _normalize(law: str) -> str:
        return re.sub(r'[\s　，。、；：\u201c\u201d\u2018\u2019（）()\u7b2c\u6761]', '', law).lower()

    gt_normalized = {_normalize(l) for l in ground_truth_laws}
    pred_normalized = {_normalize(l): l for l in predicted_laws}

    matched = [
        pred_normalized[pn]
        for pn in pred_normalized
        if any(pn in gn or gn in pn for gn in gt_normalized)
    ]

    accuracy = len(matched) / len(ground_truth_laws) if ground_truth_laws else 0
    precision = len(matched) / len(predicted_laws) if predicted_laws else 0

    return {
        "law_accuracy": round(accuracy, 4),
        "law_precision": round(precision, 4),
        "predicted_count": len(predicted_laws),
        "ground_truth_count": len(ground_truth_laws),
        "matched_count": len(matched),
        "matched": matched,
    }


# ========== Level II: 文书评测 ==========

_CD_REQUIRED_SECTIONS = [
    ("header", "民事起诉状", "文书标题"),
    ("plaintiff", r"原告[：:]", "原告信息"),
    ("defendant", r"被告[：:]", "被告信息"),
    ("claims", r"诉讼请求|请求.*判令", "诉讼请求"),
    ("facts", r"事实.{0,5}理由|案件事实", "事实与理由"),
    ("evidence", r"证据|附件", "证据清单"),
    ("court", r"人民法院|此致", "受诉法院"),
    ("signature", r"具状人|起诉人|签名", "签名"),
]

_DD_REQUIRED_SECTIONS = [
    ("header", "民事答辩状", "文书标题"),
    ("respondent", r"答辩人|被告", "答辩人信息"),
    ("appellant", r"被答辩人|原告", "被答辩人信息"),
    ("defense_claims", r"答辩请求|答辩意见", "答辩请求"),
    ("facts", r"事实.{0,5}理由|答辩理由", "事实与理由"),
    ("evidence", r"证据", "证据"),
    ("signature", r"答辩人|签名", "签名"),
]


def evaluate_format_following(
    document_text: str,
    scenario: str = "CD",
) -> Dict[str, Any]:
    """FOR: 文书格式合规评分。"""
    sections = _CD_REQUIRED_SECTIONS if scenario == "CD" else _DD_REQUIRED_SECTIONS

    found = []
    missing = []
    order_correct = True
    last_pos = -1

    for section_id, pattern, label in sections:
        match = re.search(pattern, document_text)
        if match:
            found.append({"section": section_id, "label": label, "position": match.start()})
            if match.start() < last_pos:
                order_correct = False
            last_pos = match.start()
        else:
            missing.append({"section": section_id, "label": label})

    score = len(found) / len(sections) if sections else 0
    if not order_correct:
        score *= 0.9

    return {
        "for_score": round(score, 4),
        "sections_found": len(found),
        "sections_total": len(sections),
        "missing_sections": missing,
        "order_correct": order_correct,
        "details": found,
    }


_DOC_PROMPT = """你是一位法律文书审查专家。请评估以下{doc_type}的内容质量。

【文书内容】
{document_text}

请评估以下项目的完整性和准确性（每项 0 或 1，或 1-10 分）：
1. 当事人信息完整性（姓名、性别、出生日期、民族、住址）[0-1]
2. 诉讼请求/答辩请求的明确性 [1-10]
3. 事实陈述的完整性 [1-10]
4. 法律依据的充分性 [1-10]
5. 证据列举的完整性 [1-10]

输出 JSON：
{{"doc_score": 1-10, "party_info_complete": 0或1, "claims_clarity": 1-10, "fact_completeness": 1-10, "legal_basis": 1-10, "evidence_listing": 1-10, "reasoning": "评分依据"}}
"""


# ========== Big Five 人格特质 ==========
# 参考 J1-ENVS Section 2.1 的人格理论

BIG_FIVE_TRAITS = {
    "openness": {
        "label": "开放性",
        "high": "你是一个思想开放的人，愿意接受新观点，善于从不同角度思考问题。表达方式丰富多样。",
        "medium": "你对新事物持中立态度，既不排斥也不特别追求，表达方式较为平稳。",
        "low": "你倾向于传统和实际，不太接受新观点，表达方式较为保守直接。",
    },
    "conscientiousness": {
        "label": "尽责性",
        "high": "你做事非常认真细致，注重细节，回答问题条理清晰，会主动提供完整信息。",
        "medium": "你做事比较认真，但不会过分纠结细节，回答较为中规中矩。",
        "low": "你做事比较随意，可能遗漏一些细节，回答较为简略。",
    },
    "extraversion": {
        "label": "外向性",
        "high": "你性格外向，善于表达，话比较多，会主动补充信息，情绪表达强烈。",
        "medium": "你性格适中，该说的会说，不会过多或过少。",
        "low": "你性格内向，不善言辞，回答简短，需要被引导才会提供更多信息。",
    },
    "agreeableness": {
        "label": "宜人性",
        "high": "你性格温和友善，容易与人合作，倾向于认可对方的观点，不太喜欢冲突。",
        "medium": "你对人态度一般，既不特别友善也不冷漠。",
        "low": "你性格较为强势，不轻易妥协，可能会质疑对方的观点。",
    },
    "neuroticism": {
        "label": "神经质",
        "high": "你情绪波动较大，容易焦虑和紧张，面对法律问题时会表现出明显的担忧和不安。",
        "medium": "你情绪较为稳定，但面对重要问题时偶尔会有些紧张。",
        "low": "你情绪非常稳定，面对法律问题也能保持冷静理性。",
    },
}


def build_personality_instruction(
    traits: Dict[str, str],
) -> str:
    """基于 Big Five 人格特质构建角色行为指令。

    Args:
        traits: {"openness": "high"/"medium"/"low", ...}
    """
    parts = ["【人格特征】"]
    for trait_name, level in traits.items():
        trait_def = BIG_FIVE_TRAITS.get(trait_name)
        if not trait_def:
            continue
        desc = trait_def.get(level, trait_def.get("medium", ""))
        parts.append(f"- {trait_def['label']}：{desc}")

    return "\n".join(parts)


def generate_random_personality() -> Dict[str, str]:
    """随机生成一组 Big Five 人格特质。"""
    import random
    levels = ["high", "medium", "low"]
    return {trait: random.choice(levels) for trait in BIG_FIVE_TRAITS}


# ========== 行为一致性检测 ==========

_BEHAVIOR_CONSISTENCY_PROMPT = """你是一位行为分析专家。请评估以下角色在对话中的行为一致性。

【角色设定】
角色名: {role_name}
角色背景: {role_background}

【对话历史（该角色的所有发言）】
{role_utterances}

请评估：
1. 角色扮演的一致性：发言是否始终符合角色设定？
2. 信息一致性：是否存在前后矛盾的陈述？
3. 情绪一致性：情绪变化是否自然合理？
4. 策略一致性：行为策略是否连贯？

输出 JSON：
{{"consistency_score": 0-100, "role_adherence": 0-100, "info_consistency": 0-100, "emotion_consistency": 0-100, "strategy_consistency": 0-100, "inconsistencies": ["发现的不一致之处"], "reasoning": "评分依据"}}
"""


class J1EvalMetrics:
    """J1-EVAL 细粒度评测指标集合。"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def _call_llm_json(self, prompt: str) -> Dict:
        try:
            result = self.llm.chat_json(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            return result if isinstance(result, dict) else {}
        except Exception as e:
            logger.warning(f"J1-EVAL LLM 调用失败: {e}")
            return {}

    def evaluate_judgment(
        self,
        judgment_text: str,
        ground_truth: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """JUD: 判决质量评分。"""
        gt_section = ""
        if ground_truth:
            gt_section = f"【参考判决】\n{ground_truth.get('judgment', '')[:1500]}"

        result = self._call_llm_json(
            _JUD_PROMPT.format(
                judgment_text=judgment_text[:4000],
                ground_truth_section=gt_section,
            )
        )
        return {"metric": "JUD", **result}

    def evaluate_reasoning(
        self,
        judgment_text: str,
        ground_truth: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """REA: 裁判理由质量。"""
        gt_section = ""
        if ground_truth:
            gt_section = f"【参考裁判理由】\n{ground_truth.get('reasoning', '')[:1500]}"

        result = self._call_llm_json(
            _REA_PROMPT.format(
                judgment_text=judgment_text[:4000],
                ground_truth_section=gt_section,
            )
        )
        return {"metric": "REA", **result}

    def evaluate_law_accuracy(
        self,
        predicted_laws: List[str],
        ground_truth_laws: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """LAW: 法条引用准确率。"""
        return {"metric": "LAW", **evaluate_law_accuracy(predicted_laws, ground_truth_laws)}

    def evaluate_document(
        self,
        document_text: str,
        scenario: str = "CD",
    ) -> Dict[str, Any]:
        """DOC: 文书内容质量。"""
        doc_type = "起诉状" if scenario == "CD" else "答辩状"
        result = self._call_llm_json(
            _DOC_PROMPT.format(
                doc_type=doc_type,
                document_text=document_text[:4000],
            )
        )
        return {"metric": "DOC", "scenario": scenario, **result}

    def evaluate_format(
        self,
        document_text: str,
        scenario: str = "CD",
    ) -> Dict[str, Any]:
        """FOR: 文书格式合规。"""
        return {"metric": "FOR", **evaluate_format_following(document_text, scenario)}

    def evaluate_behavior_consistency(
        self,
        role_name: str,
        role_background: str,
        dialog_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """行为一致性检测。"""
        utterances = "\n".join(
            f"[轮次{item.get('turn', '?')}] {item.get('message', '')[:300]}"
            for item in dialog_history
            if item.get("role") == role_name
        )
        if not utterances:
            return {"consistency_score": 0, "note": "该角色无发言记录"}

        result = self._call_llm_json(
            _BEHAVIOR_CONSISTENCY_PROMPT.format(
                role_name=role_name,
                role_background=role_background[:500],
                role_utterances=utterances[:3000],
            )
        )
        return {"metric": "behavior_consistency", **result}

    def evaluate_all_level3(
        self,
        judgment_text: str,
        predicted_laws: Optional[List[str]] = None,
        ground_truth: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Level III 完整评测（JUD + REA + LAW）。"""
        jud = self.evaluate_judgment(judgment_text, ground_truth)
        rea = self.evaluate_reasoning(judgment_text, ground_truth)

        gt_laws = ground_truth.get("law", []) if ground_truth else None
        law = self.evaluate_law_accuracy(predicted_laws or [], gt_laws)

        jud_s = float(jud.get("jud_score", 5))
        rea_s = float(rea.get("rea_score", 5))
        law_s = float(law.get("law_accuracy", 0.5)) * 10 if law.get("law_accuracy") is not None else 5

        composite = jud_s * 0.35 + rea_s * 0.35 + law_s * 0.30

        return {
            "JUD": jud,
            "REA": rea,
            "LAW": law,
            "composite_level3": round(composite, 2),
        }
