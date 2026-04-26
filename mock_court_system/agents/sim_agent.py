"""
模拟角色 Agent
用 LLM 模拟当事人/原告/被告等角色的回复，支持自动推进对话。

增强版：支持基于 TKI 冲突模型的策略注入与动态策略切换。
参考 AgentMediation (2509.06586) 的 Thomas-Kilmann 冲突模式。
"""
from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from core import LLMClient


# ========== TKI 冲突策略 ==========
# assertiveness (α) × cooperativeness (β)

CONFLICT_STRATEGIES = {
    "competing": {
        "label": "竞争型",
        "alpha": "high", "beta": "low",
        "instruction": (
            "你采取竞争策略：优先维护自身利益，坚决捍卫己方立场，"
            "对对方的主张积极反驳，不轻易妥协让步。"
            "语气强硬但不失礼貌，引用事实和证据为自己辩护。"
        ),
    },
    "collaborating": {
        "label": "合作型",
        "alpha": "high", "beta": "high",
        "instruction": (
            "你采取合作策略：在坚持核心诉求的同时，积极寻找双赢方案，"
            "主动了解对方关切，提出建设性建议。"
            "愿意在次要问题上做出让步以换取核心利益的保障。"
        ),
    },
    "compromising": {
        "label": "妥协型",
        "alpha": "moderate", "beta": "moderate",
        "instruction": (
            "你采取妥协策略：愿意在合理范围内让步，寻求中间方案，"
            "不追求完全胜利但也不放弃核心利益。"
            "表现出理性和务实的态度。"
        ),
    },
    "avoiding": {
        "label": "回避型",
        "alpha": "low", "beta": "low",
        "instruction": (
            "你采取回避策略：倾向于减少正面冲突，回答尽量简洁，"
            "不主动发起争论，对敏感话题避重就轻。"
            "如果法官追问，才给出具体回答。"
        ),
    },
    "accommodating": {
        "label": "迁就型",
        "alpha": "low", "beta": "high",
        "instruction": (
            "你采取迁就策略：以和为贵，倾向于认可对方的合理部分，"
            "在自身利益和对方诉求之间优先照顾对方感受。"
            "语气温和，积极配合法庭流程。"
        ),
    },
}

# 动态策略切换的反思 prompt
_STRATEGY_REFLECTION_PROMPT = """你是一个行为策略分析师。请根据当前对话形势，判断是否需要调整行为策略。

当前策略：{current_strategy}（{strategy_label}）
最近3轮对话：
{recent_dialog}

请判断：
1. 当前策略是否有效？（对方是否在让步/僵持/激化？）
2. 是否需要切换到其他策略？

可选策略：competing（竞争）、collaborating（合作）、compromising（妥协）、avoiding（回避）、accommodating（迁就）

返回JSON：{{"should_switch": true/false, "new_strategy": "策略名", "reason": "原因"}}
"""


_CLIENT_SYSTEM_PROMPT = """你是一名普通的中国公民，正在律师事务所向律师咨询法律问题。

{case_context}

{strategy_instruction}

你的行为准则：
1. 你只是一个普通老百姓，不要使用专业法律术语
2. 如实回答律师的提问，提供你所知道的事实和细节
3. 如果律师的问题涉及你不确定或不知道的信息，如实说"我不太清楚"或"我需要回去查一下"
4. 每次回答简洁扼要，通常 2-5 句话即可
5. 适当表达自己的诉求和情绪（委屈、愤怒、焦急等），但不要过于戏剧化
6. 不要主动提供律师没有问到的信息
"""

_PLAINTIFF_SYSTEM_PROMPT = """你是一名民事案件的原告，正在法庭上参与庭审。

{case_context}

{strategy_instruction}

你的行为准则：
1. 服从审判长的指挥，审判长问什么答什么
2. 如实陈述案件事实，但从维护自身利益的角度出发
3. 表述清晰，围绕自己的诉讼请求进行陈述
4. 对被告的质证和辩论做出合理回应
5. 每次发言简洁有条理，通常 3-8 句话
6. 使用"审判长"作为对法官的称呼
"""

_DEFENDANT_SYSTEM_PROMPT = """你是一名民事案件的被告，正在法庭上参与庭审。

{case_context}

{strategy_instruction}

你的行为准则：
1. 服从审判长的指挥，审判长问什么答什么
2. 从维护自身权益的角度进行答辩
3. 对原告的诉求提出合理的反驳或部分认可
4. 对原告提交的证据进行质证
5. 每次发言简洁有条理，通常 3-8 句话
6. 使用"审判长"作为对法官的称呼
"""


