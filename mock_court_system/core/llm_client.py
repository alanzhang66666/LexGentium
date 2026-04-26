"""
LLM 客户端封装
支持多种 LLM 后端（DeepSeek、OpenAI 等）
基于 LangChain 的统一接口
"""
from typing import List, Dict, Any, Optional
import re
import json
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

def is_retryable_error(e):
    """判断是否需要重试的异常"""
    if isinstance(e, requests.exceptions.HTTPError):
        # 5xx 错误通常是服务端的临时问题，可以重试
        return e.response.status_code in [500, 502, 503, 504]
    # 连接错误、超时等网络问题也可以重试
    if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ChunkedEncodingError)):
        return True
    return False


class LLMClient:
    """LLM 客户端封装"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        timeout: int = 60,
        provider: str = "deepseek",
    ):
        self.api_key = api_key
        self.model = model or "deepseek-chat"
        self.base_url = base_url or "https://api.deepseek.com/v1"
        
        # 确保 base_url 包含协议头
        if self.base_url:
            self.base_url = self.base_url.strip()
            if not self.base_url.startswith("http://") and not self.base_url.startswith("https://"):
                self.base_url = f"https://{self.base_url}"
            
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.provider = provider
        self.mock_mode = False
        self._mock_map = {}

        # 初始化 LangChain ChatModel
        self.chat_model: Optional[BaseChatModel] = None
        if api_key and base_url:
            # 确保 base_url 包含协议头
            base_url = base_url.strip()
            if not base_url.startswith("http://") and not base_url.startswith("https://"):
                base_url = f"https://{base_url}"
            
            try:
                self.chat_model = ChatOpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    max_retries=5,
                )
            except Exception as e:
                print(f"[WARN] 初始化 LangChain ChatModel 失败: {e}")

    @classmethod
    def from_config(cls, config: Optional[Dict]) -> "LLMClient":
        """从配置字典创建客户端"""
        if not config:
            return cls()
        return cls(
            api_key=config.get("api_key"),
            model=config.get("model"),
            base_url=config.get("base_url"),
            temperature=config.get("temperature", 0.1),
            max_tokens=config.get("max_tokens", 4096),
            timeout=config.get("timeout", 60),
            provider=config.get("provider", "deepseek"),
        )

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        聊天补全（返回文本）
        
        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            **kwargs: 其他参数
        
        Returns:
            生成的文本
        """
        if self.chat_model:
            # 使用 LangChain
            return self._chat_with_langchain(messages, temperature)
        else:
            # 回退到直接 API 调用
            return self._chat_with_api(messages, temperature)

    def enable_mock(self, mock_map: dict = None):
        """Enable lightweight mock responses for offline testing."""
        self.mock_mode = True
        self._mock_map = mock_map or {}

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        聊天补全（返回 JSON）
        
        包含自动降级机制：如果 JSON 模式失败，回退到普通模式并解析
        """
        # Mock mode: return simple heuristic JSON based on prompt keywords
        if self.mock_mode:
            content = messages[-1].get("content", "") if messages else ""
            lc = content.lower()
            # Opening stage identity / rights
            if "开庭准备" in content or "开庭" in content and "发言人" in content:
                return {
                    "identity_confirmed": True,
                    "rights_acknowledged": True,
                    "recusal_response": False,
                    "absence_acknowledged": True,
                }
            if "法庭调查" in content or "原告陈述" in content or "陈述诉讼请求" in content:
                return {
                    "stated_or_responded": True,
                    "no_more_evidence": False,
                    "fact_supplement_response": False,
                    "cross_exam_intent": "none",
                    "key_point": "",
                    "burden_holder": None,
                }
            if "法庭辩论" in content or "辩论" in content:
                return {
                    "debated": True,
                    "final_statement": False,
                    "debate_intent": "none",
                    "key_point": "",
                    "burden_holder": None,
                }
            if "法庭调解" in content or "调解" in content:
                return {"mediation_response": "refuse"}
            # Extraction prompts
            if "提取诉讼请求" in content or "原告陈述：" in content:
                return {"claim_type": "一般民事", "claim_amount": None, "main_request": "支持原告诉求", "facts": []}
            if "被告答辩" in content:
                return {"admit": [], "deny": [], "defense_reason": "被告不同意", "counterclaim": None}
            # Name extraction fallback
            if "提取关键案件信息" in content or "判断发言中是否明确提及" in content:
                return {"plaintiff_name": None, "defendant_name": None}
            # Default mock: return empty dict
            return {}
        if not self.api_key:
            return {}

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "response_format": {"type": "json_object"},
            **kwargs,
        }

        try:
            return self._send_json_request(url, headers, payload)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                print("[WARN] JSON 模式请求失败，尝试普通模式...")
                if "response_format" in payload:
                    del payload["response_format"]
                try:
                    return self._send_json_request(url, headers, payload)
                except Exception as retry_e:
                    print(f"[ERROR] 重试也失败: {retry_e}")
                    return {}
            else:
                print(f"[ERROR] HTTP 错误: {e.response.status_code}, {e.response.text}")
                return {}
        except Exception as e:
            print(f"[ERROR] 未知错误: {e}")
            return {}

    @retry(
        retry=retry_if_exception(is_retryable_error),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _post_request(self, url, headers, payload):
        """带重试机制的 POST 请求"""
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response

    def _chat_with_langchain(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None
    ) -> str:
        """使用 LangChain 进行对话"""
        try:
            # 转换消息格式
            lc_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))

            # 调用模型
            if temperature is not None:
                self.chat_model.temperature = temperature
            response = self.chat_model.invoke(lc_messages)
            return response.content
        except Exception as e:
            print(f"[WARN] LangChain 调用失败: {e}，回退到 API 调用")
            return self._chat_with_api(messages, temperature)

    def _chat_with_api(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None
    ) -> str:
        """直接使用 API 进行对话"""
        if not self.api_key:
            # 离线兜底：生成“可收敛”的短模板，避免全流程在无密钥场景下卡在对话循环。
            # 注意：这里只是用于本地演示/录屏/无网环境，不影响有密钥的正常调用。
            last = messages[-1].get("content", "") if messages else ""
            content = (last or "").strip()
            lc = content.lower()

            # 以关键词粗略判断要产出的文书类型
            if ("起诉状" in content) or ("complaint" in lc):
                return (
                    "民事起诉状\n"
                    "原告：{plaintiff}\n"
                    "被告：{defendant}\n"
                    "【诉讼请求】\n"
                    "1. 判令被告承担相应民事责任。\n"
                    "2. 诉讼费用由被告承担。\n"
                    "【事实与理由】\n"
                    "（离线演示模板：根据案件摘要与证据材料生成。）\n"
                )
            if ("答辩状" in content) or ("defense" in lc) or ("答辩" in content):
                return (
                    "民事答辩状\n"
                    "答辩人（被告）：{defendant}\n"
                    "被答辩人（原告）：{plaintiff}\n"
                    "【答辩意见】\n"
                    "1. 对原告部分主张不予认可。\n"
                    "2. 请求依法驳回或部分驳回原告诉请。\n"
                    "【事实与理由】\n"
                    "（离线演示模板：围绕争点进行抗辩与证据回应。）\n"
                )
            if ("判决书" in content) or ("裁判" in content) or ("judgment" in lc) or ("判决结果" in content):
                return (
                    "案号：（2026）模拟字第0001号\n"
                    "【判决结果】\n"
                    "一、支持原告部分诉讼请求；\n"
                    "二、驳回原告其余诉讼请求。\n"
                    "【裁判理由】\n"
                    "（离线演示模板：根据争点、证据与法律适用形成裁判要旨。）\n"
                )

            # 默认：给一个短回复，避免过长输出
            return "[离线模式回复] 已收到指令，继续下一步。"

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": self.max_tokens,
        }

        try:
            response = self._post_request(url, headers, payload)
            data = response.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return content if content else f"[LLM 返回为空]"
        except Exception as e:
            return f"[LLM 请求失败: {e}]"

    def _send_json_request(
        self,
        url: str,
        headers: Dict,
        payload: Dict
    ) -> Dict[str, Any]:
        """发送 JSON 请求并解析响应"""
        response = self._post_request(url, headers, payload)

        data = response.json()
        raw_content = data["choices"][0]["message"]["content"]

        # 清洗并解析 JSON
        cleaned = self._clean_json_string(raw_content)
        try:
            return json.loads(cleaned, strict=False)
        except json.JSONDecodeError:
            # 尝试修复常见的控制字符问题
            cleaned = cleaned.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            return json.loads(cleaned, strict=False)

    @staticmethod
    def _clean_json_string(text: str) -> str:
        """清洗 Markdown 标记，提取纯 JSON"""
        text = text.strip()
        # 尝试匹配 ```json { ... } ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1)

        # 尝试匹配最外层的 { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start : end + 1]

        return text

    def call(self, prompt: str, temperature: float = 0.3) -> str:
        """简单调用接口（兼容旧代码）"""
        messages = [{"role": "user", "content": prompt}]
        return self.chat_completion(messages, temperature)
