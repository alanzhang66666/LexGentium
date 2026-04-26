"""
模拟法庭 API 客户端
与 CAIL2025 智能体法庭模拟 API 交互
"""
import requests
import json
from typing import List, Dict, Optional
from urllib.parse import urlparse
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from .api_reconstructor import APIReconstructor
from .llm_api_simulator import LLMAPISimulator, HybridAPISimulator

def is_retryable_error(e):
    """判断是否需要重试的异常"""
    if isinstance(e, requests.exceptions.HTTPError):
        return e.response.status_code in [500, 502, 503, 504]
    if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ChunkedEncodingError)):
        return True
    return False


class CourtSimulatorClient:
    """模拟法庭 API 客户端"""

    def __init__(
        self,
        base_url: str = "http://47.116.195.100:43385",
        api_key: str = "",
        scenario_prefix: str = "",
        timeout: int = 120,
        use_reconstructor: bool = False,
        reconstructor_data_dir: str = "./api_history",
        use_llm_simulator: bool = False,
        llm_simulator: Optional[LLMAPISimulator] = None,
        use_hybrid: bool = False,
        hybrid_threshold: float = 0.7,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.scenario_prefix = scenario_prefix or ""
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json"}
        self.mock_mode = False
        self._mock_responses = {}
        
        # API重建器（基于历史数据的最近邻匹配）
        self.use_reconstructor = use_reconstructor
        self.reconstructor: Optional[APIReconstructor] = None
        if use_reconstructor:
            try:
                self.reconstructor = APIReconstructor(data_dir=reconstructor_data_dir)
                print(f"API重建器已加载，包含 {len(self.reconstructor.interactions)} 条历史记录")
            except Exception as e:
                print(f"警告: 加载API重建器失败: {e}")
                self.reconstructor = None
        
        # LLM API模拟器
        self.use_llm_simulator = use_llm_simulator
        self.llm_simulator: Optional[LLMAPISimulator] = llm_simulator
        
        # 混合模拟器
        self.use_hybrid = use_hybrid
        self.hybrid_simulator: Optional[HybridAPISimulator] = None
        if use_hybrid and self.reconstructor and self.llm_simulator:
            try:
                self.hybrid_simulator = HybridAPISimulator(
                    reconstructor=self.reconstructor,
                    llm_simulator=self.llm_simulator,
                    similarity_threshold=hybrid_threshold,
                )
                print(f"混合API模拟器已启用，相似度阈值: {hybrid_threshold}")
            except Exception as e:
                print(f"警告: 初始化混合模拟器失败: {e}")
                self.hybrid_simulator = None

    def health_check(self) -> Dict:
        """健康检查"""
        url = f"{self.base_url}/health"
        try:
            proxies = {"http": None, "https": None}
            response = requests.get(
                url,
                headers=self.headers,
                proxies=proxies,
                timeout=10,
            )
            response.raise_for_status()
            return json.loads(response.text)
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "status": "Unhealthy"}

    def _is_local_backend(self) -> bool:
        """判断是否为本地后端（用于切换本地统一接口调用格式）"""
        try:
            host = (urlparse(self.base_url).hostname or "").lower()
            return host in {"127.0.0.1", "localhost", "0.0.0.0"}
        except Exception:
            return False

    @staticmethod
    def _normalize_response_payload(result: Dict) -> Dict:
        """统一远端/本地接口响应为 {'response': str, ...}"""
        if not isinstance(result, dict):
            return {"error": "Invalid response type", "raw_response": str(result)}

        if isinstance(result.get("response"), str):
            return result

        resp = result.get("response")
        if isinstance(resp, dict):
            msg = resp.get("message") or resp.get("content") or ""
            normalized = {"response": msg}
            if "role" in resp:
                normalized["role"] = resp["role"]
            normalized["_raw_response"] = result
            return normalized

        if isinstance(result.get("message"), str):
            return {"response": result.get("message", ""), "_raw_response": result}

        return result

    def enable_mock(self, mock_responses: dict = None):
        """Enable local mock responses for offline testing."""
        self.mock_mode = True
        self._mock_responses = mock_responses or {}

    @retry(
        retry=retry_if_exception(is_retryable_error),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def simulate(
        self,
        scenario: str,
        case_id: str,
        dialog_history: List[Dict],
        api_key: Optional[str] = None,
    ) -> Dict:
        """
        模拟交互
        
        Args:
            scenario: 对话场景标识 (CD/DD/CI)
            case_id: 案例编号
            dialog_history: 对话历史
            api_key: API密钥
        
        Returns:
            API响应字典
        """
        # 检查轮数上限
        max_turns_map = {"CD": 20, "DD": 20, "CI": 50}
        max_turns = max_turns_map.get(scenario, 20)

        if dialog_history:
            max_turn_in_history = max(
                item.get("turn", 0) for item in dialog_history
            )
            if max_turn_in_history >= max_turns:
                return {
                    "Status": 404,
                    "Detail": "Exceed max turn limit.",
                }

        # If mock_mode enabled, return synthesized response
        if self.mock_mode:
            # Simple mock behavior: return next speaker's canned reply or echo
            last_turn = dialog_history[-1] if dialog_history else {"role": "Judge", "message": "现在开庭。"}
            role = last_turn.get("role", "Judge")
            # Provide deterministic small responses for CI flow
            mock_resp = self._mock_responses.get(role, None)
            if mock_resp is None:
                # Default echo-like behavior
                return {"response": f"[模拟环境回复] 收到 {role} 的指令: {last_turn.get('message', '')}"}
            return {"response": mock_resp}

        # 如果启用了混合模拟器，优先使用
        if self.use_hybrid and self.hybrid_simulator:
            try:
                result = self.hybrid_simulator.generate_response(
                    scenario=scenario,
                    case_id=case_id,
                    dialog_history=dialog_history,
                )
                return result
            except Exception as e:
                print(f"混合模拟器生成失败: {e}")
        
        # 如果启用了LLM模拟器，使用LLM生成
        if self.use_llm_simulator and self.llm_simulator:
            try:
                result = self.llm_simulator.generate_response(
                    scenario=scenario,
                    case_id=case_id,
                    dialog_history=dialog_history,
                )
                result["_llm_generated"] = True
                return result
            except Exception as e:
                print(f"LLM模拟器生成失败: {e}")
        
        # 如果启用了重建器且API不可用，尝试使用历史数据匹配
        if self.use_reconstructor and self.reconstructor:
            # 先尝试使用重建器
            reconstructed = self.reconstructor.predict(
                scenario=scenario,
                case_id=case_id,
                dialog_history=dialog_history,
            )
            if reconstructed:
                # 标记这是重建的结果
                reconstructed["_reconstructed"] = True
                return reconstructed

        use_local_api = self._is_local_backend()
        url = f"{self.base_url}/" if use_local_api else f"{self.base_url}/Simulate"
        key = api_key or self.api_key

        if (not key) and (not use_local_api):
            # 如果没有API key，尝试使用替代方案
            # 优先级：混合 > LLM > 最近邻
            if self.use_hybrid and self.hybrid_simulator:
                try:
                    return self.hybrid_simulator.generate_response(
                        scenario=scenario,
                        case_id=case_id,
                        dialog_history=dialog_history,
                    )
                except Exception as e:
                    print(f"混合模拟器生成失败: {e}")
            
            if self.use_llm_simulator and self.llm_simulator:
                try:
                    result = self.llm_simulator.generate_response(
                        scenario=scenario,
                        case_id=case_id,
                        dialog_history=dialog_history,
                    )
                    result["_llm_generated"] = True
                    return result
                except Exception as e:
                    print(f"LLM模拟器生成失败: {e}")
            
            if self.use_reconstructor and self.reconstructor:
                reconstructed = self.reconstructor.predict(
                    scenario=scenario,
                    case_id=case_id,
                    dialog_history=dialog_history,
                )
                if reconstructed:
                    reconstructed["_reconstructed"] = True
                    return reconstructed
            raise ValueError("API key is required and no alternative simulator available")

        if use_local_api:
            payload = {
                "scenario": scenario,
                "case_id": case_id,
                "dialog_history": dialog_history,
            }
        else:
            payload = {
                "scenario": self._format_scenario(scenario),
                "key": key,
                "case_id": case_id,
                "dialog_history": dialog_history,
            }
        
        # Debug: Print payload
        # print(f"\n[API Request] URL: {url}")
        # print(f"[API Request] Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}\n")

        try:
            proxies = {"http": None, "https": None}
            response = requests.post(
                url,
                json=payload,
                headers=self.headers,
                proxies=proxies,
                timeout=(5, self.timeout),
            )
            response.raise_for_status()

            if not response.text or response.text.strip() == "":
                return {
                    "error": "Empty response from server",
                    "status_code": response.status_code,
                }

            try:
                result = json.loads(response.text)
                if result is None:
                    return {
                        "error": "API returned null response",
                        "status_code": response.status_code,
                        "raw_text": response.text,
                    }
                return self._normalize_response_payload(result)
            except json.JSONDecodeError as e:
                return {
                    "error": f"Invalid JSON response: {str(e)}",
                    "raw_response": response.text[:200],
                    "status_code": response.status_code,
                }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [500, 502, 503, 504]:
                raise e
            try:
                if response.text:
                    error_response = json.loads(response.text)
                    return error_response
                else:
                    return {
                        "error": str(e),
                        "status_code": response.status_code,
                        "detail": "Empty error response",
                    }
            except:
                return {
                    "error": str(e),
                    "status_code": response.status_code,
                    "raw_response": response.text[:200] if response.text else None,
                }
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ChunkedEncodingError) as e:
            # 网络错误：尝试使用重建器
            if self.use_reconstructor and self.reconstructor:
                reconstructed = self.reconstructor.predict(
                    scenario=scenario,
                    case_id=case_id,
                    dialog_history=dialog_history,
                )
                if reconstructed:
                    reconstructed["_reconstructed"] = True
                    reconstructed["_fallback_reason"] = str(e)
                    return reconstructed
            raise e
        except requests.exceptions.RequestException as e:
            # 其他请求错误：尝试使用重建器
            if self.use_reconstructor and self.reconstructor:
                reconstructed = self.reconstructor.predict(
                    scenario=scenario,
                    case_id=case_id,
                    dialog_history=dialog_history,
                )
                if reconstructed:
                    reconstructed["_reconstructed"] = True
                    reconstructed["_fallback_reason"] = str(e)
                    return reconstructed
            return {"error": str(e)}

    def _format_scenario(self, scenario: str) -> str:
        """格式化场景前缀"""
        if self.scenario_prefix and not scenario.startswith(self.scenario_prefix):
            return f"{self.scenario_prefix}{scenario}"
        return scenario

    def simulate_cd(
        self,
        case_id: str,
        dialog_history: List[Dict],
        api_key: Optional[str] = None,
    ) -> Dict:
        """起诉状生成场景"""
        if not dialog_history or dialog_history[0].get("turn") != 0:
            dialog_history.insert(
                0,
                {
                    "turn": 0,
                    "role": "Client",
                    "message": "您好，我想要起草起诉状。",
                },
            )
        return self.simulate("CD", case_id, dialog_history, api_key)

    def simulate_dd(
        self,
        case_id: str,
        dialog_history: List[Dict],
        api_key: Optional[str] = None,
    ) -> Dict:
        """答辩状生成场景"""
        if not dialog_history or dialog_history[0].get("turn") != 0:
            dialog_history.insert(
                0,
                {
                    "turn": 0,
                    "role": "Client",
                    "message": "您好,我想要起草答辩状。",
                },
            )
        return self.simulate("DD", case_id, dialog_history, api_key)

    def simulate_ci(
        self,
        case_id: str,
        dialog_history: List[Dict],
        api_key: Optional[str] = None,
    ) -> Dict:
        """民事法庭判决场景"""
        if not dialog_history or dialog_history[0].get("turn") != 0:
            dialog_history.insert(
                0,
                {
                    "turn": 0,
                    "role": "Judge",
                    "message": "现在开庭。",
                },
            )
        return self.simulate("CI", case_id, dialog_history, api_key)