def _build_case_context(input_json: Optional[Dict[str, Any]], scenario: str) -> str:
    """从 input_json 中提取案件背景，供 system prompt 使用。"""
    if not input_json:
        return "目前没有具体的案件信息，请根据律师/法官的引导自由回答。"

    parts: List[str] = []
    parts.append("以下是案件的背景信息，请根据这些信息回答问题：")

    for key in ("case_description", "fact", "facts", "case_summary", "案件描述", "事实"):
        if key in input_json and input_json[key]:
            parts.append(f"案件事实: {input_json[key]}")
            break

    for key in ("plaintiff_claims", "claims", "诉讼请求"):
        val = input_json.get(key)
        if val:
            if isinstance(val, list):
                parts.append("诉讼请求: " + "; ".join(str(v) for v in val))
            else:
                parts.append(f"诉讼请求: {val}")
            break

    for key in ("plaintiff_name", "plaintiff", "原告"):
        if key in input_json and input_json[key]:
            parts.append(f"原告: {input_json[key]}")
            break

    for key in ("defendant_name", "defendant", "被告"):
        if key in input_json and input_json[key]:
            parts.append(f"被告: {input_json[key]}")
            break

    if len(parts) == 1:
        remaining = {k: v for k, v in input_json.items()
                     if k not in ("case_id", "scenario", "team_id") and v}
        if remaining:
            import json
            parts.append("其他信息: " + json.dumps(remaining, ensure_ascii=False, indent=2))

    return "\n".join(parts)


def _history_to_lc_messages(dialog_history: List[Dict], ai_role: str) -> list:
    """将 dialog_history 转换为 LangChain 消息列表。ai_role 对应的发言作为 AI 消息，其余作为 Human 消息。"""
    msgs = []
    for item in dialog_history:
        role = item.get("role", "")
        content = item.get("message", "")
        if not content:
            continue
        if role == ai_role:
            msgs.append(AIMessage(content=content))
        else:
            msgs.append(HumanMessage(content=content))
    return msgs


