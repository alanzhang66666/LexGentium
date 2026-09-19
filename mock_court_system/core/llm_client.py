"""
LLM 客户端封装
支持多种 LLM 后端（DeepSeek、OpenAI 等）
基于 LangChain 的统一接口
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import hashlib
import os
import re
import json
import sqlite3
import threading
import time
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from typing import Iterator as _Iterator

CACHEABLE_PURPOSES = frozenset({"clerk", "extract", "score"})
DEGRADED_JSON_KEY = "_degraded"


def degraded_json(reason: str = "llm_unavailable") -> Dict[str, Any]:
    """Marker payload when JSON chat cannot produce a real model result."""
    return {DEGRADED_JSON_KEY: True, "reason": reason}


def is_degraded_json(result: Any) -> bool:
    if not isinstance(result, dict) or not result:
        return True
    return result.get(DEGRADED_JSON_KEY) is True


@dataclass
class LLMCallContext:
    """一次 LLM 调用的关联/身份上下文（Req 9.7–9.11）。

    记录全部非秘密关联身份；绝不包含 raw prompt 或 Secret。
    """

    purpose: str = "chat"
    tier: str = "fast"
    operation_id: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    configuration_identity: Optional[str] = None
    prompt_version: Optional[str] = None
    deadline: Optional[float] = None  # time.monotonic() 绝对截止时间


@dataclass
class LLMCallRecord:
    purpose: str
    model: str
    latency_ms: float
    tokens: Optional[int]
    tier: str
    cached: bool = False
    operation_id: Optional[str] = None
    request_id: Optional[str] = None
    configuration_identity: Optional[str] = None
    prompt_version: Optional[str] = None
    degraded: bool = False
    replayed: bool = False


class LLMDeadlineExceeded(RuntimeError):
    """响应到达时已越过绝对 deadline：不得再作为有效结果 commit。"""


def is_retryable_error(e):
    """判断是否需要重试的异常"""
    if isinstance(e, requests.exceptions.HTTPError):
        # 5xx 错误通常是服务端的临时问题，可以重试
        return e.response.status_code in [500, 502, 503, 504]
    # 连接错误、超时等网络问题也可以重试
    if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ChunkedEncodingError)):
        return True
    return False


class _HookableChatModel(BaseChatModel):
    """chat_model 透明代理：当前线程启用流式钩子时，invoke 内部转 stream 并逐 token 回调。

    存在动机：CD/DD 等 Agent 的 LangChain chain（prompt | chat_model | parser）
    直接持有 chat_model，会绕过 LLMClient.chat_completion 的钩子分支。
    该代理让 chain 与直接调用统一获得流式旁路，且以线程局部变量隔离并发请求。
    """
    inner: Any
    stream_local: Any

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        return "hookable-chat-proxy"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        hook = getattr(self.stream_local, "hook", None)
        if hook is None:
            return self.inner._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        chunks: List[str] = []
        for chunk in self.inner.stream(messages, stop=stop, run_manager=run_manager, **kwargs):
            piece = getattr(chunk, "content", "") or ""
            if not piece:
                continue
            chunks.append(piece)
            try:
                hook(piece)
            except Exception:
                pass
        if not chunks:
            return self.inner._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="".join(chunks)))])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        for chunk in self.inner.stream(messages, stop=stop, run_manager=run_manager, **kwargs):
            yield ChatGeneration(message=chunk)


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
        fast_model: Optional[str] = None,
        fast_max_tokens: int = 512,
        cache_path: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model = model or "deepseek-chat"
        self.fast_model = fast_model or self.model
        self.base_url = base_url or "https://api.deepseek.com/v1"
        
        # 确保 base_url 包含协议头
        if self.base_url:
            self.base_url = self.base_url.strip()
            if not self.base_url.startswith("http://") and not self.base_url.startswith("https://"):
                self.base_url = f"https://{self.base_url}"
            
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.fast_max_tokens = max(64, int(fast_max_tokens or 512))
        self.provider = provider
        self.mock_mode = False
        self._mock_map = {}
        self.mock_delay_s = 0.0
        # 线程局部流式钩子：请求级隔离（每个请求跑在独立线程），并发互不串流
        self._stream_local = threading.local()
        self._metrics: List[LLMCallRecord] = []
        self._metrics_lock = threading.Lock()
        # operation_id → committed 结果：同 Operation 重试直接回放，不再发起 provider 请求
        self._committed: Dict[str, Any] = {}
        self._committed_lock = threading.Lock()
        self._cache_enabled = os.getenv("LLM_CACHE", "1") != "0"
        self._cache_path = cache_path or os.path.join("data", "llm_cache.sqlite3")
        self._cache_lock = threading.Lock()
        if self._cache_enabled:
            self._init_cache()

        # 初始化 LangChain ChatModel
        self.chat_model: Optional[BaseChatModel] = None
        if api_key and base_url:
            # 确保 base_url 包含协议头
            base_url = base_url.strip()
            if not base_url.startswith("http://") and not base_url.startswith("https://"):
                base_url = f"https://{base_url}"
            
            try:
                _inner = ChatOpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                    # LangChain 层重试降为 2：外层 tenacity(5 次) 已兜底，
                    # 两层叠加时一次网络抖动最坏 25 连击（25×2-10s 退避）
                    max_retries=2,
                )
                self.chat_model = _HookableChatModel(inner=_inner, stream_local=self._stream_local)
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
            fast_model=config.get("fast_model") or None,
            fast_max_tokens=int(config.get("fast_max_tokens") or 512),
        )

    def _init_cache(self) -> None:
        path = self._cache_path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with self._cache_lock:
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS llm_cache (key TEXT PRIMARY KEY, value TEXT, created_at REAL)"
            )
            conn.commit()
            conn.close()

    def model_for_tier(self, tier: str) -> str:
        if tier == "fast":
            return self.fast_model or self.model
        return self.model

    def reset_metrics(self) -> None:
        with self._metrics_lock:
            self._metrics.clear()

    def get_metrics(self) -> List[LLMCallRecord]:
        with self._metrics_lock:
            return list(self._metrics)

    def metrics_summary(self) -> Dict[str, Any]:
        rows = self.get_metrics()
        if not rows:
            return {"calls": 0, "p50_ms": 0, "p95_ms": 0, "cached": 0}
        lat = sorted(r.latency_ms for r in rows)
        n = len(lat)
        return {
            "calls": n,
            "p50_ms": lat[n // 2],
            "p95_ms": lat[min(n - 1, int(n * 0.95))],
            "cached": sum(1 for r in rows if r.cached),
            "by_purpose": {p: sum(1 for r in rows if r.purpose == p) for p in {r.purpose for r in rows}},
        }

    def _record_call(
        self,
        purpose: str,
        tier: str,
        model: str,
        latency_ms: float,
        tokens=None,
        cached: bool = False,
        ctx: Optional[LLMCallContext] = None,
        degraded: bool = False,
        replayed: bool = False,
    ) -> None:
        rec = LLMCallRecord(
            purpose=purpose,
            model=model,
            latency_ms=latency_ms,
            tokens=tokens,
            tier=tier,
            cached=cached,
            operation_id=ctx.operation_id if ctx else None,
            request_id=ctx.request_id if ctx else None,
            configuration_identity=(
                ctx.configuration_identity if ctx and ctx.configuration_identity else self.configuration_identity
            ),
            prompt_version=(ctx.prompt_version if ctx and ctx.prompt_version else self._prompt_version(purpose)),
            degraded=degraded,
            replayed=replayed,
        )
        with self._metrics_lock:
            self._metrics.append(rec)

    def record_external_call(
        self,
        purpose: str,
        tier: str,
        latency_ms: float,
        ctx: Optional[LLMCallContext] = None,
        degraded: bool = False,
    ) -> None:
        """LangChain chain 等绕过 chat/chat_json 的调用手工记账。"""
        self._record_call(
            purpose,
            tier,
            self.model_for_tier(tier),
            latency_ms,
            ctx=ctx,
            degraded=degraded,
        )

    @staticmethod
    def _prompt_version(purpose: str) -> str:
        from core.prompt_registry import prompt_version

        return prompt_version(purpose)

    @property
    def configuration_identity(self) -> str:
        """LLM 配置身份 digest（模型/端点/预算），不含密钥。"""
        blob = json.dumps(
            {
                "model": self.model,
                "fast_model": self.fast_model,
                "base_url": self.base_url,
                "max_tokens": self.max_tokens,
                "fast_max_tokens": self.fast_max_tokens,
                "provider": self.provider,
            },
            sort_keys=True,
        )
        return "llmcfg_" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]

    def _past_deadline(self, ctx: Optional[LLMCallContext]) -> bool:
        return ctx is not None and ctx.deadline is not None and time.monotonic() > ctx.deadline

    def _committed_get(self, ctx: Optional[LLMCallContext]) -> Any:
        if ctx is None or not ctx.operation_id:
            return None, False
        with self._committed_lock:
            if ctx.operation_id in self._committed:
                return self._committed[ctx.operation_id], True
        return None, False

    def _committed_set(self, ctx: Optional[LLMCallContext], result: Any) -> None:
        if ctx is None or not ctx.operation_id:
            return
        with self._committed_lock:
            self._committed.setdefault(ctx.operation_id, result)

    def _cache_key(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        purpose: str = "",
        ctx: Optional[LLMCallContext] = None,
    ) -> str:
        """缓存身份：purpose/model/config/prompt-version/确定性输入 digest 全等才命中。"""
        payload: Dict[str, Any] = {
            "m": model,
            "msg": messages,
            "t": temperature,
            "p": purpose,
            "cfg": (ctx.configuration_identity if ctx and ctx.configuration_identity else self.configuration_identity),
            "pv": (ctx.prompt_version if ctx and ctx.prompt_version else self._prompt_version(purpose)),
        }
        try:
            from core.research.runtime import research_cache_namespace

            namespace = research_cache_namespace()
            if namespace:
                payload["research"] = namespace
        except Exception:
            pass
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> Optional[str]:
        if not self._cache_enabled:
            return None
        try:
            with self._cache_lock:
                conn = sqlite3.connect(self._cache_path)
                row = conn.execute("SELECT value FROM llm_cache WHERE key=?", (key,)).fetchone()
                conn.close()
            return row[0] if row else None
        except Exception:
            return None

    def _cache_set(self, key: str, value: str) -> None:
        if not self._cache_enabled:
            return
        try:
            with self._cache_lock:
                conn = sqlite3.connect(self._cache_path)
                conn.execute(
                    "INSERT OR REPLACE INTO llm_cache(key, value, created_at) VALUES (?,?,?)",
                    (key, value, time.time()),
                )
                conn.commit()
                conn.close()
        except Exception:
            pass

    def _maybe_cache(self, purpose: str, temperature: Optional[float]) -> bool:
        temp = self.temperature if temperature is None else temperature
        return purpose in CACHEABLE_PURPOSES and temp <= 0.1

    def max_tokens_for(self, purpose: str) -> int:
        """Clerk / extract / score stay short. Judgment and chat keep the full window."""
        if purpose in CACHEABLE_PURPOSES:
            return min(self.max_tokens, self.fast_max_tokens)
        return self.max_tokens

    def _chat_model_for(self, temperature: Optional[float] = None):
        """按调用绑定温度，不改写共享 chat_model。"""
        model = self.chat_model
        if model is None or temperature is None:
            return model
        inner = getattr(model, "inner", None)
        target = inner if inner is not None else model
        if not hasattr(target, "bind"):
            return model
        try:
            bound = target.bind(temperature=temperature)
            if inner is not None:
                return type(model)(inner=bound, stream_local=model.stream_local)
            return bound
        except Exception:
            return model

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        purpose: str = "chat",
        tier: str = "strong",
        context: Optional[LLMCallContext] = None,
        **kwargs
    ) -> str:
        """
        聊天补全（返回文本）
        
        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            context: 关联身份/deadline 上下文（不含 raw prompt）
            **kwargs: 其他参数
        
        Returns:
            生成的文本
        """
        model_name = self.model_for_tier(tier)
        t0 = time.perf_counter()
        committed, hit_committed = self._committed_get(context)
        if hit_committed:
            self._record_call(
                purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                ctx=context, replayed=True,
            )
            return committed
        cached = False
        if self._maybe_cache(purpose, temperature):
            hit = self._cache_get(
                self._cache_key(model_name, messages, temperature or self.temperature, purpose, context)
            )
            if hit is not None:
                cached = True
                text = hit
            else:
                text = None
        else:
            text = None
        if text is None:
            hook = getattr(self._stream_local, "hook", None)
            if hook is not None:
                text = self._chat_with_stream_hook(messages, temperature, hook)
            elif self.chat_model:
                text = self._chat_with_langchain(messages, temperature)
            else:
                text = self._chat_with_api(messages, temperature)
            if self._maybe_cache(purpose, temperature) and text:
                self._cache_set(
                    self._cache_key(model_name, messages, temperature or self.temperature, purpose, context),
                    text,
                )
        # 绝对 deadline：迟到响应不可 commit
        if self._past_deadline(context):
            self._record_call(
                purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                tokens=None, cached=cached, ctx=context, degraded=True,
            )
            raise LLMDeadlineExceeded("llm response arrived past absolute deadline")
        # 空白响应不伪成功：标 degraded
        degraded = not isinstance(text, str) or not text.strip()
        self._record_call(
            purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
            cached=cached, ctx=context, degraded=degraded,
        )
        if not degraded:
            self._committed_set(context, text)
        return text

    # ---------- 流式支持 ----------

    def set_stream_hook(self, hook) -> None:
        """在当前线程启用流式旁路：此后该线程的 chat_completion 会逐 token
        回调 hook(delta)，同时返回完整文本。仅影响调用线程。"""
        self._stream_local.hook = hook

    def clear_stream_hook(self) -> None:
        self._stream_local.hook = None

    def _chat_with_stream_hook(self, messages, temperature, hook) -> str:
        chunks: List[str] = []
        try:
            for delta in self.chat_completion_stream(messages, temperature):
                chunks.append(delta)
                try:
                    hook(delta)
                except Exception:
                    pass
        except Exception as e:
            text = "".join(chunks)
            if text:
                return text
            raise
        return "".join(chunks)

    def chat_completion_stream(self, messages: List[Dict[str, str]], temperature: Optional[float] = None):
        """流式生成：yield 增量文本片段。离线兜底时整段 yield 一次。"""
        if self.chat_model:
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
            model = self._chat_model_for(temperature)
            for chunk in model.stream(lc_messages):
                piece = getattr(chunk, "content", "") or ""
                if piece:
                    yield piece
            return

        # 直接 API 路径（requests SSE）
        if not self.api_key:
            yield self._offline_reply(messages)
            return
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=self.timeout)
        resp.raise_for_status()
        for raw_line in resp.iter_lines():
            # 显式 utf-8 解码：decode_unicode=True 在响应无 charset 时按 latin-1 解码，中文变乱码
            line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                piece = json.loads(data)["choices"][0]["delta"].get("content") or ""
            except Exception:
                continue
            if piece:
                yield piece

    def _offline_reply(self, messages) -> str:
        """离线兜底文本（与 _chat_with_api 的离线路径保持一致）。"""
        return self._chat_with_api(messages)

    def enable_mock(self, mock_map: dict = None):
        """Enable lightweight mock responses for offline testing."""
        self.mock_mode = True
        self._mock_map = mock_map or {}

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        purpose: str = "json",
        tier: str = "fast",
        context: Optional[LLMCallContext] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        聊天补全（返回 JSON）
        
        包含自动降级机制：如果 JSON 模式失败，回退到普通模式并解析
        """
        model_name = self.model_for_tier(tier)
        t0 = time.perf_counter()
        committed, hit_committed = self._committed_get(context)
        if hit_committed:
            self._record_call(
                purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                ctx=context, replayed=True,
            )
            return committed
        cached = False
        if self._maybe_cache(purpose, temperature):
            hit = self._cache_get(
                self._cache_key(model_name, messages, temperature or self.temperature, purpose, context)
            )
            if hit is not None:
                cached = True
                try:
                    parsed = json.loads(hit)
                    self._record_call(
                        purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                        cached=True, ctx=context, degraded=is_degraded_json(parsed),
                    )
                    return parsed
                except Exception:
                    cached = False
        if self.mock_delay_s:
            time.sleep(self.mock_delay_s)
        # Mock mode: return simple heuristic JSON based on prompt keywords
        if self.mock_mode:
            def _mock_done(obj: Dict[str, Any]) -> Dict[str, Any]:
                if self._past_deadline(context):
                    self._record_call(
                        purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                        cached=False, ctx=context, degraded=True,
                    )
                    return degraded_json("late_response")
                degraded = is_degraded_json(obj)
                if not degraded and self._maybe_cache(purpose, temperature):
                    self._cache_set(
                        self._cache_key(
                            model_name, messages, temperature or self.temperature,
                            purpose, context,
                        ),
                        json.dumps(obj, ensure_ascii=False),
                    )
                self._record_call(
                    purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                    cached=False, ctx=context, degraded=degraded,
                )
                if not degraded:
                    self._committed_set(context, obj)
                return obj

            content = messages[-1].get("content", "") if messages else ""
            lc = content.lower()
            if "书记员综合分析" in content or "TurnAnalysis" in content:
                return _mock_done({
                    "identity_confirmed": any(k in content for k in ["到庭", "确认", "是", "本人"]),
                    "rights_acknowledged": any(k in content for k in ["听清", "明白", "知晓"]),
                    "recusal_response": any(k in content for k in ["不申请", "回避", "没有"]),
                    "absence_acknowledged": any(k in content for k in ["听清", "明白", "缺席"]),
                    "stated_or_responded": len(content) > 20 and any(k in content for k in ["请求", "答辩", "事实"]),
                    "no_more_evidence": any(k in content for k in ["无新证据", "举证完毕", "没有证据"]),
                    "fact_supplement_response": "补充" in content,
                    "cross_exam_intent": "none",
                    "key_point": "",
                    "burden_holder": None,
                    "debated": "辩论" in content or "认为" in content,
                    "final_statement": any(k in content for k in ["陈述完毕", "没有补充"]),
                    "debate_intent": "none",
                    "mediation_response": "refuse" if any(k in content for k in ["拒绝", "不同意", "依法判决"]) else "unknown",
                    "plaintiff_name": None,
                    "defendant_name": None,
                    "claim": {"claim_type": "一般民事", "main_request": "支持原告诉求"} if "诉讼请求" in content else None,
                    "defense": {"defense_reason": "被告不同意"} if "答辩" in content else None,
                    "evidence": None,
                    "next_instruction": "对原告说：请继续配合法庭指令。",
                })
            # Opening stage identity / rights
            if "开庭准备" in content or "开庭" in content and "发言人" in content:
                return _mock_done({
                    "identity_confirmed": True,
                    "rights_acknowledged": True,
                    "recusal_response": False,
                    "absence_acknowledged": True,
                })
            if "法庭调查" in content or "原告陈述" in content or "陈述诉讼请求" in content:
                return _mock_done({
                    "stated_or_responded": True,
                    "no_more_evidence": False,
                    "fact_supplement_response": False,
                    "cross_exam_intent": "none",
                    "key_point": "",
                    "burden_holder": None,
                })
            if "法庭辩论" in content or "辩论" in content:
                return _mock_done({
                    "debated": True,
                    "final_statement": False,
                    "debate_intent": "none",
                    "key_point": "",
                    "burden_holder": None,
                })
            if "法庭调解" in content or "调解" in content:
                return _mock_done({"mediation_response": "refuse"})
            # Extraction prompts
            if "提取诉讼请求" in content or "原告陈述：" in content:
                return _mock_done({"claim_type": "一般民事", "claim_amount": None, "main_request": "支持原告诉求", "facts": []})
            if "被告答辩" in content:
                return _mock_done({"admit": [], "deny": [], "defense_reason": "被告不同意", "counterclaim": None})
            # Name extraction fallback
            if "提取关键案件信息" in content or "判断发言中是否明确提及" in content:
                return _mock_done({"plaintiff_name": None, "defendant_name": None})
            # Combined clerk analysis
            if "书记员综合分析" in content or "TurnAnalysis" in content:
                return _mock_done({
                    "identity_confirmed": True,
                    "rights_acknowledged": True,
                    "recusal_response": True,
                    "absence_acknowledged": True,
                    "stated_or_responded": True,
                    "no_more_evidence": False,
                    "fact_supplement_response": False,
                    "cross_exam_intent": "none",
                    "key_point": "",
                    "burden_holder": None,
                    "debated": True,
                    "final_statement": False,
                    "debate_intent": "none",
                    "mediation_response": "refuse",
                    "plaintiff_name": None,
                    "defendant_name": None,
                    "claim": None,
                    "defense": None,
                    "evidence": None,
                    "next_instruction": None,
                })
            # Default mock: no keyword match — caller must treat as degraded, not real scores
            self._record_call(
                purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                cached=False, ctx=context, degraded=True,
            )
            return degraded_json("mock_empty")
        if not self.api_key:
            self._record_call(
                purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                cached=False, ctx=context, degraded=True,
            )
            return degraded_json("missing_api_key")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if "max_tokens" not in kwargs:
            kwargs["max_tokens"] = self.max_tokens_for(purpose)
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "response_format": {"type": "json_object"},
            **kwargs,
        }

        try:
            parsed = self._send_json_request(url, headers, payload)
            # 绝对 deadline：迟到响应不 commit，按降级处理
            if self._past_deadline(context):
                self._record_call(
                    purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                    cached=cached, ctx=context, degraded=True,
                )
                return degraded_json("late_response")
            if self._maybe_cache(purpose, temperature):
                self._cache_set(
                    self._cache_key(model_name, messages, temperature or self.temperature, purpose, context),
                    json.dumps(parsed, ensure_ascii=False),
                )
            degraded = is_degraded_json(parsed)
            self._record_call(
                purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                cached=cached, ctx=context, degraded=degraded,
            )
            if not degraded:
                self._committed_set(context, parsed)
            return parsed
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                print("[WARN] JSON 模式请求失败，尝试普通模式...")
                if "response_format" in payload:
                    del payload["response_format"]
                try:
                    parsed = self._send_json_request(url, headers, payload)
                    self._record_call(
                        purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                        cached=False, ctx=context, degraded=is_degraded_json(parsed),
                    )
                    return parsed
                except Exception as retry_e:
                    print(f"[ERROR] 重试也失败: {retry_e}")
                    self._record_call(
                        purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                        cached=False, ctx=context, degraded=True,
                    )
                    return degraded_json("json_mode_retry_failed")
            else:
                print(f"[ERROR] HTTP 错误: {e.response.status_code}, {e.response.text}")
                self._record_call(
                    purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                    cached=False, ctx=context, degraded=True,
                )
                return degraded_json("http_error")
        except Exception as e:
            print(f"[ERROR] 未知错误: {e}")
            self._record_call(
                purpose, tier, model_name, (time.perf_counter() - t0) * 1000,
                cached=False, ctx=context, degraded=True,
            )
            return degraded_json("request_error")

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

            model = self._chat_model_for(temperature)
            response = model.invoke(lc_messages)
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
