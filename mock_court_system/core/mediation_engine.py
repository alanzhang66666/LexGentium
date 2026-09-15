"""
五阶段调解引擎
基于 AgentMediation (2509.06586) 的 Harvard HDR 框架实现。

五阶段流水线：
I.   Preliminary   —— 系统介绍案件背景，建立共识基础
II.  Statement     —— 各方陈述立场和诉求
III. OptionGen     —— 调解员归纳争议焦点、法律依据，生成初步方案
IV.  Bargaining    —— 多轮协商（参与者同意/反对/提出替代方案）
V.   Closure       —— 达成协议/确认分歧/轮次耗尽 → 调解员输出最终方案

参与者：
- Mediator（调解员）—— 由 LLM 驱动
- Party（当事人）   —— 可由 SimAgent 或人工驱动，支持 TKI 策略注入
"""
from __future__ import annotations

import json
import os
import time
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional

from core import LLMClient
from core.store.mediation_session_store import MediationSessionStore

logger = logging.getLogger("mediation_engine")
_DEFAULT_MEDIATION_DB = os.path.join("data", "mediation_sessions.sqlite3")


class MediationStage(Enum):
    PRELIMINARY = "preliminary"
    STATEMENT = "statement"
    OPTION_GENERATION = "option_generation"
    BARGAINING = "bargaining"
    CLOSURE = "closure"
    FINISHED = "finished"


@dataclass
class MediationTurn:
    stage: str
    round_index: int
    role: str
    message: str


