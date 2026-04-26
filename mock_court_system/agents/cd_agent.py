"""
CD 场景智能体 - 起诉状生成
律师通过对话收集信息并生成起诉状
"""
from typing import Dict, Any, Tuple, List
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from .base_agent import BaseAgent
from core import CourtSimulatorClient, LLMClient
from utils import DialogHistory
from core.law_retriever import LawRetriever, get_dashscope_api_key
import os


class CDAgent(BaseAgent):
    """起诉状生成智能体"""

    def __init__(
        self,
        api_client: CourtSimulatorClient,
        llm: LLMClient,
        max_turns: int = 20,
        verbose: bool = False,
    ):
        super().__init__(api_client, llm, "CD", max_turns, verbose)

        self.role = "Lawyer"
        self.user_role = "Client"
        self.doc_name = "民事起诉状"

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

        self.system_prompt = """你是一名专业的律师，正在帮助客户起草一份民事起诉状。

你需要通过与客户对话，收集以下关键信息：
1. 原告信息（如果是自然人：姓名、性别、出生日期、民族、住址；如果是法人：名称、法定代表人、住所地）
2. 被告信息（姓名或名称、联系方式等）
3. 诉讼请求（具体想要法院判决什么）
4. 事实与理由（案件的经过、起诉的原因）
5. 证据材料（有哪些证据支持诉求）

请一步步引导客户提供这些信息。每次只问1-2个关键问题。

如果客户表示需要'回去查找'或'稍后提供'某些信息超过2次，说明信息收集已达瓶颈。
如果客户重复说类似的话（如'我会尽快准备'），不要再重复询问，直接输出 "[READY_TO_DRAFT]"。

当满足以下任一条件时，必须输出 "[READY_TO_DRAFT]"：
- 已收集到基本的原告、被告、诉讼请求信息
- 客户明确表示需要时间准备材料
- 对话轮次接近上限（15轮以上）
- 客户回复开始重复

否则，简洁地提出下一个关键问题。"""

        # 初始化 LangChain Chains
        if self.llm.chat_model:
            # 指令生成 Chain
            self.instruction_prompt = ChatPromptTemplate.from_messages([
                ("system", self.system_prompt),
                MessagesPlaceholder(variable_name="history")
            ])
            self.instruction_chain = self.instruction_prompt | self.llm.chat_model | StrOutputParser()

            # 起诉状生成 Chain
            self.draft_prompt = ChatPromptTemplate.from_template("""根据以下的对话历史，请起草一份完整的{doc_name}。

格式要求：
1. 第一行必须是标题：{doc_name}（不要加空格，不要加案号）
2. 第二行开始直接写原告信息，格式：原告（自然人/法人）：XXX...
3. 然后是被告信息
4. 接着是诉讼请求、事实和理由、证据等内容
5. 不要在标题和正文之间添加案号或其他编号

对话历史：
{history_text}
""")
            self.draft_chain = self.draft_prompt | self.llm.chat_model | StrOutputParser()
        else:
            self.instruction_chain = None
            self.draft_chain = None

    def process_turn(self, dialog_history: List[Dict], case_id: str, input_json: Dict = None) -> str:
        """处理单轮对话 (API 模式)"""
        # 1. 转换历史格式
        dh = DialogHistory(self.scenario)
        dh.history = dialog_history
        history_text = ""
        for item in dialog_history:
            history_text += f"{item['role']}: {item['message']}\n"
            
        # 2. 检查是否应该结束
        if len(dialog_history) >= self.max_turns * 2:
            if self.draft_chain:
                try:
                    return self.draft_chain.invoke({
                        "doc_name": self.doc_name,
                        "history_text": history_text
                    })
                except Exception:
                    pass
            draft_messages = [{"role": "user", "content": f"根据以下对话历史，起草一份{self.doc_name}：\n\n{history_text}"}]
            return self.llm.chat_completion(draft_messages)

        # 3. 生成指令
        # instruction_chain 需要 LangChain 格式的消息列表
        lc_history = dh.get_langchain_messages()
        if self.instruction_chain:
            try:
                instruction = self.instruction_chain.invoke({"history": lc_history})
            except Exception:
                messages = [{"role": "system", "content": self.system_prompt}]
                for item in dialog_history:
                    role = "assistant" if item.get("role") == self.role else "user"
                    messages.append({"role": role, "content": item.get("message", "")})
                instruction = self.llm.chat_completion(messages)
        else:
            messages = [{"role": "system", "content": self.system_prompt}]
            for item in dialog_history:
                role = "assistant" if item.get("role") == self.role else "user"
                messages.append({"role": role, "content": item.get("message", "")})
            instruction = self.llm.chat_completion(messages)
        
        if "[READY_TO_DRAFT]" in instruction:
            if self.draft_chain:
                try:
                    return self.draft_chain.invoke({
                        "doc_name": self.doc_name,
                        "history_text": history_text
                    })
                except Exception:
                    pass
            draft_messages = [{"role": "user", "content": f"根据以下对话历史，起草一份{self.doc_name}：\n\n{history_text}"}]
            return self.llm.chat_completion(draft_messages)
            
        return instruction

    def run_case(
        self,
        case_id: str,
        **kwargs
    ) -> Tuple[DialogHistory, Dict[str, Any]]:
        """
        运行 CD 场景案例
        
        Args:
            case_id: 案例 ID
        
        Returns:
            (对话历史, 结果字典)
        """
        dialog_history = DialogHistory(self.scenario)

        # 初始问候
        initial_msg = "您好，我是您的代理律师。请问您想要起诉谁？具体是因为什么事情？"

        current_turn = 1
        instruction = initial_msg
        dialog_history.add_user_message(current_turn, instruction)

        metadata = {
            "turns": 0,
            "api_errors": [],
            "termination_reason": "",
        }

        client_responses = []
        lawyer_questions = []
        pending_count = 0

        while current_turn < self.max_turns:
            # 调用 API
            api_resp = self.api_client.simulate_cd(
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

            # 决策下一步
            if self.instruction_chain:
                # 使用 LangChain
                history_msgs = []
                for item in dialog_history.history:
                    if item["role"] == self.role:
                        history_msgs.append(AIMessage(content=item["message"]))
                    else:
                        history_msgs.append(HumanMessage(content=item["message"]))
                
                next_instruction = self.instruction_chain.invoke({"history": history_msgs}).strip()
            else:
                # 回退旧逻辑
                messages = [{"role": "system", "content": self.system_prompt}]
                for item in dialog_history.history:
                    role = "assistant" if item["role"] == self.role else "user"
                    messages.append({"role": role, "content": item["message"]})
                next_instruction = self.llm.chat_completion(messages).strip()

            # 记录客户回复
            client_responses.append(response_text)

            # 检测客户 pending 状态
            pending_keywords = [
                "要查",
                "不清楚",
                "不太清楚",
                "稍后",
                "准备",
                "整理",
                "尽快",
                "回去",
            ]
            if any(keyword in response_text for keyword in pending_keywords):
                pending_count += 1
                if pending_count >= 2:
                    if "[READY_TO_DRAFT]" not in next_instruction:
                        next_instruction = "[READY_TO_DRAFT]"
                        metadata["termination_reason"] = (
                            "Client needs time to prepare materials"
                        )

            # 检测客户回复重复
            if len(client_responses) >= 3:
                recent_three = [resp[:30] for resp in client_responses[-3:]]
                if len(set(recent_three)) <= 2 or all(
                    any(kw in r for kw in ["准备", "整理", "尽快"])
                    for r in recent_three
                ):
                    metadata["termination_reason"] = "Client responses repeating"
                    if "[READY_TO_DRAFT]" not in next_instruction:
                        next_instruction = "[READY_TO_DRAFT]"

            # 检测律师提问重复
            question_core = (
                next_instruction[:40]
                if len(next_instruction) > 40
                else next_instruction
            )
            if question_core in lawyer_questions:
                metadata["termination_reason"] = "Lawyer repeating same questions"
                if "[READY_TO_DRAFT]" not in next_instruction:
                    next_instruction = "[READY_TO_DRAFT]"
            else:
                lawyer_questions.append(question_core)

            # 提前触发终止
            if current_turn >= 10:
                if "[READY_TO_DRAFT]" not in next_instruction:
                    next_instruction = "[READY_TO_DRAFT]"
                    metadata["termination_reason"] = (
                        "Conversation too long (>=10 turns)"
                    )

            if "[READY_TO_DRAFT]" in next_instruction:
                if not metadata["termination_reason"]:
                    metadata["termination_reason"] = "Ready to draft"
                break

            current_turn += 1
            instruction = next_instruction
            dialog_history.add_user_message(current_turn, instruction)

        metadata["turns"] = current_turn
        if not metadata["termination_reason"]:
            metadata["termination_reason"] = "Max turns reached"

        # 生成起诉状
        draft_content = self._generate_complaint(dialog_history)

        return dialog_history, {
            "model_answer": draft_content,
            "metadata": metadata,
        }

    def _generate_complaint(self, dialog_history: DialogHistory) -> str:
        """生成起诉状"""
        history_text = ""
        for item in dialog_history.history:
            history_text += f"{item['role']}: {item['message']}\n"

        # 检索相关法条
        retrieved_laws_text = ""
        if self.law_retriever:
            try:
                # 使用对话历史的最后一部分作为查询，或者提取关键事实
                # 简单起见，取最后 1000 字符
                query_text = history_text[-1000:]
                laws = self.law_retriever.search(query_text, top_k=3)
                if laws:
                    retrieved_laws_text = "\n【参考法条】：\n" + "\n".join(
                        f"- {l['content']}" for l in laws
                    )
            except Exception as e:
                self.log(f"Law retrieval failed: {e}")

        if self.draft_chain:
            return self.draft_chain.invoke({
                "doc_name": self.doc_name,
                "history_text": history_text + retrieved_laws_text
            })
        else:
            draft_prompt = f"""根据以下的对话历史，请起草一份完整的{self.doc_name}。

格式要求：
1. 第一行必须是标题：{self.doc_name}（不要加空格，不要加案号）
2. 第二行开始直接写原告信息，格式：原告（自然人/法人）：XXX...
3. 然后是被告信息
4. 接着是诉讼请求、事实和理由、证据等内容
5. 不要在标题和正文之间添加案号或其他编号
6. 在“事实和理由”部分，请适当引用相关法律条款（参考下文提供的法条）。

对话历史：
{history_text}

{retrieved_laws_text}
"""
            draft_messages = [{"role": "user", "content": draft_prompt}]
            return self.llm.chat_completion(draft_messages)
