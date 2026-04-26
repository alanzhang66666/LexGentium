"""
DD 场景智能体 - 答辩状生成
律师通过对话收集信息并生成答辩状
"""
import json
import re
import time
from typing import Dict, Any, Tuple, List, Optional
from dataclasses import asdict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .base_agent import BaseAgent
from core import CourtSimulatorClient, LLMClient
from core.schemas import CaseData
from core.langchain_utils import RobustJsonOutputParser
from utils import DialogHistory
from core.law_retriever import LawRetriever, get_dashscope_api_key
import os

# --- Helper Functions from DD_Agent ---

_ORG_PATTERN = re.compile(
    r"([\u4e00-\u9fa5A-Za-z0-9（）()·\-_]{2,30}"
    r"(?:有限责任公司|股份有限公司|有限公司|集团|公司|银行|保险|医院|学校|中心|协会|委员会|局|所|处|站|厂|店))"
)

def extract_third_parties(history_text: str) -> list[str]:
    cands = []
    for m in _ORG_PATTERN.findall(history_text or ""):
        if m not in cands:
            cands.append(m)
    return cands[:5]

def _last_role_text(history_text: str, role: str) -> str:
    for line in reversed(history_text.splitlines()):
        if line.startswith(f"{role}:"):
            return line.split(":", 1)[1].strip()
    return ""

def _last_user_text(history_text: str) -> str:
    for role in ("Client", "Server", "用户", "User"):
        t = _last_role_text(history_text, role)
        if t:
            return t
    return ""

def _sanitize_for_single_question(s: str) -> str:
    return (s or "").replace("？", "。").replace("?", "。")

def enforce_single_question(message: str) -> str:
    if not message:
        return message
    first_positions = []
    for ch in ["？", "?"]:
        idx = message.find(ch)
        if idx != -1:
            first_positions.append(idx)
    if not first_positions:
        return message
    first_q_idx = min(first_positions)
    return message[: first_q_idx + 1]