@dataclass
class MediationResult:
    session_id: str
    stages_completed: List[str]
    dialog_history: List[Dict[str, Any]]
    final_solution: str
    outcome: str  # "agreement" | "disagreement" | "round_limit"
    party_decisions: Dict[str, str]  # {party_name: "accept"/"reject"/"undecided"}
    metadata: Dict[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ========== Prompt 模板 ==========

_MEDIATOR_SYSTEM = """你是一位经验丰富的人民调解员。你的职责是：
1. 保持中立，不偏向任何一方
2. 引导各方理性表达诉求
3. 归纳争议焦点，寻找共同利益
4. 基于法律规定和公平原则提出调解方案
5. 在各方之间寻求妥协和共识

案件背景：
{case_background}

当前调解阶段：{stage}
"""

_PRELIMINARY_PROMPT = """请作为调解员，向各方介绍案件背景，说明调解程序和规则，建立互信氛围。

案件背景：
{case_background}

请简要介绍：
1. 案件基本事实
2. 调解的目的和优势
3. 调解程序说明
4. 各方的权利和义务
"""

_OPTION_GEN_PROMPT = """请作为调解员，基于各方陈述和案件事实，归纳争议焦点并生成初步调解方案。

案件背景：
{case_background}

各方陈述：
{statements}

请输出 JSON：
{{
  "dispute_points": ["争议焦点1", "争议焦点2"],
  "legal_bases": ["相关法律依据1", "相关法律依据2"],
  "proposed_solution": "初步调解方案内容",
  "rationale": "方案依据和理由"
}}
"""

_BARGAINING_MEDIATOR_PROMPT = """你是调解员。当前是协商阶段第 {round_index} 轮。

案件背景：
{case_background}

初步方案：
{proposed_solution}

协商历史：
{bargaining_history}

请基于当前协商进展：
1. 总结各方立场变化
2. 识别仍存在分歧的问题
3. 提出调整后的建议方案或折中方案
4. 引导各方做出回应

请直接输出你作为调解员的发言。
"""

_CLOSURE_PROMPT = """调解即将结束。请作为调解员，总结整个调解过程并输出最终调解方案。

案件背景：
{case_background}

完整对话：
{full_dialog}

各方最终态度：
{final_attitudes}

请输出最终调解方案（包含责任分配、金额、时限等具体内容）。
如果达成协议，请明确各方的义务。
如果未达成协议，请说明主要分歧并建议后续途径。
"""

_PARTY_RESPONSE_PROMPT = """你是当事人「{party_name}」，正在参与调解。

你的背景和诉求：
{party_context}

{strategy_instruction}

调解员刚才说：
{mediator_message}

请从你的角度回应。你可以：
- 表示同意或接受
- 表示反对并说明原因
- 提出替代方案或让步条件
- 要求澄清某些问题

请保持 3-5 句话的简洁回应。
"""


class MediationEngine:
    """五阶段调解引擎。"""

    def __init__(self, llm_client: LLMClient, sim_agent=None, persist_path: Optional[str] = None):
        self.llm = llm_client
        self.sim_agent = sim_agent
        self._sessions: Dict[str, Dict[str, Any]] = {}
        if persist_path == "":
            self._store = None
        else:
            path = persist_path or os.getenv("MEDIATION_DB_PATH") or _DEFAULT_MEDIATION_DB
            self._store = MediationSessionStore(path)

    def _serialize_session(self, sess: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(sess)
        stage = payload.get("stage")
        if isinstance(stage, MediationStage):
            payload["stage"] = stage.value
        return payload

    def _deserialize_session(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(data)
        stage = payload.get("stage")
        if isinstance(stage, str):
            try:
                payload["stage"] = MediationStage(stage)
            except ValueError:
                payload["stage"] = MediationStage.PRELIMINARY
        return payload

    def _save(self, session_id: str) -> None:
        if not self._store or session_id not in self._sessions:
            return
        self._store.save(session_id, self._serialize_session(self._sessions[session_id]))

    def create_session(
        self,
        session_id: str,
        case_info: Dict[str, Any],
        party_names: Optional[List[str]] = None,
        max_bargaining_rounds: int = 5,
        nbs_reference_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建调解会话。

        ``nbs_reference_text``：纳什讨价还价公平参考点说明，将注入方案生成与协商阶段的调解员提示。
        """
        if not party_names:
            party_names = ["原告", "被告"]

        self._sessions[session_id] = {
            "case_info": case_info,
            "party_names": party_names,
            "stage": MediationStage.PRELIMINARY,
            "dialog_history": [],
            "statements": {},
            "proposed_solution": "",
            "dispute_points": [],
            "legal_bases": [],
            "bargaining_round": 0,
            "max_bargaining_rounds": max_bargaining_rounds,
            "party_decisions": {name: "undecided" for name in party_names},
            "stages_completed": [],
            "created_at": time.time(),
            "nbs_reference_text": (nbs_reference_text or "").strip(),
        }
        self._save(session_id)

        return {
            "session_id": session_id,
            "stage": MediationStage.PRELIMINARY.value,
            "party_names": party_names,
        }

    def _get_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self._sessions and self._store:
            raw = self._store.get(session_id)
            if raw:
                self._sessions[session_id] = self._deserialize_session(raw)
        if session_id not in self._sessions:
            raise ValueError("调解会话不存在。后端重启后若存档缺失，请重新创建。")
        return self._sessions[session_id]

    def _add_turn(self, sess: Dict, stage: str, role: str, message: str):
        sess["dialog_history"].append({
            "stage": stage,
            "round": len(sess["dialog_history"]),
            "role": role,
            "message": message,
        })

    def _case_bg(self, sess: Dict) -> str:
        ci = sess["case_info"]
        return json.dumps(
            {k: str(v)[:300] for k, v in ci.items() if k != "dialog_history"},
            ensure_ascii=False,
        )[:2000]

    # ================================================================
    # Stage I: Preliminary
    # ================================================================

    def run_preliminary(self, session_id: str) -> Dict[str, Any]:
        """Stage I: 调解员介绍案件和程序。"""
        sess = self._get_session(session_id)

        prompt = _PRELIMINARY_PROMPT.format(case_background=self._case_bg(sess))

        response = self.llm.chat_completion(
            [
                {"role": "system", "content": _MEDIATOR_SYSTEM.format(
                    case_background=self._case_bg(sess), stage="初步阶段")},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        self._add_turn(sess, "preliminary", "Mediator", response)
        sess["stage"] = MediationStage.STATEMENT
        sess["stages_completed"].append("preliminary")
        self._save(session_id)

        return {
            "stage": "preliminary",
            "mediator_message": response,
            "next_stage": "statement",
        }

    # ================================================================
    # Stage II: Statement
    # ================================================================

    def run_statement(
        self,
        session_id: str,
        party_name: str,
        statement: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Stage II: 当事人陈述。如果未提供 statement，由 LLM 生成。"""
        sess = self._get_session(session_id)

        if statement is None:
            party_context = self._build_party_context(sess, party_name)
            prompt = _PARTY_RESPONSE_PROMPT.format(
                party_name=party_name,
                party_context=party_context,
                strategy_instruction="请简要陈述你的立场、诉求和关切。",
                mediator_message="请你向调解员陈述你的基本立场和诉求。",
            )
            statement = self.llm.chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.3,
            )

        self._add_turn(sess, "statement", party_name, statement)
        sess["statements"][party_name] = statement

        all_stated = all(name in sess["statements"] for name in sess["party_names"])
        if all_stated:
            sess["stage"] = MediationStage.OPTION_GENERATION
            sess["stages_completed"].append("statement")
        self._save(session_id)

        return {
            "stage": "statement",
            "party": party_name,
            "statement": statement,
            "all_parties_stated": all_stated,
            "next_stage": "option_generation" if all_stated else "statement",
            "remaining_parties": [n for n in sess["party_names"] if n not in sess["statements"]],
        }

    # ================================================================
    # Stage III: Option Generation
    # ================================================================

    def run_option_generation(self, session_id: str) -> Dict[str, Any]:
        """Stage III: 调解员归纳争议焦点并生成方案。"""
        sess = self._get_session(session_id)

        statements_text = "\n".join(
            f"{name}: {text}" for name, text in sess["statements"].items()
        )

        nbs_block = sess.get("nbs_reference_text") or ""
        prefix = f"{nbs_block}\n\n" if nbs_block else ""

        prompt = prefix + _OPTION_GEN_PROMPT.format(
            case_background=self._case_bg(sess),
            statements=statements_text,
        )

        try:
            result = self.llm.chat_json(
                [{"role": "user", "content": prompt}],
                temperature=0.2,
            )
        except Exception:
            result = {}

        if not isinstance(result, dict):
            result = {}

        sess["dispute_points"] = result.get("dispute_points", [])
        sess["legal_bases"] = result.get("legal_bases", [])
        sess["proposed_solution"] = result.get("proposed_solution", "")
        rationale = result.get("rationale", "")

        mediator_msg = (
            f"经过各方陈述，本调解员归纳争议焦点如下：\n"
            f"{'、'.join(sess['dispute_points'])}\n\n"
            f"相关法律依据：{'、'.join(sess['legal_bases'])}\n\n"
            f"初步调解方案：{sess['proposed_solution']}\n\n"
            f"理由：{rationale}"
        )
        self._add_turn(sess, "option_generation", "Mediator", mediator_msg)
        sess["stage"] = MediationStage.BARGAINING
        sess["stages_completed"].append("option_generation")
        self._save(session_id)

        return {
            "stage": "option_generation",
            "dispute_points": sess["dispute_points"],
            "legal_bases": sess["legal_bases"],
            "proposed_solution": sess["proposed_solution"],
            "rationale": rationale,
            "mediator_message": mediator_msg,
            "next_stage": "bargaining",
        }

    # ================================================================
    # Stage IV: Bargaining
    # ================================================================

    def run_bargaining_turn(
        self,
        session_id: str,
        party_responses: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Stage IV: 一轮协商（调解员引导 + 各方回应）。"""
        sess = self._get_session(session_id)
        round_idx = sess["bargaining_round"]

        # 调解员发言
        bargaining_history = "\n".join(
            f"{item['role']}: {item['message'][:200]}"
            for item in sess["dialog_history"]
            if item.get("stage") == "bargaining"
        )

        nbs_block = sess.get("nbs_reference_text") or ""
        case_bg = self._case_bg(sess)
        if nbs_block:
            case_bg = f"{nbs_block}\n\n【案件背景】\n{case_bg}"

        mediator_prompt = _BARGAINING_MEDIATOR_PROMPT.format(
            round_index=round_idx + 1,
            case_background=case_bg,
            proposed_solution=sess["proposed_solution"],
            bargaining_history=bargaining_history or "（首轮协商）",
        )

        mediator_msg = self.llm.chat_completion(
            [
                {"role": "system", "content": _MEDIATOR_SYSTEM.format(
                    case_background=self._case_bg(sess), stage=f"协商第{round_idx+1}轮")},
                {"role": "user", "content": mediator_prompt},
            ],
            temperature=0.3,
        )
        self._add_turn(sess, "bargaining", "Mediator", mediator_msg)

        # 各方回应
        responses = {}
        for name in sess["party_names"]:
            if party_responses and name in party_responses:
                resp = party_responses[name]
            else:
                party_context = self._build_party_context(sess, name)
                prompt = _PARTY_RESPONSE_PROMPT.format(
                    party_name=name,
                    party_context=party_context,
                    strategy_instruction="",
                    mediator_message=mediator_msg,
                )
                resp = self.llm.chat_completion(
                    [{"role": "user", "content": prompt}],
                    temperature=0.3,
                )

            self._add_turn(sess, "bargaining", name, resp)
            responses[name] = resp

        sess["bargaining_round"] = round_idx + 1

        # 检查终止条件
        all_agree = all(
            any(kw in r for kw in ["接受", "同意", "可以", "没问题"])
            for r in responses.values()
        )
        all_disagree = all(
            any(kw in r for kw in ["拒绝", "不接受", "不同意", "不行"])
            for r in responses.values()
        )
        round_limit = sess["bargaining_round"] >= sess["max_bargaining_rounds"]

        termination = None
        if all_agree:
            termination = "agreement"
        elif all_disagree:
            termination = "disagreement"
        elif round_limit:
            termination = "round_limit"

        if termination:
            sess["stage"] = MediationStage.CLOSURE
            sess["stages_completed"].append("bargaining")
        self._save(session_id)

        return {
            "stage": "bargaining",
            "round_index": round_idx,
            "mediator_message": mediator_msg,
            "party_responses": responses,
            "termination_condition": termination,
            "next_stage": "closure" if termination else "bargaining",
            "rounds_remaining": sess["max_bargaining_rounds"] - sess["bargaining_round"],
        }

    # ================================================================
    # Stage V: Closure
    # ================================================================

    def run_closure(self, session_id: str) -> MediationResult:
        """Stage V: 调解结案。"""
        sess = self._get_session(session_id)

        full_dialog = "\n".join(
            f"[{item.get('stage', '')}] {item['role']}: {item['message'][:300]}"
            for item in sess["dialog_history"]
        )

        # 最终态度判定
        final_attitudes = {}
        for name in sess["party_names"]:
            last_msgs = [
                item for item in sess["dialog_history"]
                if item["role"] == name and item.get("stage") == "bargaining"
            ]
            if last_msgs:
                last = last_msgs[-1]["message"]
                if any(kw in last for kw in ["接受", "同意", "可以"]):
                    final_attitudes[name] = "接受"
                elif any(kw in last for kw in ["拒绝", "不接受", "不行"]):
                    final_attitudes[name] = "拒绝"
                else:
                    final_attitudes[name] = "犹豫"
            else:
                final_attitudes[name] = "未表态"

        prompt = _CLOSURE_PROMPT.format(
            case_background=self._case_bg(sess),
            full_dialog=full_dialog[-3000:],
            final_attitudes=json.dumps(final_attitudes, ensure_ascii=False),
        )

        final_solution = self.llm.chat_completion(
            [
                {"role": "system", "content": _MEDIATOR_SYSTEM.format(
                    case_background=self._case_bg(sess), stage="结案阶段")},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        self._add_turn(sess, "closure", "Mediator", final_solution)
        sess["stage"] = MediationStage.FINISHED
        sess["stages_completed"].append("closure")
        sess["party_decisions"] = final_attitudes

        outcome = "agreement" if all(v == "接受" for v in final_attitudes.values()) else "disagreement"

        result = MediationResult(
            session_id=session_id,
            stages_completed=sess["stages_completed"],
            dialog_history=sess["dialog_history"],
            final_solution=final_solution,
            outcome=outcome,
            party_decisions=final_attitudes,
            metadata={
                "dispute_points": sess["dispute_points"],
                "legal_bases": sess["legal_bases"],
                "proposed_solution": sess["proposed_solution"],
                "bargaining_rounds": sess["bargaining_round"],
            },
            elapsed_seconds=round(time.time() - sess["created_at"], 2),
        )
        self._save(session_id)

        return result

    # ================================================================
    # 一键全流程
    # ================================================================

    def run_full_mediation(
        self,
        session_id: str,
        case_info: Dict[str, Any],
        party_names: Optional[List[str]] = None,
        max_bargaining_rounds: int = 5,
        nbs_reference_text: Optional[str] = None,
    ) -> MediationResult:
        """一键运行完整五阶段调解流程。"""
        self.create_session(
            session_id, case_info, party_names, max_bargaining_rounds,
            nbs_reference_text=nbs_reference_text,
        )

        self.run_preliminary(session_id)

        sess = self._get_session(session_id)
        for name in sess["party_names"]:
            self.run_statement(session_id, name)

        self.run_option_generation(session_id)

        for _ in range(max_bargaining_rounds):
            result = self.run_bargaining_turn(session_id)
            if result.get("termination_condition"):
                break

        return self.run_closure(session_id)

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """获取调解会话状态。"""
        sess = self._get_session(session_id)
        return {
            "session_id": session_id,
            "stage": sess["stage"].value,
            "stages_completed": sess["stages_completed"],
            "bargaining_round": sess["bargaining_round"],
            "max_bargaining_rounds": sess["max_bargaining_rounds"],
            "party_names": sess["party_names"],
            "party_decisions": sess["party_decisions"],
            "dialog_count": len(sess["dialog_history"]),
            "dispute_points": sess["dispute_points"],
        }

    # ================================================================
    # 辅助
    # ================================================================

    def _build_party_context(self, sess: Dict, party_name: str) -> str:
        ci = sess["case_info"]
        parts = [f"你是{party_name}。"]

        for key in ("case_description", "fact", "facts", "案件描述"):
            if key in ci and ci[key]:
                parts.append(f"案件事实: {str(ci[key])[:500]}")
                break

        if party_name in ("原告",):
            for key in ("plaintiff_claims", "claims", "诉讼请求"):
                val = ci.get(key)
                if val:
                    parts.append(f"你的诉求: {val}")
                    break

        return "\n".join(parts)