class SimAgent:
    """模拟角色 Agent —— 使用 LLM 扮演当事人、原告或被告。
    
    增强：
    - TKI 冲突策略注入和动态策略切换（AgentMediation）
    - Big Five 人格特质支持（J1-EVAL）
    """

    def __init__(
        self,
        llm: LLMClient,
        strategy: Optional[str] = None,
        enable_dynamic_strategy: bool = False,
        personality: Optional[Dict[str, str]] = None,
    ):
        self.llm = llm
        self._strategy = strategy
        self._enable_dynamic = enable_dynamic_strategy
        self._personality = personality
        self._strategy_history: List[str] = []
        if strategy:
            self._strategy_history.append(strategy)

        if self.llm.chat_model:
            self._chain_prompt = ChatPromptTemplate.from_messages([
                ("system", "{system_prompt}"),
                MessagesPlaceholder(variable_name="history"),
            ])
            self._chain = self._chain_prompt | self.llm.chat_model | StrOutputParser()
        else:
            self._chain = None

    # ---------- 策略管理 ----------

    @property
    def strategy(self) -> Optional[str]:
        return self._strategy

    @strategy.setter
    def strategy(self, value: Optional[str]):
        if value and value not in CONFLICT_STRATEGIES:
            raise ValueError(f"Unknown strategy: {value}. Choose from {list(CONFLICT_STRATEGIES.keys())}")
        self._strategy = value
        if value:
            self._strategy_history.append(value)

    def _get_strategy_instruction(self) -> str:
        parts = []
        if self._strategy and self._strategy in CONFLICT_STRATEGIES:
            parts.append(CONFLICT_STRATEGIES[self._strategy]["instruction"])
        if self._personality:
            try:
                from evaluation.lib.j1eval_metrics import build_personality_instruction
                parts.append(build_personality_instruction(self._personality))
            except ImportError:
                pass
        return "\n\n".join(parts)

    def _maybe_switch_strategy(self, dialog_history: List[Dict]) -> None:
        """动态策略切换：分析近期对话走势，决定是否调整策略。"""
        if not self._enable_dynamic or not self._strategy:
            return
        if len(dialog_history) < 6:
            return

        recent = dialog_history[-6:]
        recent_text = "\n".join(
            f"{item.get('role', '?')}: {item.get('message', '')[:100]}"
            for item in recent
        )
        strat_info = CONFLICT_STRATEGIES.get(self._strategy, {})
        prompt = _STRATEGY_REFLECTION_PROMPT.format(
            current_strategy=self._strategy,
            strategy_label=strat_info.get("label", ""),
            recent_dialog=recent_text,
        )
        try:
            import json as _json
            result = self.llm.chat_json([{"role": "user", "content": prompt}])
            if result and result.get("should_switch") and result.get("new_strategy"):
                new_strat = result["new_strategy"]
                if new_strat in CONFLICT_STRATEGIES and new_strat != self._strategy:
                    self.strategy = new_strat
        except Exception:
            pass

    # ---------- 核心调用 ----------

    def _invoke(self, system_prompt: str, dialog_history: List[Dict], ai_role: str) -> str:
        lc_msgs = _history_to_lc_messages(dialog_history, ai_role)
        if self._chain:
            return self._chain.invoke({
                "system_prompt": system_prompt,
                "history": lc_msgs,
            })
        return self.llm.chat_completion([
            {"role": "system", "content": system_prompt},
            *[{"role": "assistant" if m.type == "ai" else "user", "content": m.content}
              for m in lc_msgs],
        ])

    def simulate_client(
        self,
        dialog_history: List[Dict],
        input_json: Optional[Dict[str, Any]] = None,
        scenario: str = "CD",
    ) -> str:
        """模拟当事人（Client）回复律师提问。用于 CD/DD 场景。"""
        self._maybe_switch_strategy(dialog_history)
        ctx = _build_case_context(input_json, scenario)
        prompt = _CLIENT_SYSTEM_PROMPT.format(
            case_context=ctx,
            strategy_instruction=self._get_strategy_instruction(),
        )
        return self._invoke(prompt, dialog_history, ai_role="Client")

    def simulate_plaintiff(
        self,
        dialog_history: List[Dict],
        input_json: Optional[Dict[str, Any]] = None,
    ) -> str:
        """模拟原告（Plaintiff）在庭审中的发言。用于 CI 场景。"""
        self._maybe_switch_strategy(dialog_history)
        ctx = _build_case_context(input_json, "CI")
        prompt = _PLAINTIFF_SYSTEM_PROMPT.format(
            case_context=ctx,
            strategy_instruction=self._get_strategy_instruction(),
        )
        return self._invoke(prompt, dialog_history, ai_role="Plaintiff")

    def simulate_defendant(
        self,
        dialog_history: List[Dict],
        input_json: Optional[Dict[str, Any]] = None,
    ) -> str:
        """模拟被告（Defendant）在庭审中的发言。用于 CI 场景。"""
        self._maybe_switch_strategy(dialog_history)
        ctx = _build_case_context(input_json, "CI")
        prompt = _DEFENDANT_SYSTEM_PROMPT.format(
            case_context=ctx,
            strategy_instruction=self._get_strategy_instruction(),
        )
        return self._invoke(prompt, dialog_history, ai_role="Defendant")

    def simulate_plaintiff_with_strategy(
        self,
        dialog_history: List[Dict],
        complaint_text: str = "",
        cd_extracted_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """基于起诉状和 CD 阶段收集的信息，模拟原告在庭审中的发言。"""
        self._maybe_switch_strategy(dialog_history)
        parts = ["以下是你（原告）方的完整背景信息，请严格基于这些内容进行发言："]
        if complaint_text:
            parts.append(f"【你的律师撰写的起诉状摘要】\n{complaint_text[:2000]}")
        if cd_extracted_info:
            facts = cd_extracted_info.get("facts", "")
            claims = cd_extracted_info.get("claims", [])
            if facts:
                parts.append(f"【你向律师陈述的事实】\n{facts[:1500]}")
            if claims:
                parts.append("【诉讼请求】\n" + "\n".join(str(c) for c in claims))
        ctx = "\n\n".join(parts) if len(parts) > 1 else "请根据法官的引导自由回答。"
        prompt = _PLAINTIFF_SYSTEM_PROMPT.format(
            case_context=ctx,
            strategy_instruction=self._get_strategy_instruction(),
        )
        return self._invoke(prompt, dialog_history, ai_role="Plaintiff")

    def simulate_defendant_with_strategy(
        self,
        dialog_history: List[Dict],
        defense_text: str = "",
        dd_extracted_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """基于答辩状和 DD 阶段收集的信息，模拟被告在庭审中的发言。"""
        self._maybe_switch_strategy(dialog_history)
        parts = ["以下是你（被告）方的完整背景信息，请严格基于这些内容进行答辩："]
        if defense_text:
            parts.append(f"【你的律师撰写的答辩状摘要】\n{defense_text[:2000]}")
        if dd_extracted_info:
            facts = dd_extracted_info.get("facts", [])
            defense_claims = dd_extracted_info.get("defense_claims", [])
            if facts:
                if isinstance(facts, list):
                    parts.append("【你向律师陈述的事实】\n" + "\n".join(str(f) for f in facts[-5:]))
                else:
                    parts.append(f"【你向律师陈述的事实】\n{facts}")
            if defense_claims:
                parts.append("【答辩请求】\n" + "\n".join(str(c) for c in defense_claims))
        ctx = "\n\n".join(parts) if len(parts) > 1 else "请根据法官的引导自由回答。"
        prompt = _DEFENDANT_SYSTEM_PROMPT.format(
            case_context=ctx,
            strategy_instruction=self._get_strategy_instruction(),
        )
        return self._invoke(prompt, dialog_history, ai_role="Defendant")

    def simulate_role(
        self,
        role: str,
        dialog_history: List[Dict],
        input_json: Optional[Dict[str, Any]] = None,
        scenario: str = "CD",
    ) -> str:
        """根据角色名称自动选择模拟方法。"""
        role_upper = role.strip()
        if role_upper in ("Client", "客户", "当事人"):
            return self.simulate_client(dialog_history, input_json, scenario)
        elif role_upper in ("Plaintiff", "原告"):
            return self.simulate_plaintiff(dialog_history, input_json)
        elif role_upper in ("Defendant", "被告"):
            return self.simulate_defendant(dialog_history, input_json)
        return self.simulate_client(dialog_history, input_json, scenario)