class DDAgent(BaseAgent):
    """答辩状生成智能体"""

    def __init__(
        self,
        api_client: CourtSimulatorClient,
        llm: LLMClient,
        max_turns: int = 20,
        verbose: bool = False,
    ):
        super().__init__(api_client, llm, "DD", max_turns, verbose)
        self.role = "Lawyer"
        self.user_role = "Client"
        self.doc_name = "民事答辩状"

        # 初始化法律检索器
        try:
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
            # 信息抽取 Chain
            self.extraction_prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个严谨的法律文书专家。请输出严格的JSON。"),
                ("user", "{prompt}")
            ])
            self.extraction_chain = self.extraction_prompt | self.llm.chat_model | RobustJsonOutputParser()

            # 策略决策 Chain
            self.strategy_prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个专业的律师。在生成答辩状前，必须确保有足够的‘事实与理由’和‘证据’。不要轻易STOP。"),
                ("user", "{prompt}")
            ])
            self.strategy_chain = self.strategy_prompt | self.llm.chat_model | RobustJsonOutputParser()
        else:
            self.extraction_chain = None
            self.strategy_chain = None

    def run_case(
        self,
        case_id: str,
        case_info: Dict = None,
        **kwargs
    ) -> Tuple[DialogHistory, Dict[str, Any]]:
        """
        运行 DD 场景案例
        """
        dialog_history = DialogHistory(self.scenario)
        
        # 尝试从 kwargs 获取初始数据
        input_json = kwargs.get("input_json", {})
        c_info = input_json.get("case_info", {})
        complaint = input_json.get("complaint", {})
        
        case_data = CaseData(
            case_number=c_info.get("case_number", ""),
            court_name=c_info.get("court", "（法院名称）"),
            plaintiff_claims=complaint.get("plaintiff_claim", []),
            plaintiff_facts=complaint.get("plaintiff_case_description", ""),
            user_role="被告"
        )

        # 初始问候
        initial_msg = "您好，我是您的代理律师。请问您收到了谁的起诉状？您对起诉内容有什么意见？"
        
        current_turn = 1
        instruction = initial_msg
        dialog_history.add_user_message(current_turn, instruction)

        metadata = {
            "turns": 0,
            "api_errors": [],
            "termination_reason": "",
        }

        while current_turn < self.max_turns:
            # 调用 API
            api_resp = self.api_client.simulate_dd(
                case_id=case_id,
                dialog_history=dialog_history.get_api_format(),
            )

            response_text = api_resp.get("response")

            if not response_text:
                metadata["api_errors"].append(api_resp)
                metadata["termination_reason"] = "API Error or Empty Response"
                break

            dialog_history.add_env_response(
                current_turn,
                self.user_role,
                response_text,
            )

            self.log(f"Turn {current_turn} Lawyer: {instruction}")
            self.log(f"Turn {current_turn} Client: {response_text}")

            # 1. 信息抽取
            history_text = self._history_to_text(dialog_history)
            case_data = self._extract_info(history_text, case_data)
            
            # 2. 决策下一步
            should_stop, next_q = self._judge_status(case_data, current_turn, history_text)
            
            if should_stop:
                metadata["termination_reason"] = "Ready to draft"
                break

            current_turn += 1
            instruction = enforce_single_question(next_q)
            dialog_history.add_user_message(current_turn, instruction)

        metadata["turns"] = current_turn
        if not metadata["termination_reason"]:
            metadata["termination_reason"] = "Max turns reached"

        # 生成答辩状
        draft_content = self._render_defense(case_data, case_data.court_name)

        return dialog_history, {
            "model_answer": draft_content,
            "metadata": metadata,
        }

    def process_turn(self, dialog_history: List[Dict], case_id: str, input_json: Dict = None) -> str:
        """处理单轮对话 (API 模式)"""
        # 1. 转换历史格式
        dh = DialogHistory(self.scenario)
        dh.history = dialog_history
        history_text = self._history_to_text(dh)
        
        # 2. 初始化 CaseData
        if input_json:
            c_info = input_json.get("case_info", {})
            complaint = input_json.get("complaint", {})
            case_data = CaseData(
                case_number=c_info.get("case_number", ""),
                court_name=c_info.get("court", "（法院名称）"),
                plaintiff_claims=complaint.get("plaintiff_claim", []),
                plaintiff_facts=complaint.get("plaintiff_case_description", ""),
                user_role="被告"
            )
        else:
            case_data = CaseData(user_role="被告")
        
        # 3. 信息抽取 (使用完整历史以确保不遗漏早期信息)
        # 注意：_extract_info 内部会调用 _build_extraction_prompt
        # 我们需要确保 _build_extraction_prompt 能看到足够的信息
        case_data = self._extract_info(history_text, case_data)
        
        # 4. 决策下一步
        # API 传入的 dialog_history 包含当前轮次的所有消息
        # turn count 可以近似为 len(dialog_history) / 2
        current_turn = len(dialog_history) // 2 + 1
        should_stop, next_q = self._judge_status(case_data, current_turn, history_text)
        
        if should_stop:
            # 生成答辩状作为最终回复
            return self._render_defense(case_data, case_data.court_name)
            
        return enforce_single_question(next_q)

    def _history_to_text(self, dialog_history: DialogHistory) -> str:
        text = ""
        for item in dialog_history.history:
            text += f"{item['role']}: {item['message']}\n"
        return text

    def _extract_info(self, history_text: str, current_data: CaseData) -> CaseData:
        """信息抽取逻辑"""
        # 1. 规则兜底
        last_turn = _last_user_text(history_text)
        if current_data.user_entity_type == "未知":
            if any(kw in last_turn for kw in ["公司", "单位", "企业", "集团", "法定代表人", "法人"]):
                current_data.user_entity_type = "法人"
            elif any(kw in last_turn for kw in ["个人", "我本人", "自然人", "公民"]):
                current_data.user_entity_type = "自然人"

        # 2. LLM 提取
        prompt_text = self._build_extraction_prompt(history_text, current_data)
        
        if self.extraction_chain:
            try:
                resp = self.extraction_chain.invoke({"prompt": prompt_text})
            except Exception as e:
                self.log(f"Extraction Chain Error: {e}")
                resp = {}
        else:
            messages = [
                {"role": "system", "content": "你是一个严谨的法律文书专家。请输出严格的JSON。"},
                {"role": "user", "content": prompt_text}
            ]
            resp = self.llm.chat_json(messages, temperature=0.1)
        
        if isinstance(resp, dict) and "data" in resp:
            current_data = self._merge_data(current_data, resp["data"], resp.get("reasoning", ""))
        
        # 3. 规则兜底提取 (针对 LLM 容易漏掉的简单否定)
        if not current_data.defense_claims:
            if any(kw in last_turn for kw in ["不认可", "不同意", "反对", "驳回", "没有依据", "不属实"]):
                # 如果用户明确表示不认可，但 LLM 没提取到，手动添加一个通用的抗辩请求
                current_data.defense_claims.append("请求驳回原告全部诉讼请求")
                current_data.facts.append(f"被告对原告诉求表示不认可：{last_turn[:50]}...")

        return current_data

    def _build_extraction_prompt(self, history_text: str, current_data: CaseData) -> str:
        # 使用完整历史，避免遗漏早期的起诉状信息
        recent_history = history_text
        
        bg_info = f"""
【原告起诉信息】
诉求：{json.dumps(current_data.plaintiff_claims, ensure_ascii=False)}
事实：{current_data.plaintiff_facts}
"""
        current_json = json.dumps(asdict(current_data), ensure_ascii=False, indent=2)

        return f"""
任务：从对话中提取信息更新 CaseData。

{bg_info}

【当前已知数据】
{current_json}

【最新对话片段】
{recent_history}

【提取规则】
1. **起诉状信息**：如果用户提供了起诉状内容（通常在对话开头），请提取：
   - 原告诉求 (plaintiff_claims)
   - 原告事实与理由 (plaintiff_facts)
   - 案号 (case_number)
   - 法院名称 (court_name)
2. **身份信息**：提取姓名、性别、出生日期、民族、住址（自然人）或名称、法定代表人、住所地（法人）。
3. **处理“无证据”的情况**：
   - 如果用户说“没有资料”、“时间太久”、“没保留”，请务必将这些作为 Facts (事实) 提取出来！
   - 示例 Facts: "因时间久远，被告处已无2010年前的档案资料"
   - 此时 Evidence 字段保持为空即可，但 Facts 必须记录“没有证据”这一情况。
4. **第三方甩锅**：
   - 如果用户提到“是XX集团的事”，提取为 Facts: "业务已由XX集团接手", "责任应由XX集团承担".
   - 同时如果有明确请求，提取为 Defense Claims: "请求追加XX集团为第三人".

【输出结构】
{{
  "reasoning": "...",
  "data": {{
      "case_number": "...",
      "court_name": "...",
      "plaintiff_claims": ["..."],
      "plaintiff_facts": "...",
      "user_entity_type": "自然人/法人/未知", 
      "person_info": {{...}}, 
      "org_info": {{...}},
      "defense_claims": [], 
      "facts": ["因历史原因资料缺失", "责任在鹤煤集团"],
      "evidence": [] 
  }}
}}
"""

    def _merge_data(self, old_obj: CaseData, new_dict: Dict[str, Any], reasoning: str) -> CaseData:
        # 0. 案件基础信息
        if new_dict.get("case_number"): old_obj.case_number = new_dict["case_number"]
        if new_dict.get("court_name"): old_obj.court_name = new_dict["court_name"]
        if new_dict.get("plaintiff_claims"): old_obj.plaintiff_claims = new_dict["plaintiff_claims"]
        if new_dict.get("plaintiff_facts"): old_obj.plaintiff_facts = new_dict["plaintiff_facts"]

        # 1. 基础字段
        new_type = new_dict.get("user_entity_type")
        if new_type in ["自然人", "法人"]:
            old_obj.user_entity_type = new_type
        
        new_o = new_dict.get("org_info", {})
        if new_o.get("name") and old_obj.user_entity_type != "法人":
            old_obj.user_entity_type = "法人"
            
        new_p = new_dict.get("person_info", {})
        if new_p.get("name") and not new_o.get("name") and old_obj.user_entity_type == "未知":
            old_obj.user_entity_type = "自然人"

        # 2. Person Info
        for k in ["name", "gender", "dob", "ethnicity", "address"]:
            val = new_p.get(k)
            if val and val not in ["用户", "我", "本人", "被告", "未知"]:
                setattr(old_obj.person_info, k, val)

        # 3. Org Info
        for k in ["name", "address", "legal_rep"]:
            val = new_o.get(k)
            if val and val not in ["用户", "我", "单位"]:
                setattr(old_obj.org_info, k, val)

        # 4. 列表字段
        if new_dict.get("defense_claims"): 
            valid_claims = []
            for c in new_dict["defense_claims"]:
                if any(kw in c for kw in ["请求", "驳回", "同意", "不认可", "确认", "追加"]):
                    valid_claims.append(c)
            if valid_claims:
                old_obj.defense_claims = valid_claims

        if new_dict.get("facts"):
            for f in new_dict["facts"]:
                if f and f not in old_obj.facts:
                    old_obj.facts.append(f)
        
        if new_dict.get("evidence"):
            for e in new_dict["evidence"]:
                if e and e not in old_obj.evidence:
                    old_obj.evidence.append(e)
        
        old_obj.last_reasoning = reasoning
        return old_obj

    def _judge_status(self, data: CaseData, turn_count: int, history_text: str) -> Tuple[bool, str]:
        """判断当前状态，决定下一句回复"""
        # 1. 轮次保护
        if turn_count >= 18: 
            return True, "（轮次即将耗尽，准备生成文书）"

        # 2. 身份必填项
        if data.user_entity_type == "未知":
            return False, "请问您是自然人（个人）还是法人（公司）？我们需要先确定答辩主体。"
            
        missing = data.get_missing_mandatory_fields()
        if missing:
            # Check if we already asked for these fields in the last turn
            last_lawyer_msg = ""
            parts = history_text.split(f"{self.role}:")
            if len(parts) > 1:
                last_lawyer_msg = parts[-1].split(f"{self.user_role}:")[0].strip()
            
            still_missing = []
            for m in missing:
                if m in last_lawyer_msg:
                    # We asked, but it's still missing. Fill with placeholder to stop loop.
                    if m == "单位住所地":
                        data.org_info.address = "（地址详见营业执照）"
                    elif m == "详细住址":
                        data.person_info.address = "（地址待补）"
                    elif m == "法定代表人姓名":
                        data.org_info.legal_rep = "（姓名待补）"
                    elif m == "单位名称":
                        data.org_info.name = "（名称待补）"
                    elif m == "姓名":
                        data.person_info.name = "（姓名待补）"
                    # For other fields, we might still ask or just skip
                else:
                    still_missing.append(m)
            
            if still_missing:
                targets = "、".join(still_missing)
                return False, f"请补充起草答辩状必须的当事人信息：{targets}。"

        # 2.5. 缺失起诉状信息的兜底
        if not data.plaintiff_claims and not data.plaintiff_facts:
             # 如果没有起诉状信息，必须问用户
             if "起诉状" not in history_text:
                 return False, "我这边暂时没有看到起诉状的详细内容。请问原告具体的诉讼请求和事实理由是什么？"

        # 3. 针对原告事实的回应 (新增逻辑：优先确认事实)
        # 如果我们还没有收集到任何关于事实的描述（或者只有默认的），且原告有事实描述
        if data.plaintiff_facts and not data.facts:
             # 简单判断一下历史对话中是否讨论过事实
             if "事实" not in history_text and "经过" not in history_text:
                 return False, f"原告在起诉状中描述了以下事实：\n{data.plaintiff_facts}\n\n请问您对这些事实描述是否认可？如果不认可，请详细说明真实情况。"

        # 4. 针对原告诉求的初步回应
        # Check if we already asked this
        last_lawyer_msg = ""
        parts = history_text.split(f"{self.role}:")
        if len(parts) > 1:
            last_lawyer_msg = parts[-1].split(f"{self.user_role}:")[0].strip()

        claims_question_marker = "请问您对这些诉求是完全不认可，还是部分认可？"

        if data.plaintiff_claims and not data.defense_claims:
             # Check if we have asked this question too many times
             ask_count = history_text.count(claims_question_marker)
             if ask_count >= 2:
                 # We asked twice, user probably answered but we missed it or they are vague.
                 # Assume "Reject All" to move forward.
                 data.defense_claims.append("请求驳回原告全部诉讼请求")
                 # Fall through to next logic
             elif claims_question_marker not in last_lawyer_msg:
                 claims_str = "\n".join([f"{i+1}. {c}" for i, c in enumerate(data.plaintiff_claims)])
                 return False, f"原告在起诉状中提出了以下诉求：\n{claims_str}\n\n{claims_question_marker}"
             else:
                 # We asked, but user didn't give a clear stance.
                 return False, "我们需要明确您对这些诉求的意见（认可/不认可），以便起草答辩状。如果不清楚，也可以回答“不认可”。"

        # 5. 智能追问
        llm_q = self._ask_llm_strategy(data, history_text)
        
        if llm_q and "STOP" not in llm_q:
            return False, llm_q

        return True, "信息收集完毕，我将为您起草答辩状。"

    def _ask_llm_strategy(self, data: CaseData, history_text: str) -> str:
        last_turn = _last_user_text(history_text)
        
        user_denied = any(kw in last_turn for kw in ["没有", "不清楚", "不知道", "太久", "丢失", "没保留"])
        
        summary = {
            "plaintiff_facts": data.plaintiff_facts,
            "plaintiff_claims": data.plaintiff_claims,
            "our_defense_stance": data.defense_claims,
            "collected_facts": data.facts,
            "collected_evidence": data.evidence,
            "user_last_response": last_turn
        }

        prompt_text = f"""
你是一名被告律师。你的目标是完善答辩状。
【当前案件状态】
{json.dumps(summary, ensure_ascii=False, indent=2)}

【最近对话】
{history_text[-1000:]}

【决策逻辑】
1. **检测“死胡同”**:
   - 如果用户已经表示“没有资料”、“时间太久不记得”，**绝对禁止**再追问“有没有新闻报道”、“有没有间接证据”。
   - 此时你应该**转换策略**：
     - 策略A：询问是否申请**法院依职权调查**？
     - 策略B：询问是否申请**追加第三人**（如果用户提到了第三方责任）？
     - 策略C：如果没别的可问，输出 STOP。

2. **常规追问 (必须严格执行)**:
   - **理由询问**：如果用户表示“不认可”原告诉求，但`collected_facts`中没有详细的反驳理由（只有简单的“不认可”），必须追问：“您不认可的具体理由是什么？事实情况是怎样的？”
   - **证据询问**：如果用户提出了反驳理由（Facts），但`collected_evidence`为空，且之前没问过证据，必须追问：“您有哪些证据可以支持您的主张？”
   - **反诉询问**：如果用户提到原告行为造成了损失，询问是否提出反诉。

3. **结束判断**:
   - 只有当：(1) 明确了对原告诉求的态度；(2) 收集到了反驳理由（或确认无理由）；(3) 确认了证据情况（有或无），才输出 STOP。

【输出格式 JSON】
需要追问：{{"question": "既然您不认可原告的说法，请问真实的情况是怎样的？"}}
无需追问：{{"question": "STOP"}}
"""
        
        try:
            if self.strategy_chain:
                resp = self.strategy_chain.invoke({"prompt": prompt_text})
            else:
                messages = [
                    {"role": "system", "content": "你是一个专业的律师。在生成答辩状前，必须确保有足够的‘事实与理由’和‘证据’。不要轻易STOP。"},
                    {"role": "user", "content": prompt_text}
                ]
                resp = self.llm.chat_json(messages, temperature=0.2)

            if isinstance(resp, dict):
                q = resp.get("question", "STOP").strip()
                
                # Sanity check for the question
                if not q or len(q) < 4 or q == ":" or q == "：":
                    # Fallback logic if LLM gives garbage
                    if "责任" in last_turn and ("集团" in last_turn or "公司" in last_turn):
                         return "既然您认为责任在第三方，我们是否申请追加其为第三人？"
                    return "STOP"

                if user_denied and any(w in q for w in ["新闻", "报表", "记录", "凭证", "证据"]):
                    if "集团" in str(data.facts) or "集团" in last_turn:
                         return "既然您手头没有直接证据，且相关资料由鹤煤集团掌握，我们是否在答辩状中明确申请追加其为第三人？"
                    return "STOP"
                return q
            return "STOP"
        except Exception as e:
            self.log(f"Strategy Chain Error: {e}")
            return "STOP"

    def _render_defense(self, data: CaseData, court_name: str) -> str:
        """渲染答辩状"""
        # 检索相关法条
        retrieved_laws_text = ""
        if self.law_retriever:
            try:
                # 使用事实部分作为查询
                query_text = "\n".join(data.facts) if data.facts else ""
                if not query_text:
                    query_text = "\n".join(data.defense_claims) if data.defense_claims else ""
                
                if query_text:
                    laws = self.law_retriever.search(query_text[:1000], top_k=3)
                    if laws:
                        retrieved_laws_text = "\n            【参考法条】：\n" + "\n".join(
                            f"            - {l['content']}" for l in laws
                        )
            except Exception as e:
                self.log(f"Law retrieval failed: {e}")

        parts = []
        parts.append(f"                {self.doc_name}\n")
        
        # 身份部分
        if data.user_entity_type == "自然人":
            p = data.person_info
            info_str = f"答辩人（被告）：{p.name or '（姓名）'}"
            if p.gender: info_str += f"，{p.gender}"
            if p.dob: info_str += f"，{p.dob}出生"
            if p.ethnicity: info_str += f"，{p.ethnicity}"
            info_str += f"，住{p.address or '（地址待补）'}。"
            parts.append(f"            {info_str}")
        
        elif data.user_entity_type == "法人":
            o = data.org_info
            parts.append(f"            答辩人（被告）：{o.name or '（单位名称）'}，"
                         f"法定代表人：{o.legal_rep or '（姓名）'}，"
                         f"住所：{o.address or '（地址待补）'}。")
        else:
            parts.append("            答辩人：(信息缺失)")

        parts.append("")
        
        # 案号部分
        c_no = data.case_number or "（案号）"
        c_court = court_name or data.court_name or "（法院名称）"
        parts.append(f"            对{c_court}（{c_no}）一案的起诉，答辩如下：")
        
        # 答辩意见
        parts.append("            一、答辩请求：")
        if data.defense_claims:
            for i, c in enumerate(data.defense_claims):
                parts.append(f"            {i+1}. {c}")
        else:
            parts.append("            1. 请求驳回原告全部诉讼请求。")

        parts.append("\n            二、事实与理由：")
        if data.facts:
            unique_facts = list(dict.fromkeys(data.facts))
            for f in unique_facts:
                parts.append(f"            - {f}")
        else:
            parts.append("            （事实部分待补充）")
            
        if retrieved_laws_text:
            parts.append("\n            三、法律依据：")
            parts.append(retrieved_laws_text)

        # 证据部分
        parts.append("\n            证据和证据来源，证人姓名和住所：")
        if data.evidence:
             unique_ev = list(dict.fromkeys(data.evidence))
             for e in unique_ev:
                 parts.append(f"            - {e}")
        else:
            parts.append("            无")

        parts.append("\n            此致")
        parts.append(f"            {c_court}")
        parts.append("")
        
        signer = data.person_info.name if data.user_entity_type == "自然人" else data.org_info.name
        parts.append(f"            答辩人：{signer or 'XXX'}")
        parts.append("            XXXX年XX月XX日")

        return "\n".join(parts)
