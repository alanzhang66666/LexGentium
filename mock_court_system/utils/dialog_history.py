"""
对话历史管理
"""
from typing import List, Dict
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


class DialogHistory:
    """对话历史管理器"""

    def __init__(self, scenario: str = ""):
        self.scenario = scenario
        self.history: List[Dict] = []
        self.current_turn = 0

    def get_langchain_messages(self) -> List[any]:
        """获取 LangChain 格式的消息列表"""
        messages = []
        for item in self.history:
            role = item.get("role", "")
            content = item.get("message", "")
            
            # 根据场景映射角色
            if self.scenario in ["CD", "DD"]:
                # 律师场景：Lawyer 是 AI，Client 是 Human
                if role == "Lawyer":
                    messages.append(AIMessage(content=content))
                else:
                    messages.append(HumanMessage(content=content))
            elif self.scenario == "CI":
                # 法官场景：Judge 是 AI，其他是 Human
                if role in ["Judge", "法官", "审判长"]:
                    messages.append(AIMessage(content=content))
                else:
                    messages.append(HumanMessage(content=f"{role}: {content}"))
            else:
                # 默认
                messages.append(HumanMessage(content=f"{role}: {content}"))
        return messages

    def add_user_message(self, turn: int, message: str, role: str = None):
        """
        添加用户（智能体）消息
        
        Args:
            turn: 轮次
            message: 消息内容
            role: 角色（如不指定，根据场景自动判断）
        """
        if role is None:
            # 根据场景自动判断角色
            if self.scenario in ["CD", "DD"]:
                role = "Lawyer"
            elif self.scenario == "CI":
                role = "Judge"
            else:
                role = "User"

        self.history.append({"turn": turn, "role": role, "message": message})
        self.current_turn = turn

    def add_env_response(self, turn: int, role: str, message: str):
        """
        添加环境（API）响应
        
        Args:
            turn: 轮次
            role: 角色 (Client/Plaintiff/Defendant)
            message: 消息内容
        """
        self.history.append({"turn": turn, "role": role, "message": message})

    def get_api_format(self) -> List[Dict]:
        """获取 API 格式的对话历史"""
        return self.history.copy()

    def get_last_turn(self) -> int:
        """获取当前轮次"""
        return self.current_turn

    def get_next_turn(self) -> int:
        """获取下一轮次"""
        self.current_turn += 1
        return self.current_turn

    def to_text(self) -> str:
        """转换为文本格式"""
        lines = []
        for item in self.history:
            lines.append(f"{item['role']}: {item['message']}")
        return "\n".join(lines)

    def get_last_n_turns(self, n: int = 3) -> List[Dict]:
        """获取最近 N 轮对话"""
        return self.history[-n:] if len(self.history) >= n else self.history

    def clear(self):
        """清空历史"""
        self.history = []
        self.current_turn = 0
