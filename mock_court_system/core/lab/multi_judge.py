"""
异构多法官聚合引擎
基于 PROClaim (2603.28488) 的 Heterogeneous Multi-Judge Aggregation。

核心思想：
- 用多个不同的 LLM（或同一 LLM 的不同 temperature/prompt 变体）独立生成判决
- 通过投票、加权融合或元判决来聚合最终结果
- 减少单一模型的系统偏见，提高判决的鲁棒性和可信度

聚合策略：
1. Majority Voting —— 多数票决定（适用于离散判决）
2. Weighted Aggregation —— 加权融合（按模型可信度加权）
3. Meta-Judge —— 元法官模式（一个 LLM 审阅其他 LLM 的判决后做最终裁定）
"""
from __future__ import annotations

import logging
import re
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("multi_judge")


@dataclass
class JudgeConfig:
    """单个法官配置"""
    judge_id: str
    provider: str = "default"
    model: Optional[str] = None
    temperature: float = 0.1
    weight: float = 1.0
    system_prompt_variant: str = "standard"


@dataclass
class JudgeOutput:
    """单个法官的判决输出"""
    judge_id: str
    judgment_text: str
    reasoning: str = ""
    laws_cited: List[str] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AggregatedJudgment:
    """聚合后的最终判决"""
    final_judgment: str
    aggregation_method: str
    individual_judgments: List[JudgeOutput]
    agreement_score: float
    dissenting_opinions: List[Dict[str, str]]
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_judgment": self.final_judgment,
            "aggregation_method": self.aggregation_method,
            "individual_judgments": [j.to_dict() for j in self.individual_judgments],
            "agreement_score": self.agreement_score,
            "dissenting_opinions": self.dissenting_opinions,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


# 不同风格的法官 system prompt 变体
_JUDGE_VARIANTS = {
    "standard": "你是一位严格依法裁判的民事法官，注重法律适用的准确性。",
    "pragmatic": "你是一位注重实际效果和可执行性的民事法官，在法律框架内寻求务实的解决方案。",
    "protective": "你是一位倾向于保护弱势方合法权益的民事法官，严格审查证据，确保公正。",
}

_JUDGMENT_PROMPT = """{system_persona}

请基于以下案件信息做出判决：

【案件事实】
{case_facts}

【原告诉求】
{claims}

【庭审记录摘要】
{trial_summary}

请输出完整判决，包含：
1. 本院认为（裁判理由）
2. 判决如下（判决主文）
3. 适用法条"""

_META_JUDGE_PROMPT = """你是最高法院的资深法官。以下是三位不同法官对同一案件的独立判决。
请审阅这些判决，综合考虑后做出最终裁定。

{individual_judgments}

请注意：
1. 如果多数法官意见一致，通常应采纳多数意见
2. 如果少数意见有更充分的法律依据，可以采纳少数意见但需说明理由
3. 最终判决应当是最经得起上诉审查的版本

请输出：
1. 最终判决（综合各法官意见的最佳版本）
2. 对分歧点的分析
3. 采纳/不采纳各法官意见的理由"""


def _extract_laws_from_text(text: str) -> List[str]:
    """从判决文本中提取法条引用。"""
    patterns = [
        r'《[^》]+》第[^，。；\n]+条',
        r'民法典第[^，。；\n]+条',
        r'民事诉讼法第[^，。；\n]+条',
    ]
    laws = []
    for p in patterns:
        laws.extend(re.findall(p, text))
    return list(set(laws))


def _compute_agreement(judgments: List[JudgeOutput]) -> float:
    """计算各法官之间的判决一致性（0-1）。"""
    if len(judgments) < 2:
        return 1.0

    texts = [j.judgment_text for j in judgments]
    total_pairs = 0
    agree_pairs = 0

    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            total_pairs += 1
            t1, t2 = texts[i], texts[j]
            # 简单的关键词一致性检查
            support_kw = ["支持", "成立", "应当"]
            reject_kw = ["驳回", "不予支持", "不成立"]

            t1_supports = any(k in t1 for k in support_kw)
            t2_supports = any(k in t2 for k in support_kw)
            t1_rejects = any(k in t1 for k in reject_kw)
            t2_rejects = any(k in t2 for k in reject_kw)

            if t1_supports == t2_supports and t1_rejects == t2_rejects:
                agree_pairs += 1

    return round(agree_pairs / max(total_pairs, 1), 4)


