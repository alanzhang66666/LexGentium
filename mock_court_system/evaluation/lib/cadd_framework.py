"""
CADD 框架扩展
基于 CADD (2511.11715v1) 的核心思想，
实现对称行为记录、可解释决策生成和渐进式基准测试。

1. 对称行为记录 (Symmetric Behavior Annotation)
   - 庭审过程中同时记录原告和被告的行为特征
   - 每轮发言提取行为类型、策略倾向、情绪状态

2. 可解释决策生成 (Explainable Decision Generation)
   - 将 "检测器置信度下降" 转化为 "因为对方享有优先通行权所以系统让行"
   - 每个判决点都附带人类可理解的法律解释

3. 渐进式基准 (Progressive Benchmarking)
   - Level 1: 基础责任分类
   - Level 2: 细粒度法条识别
   - Level 3: 时序因果重建
   - Level 4: 可解释决策生成
   - Level 5: 反事实推理
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

logger = logging.getLogger("cadd_framework")

# ========== 1. 对称行为记录 ==========

_BEHAVIOR_EXTRACT_PROMPT = """你是一位法庭行为分析专家。请从以下单轮发言中提取发言者的行为特征。

【发言者】{speaker}
【发言阶段】{stage}
【发言内容】
{utterance}

请提取以下信息：
1. 行为类型：从以下选项中选择一个最匹配的
   - assert_claim（主张权利/提出诉求）
   - present_evidence（举证/提交证据）
   - challenge（质疑/反驳对方）
   - concede（让步/承认部分事实）
   - evade（回避/模糊回答）
   - cooperate（配合/表达合作意愿）
   - emotional_appeal（情感诉求）
   - procedural（程序性发言/回应法官指令）

2. 策略倾向：competing/collaborating/compromising/avoiding/accommodating
3. 情绪状态：calm/anxious/angry/sad/confident/frustrated
4. 关键主张或事实：简要概括

