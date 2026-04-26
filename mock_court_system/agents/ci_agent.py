"""
CI 场景智能体 - 法庭判决
审判长主持庭审并生成判决书
"""
import re
import json
from typing import Dict, Any, Tuple, List, Optional
from dataclasses import asdict
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .base_agent import BaseAgent
from core import CourtSimulatorClient, LLMClient
from core.schemas import (
    CaseInfo, PartyRole, CourtState, CourtSubStage, Evidence, Message,
    StructuredJudgment,
)
from core.state_machine import StateMachine
from core.langchain_utils import RobustJsonOutputParser
from core.law_retriever import LawRetriever, get_dashscope_api_key
from utils import DialogHistory
import os


class CIAgent(BaseAgent):
    """法庭判决智能体"""

    def __init__(
        self,
        api_client: CourtSimulatorClient,
        llm: LLMClient,
        max_turns: int = 50,
        instruction_mode: str = "template",
        verbose: bool = False,
    ):
        super().__init__(api_client, llm, "CI", max_turns, verbose)
        self.instruction_mode = instruction_mode
        self.role = "Judge"
        
        # 内部状态
        self.state_machine = StateMachine()
        self.dialogue: List[Message] = []
        self.evidences: List[Evidence] = []
        self.extracted = {
            "plaintiff_claim": {},
            "defendant_defense": {},
            "summary": "",
        }
        self.judgment_json: Optional[Dict] = None
        self.finished: bool = False
        self.max_cross_exam_rounds: int = 4
        self.max_cross_exam_retries: int = 2
        
        # 标记是否已从对话中确认了当事人姓名
        self.name_confirmed_by_dialogue = {
            "plaintiff": False,
            "defendant": False
        }

        # 初始化法律检索器
        try:
            # 使用相对路径以避免 Windows 下 Faiss 对中文路径的支持问题
            # 假设运行目录为 mock_court_multiagents
            db_dir = "database"
            self.law_retriever = LawRetriever(
                db_path=os.path.join(db_dir, "legal_articles.db"),
                index_path=os.path.join(db_dir, "legal_articles.index"),
                mapping_path=os.path.join(db_dir, "legal_articles_id_map.npy"),
                api_key=get_dashscope_api_key()
            )
            self.log("LawRetriever initialized successfully.")
        except Exception as e:
            self.log(f"Failed to initialize LawRetriever: {e}")
            self.law_retriever = None

        # 初始化 LangChain Chains
        if self.llm.chat_model:
            # 1. 状态分析 Chain (JSON)
            self.analysis_prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个专业的法庭书记员。请根据输入分析庭审状态，并输出严格的JSON格式。"),
                ("user", "{prompt}")
            ])
            self.analysis_chain = self.analysis_prompt | self.llm.chat_model | RobustJsonOutputParser()

            # 2. 指令生成 Chain (String)
            self.instruction_prompt = ChatPromptTemplate.from_messages([
                ("system", "{system_prompt}"),
                ("user", "{stage_prompt}")
            ])
            self.instruction_chain = self.instruction_prompt | self.llm.chat_model | StrOutputParser()

            # 3. 判决生成 Chain (JSON)
            self.judgment_prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个资深的民事法官。请根据案情生成判决书，输出严格的JSON格式。"),
                ("user", "{prompt}")
            ])
            self.judgment_chain = self.judgment_prompt | self.llm.chat_model | RobustJsonOutputParser()

            # 4. 信息抽取 Chain (JSON)
            self.extraction_prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个法庭记录员。请从对话中提取关键信息，输出严格的JSON格式。"),
                ("user", "{prompt}")
            ])
            self.extraction_chain = self.extraction_prompt | self.llm.chat_model | RobustJsonOutputParser()

            # 5. 摘要生成 Chain (String)
            self.summary_prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个法庭记录员。请总结庭审对话。"),
                ("user", "{prompt}")
            ])
            self.summary_chain = self.summary_prompt | self.llm.chat_model | StrOutputParser()
        else:
            self.analysis_chain = None
            self.instruction_chain = None
            self.judgment_chain = None
            self.extraction_chain = None
            self.summary_chain = None

    def process_turn(self, dialog_history: List[Dict], case_id: str, input_json: Dict = None) -> str:
        """处理单轮对话 (API 模式)"""
        # 0. 初始化 CaseInfo
        if input_json:
            self.case_info = self._build_case_info(input_json)
        elif not hasattr(self, 'case_info') or not self.case_info:
            # 尝试构建一个空的 CaseInfo 防止报错
            self.case_info = CaseInfo(case_id=case_id)

        # 1. 重置状态
        self.state_machine = StateMachine()
        self.dialogue = []
        self.evidences = []
        self.extracted = {
            "plaintiff_claim": {},
            "defendant_defense": {},
            "summary": "",
        }
        self.finished = False
        
        # 2. 快速回放历史 (除了最后一条)
        if not dialog_history:
            return self._start_court()
            
        # 转换历史格式并回放
        for i, item in enumerate(dialog_history[:-1]):
            role_str = item["role"]
            content = item["message"]
            
            role = self._map_role(role_str)
            self._add_msg(role, content)
            
            if role != PartyRole.JUDGE:
                # User message: update state using heuristics
                self._fast_update_state(role, content)
                
        # 3. 处理最后一条消息 (使用真实逻辑)
        last_item = dialog_history[-1]
        last_role = self._map_role(last_item["role"])
        last_content = last_item["message"]
        
        if last_role == PartyRole.JUDGE:
             return self._next_instruction()
        
        return self._step(last_role, last_content)

    def _map_role(self, role_str: str) -> PartyRole:
        if role_str in ["Judge", "法官", "审判长"]:
            return PartyRole.JUDGE
        elif role_str in ["Plaintiff", "原告", "Client"]: # Client usually maps to the user role
            return PartyRole.PLAINTIFF
        elif role_str in ["Defendant", "被告"]:
            return PartyRole.DEFENDANT
        return PartyRole.PLAINTIFF

    def _fast_update_state(self, role: PartyRole, content: str):
        """使用规则快速更新状态 (用于回放)"""
        state = self.state_machine.current_state
        content = content.strip()
        
        if state == CourtState.OPENING:
            p = self.state_machine.opening_phase
            if role == PartyRole.PLAINTIFF:
                if any(w in content for w in ["确认", "是", "到庭", "本人"]): p["plaintiff_verified"] = True
                if any(w in content for w in ["听清", "明白", "清楚", "知晓"]): p["rights_informed_mask"]["plaintiff"] = True
                if any(w in content for w in ["不申请", "没有", "无"]): p["recusal_asked_mask"]["plaintiff"] = True
                if any(w in content for w in ["听清", "明白", "清楚", "知晓"]): p["absence_acknowledged"] = True
            elif role == PartyRole.DEFENDANT:
                if any(w in content for w in ["确认", "是", "到庭", "本人"]): p["defendant_verified"] = True
                if any(w in content for w in ["听清", "明白", "清楚", "知晓"]): p["rights_informed_mask"]["defendant"] = True
                if any(w in content for w in ["不申请", "没有", "无"]): p["recusal_asked_mask"]["defendant"] = True
                
        elif state == CourtState.INVESTIGATION:
            p = self.state_machine.investigation_phase
            if role == PartyRole.PLAINTIFF:
                if not p["plaintiff_stated"] and len(content) > 5: p["plaintiff_stated"] = True
            elif role == PartyRole.DEFENDANT:
                if not p["defendant_responded"] and len(content) > 5: p["defendant_responded"] = True
            
            # 简单的证据/质证跳过逻辑
            if "没有" in content or "完毕" in content or "无异议" in content:
                # 这是一个非常粗略的假设，但在回放中可能足够
                pass

        elif state == CourtState.DEBATE:
            p = self.state_machine.debate_phase
            if role == PartyRole.PLAINTIFF:
                if not p["plaintiff_debated"] and len(content) > 5: p["plaintiff_debated"] = True
            elif role == PartyRole.DEFENDANT:
                if not p["defendant_debated"] and len(content) > 5: p["defendant_debated"] = True

        # Try transition
        self.state_machine.try_transition()

    def run_case(
        self,
        case_id: str,
        case_info: Dict = None,
        **kwargs
    ) -> Tuple[DialogHistory, Dict[str, Any]]:
        """
        运行 CI 场景案例
        """
        # 构造 CaseInfo
        input_json = kwargs.get("input_json", {})
        if not case_info and input_json:
            case_info = self._build_case_info(input_json)
        elif not case_info:
            # 兜底
            case_info = CaseInfo(case_id=case_id)
            
        self.case_info = case_info
        
        # 重置状态
        self.state_machine = StateMachine()
        self.dialogue = []
        self.evidences = []
        self.extracted = {"plaintiff_claim": {}, "defendant_defense": {}, "summary": ""}
        self.judgment_json = None
        self.finished = False

        dialog_history = DialogHistory(self.scenario)

        # 开庭
        instruction = self._start_court()
        current_turn = 1
        dialog_history.add_user_message(current_turn, instruction)

        metadata = {
            "turns": 0,
            "api_errors": [],
            "termination_reason": "",
            "judge_report": {},
        }

        while current_turn <= self.max_turns:
            # 推断目标角色
            expected_role = self._infer_target_role(instruction)
            
            self.log(f"Turn {current_turn} Judge: {instruction}")

            # 调用 API (增加重试机制)
            response_text = None
            for attempt in range(3):
                try:
                    api_resp = self.api_client.simulate_ci(
                        case_id=case_id,
                        dialog_history=dialog_history.get_api_format(),
                    )
                    response_text = api_resp.get("response")
                    if response_text:
                        break
                    else:
                        self.log(f"Warning: Empty response from API (Attempt {attempt+1}/3)")
                        if "error" in api_resp:
                            self.log(f"API Error: {api_resp['error']}")
                except Exception as e:
                    self.log(f"Error calling API (Attempt {attempt+1}/3): {e}")
            
            if not response_text:
                metadata["api_errors"].append(api_resp if 'api_resp' in locals() else {"error": "Failed after retries"})
                metadata["termination_reason"] = "API Error or Empty Response"
                self.log("Terminating due to API failure.")
                break

            # 记录环境响应
            env_role = "Plaintiff" if expected_role == PartyRole.PLAINTIFF else "Defendant"
            dialog_history.add_env_response(
                current_turn,
                env_role,
                response_text,
            )
            
            self.log(f"Turn {current_turn} {env_role}: {response_text}")

            # 审判长决策
            next_instruction = self._step(expected_role, response_text)
            
            if self.finished:
                metadata["termination_reason"] = "Judgment Generated"
                # 追加最终指令（判决书）
                current_turn += 1
                dialog_history.add_user_message(current_turn, next_instruction)
                break

            current_turn += 1
            instruction = next_instruction
            dialog_history.add_user_message(current_turn, instruction)

        metadata["turns"] = current_turn
        metadata["judge_report"] = self._report()
        if not metadata["termination_reason"]:
            metadata["termination_reason"] = "Max turns reached"

        return dialog_history, {
            "model_answer": self._get_ci_model_answer(),
            "metadata": metadata,
        }

    def _build_case_info(self, case_item: Dict) -> CaseInfo:
        """构造 CaseInfo"""
        plaintiff = case_item.get("plaintiff_info", {}) or {}
        defendant = case_item.get("defendant_info", {}) or {}
        claim_desc = case_item.get("claim_description") or case_item.get("claim", "") or ""

        return CaseInfo(
            case_number=str(case_item.get("id", "")),
            plaintiff_name=plaintiff.get("name", "原告"),
            defendant_name=defendant.get("name", "被告"),
            case_type=case_item.get("case_type", "民事纠纷"),
            claim_amount=case_item.get("claim_amount"),
            claim_description=claim_desc,
            third_party_findings=case_item.get("third_party_findings", ""),
            plaintiff_info=plaintiff,
            defendant_info=defendant,
        )

    def _infer_target_role(self, instruction: str) -> PartyRole:
        if "对被告" in instruction:
            return PartyRole.DEFENDANT
        if "对原告" in instruction:
            return PartyRole.PLAINTIFF
        return PartyRole.PLAINTIFF

    def _start_court(self) -> str:
        """开庭"""
        if self.instruction_mode == "template":
            resp = "对原告说：现在开庭。请原告核实身份信息，并确认是否由本人到庭参加诉讼。"
        else:
            system = self._get_system_prompt()
            stage = self._get_opening_prompt()
            if self.instruction_chain:
                resp = self.instruction_chain.invoke({"system_prompt": system, "stage_prompt": stage})
            else:
                resp = self.llm.call(system + "\n\n" + stage)
        
        self._add_msg(PartyRole.JUDGE, resp)
        # 开庭阶段由状态机自动检测完成，不再手动标记
        # self.state_machine.mark_opening_complete()
        self.state_machine.try_transition()
        return resp

    def _step(self, role: PartyRole, content: str) -> str:
        """处理一轮对话"""
        self._add_msg(role, content)
        self._extract_info(role, content)
        self._update_phase(role, content)
        self.state_machine.try_transition()

        if self.state_machine.current_state == CourtState.JUDGMENT:
            return self._make_judgment()

        return self._next_instruction()

    def _next_instruction(self) -> str:
        """生成下一条指令"""
        s = self.state_machine.current_state

        if self.instruction_mode == "template":
            resp = self._template_instruction(s)
        else:
            system = self._get_system_prompt()
            last = self.dialogue[-1] if self.dialogue else None
            if s == CourtState.OPENING:
                stage = self._get_opening_prompt()
            elif s == CourtState.INVESTIGATION:
                stage = self._get_investigation_prompt(last)
            elif s == CourtState.DEBATE:
                stage = self._get_debate_prompt()
            elif s == CourtState.MEDIATION:
                stage = self._get_mediation_prompt()
            else:

                # 1.1 宣布审判庭构成及适用程序（关键词：构成/适用程序）
                if not p.get("court_composition_announced"):
                    self.state_machine.update_phase_status(court_composition_announced=True)
                    return "对原告说：本案由审判员组成独任庭，书记员负责记录，现宣布本庭构成。"
                if not p.get("procedure_announced"):
                    self.state_machine.update_phase_status(procedure_announced=True)
                    return "对被告说：本案适用简易程序审理，现告知并请确认是否听清。"
                return "【系统】当前状态不支持生成指令。"
            
            if self.instruction_chain:
                resp = self.instruction_chain.invoke({"system_prompt": system, "stage_prompt": stage})
            else:
                resp = self.llm.call(system + "\n\n" + stage)

        self._add_msg(PartyRole.JUDGE, resp)
        return resp

    def _make_judgment(self) -> str:
        """生成判决"""
        if not self.extracted.get("summary"):
            self.extracted["summary"] = self._summarize_dialogue()
        
        summary = self.extracted["summary"]
        prompt = self._get_judgment_prompt(summary)
        
        if self.judgment_chain:
            try:
                self.judgment_json = self.judgment_chain.invoke({"prompt": prompt})
            except Exception as e:
                self.log(f"Judgment Chain Error: {e}. Falling back to chat_json.")
                self.judgment_json = self.llm.chat_json([{"role": "user", "content": prompt}])
        else:
            self.judgment_json = self.llm.chat_json([{"role": "user", "content": prompt}])

        self.finished = True
        self.state_machine.try_transition()
        return self._format_judgment_text()

    # --- 辅助方法 ---

    def _add_msg(self, role: PartyRole, content: str):
        self.dialogue.append(
            Message(
                role=role,
                content=content,
                timestamp=datetime.now().isoformat(),
                state=self.state_machine.current_state,
            )
        )

    def _update_case_info_from_content(self, role: PartyRole, content: str):
        """从对话内容中更新案件信息 (LLM based)"""
        # 仅在开庭阶段或法庭调查初期关注身份信息，避免每轮都调用 LLM
        if self.state_machine.current_state not in [CourtState.OPENING, CourtState.INVESTIGATION]:
            return
        
        # 仅当发言中包含可能涉及身份的关键词时才触发
        if not any(k in content for k in ["我是", "本人", "代理人", "被告", "原告", "姓名", "身份"]):
            return

        prompt = f"""
你是一个法庭书记员。请根据发言内容提取关键案件信息。

当前记录：
原告姓名：{self.case_info.plaintiff_name}
被告姓名：{self.case_info.defendant_name}

发言人：{role.value}
发言内容：{content}

任务：
1. 判断发言中是否明确提及了原告或被告的准确姓名（用于修正当前记录）。
2. 注意区分“代理人姓名”和“当事人姓名”。我们只需要“当事人姓名”。
   - 例如：“我是被告张三的代理人李四” -> 被告是“张三”。
   - 例如：“我是被告张三” -> 被告是“张三”。
   - 例如：“我是原告代理人” -> 无法提取原告姓名。

请返回 JSON 格式：
{{
    "plaintiff_name": "提取到的原告当事人姓名" or null,
    "defendant_name": "提取到的被告当事人姓名" or null
}}
"""
        try:
            data = self.llm.chat_json([{"role": "user", "content": prompt}])
            
            if data:
                p_name = data.get("plaintiff_name")
                d_name = data.get("defendant_name")
                
                if p_name and p_name != self.case_info.plaintiff_name and p_name != "null":
                    self.log(f"Updating plaintiff name from dialogue: {p_name}")
                    self.case_info.plaintiff_name = p_name
                    self.name_confirmed_by_dialogue["plaintiff"] = True
                    
                if d_name and d_name != self.case_info.defendant_name and d_name != "null":
                    self.log(f"Updating defendant name from dialogue: {d_name}")
                    self.case_info.defendant_name = d_name
                    self.name_confirmed_by_dialogue["defendant"] = True
                    
        except Exception as e:
            self.log(f"Failed to update case info from content: {e}")

    def _extract_info(self, role: PartyRole, content: str):
        """信息抽取"""
        # 尝试从对话中更新案件信息（如姓名）
        self._update_case_info_from_content(role, content)

        state = self.state_machine.current_state
        if state == CourtState.INVESTIGATION:
            p = self.state_machine.investigation_phase
            
            # 1. Extract Claim/Defense
            if role == PartyRole.PLAINTIFF and not p["plaintiff_stated"]:
                self.extracted["plaintiff_claim"] = self._extract_claim(content)
                # Don't extract evidence during initial statement to avoid confusion
                return 
            
            if role == PartyRole.DEFENDANT and not p["defendant_responded"]:
                self.extracted["defendant_defense"] = self._extract_defense(content)
                # Don't extract evidence during initial defense
                return

            if any(k in content for k in ["证据", "凭证", "合同", "微信聊天", "录音"]):
                ev = self._extract_evidence(content, role)
                if ev:
                    self.evidences.append(ev)

    def _analyze_state_with_llm(self, role: PartyRole, content: str) -> Dict:
        """使用 LLM 分析当前发言对状态机的影响"""
        state = self.state_machine.current_state
        
        if state == CourtState.OPENING:
            prompt = f"""
你是一个法庭书记员。
当前阶段：开庭准备
发言人：{role.value}
发言内容：{content}

请判断该发言包含的意图：
1. "identity_confirmed": 确认身份/到庭。
2. "rights_acknowledged": 听清/明白/知晓诉讼权利义务。
3. "recusal_response": 回答是否申请回避（无论申请还是不申请，只要回答了就算）。
4. "absence_acknowledged": 听清/明白/知晓缺席审理后果。

请返回 JSON 格式：
{{
    "identity_confirmed": true/false,
    "rights_acknowledged": true/false,
    "recusal_response": true/false,
    "absence_acknowledged": true/false
}}
"""
        elif state == CourtState.INVESTIGATION:
            prompt = f"""
你是一个法庭书记员，负责记录庭审进度。
当前阶段：法庭调查
发言人：{role.value}
发言内容：{content}

请判断该发言是否包含以下意图（仅根据发言内容判断）：
1. "stated_or_responded": 原告陈述了诉讼请求/事实，或被告进行了答辩。（注意：简单的“在”、“是”不算，必须有实质内容）
2. "no_more_evidence": 明确表示“无新证据”、“举证完毕”、“没有证据了”、“证据出示完毕”等。
3. "fact_supplement_response": 回答了法庭关于“事实是否有补充”的询问（无论有无补充）。
4. "cross_exam_intent": 针对对方证据/观点的态度。
   - "objection": 有异议/质疑/反驳/提出新问题。
   - "question": 提出疑问。
   - "accept": 认可/无异议/无补充/不再追问。
   - "no_proof": 明确表示“无法证明”、“没有相关证据”、“无法解释”等（仅在被要求举证/解释时）。
   - "none": 未涉及质证或回应。
5. "key_point": 如果是 objection/question，请用一句话概括核心观点（不超过30字）。
6. "burden_analysis": 请根据“谁主张谁举证”及“抗辩需举证”原则分析举证责任：
   - 如果发言是单纯否认/质疑对方证据（如“不认可”、“假的”），举证责任在**对方**（plaintiff/defendant）。
   - 如果发言是提出新事实/抗辩（如“已付款”、“不可抗力”），举证责任在**发言人**（plaintiff/defendant）。
   - 如果是 no_proof，则为 null。
   - 如果是 accept，则为 null。

请返回 JSON 格式：
{{
    "stated_or_responded": true/false,
    "no_more_evidence": true/false,
    "fact_supplement_response": true/false,
    "cross_exam_intent": "objection" / "question" / "accept" / "no_proof" / "none",
    "key_point": "...",
    "burden_holder": "plaintiff" / "defendant" / null
}}
"""
        elif state == CourtState.DEBATE:
            prompt = f"""
你是一个法庭书记员。
当前阶段：法庭辩论
发言人：{role.value}
发言内容：{content}

请判断该发言是否包含以下意图：
1. "debated": 发表了辩论意见。（有实质性观点）
2. "final_statement": 明确表示“陈述完毕”、“没有补充”、“发表完毕”、“无其他意见”等，通常用于最后陈述环节。
3. "debate_intent": 针对对方观点的态度。
   - "rebuttal": 反驳/提出不同观点/指出对方错误。
   - "new_point": 提出新的辩论观点。
   - "restatement": 重申已有观点。
   - "concede": 认可对方观点/无力反驳/不再纠缠。
   - "no_proof": 明确表示“无法证明”、“没有证据支持”等。
   - "none": 未涉及实质辩论。
4. "key_point": 如果是 rebuttal/new_point，请用一句话概括核心观点（不超过30字）。
5. "burden_analysis": 请根据“谁主张谁举证”原则分析：
   - 如果是单纯反驳（否认对方观点），举证责任在**对方**。
   - 如果是提出新观点/新事实，举证责任在**发言人**。

请返回 JSON 格式：
{{
    "debated": true/false,
    "final_statement": true/false,
    "debate_intent": "rebuttal" / "new_point" / "restatement" / "concede" / "no_proof" / "none",
    "key_point": "...",
    "burden_holder": "plaintiff" / "defendant" / null
}}
"""
        elif state == CourtState.MEDIATION:
            prompt = f"""
你是一个法庭书记员。
当前阶段：法庭调解
发言人：{role.value}
发言内容：{content}

请判断该发言对调解的态度。
规则：
1. 只要出现“拒绝”、“不同意”、“不接受”、“依法判决”、“不需要调解”、“坚持诉讼请求”等否定或强硬词汇，必须返回 "refuse"。
2. 只要出现“同意”、“愿意”、“接受”、“可以调解”等肯定词汇，必须返回 "agree"。
3. 只有在完全无法判断意图，或者仅询问调解方案但未表态时，才返回 "unknown"。

请返回 JSON 格式：
{{
    "mediation_response": "agree" / "refuse" / "unknown"
}}
"""
        else:
            return {}

        if self.analysis_chain:
            try:
                return self.analysis_chain.invoke({"prompt": prompt})
            except Exception as e:
                self.log(f"Analysis Chain Error: {e}. Falling back to chat_json.")
                return self.llm.chat_json([{"role": "user", "content": prompt}])
        else:
            return self.llm.chat_json([{"role": "user", "content": prompt}])

    def _update_phase(self, role: PartyRole, content: str):
        """更新阶段状态 (LLM 增强版)"""
        s = self.state_machine.current_state
        
        # 调用 LLM 分析意图
        result = self._analyze_state_with_llm(role, content)
        
        if s == CourtState.OPENING:
            p = self.state_machine.opening_phase
            # 身份核实
            if result.get("identity_confirmed"):
                if role == PartyRole.PLAINTIFF:
                    self.state_machine.update_phase_status(plaintiff_verified=True)
                elif role == PartyRole.DEFENDANT:
                    self.state_machine.update_phase_status(defendant_verified=True)
            
            # 权利义务
            if result.get("rights_acknowledged"):
                mask = dict(p["rights_informed_mask"])
                if role == PartyRole.PLAINTIFF:
                    mask["plaintiff"] = True
                elif role == PartyRole.DEFENDANT:
                    mask["defendant"] = True
                self.state_machine.update_phase_status(rights_informed_mask=mask)

            # 回避申请
            if result.get("recusal_response"):
                mask = dict(p["recusal_asked_mask"])
                if role == PartyRole.PLAINTIFF:
                    mask["plaintiff"] = True
                elif role == PartyRole.DEFENDANT:
                    mask["defendant"] = True
                self.state_machine.update_phase_status(recusal_asked_mask=mask)

            # 缺席后果
            if result.get("absence_acknowledged"):
                mask = dict(p["absence_asked_mask"])
                if role == PartyRole.PLAINTIFF:
                    mask["plaintiff"] = True
                elif role == PartyRole.DEFENDANT:
                    mask["defendant"] = True
                self.state_machine.update_phase_status(absence_asked_mask=mask)

        elif s == CourtState.INVESTIGATION:
            p = self.state_machine.investigation_phase
            if "closed_topics" not in p:
                p["closed_topics"] = []
            
            # --- 多轮质证逻辑 ---
            ce_intent = result.get("cross_exam_intent", "none")
            key_point = result.get("key_point", "")
            burden_holder = result.get("burden_holder")
            provider = p.get("last_evidence_provider")
            disc = p["current_discussion"]
            closed_topics = p.get("closed_topics", [])

            # [Fix] 如果当前发言人已被标记为“无更多证据”，且 LLM 判定举证责任在发言人自己，
            # 或者当前讨论正等待该发言人举证，则强制结束讨论（避免死循环）。
            role_key = "plaintiff" if role == PartyRole.PLAINTIFF else "defendant"
            is_no_more = p["no_more_evidence"].get(role_key)
            
            # 检查是否正卡在该人的举证责任上
            is_stuck_on_burden = (disc["is_active"] and disc.get("burden_holder") == role_key)
            # 检查当前发言是否试图开启/维持自己的举证责任
            new_burden_on_self = (burden_holder == role_key)

            if is_no_more and (is_stuck_on_burden or new_burden_on_self):
                topic = key_point or disc.get("pending_question") or "争议点"
                self.log(f"Force closing discussion on '{topic}' because {role.value} has no more evidence.")
                ce_intent = "none"
                
                # 强制结束讨论
                disc["is_active"] = False
                disc["pending_question"] = None
                disc["burden_holder"] = None
                disc["last_speaker_role"] = None
                disc["round_count"] = 0
                disc["repeat_count"] = 0
                disc["topic_signature"] = None
                disc["topic"] = None
                
                self.state_machine.update_phase_status(waiting_for_cross_exam=False)
                
                # 记录失败结果
                fail_msg = f"{role.value}无法就“{topic}”提供有效新证据"
                self.state_machine.investigation_phase["last_discussion_result"] = fail_msg

            # [Fix] 关键词检测辅助判断 no_proof，防止 LLM 漏判导致死循环
            if any(k in content for k in ["无证据", "没有证据", "无法提供", "无新证据", "没有新证据"]):
                if ce_intent not in ["no_proof", "accept"]:
                    self.log(f"Keyword override: setting ce_intent to 'no_proof' based on content.")
                    ce_intent = "no_proof"

            # 如果处于等待质证状态，或者正在进行多轮讨论
            if p["waiting_for_cross_exam"] or disc["is_active"]:
                # 1. 如果是 质疑/提问 -> 激活讨论，记录问题，保持等待状态
                if ce_intent in ["objection", "question"]:
                    holder_for_sig = burden_holder or disc.get("burden_holder") or "unknown"
                    topic_candidate = (key_point or disc.get("pending_question") or "").strip()
                    signature = f"{provider or 'unknown'}|{holder_for_sig}|{topic_candidate or 'default'}"

                    if signature in closed_topics:
                        final_question = topic_candidate or "争议事项"
                        self.log(
                            f"Cross-exam topic {final_question} already closed. Skipping further inquiry."
                        )
                        target_holder = disc.get("burden_holder") or burden_holder
                        if not target_holder:
                            if provider == PartyRole.PLAINTIFF.value:
                                target_holder = "plaintiff"
                            elif provider == PartyRole.DEFENDANT.value:
                                target_holder = "defendant"
                        disc["is_active"] = False
                        disc["pending_question"] = None
                        disc["burden_holder"] = None
                        disc["last_speaker_role"] = None
                        disc["round_count"] = 0
                        disc["repeat_count"] = 0
                        disc["topic_signature"] = signature
                        self.state_machine.investigation_phase["last_discussion_result"] = (
                            f"围绕“{final_question}”的质证已处理完毕，法庭继续下一项程序。"
                        )
                        self.state_machine.update_phase_status(waiting_for_cross_exam=False)
                        if target_holder in ("plaintiff", "defendant"):
                            nm = dict(p["no_more_evidence"])
                            if not nm.get(target_holder):
                                self.log(
                                    f"Marking {target_holder} as no-more-evidence after stalled质证 on {final_question}."
                                )
                                nm[target_holder] = True
                                self.state_machine.update_phase_status(no_more_evidence=nm)
                    else:
                        was_active = disc["is_active"]
                        previous_signature = disc.get("topic_signature")
                        if not was_active:
                            disc["round_count"] = 0
                            disc["is_active"] = True
                        disc["round_count"] += 1

                        if key_point:
                            disc["pending_question"] = key_point.strip()
                        elif not disc.get("pending_question"):
                            disc["pending_question"] = ""

                        # [Fix] 当原告为反驳被告异议而举证时，举证责任应转向被告，让其质证
                        if role == PartyRole.PLAINTIFF and provider == PartyRole.DEFENDANT:
                            disc["burden_holder"] = "defendant"
                        elif role == PartyRole.DEFENDANT and provider == PartyRole.PLAINTIFF:
                            disc["burden_holder"] = "plaintiff"
                        
                        if burden_holder:
                            disc["burden_holder"] = burden_holder  # 记录举证责任人

                        holder_for_sig = disc.get("burden_holder") or holder_for_sig
                        question_text = (disc.get("pending_question") or "").strip()
                        signature = f"{provider or 'unknown'}|{holder_for_sig}|{question_text or 'default'}"
                        disc["topic_signature"] = signature
                        disc["topic"] = question_text or None

                        if not was_active:
                            if previous_signature == signature:
                                disc["repeat_count"] += 1
                            else:
                                disc["repeat_count"] = 0

                        disc["last_speaker_role"] = role.value

                        force_due_to_repeat = disc["repeat_count"] >= self.max_cross_exam_retries
                        force_due_to_loop = disc["round_count"] >= self.max_cross_exam_rounds

                        if force_due_to_repeat or force_due_to_loop:
                            final_question = question_text or key_point or "争议事项"
                            target_holder = disc.get("burden_holder") or burden_holder
                            if not target_holder:
                                if provider == PartyRole.PLAINTIFF.value:
                                    target_holder = "plaintiff"
                                elif provider == PartyRole.DEFENDANT.value:
                                    target_holder = "defendant"
                            reason = "repeated stalls" if force_due_to_repeat else "loop count limit"
                            self.log(
                                f"Cross-exam {reason} reached on {final_question}. Moving on."
                            )
                            disc["is_active"] = False
                            disc["pending_question"] = None
                            disc["burden_holder"] = None
                            disc["last_speaker_role"] = None
                            disc["round_count"] = 0
                            disc["repeat_count"] = 0
                            if signature not in closed_topics:
                                closed_topics.append(signature)
                            self.state_machine.investigation_phase["last_discussion_result"] = (
                                f"围绕“{final_question}”的质证往返已充分，法庭将根据现有材料予以处理。"
                            )
                            self.state_machine.update_phase_status(waiting_for_cross_exam=False)
                            if target_holder in ("plaintiff", "defendant"):
                                nm = dict(p["no_more_evidence"])
                                if not nm.get(target_holder):
                                    self.log(
                                        f"Marking {target_holder} as no-more-evidence after repeated质证 on {final_question}."
                                    )
                                    nm[target_holder] = True
                                    self.state_machine.update_phase_status(no_more_evidence=nm)
                        else:
                            self.state_machine.update_phase_status(waiting_for_cross_exam=True)
                
                # 2. 如果是 认可/无异议 -> 结束讨论，解除等待状态
                elif ce_intent == "accept":
                    disc["is_active"] = False
                    disc["pending_question"] = None
                    disc["burden_holder"] = None
                    disc["last_speaker_role"] = None
                    disc["round_count"] = 0
                    disc["repeat_count"] = 0
                    disc["topic_signature"] = None
                    disc["topic"] = None
                    self.state_machine.update_phase_status(waiting_for_cross_exam=False)
                
                # 3. 如果是 举证不能 -> 结束讨论，记录结果
                elif ce_intent == "no_proof":
                    disc["is_active"] = False
                    disc["pending_question"] = None
                    disc["burden_holder"] = None
                    disc["round_count"] = 0
                    disc["repeat_count"] = 0
                    disc["topic_signature"] = None
                    disc["topic"] = None
                    # 记录失败结果，供指令生成使用
                    fail_msg = f"{role.value}无法就“{key_point or '争议点'}”提供证据"
                    self.state_machine.investigation_phase["last_discussion_result"] = fail_msg
                    self.state_machine.update_phase_status(waiting_for_cross_exam=False)

                # 4. 如果是 none (未识别出明确意图)，但对方确实发言了
                # 只有当它是对质证的回应时，我们才考虑是否默认结束
                elif not disc["is_active"]:
                    provider = p["last_evidence_provider"]
                    if (provider == PartyRole.PLAINTIFF.value and role == PartyRole.DEFENDANT) or \
                       (provider == PartyRole.DEFENDANT.value and role == PartyRole.PLAINTIFF):
                        self.state_machine.update_phase_status(waiting_for_cross_exam=False)
                
                # 5. [Fix] 如果处于 active discussion，且对方回应了（但不是反问/反驳），视为解释完毕，结束此轮
                elif disc["is_active"]:
                    # 如果当前发言人不是上一轮的发起人（即他是回应者）
                    if role.value != disc["last_speaker_role"]:
                        disc["is_active"] = False
                        disc["pending_question"] = None
                        disc["burden_holder"] = None
                        disc["last_speaker_role"] = None
                        disc["round_count"] = 0
                        self.state_machine.update_phase_status(waiting_for_cross_exam=False)

            # [Fix] Global no_more_evidence keyword check
            # 增加 "无证据", "没有证据" 等强否定词，确保能跳出循环
            is_global_no_more = result.get("no_more_evidence") or \
                                any(k in content for k in ["无新证据", "没有新证据", "举证完毕", "证据出示完毕", "无证据", "没有证据", "无补充", "没有补充"])

            if role == PartyRole.PLAINTIFF:
                if not p["plaintiff_stated"] and result.get("stated_or_responded"):
                    self.state_machine.update_phase_status(plaintiff_stated=True)
                
                if is_global_no_more:
                    nm = dict(p["no_more_evidence"])
                    if not nm["plaintiff"]:
                        self.log("Detected global no_more_evidence for Plaintiff via keywords/LLM.")
                        nm["plaintiff"] = True
                        self.state_machine.update_phase_status(no_more_evidence=nm)
            
            elif role == PartyRole.DEFENDANT:
                if not p["defendant_responded"] and result.get("stated_or_responded"):
                    self.state_machine.update_phase_status(defendant_responded=True)
                
                if is_global_no_more:
                    nm = dict(p["no_more_evidence"])
                    if not nm["defendant"]:
                        self.log("Detected global no_more_evidence for Defendant via keywords/LLM.")
                    nm["defendant"] = True
                    self.state_machine.update_phase_status(no_more_evidence=nm)

            # [Fix] Keyword check for fact supplement response
            # 防止 LLM 漏判导致法官反复询问“是否有补充”
            is_fact_supplement_response = result.get("fact_supplement_response") or \
                                          any(k in content for k in ["无补充", "没有补充", "无异议", "没有异议", "不补充", "无意见", "没有意见"])

            if is_fact_supplement_response:
                mask = dict(p["fact_inquiry_mask"])
                if role == PartyRole.PLAINTIFF:
                    mask["plaintiff"] = True
                elif role == PartyRole.DEFENDANT:
                    mask["defendant"] = True
                self.state_machine.update_phase_status(fact_inquiry_mask=mask)

        elif s == CourtState.DEBATE:
            p = self.state_machine.debate_phase
            
            # --- 多轮辩论逻辑 ---
            d_intent = result.get("debate_intent", "none")
            key_point = result.get("key_point", "")
            burden_holder = result.get("burden_holder")
            topic = p["current_topic"]

            # 交互逻辑更新
            # 1. 如果检测到反驳或新观点 -> 激活讨论，等待对方回应
            if d_intent in ["rebuttal", "new_point"]:
                topic["is_active"] = True
                topic["point"] = key_point
                topic["last_speaker_role"] = role.value
                topic["burden_holder"] = burden_holder
                topic["round_count"] += 1
                
                # 增加死循环熔断机制：如果同一话题辩论超过3轮，强制结束
                if topic["round_count"] >= 3:
                    self.log(f"Debate round limit reached ({topic['round_count']}). Forcing end of topic.")
                    topic["is_active"] = False
                    self.state_machine.update_phase_status(waiting_for_rebuttal=False)
                else:
                    self.state_machine.update_phase_status(waiting_for_rebuttal=True)
            
            # 2. 如果是认可/无补充 -> 结束当前话题
            elif d_intent == "concede":
                topic["is_active"] = False
                topic["point"] = None
                topic["burden_holder"] = None
                topic["round_count"] = 0
                self.state_machine.update_phase_status(waiting_for_rebuttal=False)
            
            # 3. 如果是 举证不能 -> 结束讨论
            elif d_intent == "no_proof":
                topic["is_active"] = False
                topic["point"] = None
                topic["burden_holder"] = None
                topic["round_count"] = 0
                fail_msg = f"{role.value}无法就“{key_point or '争议点'}”提供证据支持"
                self.state_machine.debate_phase["last_discussion_result"] = fail_msg
                self.state_machine.update_phase_status(waiting_for_rebuttal=False)

            # 4. 如果处于活跃讨论中，且对方回应了但不是反驳 -> 视为解释完毕，结束此轮
            elif topic["is_active"]:
                last_speaker = topic["last_speaker_role"]
                if last_speaker != role.value:
                    topic["is_active"] = False
                    self.state_machine.update_phase_status(waiting_for_rebuttal=False)

            # 基础状态更新
            if role == PartyRole.PLAINTIFF:
                if result.get("debated"):
                    self.state_machine.update_phase_status(plaintiff_debated=True)
                if result.get("final_statement"):
                    fs = dict(p["final_statement"])
                    fs["plaintiff"] = True
                    self.state_machine.update_phase_status(final_statement=fs)
                    # 如果发表了最后陈述，强制结束讨论
                    self.state_machine.update_phase_status(waiting_for_rebuttal=False)
            elif role == PartyRole.DEFENDANT:
                if result.get("debated"):
                    self.state_machine.update_phase_status(defendant_debated=True)
                if result.get("final_statement"):
                    fs = dict(p["final_statement"])
                    fs["defendant"] = True
                    self.state_machine.update_phase_status(final_statement=fs)
                    # 如果发表了最后陈述，强制结束讨论
                    self.state_machine.update_phase_status(waiting_for_rebuttal=False)

        elif s == CourtState.MEDIATION:
            p = self.state_machine.mediation_phase
            if not p["asked"]:
                self.state_machine.update_phase_status(asked=True)
            
            resp = result.get("mediation_response", "").lower()
            if resp in ["agree", "refuse"]:
                if role == PartyRole.PLAINTIFF:
                    self.state_machine.update_phase_status(plaintiff_response=resp)
                elif role == PartyRole.DEFENDANT:
                    self.state_machine.update_phase_status(defendant_response=resp)
            
            # Check if announcement was made
            if p["plaintiff_response"] and p["defendant_response"]:
                if len(self.dialogue) >= 2:
                    last_judge_msg = self.dialogue[-2].content
                    if "择期宣判" in last_judge_msg or "安排调解事宜" in last_judge_msg:
                        self.state_machine.update_phase_status(announced=True)

    # --- Prompt 相关 ---

    def _get_system_prompt(self) -> str:
        return """你是模拟民事法庭的审判长。你的职责是主持庭审，引导原被告进行陈述、举证、质证和辩论。
要求：
1. 始终使用庄重、正式的中文法言法语；
2. 保持中立、公正，不替任何一方作答；
3. 只给出“审判长对当事人的指令”，不要生成当事人会说的话；
4. 输出统一格式：对[原告/被告]说：[你的指令]。"""

    def _get_opening_prompt(self) -> str:
        return f"""当前阶段：开庭准备
案件信息：
- 案号：{self.case_info.case_number}
- 原告：{self.case_info.plaintiff_name}
- 被告：{self.case_info.defendant_name}
任务：宣布开庭，核实双方身份，告知诉讼权利义务。
请只输出一句指令。"""

    def _get_investigation_prompt(self, last_msg: Optional[Message]) -> str:
        p = self.state_machine.investigation_phase
        ctx = f"""当前阶段：法庭调查
进度：
- 原告是否已陈述诉讼请求及事实理由：{p['plaintiff_stated']}
- 被告是否已答辩：{p['defendant_responded']}
- 原告是否表示无新证据：{p['no_more_evidence']['plaintiff']}
- 被告是否表示无新证据：{p['no_more_evidence']['defendant']}"""
        if last_msg:
            ctx += f"\n上一轮发言：{last_msg.role.value} 说：{last_msg.content}\n"
        ctx += """请根据当前进度，有条理地推进。只输出一句指令。"""
        return ctx

    def _get_debate_prompt(self) -> str:
        p = self.state_machine.debate_phase
        return f"""当前阶段：法庭辩论
进度：
- 争议焦点是否已归纳：{p['focus_summarized']}
- 原告是否已充分发表辩论意见：{p['plaintiff_debated']}
- 被告是否已充分发表辩论意见：{p['defendant_debated']}
- 双方是否已作最后陈述：{p['final_statement']}
任务：推进辩论或最后陈述。只输出一句指令。"""

    def _get_mediation_prompt(self) -> str:
        p = self.state_machine.mediation_phase
        return f"""当前阶段：法庭调解
进度：
- 是否已经询问双方调解意愿：{p['asked']}
- 原告态度：{p['plaintiff_response']}
- 被告态度：{p['defendant_response']}
任务：询问调解意愿或宣布调解结果。只输出一句指令。"""

    def _get_judgment_prompt(self, summary: str) -> str:
        ev_text = "\n".join(f"- 由{e.provider.value}提交，内容：{e.content}；证明目的：{e.purpose}" for e in self.evidences)
        
        # 动态修正被告姓名：如果第三方查明事实中明确借款人姓名，则优先使用
        # 但如果庭审对话中已经确认了姓名，则不覆盖
        if not self.name_confirmed_by_dialogue["defendant"]:
            # 使用 LLM 提取
            extraction_prompt = f"""
请从以下【第三方查明事实】中提取借款人（被告）的姓名：
{self.case_info.third_party_findings}

返回 JSON: {{"defendant_name": "姓名" or null}}
"""
            try:
                data = self.llm.chat_json([{"role": "user", "content": extraction_prompt}])
                if data and data.get("defendant_name"):
                    found_name = data.get("defendant_name")
                    if found_name and found_name != "null" and found_name != self.case_info.defendant_name:
                        self.log(f"Updating defendant name from findings (LLM): {found_name}")
                        self.case_info.defendant_name = found_name
            except Exception as e:
                self.log(f"Failed to extract name from findings: {e}")
        
        defendant_name = self.case_info.defendant_name

        # 检索相关法条
        retrieved_laws_text = ""
        if self.law_retriever:
            # 优先使用第三方查明事实，其次使用摘要，最后使用诉讼请求
            query_text = self.case_info.third_party_findings
            if not query_text and summary:
                query_text = summary
            if not query_text:
                query_text = self.case_info.claim_description
            
            if query_text:
                try:
                    # 限制查询长度，避免过长导致 embedding 截断或 BM25 噪声过大
                    # 取前 1000 个字符通常足够覆盖核心事实
                    search_query = query_text[:1000]
                    laws = self.law_retriever.search(search_query, top_k=5)
                    if laws:
                        retrieved_laws_text = "\n【参考法条（仅供参考，请优先适用）】：\n" + "\n".join(
                            f"- {l['content']}" for l in laws
                        )
                except Exception as e:
                    self.log(f"Law retrieval failed: {e}")

        return f"""
你现在要扮演“撰写民事判决书的审判长助理”。请严格按照“先思考、后输出 JSON”的方式工作。

【案件基本信息】
原告：{self.case_info.plaintiff_name}
被告：{defendant_name}
案由/类型：{self.case_info.case_type}
诉讼请求：{self.case_info.claim_description}

【第三方查明的客观事实（应予采信）】：
{self.case_info.third_party_findings}

【庭审过程摘要】：
{summary}

【证据清单】：
{ev_text}
{retrieved_laws_text}

请按以下思维链步骤推理：
1. 事实认定：基于上述材料，分条写出“本院查明的事实”；
2. 争议焦点：列出 2-3 个本案的核心争议焦点；
3. 法律适用：针对每个争议焦点，指出适用的《中华人民共和国民法典》等法律条款，并结合案情作出分析；
4. 责任承担与判决结论：逐项判断原告各项诉讼请求是否有事实和法律依据，应予支持/部分支持/不予支持；
5. 形成完整的判决主文。

最终只输出一段合法 JSON，格式如下（注意键名不要改动）：
{{
  "fact_finding": "本院查明：……",
  "dispute_focus": ["焦点1", "焦点2"],
  "legal_analysis": "本院认为：……（系统性分析）",
  "applicable_laws": [
    {{"law": "《中华人民共和国民法典》第XXX条", "content": "条文要点概括", "applied_to": "对应的争议焦点编号或描述"}}
  ],
  "liability_mapping": {{
    "plaintiff_claims": ["诉请1", "诉请2"],
    "court_adoption": ["支持/驳回/部分支持 及理由（逐项）"]
  }},
  "judgment_result": "判决如下：一、……；二、……。"
}}

【重要约束】
1. 判决书中的当事人姓名必须与【案件基本信息】中的原告、被告姓名完全一致，严禁虚构或替换人名。
2. 特别注意：本案被告确认为“{defendant_name}”，判决书中必须统一使用该名字。
"""

    # --- 模板指令 ---

    def _template_instruction(self, state: CourtState) -> str:
        # 辅助函数：添加前缀信息
        def with_prefix(text: str, prefix_msg: str) -> str:
            if not prefix_msg:
                return text
            if "：" in text:
                role_part, content = text.split("：", 1)
                return f"{role_part}：鉴于{prefix_msg}，本庭已记录在案。{content}"
            return text

        if state == CourtState.OPENING:
            p = self.state_machine.opening_phase
            # 1. 身份核实
            if not p["plaintiff_verified"]:
                return "对原告说：请原告核实身份信息，并确认是否由本人到庭参加诉讼。"
            if not p["defendant_verified"]:
                return "对被告说：请被告核实身份信息，并确认是否由本人到庭参加诉讼。"

            # 1.1 宣布庭审构成及适用程序（只做一次，并及时更新状态）
            if not p["court_composition_announced"]:
                self.state_machine.update_phase_status(court_composition_announced=True)
                return "对原告说：本案由审判员独任审理，书记员依法记录，现正式宣布本庭构成。"
            if not p["procedure_announced"]:
                self.state_machine.update_phase_status(procedure_announced=True)
                return "对被告说：本案适用简易程序进行审理，请确认是否知悉并遵守法庭秩序。"
            
            # 2. 权利义务
            if not all(p["rights_informed_mask"].values()):
                if not p["rights_informed_mask"]["plaintiff"]:
                    return "对原告说：现在告知当事人诉讼权利和义务（委托代理人、申请回避、提供证据、辩论等）。请原告确认是否听清？"
                return "对被告说：请被告确认是否听清诉讼权利义务？"
            
            # 3. 回避申请
            if not all(p["recusal_asked_mask"].values()):
                if not p["recusal_asked_mask"]["plaintiff"]:
                    return "对原告说：根据法律规定，审判人员有法定情形的，当事人有权申请回避。请原告确认是否申请回避？"
                return "对被告说：请被告确认是否申请回避？"
            
            # 4. 缺席后果
            if not all(p["absence_asked_mask"].values()):
                if not p["absence_asked_mask"]["plaintiff"]:
                    return "对原告说：经传票传唤，无正当理由拒不到庭的，将依法缺席审理。请原告确认是否知晓缺席审理的法律后果？"
                return "对被告说：请被告确认是否知晓缺席审理后果？"

            return "对原告说：身份核实及权利义务告知完毕，现在开始法庭调查。请原告陈述诉讼请求及事实理由。"

        if state == CourtState.INVESTIGATION:
            p = self.state_machine.investigation_phase
            prefix = p.pop("last_discussion_result", "")
            
            # 1. 陈述与答辩
            if not p["plaintiff_stated"]:
                return with_prefix("对原告说：请陈述诉讼请求及事实理由，如实说明争议经过。", prefix)
            if not p["defendant_responded"]:
                return with_prefix("对被告说：请陈述答辩意见，并说明是否认可原告主张的事实。", prefix)
            
            # 2. 举证与质证 (Interleaved)
            if p["waiting_for_cross_exam"]:
                provider = p["last_evidence_provider"]
                disc = p["current_discussion"]
                
                instr = ""
                # 如果正在进行多轮讨论 (Active Discussion)
                if disc["is_active"] and disc["pending_question"]:
                    last_speaker = disc["last_speaker_role"]
                    question = disc["pending_question"]
                    burden_holder = disc["burden_holder"]
                    
                    # 如果明确了举证责任人，优先向责任人发问
                    if burden_holder:
                        # [Fix] 检查举证责任人是否已无新证据
                        holder_is_dry = p["no_more_evidence"].get(burden_holder, False)
                        
                        if not holder_is_dry:
                            if burden_holder == "plaintiff":
                                instr = f"对原告说：被告对“{question}”提出异议。根据谁主张谁举证原则，请原告就此提供进一步证据或说明。"
                            elif burden_holder == "defendant":
                                instr = f"对被告说：被告提出了“{question}”的新主张。根据抗辩需举证原则，请被告就此提供证据。"
                        else:
                            # 如果责任人已无证据，不再强求举证，而是转向询问对方或进行解释
                            # 避免死循环：法官不断要证据 -> 被告无证据 -> 法官又要证据
                            if burden_holder == "plaintiff":
                                instr = f"对原告说：被告对“{question}”提出异议。请原告就此进行说明（无需重复提交证据）。"
                            elif burden_holder == "defendant":
                                instr = f"对被告说：被告提出了“{question}”的新主张。请被告就此进行说明（无需重复提交证据）。"
                    
                    if not instr:
                        # 默认逻辑：如果上一轮是原告说的，现在问被告
                        if last_speaker == PartyRole.PLAINTIFF.value:
                            instr = f"对被告说：原告提出“{question}”。请被告进行解释或回应。"
                        # 如果上一轮是被告说的，现在问原告
                        else:
                            instr = f"对原告说：被告提出“{question}”。请原告进行解释或回应。"
                else:
                    # 默认质证指令
                    if provider == PartyRole.PLAINTIFF.value:
                        instr = "对被告说：请被告对原告提交的证据发表质证意见。如有异议请具体说明，无异议请明确认可。"
                    else:
                        instr = "对原告说：请原告对被告提交的证据发表质证意见。如有异议请具体说明，无异议请明确认可。"
                
                return with_prefix(instr, prefix)

            if not p["no_more_evidence"]["plaintiff"]:
                return with_prefix("对原告说：请出示证据并说明来源、内容及证明目的，如无新证据请明确说明。", prefix)
            
            if not p["no_more_evidence"]["defendant"]:
                return with_prefix("对被告说：请出示证据或就原告证据发表质证意见，如无新证据请明确说明。", prefix)
            
            # 3. 事实核实
            if not all(p["fact_inquiry_mask"].values()):
                if not p["fact_inquiry_mask"]["plaintiff"]:
                    return with_prefix("对原告说：法庭对事实部分进行发问核实，是否还有需要补充的事实？", prefix)
                return with_prefix("对被告说：法庭对事实部分进行发问核实，是否还有需要补充的事实？", prefix)

            return with_prefix("对原告说：双方举证质证完毕，请准备进入法庭辩论阶段。", prefix)
        
        if state == CourtState.DEBATE:
            p = self.state_machine.debate_phase
            prefix = p.pop("last_discussion_result", "")
            topic = p["current_topic"]

            # 1. 优先处理多轮辩论
            if p["waiting_for_rebuttal"] and topic["is_active"] and topic["point"]:
                last_speaker = topic["last_speaker_role"]
                point = topic["point"]
                burden_holder = topic["burden_holder"]

                instr = ""
                # 举证责任导向
                if burden_holder:
                    # 责任在原告
                    if burden_holder == "plaintiff":
                        # 情况A: 被告反驳原告 (Last Speaker: Defendant) -> 原告需证明
                        if last_speaker == PartyRole.DEFENDANT.value:
                            instr = f"对原告说：被告反驳了“{point}”。请原告提供证据或法律依据予以回应。"
                        # 情况B: 原告提出新观点 (Last Speaker: Plaintiff) -> 原告需证明 (通常此时会问被告意见，但如果强调举证，也可以追问原告)
                        else:
                            instr = f"对被告说：原告提出了“{point}”。请被告对此发表意见。" # 这种情况下通常转给对方质辩

                    # 责任在被告
                    elif burden_holder == "defendant":
                        # 情况C: 原告反驳被告 (Last Speaker: Plaintiff) -> 被告需证明
                        if last_speaker == PartyRole.PLAINTIFF.value:
                            instr = f"对被告说：原告对“{point}”提出异议。请被告提供证据或法律依据予以证明。"
                        # 情况D: 被告提出新观点 (Last Speaker: Defendant) -> 被告需证明
                        else:
                            instr = f"对原告说：被告提出了“{point}”。请原告对此发表意见。"

                if not instr:
                    if last_speaker == PartyRole.PLAINTIFF.value:
                        instr = f"对被告说：原告指出“{point}”。请被告对此进行回应。"
                    else:
                        instr = f"对原告说：被告指出“{point}”。请原告对此进行回应。"
                
                return with_prefix(instr, prefix)

            if not p["focus_summarized"]:
                self.state_machine.update_phase_status(focus_summarized=True)
                return with_prefix("对原告说：法庭调查结束，现在开始法庭辩论。本案争议焦点业已归纳，请原告围绕焦点先行发表辩论意见。", prefix)
            if not p["plaintiff_debated"]:
                return with_prefix("对原告说：请围绕争议焦点进一步发表辩论意见。", prefix)
            if not p["defendant_debated"]:
                return with_prefix("对被告说：请就争议焦点发表辩论意见并回应原告观点。", prefix)
            if not p["final_statement"]["plaintiff"]:
                return with_prefix("对原告说：法庭辩论结束，请作最后陈述。", prefix)
            if not p["final_statement"]["defendant"]:
                return with_prefix("对被告说：请作最后陈述并说明是否还有补充意见。", prefix)
            
            # [Fix] 确保双方都陈述完毕后，才进入调解
            if p["final_statement"]["plaintiff"] and p["final_statement"]["defendant"]:
                return with_prefix("对原告说：双方最后陈述完毕，法庭将进入调解阶段。", prefix)
            
            # Fallback
            return with_prefix("对原告说：法庭辩论结束，请作最后陈述。", prefix)
            
        if state == CourtState.MEDIATION:
            p = self.state_machine.mediation_phase
            if not p["asked"]:
                return "对原告说：法庭拟开展调解，请明确是否同意调解。"
            if p["plaintiff_response"] is None:
                return "对原告说：请明确是否同意在法庭主持下调解。"
            if p["defendant_response"] is None:
                return "对被告说：请明确是否同意在法庭主持下调解。"
            
            # 双方都已表态
            if p["plaintiff_response"] == "agree" and p["defendant_response"] == "agree":
                return "对原告说：鉴于双方均同意调解，法庭将主持调解工作，具体安排调解事宜。"
            
            # 至少一方拒绝
            reason = ""
            if p["plaintiff_response"] == "refuse" and p["defendant_response"] == "refuse":
                reason = "双方当事人均明确表示不同意调解"
            elif p["plaintiff_response"] == "refuse":
                reason = "原告明确表示不同意调解"
            else:
                reason = "被告明确表示不同意调解"
                
            return f"对原告说：鉴于{reason}，法庭不再组织调解。本案将择期宣判。"
            
        return "对原告说：请继续配合法庭指令。"

    # --- 抽取与摘要 ---

    def _extract_claim(self, text: str) -> Dict:
        prompt = f"从下面的“原告陈述”中，提取诉讼请求信息，严格按 JSON 输出：\n原告陈述：{text}\n输出示例：{{'claim_type': '...', 'claim_amount': 50000, 'main_request': '...', 'facts': []}}"
        if self.extraction_chain:
            try:
                return self.extraction_chain.invoke({"prompt": prompt})
            except Exception as e:
                self.log(f"Extraction Chain Error: {e}. Falling back to chat_json.")
                return self.llm.chat_json([{"role": "user", "content": prompt}])
        return self.llm.chat_json([{"role": "user", "content": prompt}])

    def _extract_defense(self, text: str) -> Dict:
        prompt = f"从下面的“被告答辩”中，提取关键信息，严格按 JSON 输出：\n被告答辩：{text}\n输出示例：{{'admit': [], 'deny': [], 'defense_reason': '...', 'counterclaim': null}}"
        if self.extraction_chain:
            try:
                return self.extraction_chain.invoke({"prompt": prompt})
            except Exception as e:
                self.log(f"Extraction Chain Error: {e}. Falling back to chat_json.")
                return self.llm.chat_json([{"role": "user", "content": prompt}])
        return self.llm.chat_json([{"role": "user", "content": prompt}])

    def _is_duplicate_evidence(self, content: str, role: PartyRole) -> bool:
        """Check if the evidence content is substantially similar to existing evidence from the same role."""
        # Normalize content (remove whitespace, punctuation)
        def normalize(s):
            return "".join(c for c in s if c.isalnum())
        
        norm_content = normalize(content)
        if not norm_content:
            return False
            
        for ev in self.evidences:
            if ev.provider != role:
                continue
            
            norm_ev = normalize(ev.content)
            # Check for containment or high similarity
            if norm_content in norm_ev or norm_ev in norm_content:
                return True
        return False

    def _extract_evidence(self, text: str, role: PartyRole) -> Optional[Evidence]:
        prompt = f"""
当事人（{role.value}）刚刚的发言中，疑似涉及“提交证据”。
请判断该发言是“提交新证据”还是“对已有证据发表意见/质证”。
发言内容：{text}

如果是提交新证据，请提取证据信息。
如果是质证或仅提及证据但未提交，请将 is_submission 设为 false。

严格按 JSON 输出：
{{
    "is_submission": true/false,
    "evidence_content": "...",
    "purpose": "..."
}}
"""
        if self.extraction_chain:
            try:
                data = self.extraction_chain.invoke({"prompt": prompt})
            except Exception as e:
                self.log(f"Extraction Chain Error: {e}. Falling back to chat_json.")
                data = self.llm.chat_json([{"role": "user", "content": prompt}])
        else:
            data = self.llm.chat_json([{"role": "user", "content": prompt}])
        
        if not data.get("is_submission"):
            return None

        # Check for duplicates
        if self._is_duplicate_evidence(data.get("evidence_content", text), role):
            self.log(f"Detected duplicate evidence from {role.value}. Treating as 'no more evidence'.")
            # Force update no_more_evidence
            nm = dict(self.state_machine.investigation_phase["no_more_evidence"])
            # Map PartyRole to lowercase key ('plaintiff' or 'defendant')
            key = "plaintiff" if role == PartyRole.PLAINTIFF else "defendant"
            nm[key] = True
            self.state_machine.update_phase_status(no_more_evidence=nm)
            return None

        # 标记需要质证
        self.state_machine.update_phase_status(
            waiting_for_cross_exam=True,
            last_evidence_provider=role.value
        )
        
        return Evidence(
            evidence_id=f"E_{role.value}_{abs(hash(text)) % 10000}",
            provider=role,
            content=data.get("evidence_content", text),
            purpose=data.get("purpose", ""),
        )

    def _summarize_dialogue(self) -> str:
        conv = "\n".join(f"{m.role.value}: {m.content}" for m in self.dialogue)
        prompt = f"下面是一段模拟民事庭审的对话记录，请用 300 字以内，提炼出本案要点摘要，包含：原告诉求、被告抗辩、证据情况、争议焦点。\n对话如下：\n{conv}"
        if self.summary_chain:
            return self.summary_chain.invoke({"prompt": prompt})
        return self.llm.call(prompt)

    def _format_judgment_text(self) -> str:
        if not self.judgment_json:
            return "【系统】未能成功生成结构化判决结果，请检查模型输出。"
        j = self.judgment_json
        parts = [
            f"案号：{self.case_info.case_number}",
            f"原告：{self.case_info.plaintiff_name}",
            f"被告：{self.case_info.defendant_name}",
            "",
            "【本院查明】",
            j.get("fact_finding", ""),
            "",
            "【争议焦点】",
        ]
        for idx, fp in enumerate(j.get("dispute_focus", []), 1):
            parts.append(f"  {idx}. {fp}")
        parts.extend([
            "",
            "【本院认为】",
            j.get("legal_analysis", ""),
            "",
            "【适用法律】",
        ])
        for law in j.get("applicable_laws", []):
            applied_to = law.get("applied_to", "")
            suffix = f"（适用于：{applied_to}）" if applied_to else ""
            parts.append(f"- {law.get('law', '')}：{law.get('content', '')}{suffix}")

        lm = j.get("liability_mapping", {})
        if lm:
            parts.extend(["", "【诉请与裁判对照】"])
            claims = lm.get("plaintiff_claims", [])
            adoptions = lm.get("court_adoption", [])
            for i, claim in enumerate(claims):
                adoption = adoptions[i] if i < len(adoptions) else "—"
                parts.append(f"  {i+1}. 诉请：{claim} → 裁判：{adoption}")

        parts.extend(["", "【判决结果】", j.get("judgment_result", ""), "", "审判长：某某（模拟）"])
        return "\n".join(parts)

    def get_structured_judgment(self) -> dict:
        """返回结构化判决结果，形成事实-争点-法条-结论链路。"""
        sj = StructuredJudgment()
        if not self.judgment_json:
            return sj.to_dict()

        j = self.judgment_json
        sj.facts = [{"content": j.get("fact_finding", ""), "source": "court_finding"}]
        sj.dispute_points = j.get("dispute_focus", [])
        sj.legal_articles = j.get("applicable_laws", [])
        sj.liability_mapping = j.get("liability_mapping", {})
        sj.conclusion = j.get("judgment_result", "")

        mp = self.state_machine.mediation_phase
        if mp["asked"]:
            sj.mediation_result = {
                "plaintiff_response": mp["plaintiff_response"],
                "defendant_response": mp["defendant_response"],
                "announced": mp["announced"],
                "outcome": "mediation_agreed" if (mp["plaintiff_response"] == "agree" and mp["defendant_response"] == "agree") else "mediation_refused",
            }
        return sj.to_dict()

    def _report(self) -> Dict:
        return {
            "case_info": asdict(self.case_info),
            "dialogue_count": len(self.dialogue),
            "evidence_count": len(self.evidences),
            "extracted": self.extracted,
            "judgment_json": self.judgment_json,
            "structured_judgment": self.get_structured_judgment(),
            "state_history": [s.value for s in self.state_machine.state_history],
            "sub_stage_history": [s.value for s in self.state_machine.sub_stage_history],
            "compliance_report": self.state_machine.get_compliance_report(),
        }

    def _get_ci_model_answer(self) -> Dict[str, object]:
        if not self.judgment_json:
            return {
                "court_reasoning": self.extracted.get("summary", ""),
                "court_judgment": "",
                "law": [],
                "structured_judgment": self.get_structured_judgment(),
            }
        laws = [law.get("law", "") for law in self.judgment_json.get("applicable_laws", []) if law.get("law")]
        return {
            "court_reasoning": self.judgment_json.get("legal_analysis", ""),
            "court_judgment": self.judgment_json.get("judgment_result", ""),
            "law": laws,
            "structured_judgment": self.get_structured_judgment(),
        }
