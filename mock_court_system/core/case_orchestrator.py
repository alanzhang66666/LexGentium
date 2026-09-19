"""
全流程案件编排器（增强版）
串联 CD（起诉状）-> DD（答辩状）-> CI（庭审判决）三阶段管道。

增强内容（修复策略注入 + per-party SimAgent + 跨轮记忆）：
- 策略注入：cd_strategy/dd_strategy 实际通过 SimAgent 策略设置影响当事人行为
- per-party SimAgent：为原告侧和被告侧创建独立策略的 SimAgent
- 跨轮记忆：可注入前轮判决摘要，让当事人在后续轮次调整论证重点
- 争议原因注入：AgentMediation 风格的 dispute cause 可嵌入 case_info
"""
from __future__ import annotations

import json
import os
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

from core import LLMClient, CourtSimulatorClient
from agents import CDAgent, DDAgent, CIAgent, SimAgent
from agents.sim_agent import CONFLICT_STRATEGIES

logger = logging.getLogger("orchestrator")

#: 全案自动 CI 默认步数上限（AGENTS.md：CI_MAX_AUTO_TURNS 默认 30）
DEFAULT_CI_AUTO_TURN_CAP = 30
CI_AUTO_TURN_ENV = "CI_MAX_AUTO_TURNS"