输出 JSON：
{{"behavior_type": "...", "strategy_tendency": "...", "emotion": "...", "key_point": "简要概括", "assertiveness": 0-10, "cooperativeness": 0-10}}
"""


@dataclass
class BehaviorRecord:
    """单轮对称行为记录"""
    turn: int
    speaker: str
    stage: str
    behavior_type: str
    strategy_tendency: str
    emotion: str
    key_point: str
    assertiveness: float
    cooperativeness: float
    raw_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SymmetricBehaviorTracker:
    """对称行为追踪器：同时记录双方行为。"""

    def __init__(self, llm_client):
        self.llm = llm_client
        self._records: List[BehaviorRecord] = []

    def record_turn(
        self,
        turn: int,
        speaker: str,
        stage: str,
        utterance: str,
    ) -> BehaviorRecord:
        """从单轮发言提取行为记录。"""
        try:
            result = self.llm.chat_json(
                [{"role": "user", "content": _BEHAVIOR_EXTRACT_PROMPT.format(
                    speaker=speaker,
                    stage=stage,
                    utterance=utterance[:1000],
                )}],
                temperature=0.1,
            )
        except Exception as e:
            logger.warning(f"行为提取失败: {e}")
            result = {}

        if not isinstance(result, dict):
            result = {}

        record = BehaviorRecord(
            turn=turn,
            speaker=speaker,
            stage=stage,
            behavior_type=result.get("behavior_type", "procedural"),
            strategy_tendency=result.get("strategy_tendency", "compromising"),
            emotion=result.get("emotion", "calm"),
            key_point=result.get("key_point", ""),
            assertiveness=float(result.get("assertiveness", 5)),
            cooperativeness=float(result.get("cooperativeness", 5)),
            raw_message=utterance[:500],
        )
        self._records.append(record)
        return record

    def record_dialog_history(
        self,
        dialog_history: List[Dict[str, Any]],
        party_roles: Optional[List[str]] = None,
    ) -> List[BehaviorRecord]:
        """批量从对话历史提取行为记录（仅提取当事人的发言）。"""
        if party_roles is None:
            party_roles = ["Plaintiff", "Defendant", "原告", "被告", "Client"]

        records = []
        for item in dialog_history:
            role = item.get("role", "")
            if role not in party_roles:
                continue
            rec = self.record_turn(
                turn=item.get("turn", len(records)),
                speaker=role,
                stage=item.get("stage", "unknown"),
                utterance=item.get("message", ""),
            )
            records.append(rec)
        return records

    def get_symmetric_summary(self) -> Dict[str, Any]:
        """生成对称行为摘要。"""
        speakers = set(r.speaker for r in self._records)
        summary = {}

        for speaker in speakers:
            speaker_records = [r for r in self._records if r.speaker == speaker]
            if not speaker_records:
                continue

            behavior_counts = {}
            strategy_counts = {}
            emotion_counts = {}
            total_assert = 0
            total_coop = 0

            for r in speaker_records:
                behavior_counts[r.behavior_type] = behavior_counts.get(r.behavior_type, 0) + 1
                strategy_counts[r.strategy_tendency] = strategy_counts.get(r.strategy_tendency, 0) + 1
                emotion_counts[r.emotion] = emotion_counts.get(r.emotion, 0) + 1
                total_assert += r.assertiveness
                total_coop += r.cooperativeness

            n = len(speaker_records)
            summary[speaker] = {
                "turn_count": n,
                "dominant_behavior": max(behavior_counts, key=behavior_counts.get),
                "behavior_distribution": behavior_counts,
                "dominant_strategy": max(strategy_counts, key=strategy_counts.get),
                "strategy_distribution": strategy_counts,
                "dominant_emotion": max(emotion_counts, key=emotion_counts.get),
                "emotion_distribution": emotion_counts,
                "avg_assertiveness": round(total_assert / n, 2),
                "avg_cooperativeness": round(total_coop / n, 2),
            }

        return {"speakers": summary, "total_records": len(self._records)}

    def get_all_records(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._records]


# ========== 2. 可解释决策生成 ==========

_EXPLAINABLE_DECISION_PROMPT = """你是一位法律解释专家。请将以下判决要点转化为普通人能理解的解释。

【判决要点】
{decision_point}

【相关法律依据】
{legal_basis}

【案件背景简述】
{case_summary}

请生成两个版本的解释：
1. 法律专业版（面向律师和法官）
2. 通俗版（面向普通公民，不使用法律术语）

输出 JSON：
{{"professional_explanation": "法律专业版解释", "plain_explanation": "通俗版解释", "key_legal_principle": "核心法律原则", "analogy": "类比说明（用日常生活例子解释）"}}
"""


class ExplainableDecisionGenerator:
    """可解释决策生成器。"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def explain_decision(
        self,
        decision_point: str,
        legal_basis: str = "",
        case_summary: str = "",
    ) -> Dict[str, Any]:
        """为单个判决点生成可解释说明。"""
        try:
            result = self.llm.chat_json(
                [{"role": "user", "content": _EXPLAINABLE_DECISION_PROMPT.format(
                    decision_point=decision_point[:1000],
                    legal_basis=legal_basis[:500],
                    case_summary=case_summary[:500],
                )}],
                temperature=0.2,
            )
        except Exception as e:
            logger.warning(f"可解释决策生成失败: {e}")
            result = {}

        return result if isinstance(result, dict) else {}

    def explain_full_judgment(
        self,
        judgment_text: str,
        case_summary: str = "",
    ) -> Dict[str, Any]:
        """为完整判决书生成可解释版本。"""
        # 提取判决主文部分
        decision_points = []

        patterns = [
            r'(判决如下[：:].+?)(?=\n\n|本判决|如不服)',
            r'(一[、．].+?)(?=\n\n|本判决)',
            r'(驳回.+?诉讼请求)',
            r'(被告.*?应.*?支付.*?\d+)',
        ]

        for pat in patterns:
            matches = re.findall(pat, judgment_text, re.DOTALL)
            for m in matches:
                if len(m.strip()) > 10:
                    decision_points.append(m.strip()[:500])

        if not decision_points:
            decision_points = [judgment_text[-500:]]

        explanations = []
        for dp in decision_points[:5]:
            exp = self.explain_decision(dp, "", case_summary)
            explanations.append({
                "decision_point": dp[:200],
                "explanation": exp,
            })

        return {
            "decision_points_count": len(decision_points),
            "explanations": explanations,
        }


