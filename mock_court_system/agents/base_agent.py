"""
基础智能体抽象类
所有场景的智能体都继承自此类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, List
from core import CourtSimulatorClient, LLMClient
from utils import DialogHistory, ResultGenerator


class BaseAgent(ABC):
    """基础智能体抽象类"""

    def __init__(
        self,
        api_client: CourtSimulatorClient,
        llm: LLMClient,
        scenario: str,
        max_turns: int = 20,
        verbose: bool = False,
    ):
        """
        初始化智能体
        
        Args:
            api_client: API 客户端
            llm: LLM 客户端
            scenario: 场景标识 (CD/DD/CI)
            max_turns: 最大轮次
            verbose: 是否打印详细日志
        """
        self.api_client = api_client
        self.llm = llm
        self.scenario = scenario
        self.max_turns = max_turns
        self.verbose = verbose

    @abstractmethod
    def run_case(self, case_id: str, **kwargs) -> Tuple[DialogHistory, Dict[str, Any]]:
        """
        运行单个案例
        
        Args:
            case_id: 案例 ID
            **kwargs: 其他参数
        
        Returns:
            (对话历史, 结果字典)
        """
        pass

    def process_turn(self, dialog_history: List[Dict], case_id: str, input_json: Dict = None) -> str:
        """
        处理单轮对话 (API 模式)
        
        Args:
            dialog_history: 对话历史列表 [{"role": "...", "message": "..."}]
            case_id: 案例 ID
            input_json: 案例输入信息 (可选)
            
        Returns:
            生成的回复内容
        """
        raise NotImplementedError("该智能体尚未实现 process_turn 方法")

    def log(self, message: str):
        """打印日志"""
        if self.verbose:
            print(message, flush=True)