class MultiJudgeEngine:
    """异构多法官聚合引擎。"""

    def __init__(self, primary_llm, additional_llms: Optional[List] = None):
        """
        Args:
            primary_llm: 主 LLMClient
            additional_llms: 额外的 LLMClient 列表（不同模型/提供商）
        """
        self.primary_llm = primary_llm
        self.additional_llms = additional_llms or []

    def _generate_judgment(
        self,
        llm,
        judge_config: JudgeConfig,
        case_facts: str,
        claims: str,
        trial_summary: str = "",
    ) -> JudgeOutput:
        """用指定 LLM 和配置生成单个法官的判决。"""
        persona = _JUDGE_VARIANTS.get(
            judge_config.system_prompt_variant,
            _JUDGE_VARIANTS["standard"],
        )
        prompt = _JUDGMENT_PROMPT.format(
            system_persona=persona,
            case_facts=case_facts[:2500],
            claims=claims[:500],
            trial_summary=trial_summary[:1500],
        )

        try:
            response = llm.chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=judge_config.temperature,
            )
            laws = _extract_laws_from_text(response)
            return JudgeOutput(
                judge_id=judge_config.judge_id,
                judgment_text=response.strip(),
                laws_cited=laws,
                confidence=0.7,
            )
        except Exception as e:
            logger.warning(f"Judge {judge_config.judge_id} failed: {e}")
            return JudgeOutput(
                judge_id=judge_config.judge_id,
                judgment_text=f"[判决生成失败: {e}]",
                confidence=0.0,
            )

    def generate_multi_judgments(
        self,
        case_facts: str,
        claims: str,
        trial_summary: str = "",
        num_judges: int = 3,
    ) -> List[JudgeOutput]:
        """用多个法官独立生成判决。"""
        variants = list(_JUDGE_VARIANTS.keys())
        judgments = []

        # 法官 1: 主 LLM，标准风格
        configs = [
            JudgeConfig(
                judge_id=f"judge_{i + 1}",
                system_prompt_variant=variants[i % len(variants)],
                temperature=0.1 + i * 0.1,
                weight=1.0 if i == 0 else 0.8,
            )
            for i in range(num_judges)
        ]

        all_llms = [self.primary_llm] + self.additional_llms

        # 各法官判决完全独立，并行生成（LLM 生成占判决总时长的绝对大头）
        from concurrent.futures import ThreadPoolExecutor

        def _one(i: int) -> JudgeOutput:
            llm = all_llms[i % len(all_llms)]
            return self._generate_judgment(llm, configs[i], case_facts, claims, trial_summary)

        with ThreadPoolExecutor(max_workers=len(configs)) as pool:
            judgments = list(pool.map(_one, range(len(configs))))

        return judgments

    @staticmethod
    def _classify_stance(text: str) -> str:
        """从判决文本中提取立场：support / reject / partial / unknown。"""
        support_kw = ["支持原告", "予以支持", "诉讼请求成立", "应予支持"]
        reject_kw = ["驳回原告", "不予支持", "诉讼请求不成立", "驳回诉讼请求"]
        partial_kw = ["部分支持", "部分予以支持", "部分成立"]

        has_support = any(k in text for k in support_kw)
        has_reject = any(k in text for k in reject_kw)
        has_partial = any(k in text for k in partial_kw)

        if has_partial or (has_support and has_reject):
            return "partial"
        if has_support:
            return "support"
        if has_reject:
            return "reject"
        return "unknown"

    def aggregate_majority_vote(self, judgments: List[JudgeOutput]) -> AggregatedJudgment:
        """多数票聚合：基于判决结论（支持/驳回/部分支持）投票，选择多数立场中最优判决。"""
        if not judgments:
            return AggregatedJudgment(
                final_judgment="", aggregation_method="majority_vote",
                individual_judgments=[], agreement_score=0,
                dissenting_opinions=[], confidence=0,
            )

        stance_map: Dict[str, List[JudgeOutput]] = {}
        for j in judgments:
            stance = self._classify_stance(j.judgment_text)
            stance_map.setdefault(stance, []).append(j)

        majority_stance = max(stance_map, key=lambda s: len(stance_map[s]))
        majority_group = stance_map[majority_stance]

        best = max(majority_group, key=lambda j: j.confidence)

        agreement = _compute_agreement(judgments)

        dissenting = [
            {"judge_id": j.judge_id, "stance": self._classify_stance(j.judgment_text),
             "summary": j.judgment_text[:200]}
            for j in judgments
            if self._classify_stance(j.judgment_text) != majority_stance
        ]

        return AggregatedJudgment(
            final_judgment=best.judgment_text,
            aggregation_method="majority_vote",
            individual_judgments=judgments,
            agreement_score=agreement,
            dissenting_opinions=dissenting,
            confidence=agreement * best.confidence,
            metadata={
                "selected_judge": best.judge_id,
                "majority_stance": majority_stance,
                "vote_distribution": {s: len(js) for s, js in stance_map.items()},
            },
        )

    def aggregate_meta_judge(
        self, judgments: List[JudgeOutput], case_facts: str = "",
    ) -> AggregatedJudgment:
        """元法官聚合：一个 LLM 审阅所有判决后做最终裁定。"""
        if not judgments:
            return AggregatedJudgment(
                final_judgment="", aggregation_method="meta_judge",
                individual_judgments=[], agreement_score=0,
                dissenting_opinions=[], confidence=0,
            )

        individual_text = ""
        for j in judgments:
            individual_text += f"\n--- 法官 {j.judge_id} 的判决 ---\n{j.judgment_text[:1500]}\n"

        try:
            meta_response = self.primary_llm.chat_completion(
                [{"role": "user", "content": _META_JUDGE_PROMPT.format(
                    individual_judgments=individual_text,
                )}],
                temperature=0.1,
            )
        except Exception as e:
            logger.warning(f"Meta-judge failed: {e}")
            return self.aggregate_majority_vote(judgments)

        agreement = _compute_agreement(judgments)

        return AggregatedJudgment(
            final_judgment=meta_response.strip(),
            aggregation_method="meta_judge",
            individual_judgments=judgments,
            agreement_score=agreement,
            dissenting_opinions=[],
            confidence=min(agreement + 0.2, 1.0),
            metadata={"meta_judge_model": self.primary_llm.model},
        )

    def run(
        self,
        case_facts: str,
        claims: str,
        trial_summary: str = "",
        num_judges: int = 3,
        aggregation: str = "meta_judge",
    ) -> AggregatedJudgment:
        """完整的多法官判决流程。"""
        judgments = self.generate_multi_judgments(
            case_facts, claims, trial_summary, num_judges,
        )

        if aggregation == "meta_judge":
            return self.aggregate_meta_judge(judgments, case_facts)
        return self.aggregate_majority_vote(judgments)