# ========== 3. 渐进式基准测试 ==========

PROGRESSIVE_BENCHMARK_LEVELS = {
    1: {
        "name": "基础责任分类",
        "description": "判断原告/被告谁应承担主要责任",
        "difficulty": "easy",
        "required_capabilities": ["fact_finding", "basic_liability"],
        "evaluation_method": "binary_accuracy",
    },
    2: {
        "name": "细粒度法条识别",
        "description": "识别案件适用的具体法律条文",
        "difficulty": "medium",
        "required_capabilities": ["memorization", "understanding"],
        "evaluation_method": "law_accuracy",
    },
    3: {
        "name": "时序因果重建",
        "description": "重建事件发生的完整时间线和因果关系",
        "difficulty": "medium-hard",
        "required_capabilities": ["logic_inference", "temporal_reasoning"],
        "evaluation_method": "causal_chain_quality",
    },
    4: {
        "name": "可解释决策生成",
        "description": "为每个判决点提供可理解的法律解释",
        "difficulty": "hard",
        "required_capabilities": ["generation", "discrimination"],
        "evaluation_method": "explanation_quality",
    },
    5: {
        "name": "反事实推理",
        "description": "分析如果某方行为不同，结果会如何变化",
        "difficulty": "very-hard",
        "required_capabilities": ["counterfactual_reasoning", "causal_inference"],
        "evaluation_method": "counterfactual_validity",
    },
}


def get_benchmark_level_info(level: int) -> Dict[str, Any]:
    """获取渐进式基准的层级信息。"""
    info = PROGRESSIVE_BENCHMARK_LEVELS.get(level)
    if not info:
        return {"error": f"Unknown level: {level}. Valid: 1-5"}
    return {"level": level, **info}


def assess_agent_capability_level(
    evaluation_results: Dict[str, Any],
) -> Dict[str, Any]:
    """基于评测结果评估 Agent 达到的能力层级。"""
    achieved_levels = []

    # Level 1: 基础责任分类
    liability_chain = evaluation_results.get("liability_chain", {})
    if liability_chain.get("quality_metrics", {}).get("score", 0) > 0.3:
        achieved_levels.append(1)

    # Level 2: 法条识别
    law_eval = evaluation_results.get("law_accuracy", {})
    if (law_eval.get("law_accuracy") or 0) > 0.3:
        achieved_levels.append(2)

    # Level 3: 因果推理
    lexeval = evaluation_results.get("lexeval_cognitive", {})
    logic = next(
        (l for l in lexeval.get("levels", []) if l.get("level") == "logic_inference"),
        {},
    )
    if float(logic.get("score", 0)) >= 6:
        achieved_levels.append(3)

    # Level 4: 可解释性
    generation = next(
        (l for l in lexeval.get("levels", []) if l.get("level") == "generation"),
        {},
    )
    if float(generation.get("score", 0)) >= 6:
        achieved_levels.append(4)

    # Level 5: 反事实推理（需要反事实分析结果）
    counterfactual = evaluation_results.get("counterfactual_analysis", {})
    if counterfactual and counterfactual.get("llm_prediction", {}).get("recommendation"):
        achieved_levels.append(5)

    max_level = max(achieved_levels) if achieved_levels else 0

    return {
        "max_achieved_level": max_level,
        "achieved_levels": achieved_levels,
        "total_levels": 5,
        "level_details": {
            lvl: {
                **PROGRESSIVE_BENCHMARK_LEVELS[lvl],
                "achieved": lvl in achieved_levels,
            }
            for lvl in range(1, 6)
        },
    }
