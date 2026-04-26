"""
Behavior-Liability-Statute 推理链
基于 CADD (2511.11715) 的结构化推理框架，
从行为到法律后果建立可追溯的推理链条。

推理链结构：
  Behavior（行为）→ Liability（责任类型）→ Statute（适用法条）

用途：
- 在判决书生成后，提取结构化的责任归因链
- 为博弈评测提供法律推理质量的定量指标
- 支持反事实分析（如果行为不同，责任如何变化）
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional

logger = logging.getLogger("liability_chain")

_EXTRACT_CHAIN_PROMPT = """你是一位法律推理专家。请从以下判决书/调解方案中提取 Behavior-Liability-Statute 推理链。

【判决书/调解方案】
{judgment_text}

请识别所有参与方的行为及其对应的法律责任和法律依据，以结构化方式输出。

输出严格 JSON 格式：
{{
  "chains": [
    {{
      "party": "行为方名称（如原告/被告）",
      "behavior": "具体行为描述",
      "behavior_type": "行为类型（如：违约/侵权/不当得利/缔约过失等）",
      "liability_type": "责任类型（如：违约责任/侵权损害赔偿/返还不当得利等）",
      "statute": "适用法条全文引用（如：民法典第577条）",
      "statute_article": "法条编号（如：民法典577）",
      "court_adoption": true或false（法院是否采纳该推理）,
      "reasoning": "法院就该行为与责任之间因果关系的论证要点"
    }}
  ],
  "overall_liability_allocation": {{
    "原告": "承担比例或金额",
    "被告": "承担比例或金额"
  }},
  "key_dispute_resolution": "核心争议的最终裁判结论"
}}
"""

_COUNTERFACTUAL_CHAIN_PROMPT = """你是一位法律因果推理专家。请基于以下已有的 Behavior-Liability-Statute 推理链，
分析如果某方行为发生变化，法律责任将如何变化。

【现有推理链】
{existing_chain}

【假设行为变化】
{party} 的行为从「{original_behavior}」变为「{hypothetical_behavior}」

请分析：
1. 该行为变化是否会改变责任类型？
2. 适用法条是否会变化？
3. 最终判决结果可能如何变化？

输出 JSON：
{{
  "liability_change": true/false,
  "new_liability_type": "变化后的责任类型",
  "new_statute": "变化后适用的法条",
  "impact_assessment": "影响评估",
  "judgment_change_prediction": "判决结果变化预测"
}}
"""


@dataclass
class ChainItem:
    """推理链条目"""
    party: str
    behavior: str
    behavior_type: str
    liability_type: str
    statute: str
    statute_article: str
    court_adoption: bool
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LiabilityChainResult:
    """推理链提取结果"""
    chains: List[ChainItem]
    overall_allocation: Dict[str, str]
    key_resolution: str
    quality_metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chains": [c.to_dict() for c in self.chains],
            "overall_liability_allocation": self.overall_allocation,
            "key_dispute_resolution": self.key_resolution,
            "quality_metrics": self.quality_metrics,
        }


class LiabilityChainExtractor:
    """从判决书中提取 Behavior-Liability-Statute 推理链。"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def extract(self, judgment_text: str) -> LiabilityChainResult:
        """从判决文本提取推理链。"""
        if not judgment_text or len(judgment_text.strip()) < 50:
            return LiabilityChainResult(
                chains=[], overall_allocation={},
                key_resolution="", quality_metrics={"score": 0},
            )

        prompt = _EXTRACT_CHAIN_PROMPT.format(
            judgment_text=judgment_text[:4000],
        )

        try:
            result = self.llm.chat_json(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
            )
        except Exception as e:
            logger.warning(f"推理链提取 LLM 调用失败: {e}")
            result = {}

        if not isinstance(result, dict):
            result = {}

        chains = []
        for item in result.get("chains", []):
            if isinstance(item, dict):
                chains.append(ChainItem(
                    party=item.get("party", ""),
                    behavior=item.get("behavior", ""),
                    behavior_type=item.get("behavior_type", ""),
                    liability_type=item.get("liability_type", ""),
                    statute=item.get("statute", ""),
                    statute_article=item.get("statute_article", ""),
                    court_adoption=item.get("court_adoption", False),
                    reasoning=item.get("reasoning", ""),
                ))

        quality = self._assess_chain_quality(chains, judgment_text)

        return LiabilityChainResult(
            chains=chains,
            overall_allocation=result.get("overall_liability_allocation", {}),
            key_resolution=result.get("key_dispute_resolution", ""),
            quality_metrics=quality,
        )

    def counterfactual(
        self,
        existing_chain: LiabilityChainResult,
        party: str,
        original_behavior: str,
        hypothetical_behavior: str,
    ) -> Dict[str, Any]:
        """反事实推理：如果行为改变，责任如何变化。"""
        chain_text = json.dumps(
            [c.to_dict() for c in existing_chain.chains],
            ensure_ascii=False, indent=2,
        )[:3000]

        prompt = _COUNTERFACTUAL_CHAIN_PROMPT.format(
            existing_chain=chain_text,
            party=party,
            original_behavior=original_behavior,
            hypothetical_behavior=hypothetical_behavior,
        )

        try:
            result = self.llm.chat_json(
                [{"role": "user", "content": prompt}],
                temperature=0.2,
            )
        except Exception as e:
            logger.warning(f"反事实推理 LLM 调用失败: {e}")
            result = {}

        return result if isinstance(result, dict) else {}

    @staticmethod
    def _assess_chain_quality(chains: List[ChainItem], judgment_text: str) -> Dict[str, Any]:
        """评估推理链质量。"""
        if not chains:
            return {"score": 0.0, "completeness": 0.0, "statute_coverage": 0.0}

        # 完整性：有多少条链有完整的 behavior + liability + statute
        complete = sum(
            1 for c in chains
            if c.behavior and c.liability_type and c.statute
        )
        completeness = complete / len(chains) if chains else 0

        # 法条覆盖：提取的法条在判决文本中是否出现
        statutes_found = 0
        for c in chains:
            if c.statute_article:
                article_num = re.sub(r'[^\d]', '', c.statute_article)
                if article_num and article_num in judgment_text:
                    statutes_found += 1
        statute_coverage = statutes_found / len(chains) if chains else 0

        # 法院采纳率
        adopted = sum(1 for c in chains if c.court_adoption)
        adoption_rate = adopted / len(chains) if chains else 0

        overall = completeness * 0.4 + statute_coverage * 0.3 + adoption_rate * 0.3

        return {
            "score": round(overall, 4),
            "completeness": round(completeness, 4),
            "statute_coverage": round(statute_coverage, 4),
            "adoption_rate": round(adoption_rate, 4),
            "chain_count": len(chains),
            "complete_chains": complete,
        }
