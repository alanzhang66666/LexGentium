"""
CI 推理状态的提取与序列化（core 层，供 api 与 orchestrator 共用）。

设计：ReasoningState 是 CIAgent 推理过程的完整可序列化快照，
用于跨轮/跨请求恢复，消除用启发式规则重放自然语言导致的状态漂移。
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict


def extract_ci_reasoning_state(ci_agent) -> Dict[str, Any]:
    """从 CIAgent 提取可序列化的推理状态快照。"""
    return {
        "state_machine": ci_agent.state_machine.to_dict(),
        "dialogue": [
            {"role": m.role.value, "content": m.content} for m in ci_agent.dialogue
        ],
        "evidences": [
            {**asdict(ev), "provider": ev.provider.value}
            for ev in getattr(ci_agent, "evidences", [])
        ],
        "extracted": ci_agent.extracted,
        "fact_ledger": (
            ci_agent.fact_ledger.to_dict()
            if getattr(ci_agent, "fact_ledger", None) else {"claims": [], "evidence": {}, "counter": 0}
        ),
        "judgment_json": ci_agent.judgment_json,
        "judgment_status": getattr(ci_agent, "judgment_status", "failed"),
        "name_confirmed_by_dialogue": dict(
            getattr(ci_agent, "name_confirmed_by_dialogue", {})
        ),
        "finished": bool(ci_agent.finished),
    }
