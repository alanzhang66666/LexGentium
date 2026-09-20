from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Optional

from agents import CDAgent, CIAgent, DDAgent, SimAgent
from core.api_client import CourtSimulatorClient
from core.case_orchestrator import FullCaseOrchestrator
from core.game_engine import GameEngine
from core.llm_client import LLMClient
from core.mediation_engine import MediationEngine


class MockApiClient(CourtSimulatorClient):
    def __init__(self):
        pass


@dataclass
class RuntimeContext:
    api_client: CourtSimulatorClient
    llm_client: LLMClient
    cd_agent: CDAgent
    dd_agent: DDAgent
    ci_agent: CIAgent
    sim_agent: SimAgent
    orchestrator: FullCaseOrchestrator
    game_engine: GameEngine
    mediation_engine: MediationEngine


def create_llm_client(settings: Any) -> LLMClient:
    return LLMClient(
        api_key=settings.llm.api_key,
        base_url=settings.llm.base_url,
        model=settings.llm.model,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        timeout=settings.llm.timeout,
        provider=settings.llm.provider,
        fast_model=getattr(settings.llm, "fast_model", None) or None,
        fast_max_tokens=getattr(settings.llm, "fast_max_tokens", 512) or 512,
        thinking=getattr(settings.llm, "thinking", "enabled") or "enabled",
        reasoning_effort=getattr(settings.llm, "reasoning_effort", "high") or "high",
        fast_thinking=getattr(settings.llm, "fast_thinking", "disabled") or "disabled",
        fast_reasoning_effort=getattr(settings.llm, "fast_reasoning_effort", "low") or "low",
        demo_mode=bool(getattr(settings.llm, "demo_mode", False)),
    )


def create_runtime(settings: Any) -> RuntimeContext:
    api_client = MockApiClient()
    llm_client = create_llm_client(settings)
    # E2E/故障注入夹具：托管 harness 可用确定性 mock provider，不触外部 LLM。
    if os.environ.get("E2E_LLM_MOCK", "") == "1":
        llm_client.enable_mock()
    cd_agent = CDAgent(api_client, llm_client)
    dd_agent = DDAgent(api_client, llm_client)
    ci_agent = CIAgent(api_client, llm_client)
    sim_agent = SimAgent(llm_client)
    return build_runtime_context(
        api_client=api_client,
        llm_client=llm_client,
        cd_agent=cd_agent,
        dd_agent=dd_agent,
        ci_agent=ci_agent,
        sim_agent=sim_agent,
    )


def build_runtime_context(
    *,
    api_client: CourtSimulatorClient,
    llm_client: LLMClient,
    cd_agent: CDAgent,
    dd_agent: DDAgent,
    ci_agent: CIAgent,
    sim_agent: SimAgent,
) -> RuntimeContext:
    orchestrator = FullCaseOrchestrator(
        llm_client=llm_client,
        cd_agent=cd_agent,
        dd_agent=dd_agent,
        ci_agent=ci_agent,
        sim_agent=sim_agent,
    )
    game_engine = GameEngine(orchestrator, llm_client)
    mediation_engine = MediationEngine(llm_client, sim_agent)
    return RuntimeContext(
        api_client=api_client,
        llm_client=llm_client,
        cd_agent=cd_agent,
        dd_agent=dd_agent,
        ci_agent=ci_agent,
        sim_agent=sim_agent,
        orchestrator=orchestrator,
        game_engine=game_engine,
        mediation_engine=mediation_engine,
    )


def rebind_runtime_llm(
    runtime: RuntimeContext,
    new_llm: LLMClient,
    *,
    logger: Optional[Any] = None,
) -> RuntimeContext:
    runtime.llm_client = new_llm

    for agent in (runtime.cd_agent, runtime.dd_agent, runtime.ci_agent):
        agent.llm = new_llm
        if hasattr(agent, "_rebuild_chains"):
            agent._rebuild_chains()
            continue

        try:
            if not new_llm.chat_model:
                continue

            from core.langchain_utils import RobustJsonOutputParser
            from langchain_core.output_parsers import StrOutputParser

            if hasattr(agent, "instruction_prompt"):
                agent.instruction_chain = agent.instruction_prompt | new_llm.chat_model | StrOutputParser()
            if hasattr(agent, "draft_prompt"):
                agent.draft_chain = agent.draft_prompt | new_llm.chat_model | StrOutputParser()
            if hasattr(agent, "extraction_prompt"):
                agent.extraction_chain = agent.extraction_prompt | new_llm.chat_model | RobustJsonOutputParser()
            if hasattr(agent, "strategy_prompt"):
                agent.strategy_chain = agent.strategy_prompt | new_llm.chat_model | RobustJsonOutputParser()
            if hasattr(agent, "analysis_prompt"):
                agent.analysis_chain = agent.analysis_prompt | new_llm.chat_model | RobustJsonOutputParser()
            if hasattr(agent, "judgment_prompt"):
                agent.judgment_chain = agent.judgment_prompt | new_llm.chat_model | RobustJsonOutputParser()
            if hasattr(agent, "summary_prompt") and hasattr(agent, "extraction_prompt"):
                agent.summary_chain = agent.summary_prompt | new_llm.chat_model | StrOutputParser()
        except Exception as exc:
            if logger:
                logger.warning("Failed to rebuild agent chains: %s", exc)

    runtime.sim_agent.llm = new_llm
    if new_llm.chat_model:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

        if not hasattr(runtime.sim_agent, "_chain_prompt") or runtime.sim_agent._chain_prompt is None:
            runtime.sim_agent._chain_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", "{system_prompt}"),
                    MessagesPlaceholder(variable_name="history"),
                ]
            )
        runtime.sim_agent._chain = runtime.sim_agent._chain_prompt | new_llm.chat_model | StrOutputParser()
    else:
        runtime.sim_agent._chain = None

    runtime.orchestrator = FullCaseOrchestrator(
        llm_client=new_llm,
        cd_agent=runtime.cd_agent,
        dd_agent=runtime.dd_agent,
        ci_agent=runtime.ci_agent,
        sim_agent=runtime.sim_agent,
    )
    runtime.game_engine = GameEngine(runtime.orchestrator, new_llm)
    runtime.mediation_engine = MediationEngine(new_llm, runtime.sim_agent)
    try:
        from core.graphs.hearing_runtime import get_hearing_runtime
        get_hearing_runtime(ci_agent=runtime.ci_agent, llm=new_llm).bind(
            ci_agent=runtime.ci_agent, llm=new_llm
        )
    except Exception:
        pass
    try:
        from core.graphs.plead_runtime import get_plead_runtime
        get_plead_runtime(
            cd_agent=runtime.cd_agent, dd_agent=runtime.dd_agent, llm=new_llm,
        ).bind(cd_agent=runtime.cd_agent, dd_agent=runtime.dd_agent, llm=new_llm)
    except Exception:
        pass
    return runtime