def _env_ci_auto_turn_cap() -> int:
    raw = os.getenv(CI_AUTO_TURN_ENV, "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_CI_AUTO_TURN_CAP
    return value if value > 0 else DEFAULT_CI_AUTO_TURN_CAP


def ci_auto_turn_limit(max_turns: int, cap: Optional[int] = None) -> int:
    """CI 自动阶段步数上限：``min(max_turns * 3, cap)``。

    ``cap`` 缺省读取 ``CI_MAX_AUTO_TURNS``（默认 30，非法值回落 30）。
    达到上限即停止，不再产生额外 CI LLM 调用。
    """
    effective_cap = cap if cap is not None else _env_ci_auto_turn_cap()
    return min(max_turns * 3, effective_cap)


@dataclass
class StageResult:
    scenario: str
    dialog_history: List[Dict[str, Any]]
    final_document: str
    extracted_info: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FullCaseResult:
    case_id: str
    cd_result: Optional[StageResult] = None
    dd_result: Optional[StageResult] = None
    ci_result: Optional[StageResult] = None
    judgment_score: Optional[Dict[str, Any]] = None
    elapsed_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        def _sr(r: Optional[StageResult]) -> Optional[Dict]:
            return asdict(r) if r else None
        return {
            "case_id": self.case_id,
            "cd_result": _sr(self.cd_result),
            "dd_result": _sr(self.dd_result),
            "ci_result": _sr(self.ci_result),
            "judgment_score": self.judgment_score,
            "elapsed_seconds": self.elapsed_seconds,
        }


class _MockApiClient(CourtSimulatorClient):
    """不调远程 API 的空壳，供 Agent 初始化用。"""
    def __init__(self):
        pass


def is_cd_final(text: str) -> bool:
    return _is_cd_final(text)


def is_dd_final(text: str) -> bool:
    return _is_dd_final(text)


def is_ci_final(text: str) -> bool:
    return _is_ci_final(text)


def _is_cd_final(text: str) -> bool:
    clean = text.strip().replace("*", "").replace("#", "").replace(" ", "")
    return clean.startswith("民事起诉状")


def _is_dd_final(text: str) -> bool:
    clean = text.strip().replace("*", "").replace("#", "").replace(" ", "")
    return clean.startswith("民事答辩状")


def _is_ci_final(text: str) -> bool:
    """判决书终止检测。

    覆盖两类真实输出：CI Agent 结构化模板（"案号：..."开头）与
    LLM 按真实判决书格式直出的文本——数据集 200/200 篇判决书
    均以"民事判决书"开头，此前漏召回导致庭审打满最大轮次。
    """
    t = text.strip()
    if t.startswith("案号：") or "【判决结果】" in t:
        return True
    clean = t.replace("*", "").replace("#", "").replace(" ", "")
    return clean.startswith("民事判决书") or clean.startswith("判决书")


# ========== 争议原因注入模板（AgentMediation 五大类） ==========

DISPUTE_CAUSE_TEMPLATES = {
    "information_conflict": "本案存在严重的信息不对称问题，{detail}",
    "resource_conflict": "本案涉及有限资源的分配争议，{detail}",
    "behavioral_misconduct": "本案一方存在明显的行为过错，{detail}",
    "legal_issue": "本案涉及法律规则的理解分歧，{detail}",
    "external_factor": "本案受到外部因素影响，{detail}",
}


def _build_dispute_cause_context(cause_type: Optional[str], cause_detail: Optional[str]) -> str:
    """构建争议原因注入文本。"""
    if not cause_type:
        return ""
    template = DISPUTE_CAUSE_TEMPLATES.get(cause_type, "")
    if not template:
        return ""
    return template.format(detail=cause_detail or "具体细节请参见案件描述")


class FullCaseOrchestrator:
    """编排 CD -> DD -> CI 全流程（增强版：策略注入 + per-party SimAgent）。"""

    def __init__(
        self,
        llm_client: LLMClient,
        cd_agent: CDAgent,
        dd_agent: DDAgent,
        ci_agent: CIAgent,
        sim_agent: SimAgent,
        *,
        max_turns_per_stage: int = 20,
    ):
        self.llm = llm_client
        self.cd_agent = cd_agent
        self.dd_agent = dd_agent
        self.ci_agent = ci_agent
        self.sim_agent = sim_agent
        self.max_turns = max_turns_per_stage

    def _create_party_sim_agent(
        self,
        strategy_type: Optional[str] = None,
        enable_dynamic: bool = False,
    ) -> SimAgent:
        """为特定当事方创建独立策略的 SimAgent 实例。"""
        agent = SimAgent(
            self.llm,
            strategy=strategy_type,
            enable_dynamic_strategy=enable_dynamic,
        )
        return agent

    # ------------------------------------------------------------------
    # 阶段 1：CD（起诉状） - 策略注入修复
    # ------------------------------------------------------------------
    def run_stage_cd(
        self,
        case_info: Dict[str, Any],
        *,
        cd_strategy: Optional[str] = None,
        cd_strategy_type: Optional[str] = None,
        previous_round_summary: Optional[str] = None,
        on_progress=None,
    ) -> StageResult:
        """CDAgent（律师）+ SimAgent（原告当事人）自动对话 -> 起诉状。

        策略注入：cd_strategy_type 设置 SimAgent 的 TKI 策略类型，
        cd_strategy 作为自定义策略文本注入到 SimAgent 上下文。
        """
        case_id = case_info.get("case_id", "auto")

        # 如果有跨轮记忆，注入到 case_info
        input_json = dict(case_info)
        if previous_round_summary:
            input_json["_previous_round_insight"] = previous_round_summary

        # 创建带策略的原告侧 SimAgent
        plaintiff_sim = self._create_party_sim_agent(
            strategy_type=cd_strategy_type,
            enable_dynamic=bool(cd_strategy_type),
        )

        dialog_history: List[Dict[str, Any]] = []
        final_doc = ""

        for round_idx in range(self.max_turns):
            role, text, finished = self._agent_turn(
                "CD", case_id, dialog_history, input_json,
            )
            dialog_history.append({
                "turn": len(dialog_history),
                "role": role,
                "message": text,
            })
            if on_progress:
                on_progress("CD", round_idx, role, finished)
            if finished:
                final_doc = text
                break

            # 使用带策略的 SimAgent
            sim_text = plaintiff_sim.simulate_client(
                dialog_history, input_json, "CD",
            )
            dialog_history.append({
                "turn": len(dialog_history),
                "role": "Client",
                "message": sim_text,
            })

        if not final_doc:
            final_doc = dialog_history[-1]["message"] if dialog_history else ""

        return StageResult(
            scenario="CD",
            dialog_history=dialog_history,
            final_document=final_doc,
            extracted_info=self._extract_cd_info(dialog_history, final_doc),
            metadata={
                "turns": len(dialog_history),
                "cd_strategy": cd_strategy,
                "cd_strategy_type": cd_strategy_type,
                "strategy_injected": cd_strategy_type is not None,
            },
        )

    # ------------------------------------------------------------------
    # 阶段 2：DD（答辩状） - 策略注入修复
    # ------------------------------------------------------------------
    def run_stage_dd(
        self,
        case_info: Dict[str, Any],
        complaint_text: str,
        cd_extracted: Optional[Dict] = None,
        *,
        dd_strategy: Optional[str] = None,
        dd_strategy_type: Optional[str] = None,
        previous_round_summary: Optional[str] = None,
        on_progress=None,
    ) -> StageResult:
        """DDAgent（律师）+ SimAgent（被告当事人）自动对话 -> 答辩状。"""
        case_id = case_info.get("case_id", "auto")
        input_json = {
            **case_info,
            "complaint": {
                "plaintiff_claim": cd_extracted.get("claims", []) if cd_extracted else [],
                "plaintiff_case_description": complaint_text[:3000],
            },
        }
        if previous_round_summary:
            input_json["_previous_round_insight"] = previous_round_summary

        defendant_context = {**case_info}
        if cd_extracted:
            defendant_context["plaintiff_claims"] = cd_extracted.get("claims", [])
            defendant_context["plaintiff_facts"] = cd_extracted.get("facts", "")
        if previous_round_summary:
            defendant_context["_previous_round_insight"] = previous_round_summary

        # 创建带策略的被告侧 SimAgent
        defendant_sim = self._create_party_sim_agent(
            strategy_type=dd_strategy_type,
            enable_dynamic=bool(dd_strategy_type),
        )

        dialog_history: List[Dict[str, Any]] = []
        final_doc = ""

        for round_idx in range(self.max_turns):
            role, text, finished = self._agent_turn(
                "DD", case_id, dialog_history, input_json,
            )
            dialog_history.append({
                "turn": len(dialog_history),
                "role": role,
                "message": text,
            })
            if on_progress:
                on_progress("DD", round_idx, role, finished)
            if finished:
                final_doc = text
                break

            sim_text = defendant_sim.simulate_client(
                dialog_history, defendant_context, "DD",
            )
            dialog_history.append({
                "turn": len(dialog_history),
                "role": "Client",
                "message": sim_text,
            })

        if not final_doc:
            final_doc = dialog_history[-1]["message"] if dialog_history else ""

        return StageResult(
            scenario="DD",
            dialog_history=dialog_history,
            final_document=final_doc,
            extracted_info=self._extract_dd_info(dialog_history, final_doc),
            metadata={
                "turns": len(dialog_history),
                "dd_strategy": dd_strategy,
                "dd_strategy_type": dd_strategy_type,
                "strategy_injected": dd_strategy_type is not None,
            },
        )

    # ------------------------------------------------------------------
    # 阶段 3：CI（庭审 -> 判决） - per-party 策略注入
    # ------------------------------------------------------------------
    def run_stage_ci(
        self,
        case_info: Dict[str, Any],
        complaint_text: str,
        defense_text: str,
        cd_extracted: Optional[Dict] = None,
        dd_extracted: Optional[Dict] = None,
        *,
        plaintiff_strategy_type: Optional[str] = None,
        defendant_strategy_type: Optional[str] = None,
        previous_round_summary: Optional[str] = None,
        on_progress=None,
    ) -> StageResult:
        """CIAgent（法官）+ per-party SimAgent（原告/被告）庭审 -> 判决书。"""
        case_id = case_info.get("case_id", "auto")

        input_json = {
            **case_info,
            "complaint_text": complaint_text[:3000],
            "defense_text": defense_text[:3000],
        }
        if cd_extracted:
            input_json["plaintiff_claims"] = cd_extracted.get("claims", [])
        if dd_extracted:
            input_json["defense_claims"] = dd_extracted.get("defense_claims", [])
        if previous_round_summary:
            input_json["_previous_round_insight"] = previous_round_summary

        # 为原告和被告分别创建带策略的 SimAgent
        plaintiff_sim = self._create_party_sim_agent(
            strategy_type=plaintiff_strategy_type,
            enable_dynamic=bool(plaintiff_strategy_type),
        )
        defendant_sim = self._create_party_sim_agent(
            strategy_type=defendant_strategy_type,
            enable_dynamic=bool(defendant_strategy_type),
        )

        dialog_history: List[Dict[str, Any]] = []
        final_doc = ""
        max_ci_turns = ci_auto_turn_limit(self.max_turns)
        # 跨轮维护 CI 推理状态：避免每轮用启发式规则重放自然语言导致状态漂移
        ci_state = None
        from core.reasoning_state import extract_ci_reasoning_state

        for round_idx in range(max_ci_turns):
            role, text, finished = self._agent_turn(
                "CI", case_id, dialog_history, input_json,
                reasoning_state=ci_state,
            )
            ci_state = extract_ci_reasoning_state(self.ci_agent)
            dialog_history.append({
                "turn": len(dialog_history),
                "role": role,
                "message": text,
            })
            if on_progress:
                on_progress("CI", round_idx, role, finished)
            if finished:
                final_doc = text
                break

            next_role = self._ci_next_role(dialog_history)

            if next_role == "Plaintiff":
                sim_text = plaintiff_sim.simulate_plaintiff_with_strategy(
                    dialog_history,
                    complaint_text=complaint_text,
                    cd_extracted_info=cd_extracted,
                )
            elif next_role == "Defendant":
                sim_text = defendant_sim.simulate_defendant_with_strategy(
                    dialog_history,
                    defense_text=defense_text,
                    dd_extracted_info=dd_extracted,
                )
            else:
                break

            dialog_history.append({
                "turn": len(dialog_history),
                "role": next_role,
                "message": sim_text,
            })

        if not final_doc:
            final_doc = dialog_history[-1]["message"] if dialog_history else ""

        return StageResult(
            scenario="CI",
            dialog_history=dialog_history,
            final_document=final_doc,
            extracted_info={},
            metadata={
                "turns": len(dialog_history),
                "plaintiff_strategy_type": plaintiff_strategy_type,
                "defendant_strategy_type": defendant_strategy_type,
                "strategy_injected": (plaintiff_strategy_type is not None
                                     or defendant_strategy_type is not None),
            },
        )

    # ------------------------------------------------------------------
    # 全流程（增强版：完整策略注入 + 跨轮记忆 + 争议原因注入）
    # ------------------------------------------------------------------
    def run_full_case(
        self,
        case_info: Dict[str, Any],
        *,
        cd_strategy: Optional[str] = None,
        dd_strategy: Optional[str] = None,
        plaintiff_strategy_type: Optional[str] = None,
        defendant_strategy_type: Optional[str] = None,
        previous_round_summary: Optional[str] = None,
        dispute_cause: Optional[str] = None,
        dispute_cause_detail: Optional[str] = None,
        on_progress=None,
    ) -> FullCaseResult:
        """运行完整案件管道 CD -> DD -> CI。

        Args:
            case_info: 案件信息
            cd_strategy: 原告策略文本（自定义指令）
            dd_strategy: 被告策略文本（自定义指令）
            plaintiff_strategy_type: 原告 TKI 策略类型
            defendant_strategy_type: 被告 TKI 策略类型
            previous_round_summary: 前轮判决摘要（跨轮记忆）
            dispute_cause: 争议原因类型
            dispute_cause_detail: 争议原因详情
        """
        t0 = time.time()
        case_id = case_info.get("case_id", "auto")

        # 注入争议原因到案件信息
        enriched_case = dict(case_info)
        cause_ctx = _build_dispute_cause_context(dispute_cause, dispute_cause_detail)
        if cause_ctx:
            existing_desc = enriched_case.get("case_description", "")
            enriched_case["case_description"] = f"{existing_desc}\n\n【争议原因分析】{cause_ctx}"
            enriched_case["_dispute_cause"] = dispute_cause
            enriched_case["_dispute_cause_detail"] = dispute_cause_detail

        cd_result = self.run_stage_cd(
            enriched_case,
            cd_strategy=cd_strategy,
            cd_strategy_type=plaintiff_strategy_type,
            previous_round_summary=previous_round_summary,
            on_progress=on_progress,
        )

        dd_result = self.run_stage_dd(
            enriched_case,
            complaint_text=cd_result.final_document,
            cd_extracted=cd_result.extracted_info,
            dd_strategy=dd_strategy,
            dd_strategy_type=defendant_strategy_type,
            previous_round_summary=previous_round_summary,
            on_progress=on_progress,
        )

        ci_result = self.run_stage_ci(
            enriched_case,
            complaint_text=cd_result.final_document,
            defense_text=dd_result.final_document,
            cd_extracted=cd_result.extracted_info,
            dd_extracted=dd_result.extracted_info,
            plaintiff_strategy_type=plaintiff_strategy_type,
            defendant_strategy_type=defendant_strategy_type,
            previous_round_summary=previous_round_summary,
            on_progress=on_progress,
        )

        return FullCaseResult(
            case_id=case_id,
            cd_result=cd_result,
            dd_result=dd_result,
            ci_result=ci_result,
            elapsed_seconds=round(time.time() - t0, 2),
        )

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------
    def _agent_turn(
        self, scenario: str, case_id: str,
        dialog_history: List[Dict], input_json: Optional[Dict],
        reasoning_state: Optional[Dict] = None,
    ):
        if scenario == "CD":
            text = self.cd_agent.process_turn(dialog_history, case_id, input_json)
            if _is_cd_final(text):
                return "Final", text, True
            return "Lawyer", text, False
        elif scenario == "DD":
            text = self.dd_agent.process_turn(dialog_history, case_id, input_json)
            if _is_dd_final(text):
                return "Final", text, True
            return "Lawyer", text, False
        elif scenario == "CI":
            text = self.ci_agent.process_turn(
                dialog_history, case_id, input_json,
                reasoning_state=reasoning_state,
            )
            if _is_ci_final(text):
                return "Final", text, True
            return "Judge", text, False
        raise ValueError(f"Unknown scenario: {scenario}")

    @staticmethod
    def _ci_next_role(dialog_history: List[Dict]) -> str:
        if not dialog_history:
            return "Plaintiff"
        last_role = dialog_history[-1].get("role", "")
        if last_role == "Judge":
            msg = dialog_history[-1].get("message", "")
            if "被告" in msg:
                return "Defendant"
            return "Plaintiff"
        if last_role == "Plaintiff":
            return "Defendant"
        return "Plaintiff"

    @staticmethod
    def _extract_cd_info(dialog_history: List[Dict], final_doc: str) -> Dict:
        claims, facts_parts = [], []
        for item in dialog_history:
            msg = item.get("message", "")
            if item.get("role") == "Client":
                facts_parts.append(msg)
        return {
            "claims": claims,
            "facts": "\n".join(facts_parts[-5:]) if facts_parts else "",
            "complaint_text": final_doc,
        }

    @staticmethod
    def _extract_dd_info(dialog_history: List[Dict], final_doc: str) -> Dict:
        defense_claims, facts = [], []
        for item in dialog_history:
            if item.get("role") == "Client":
                facts.append(item.get("message", ""))
        return {
            "defense_claims": defense_claims,
            "facts": facts,
            "defense_text": final_doc,
        }
