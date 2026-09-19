"""Prompt registry — purpose → prompt-version identity (Task 5.4 / Req 9.7, 9.9).

Every LLM call carries a prompt-version identity so cache reuse requires
matching purpose + model + configuration + prompt version + input digest,
and call records expose the version without storing raw prompt text.
"""
from __future__ import annotations

import threading
from typing import Dict, Optional

_lock = threading.Lock()

# 已知 purpose 的注册版本。模板内容变更时必须 bump 版本串。
_PROMPT_VERSIONS: Dict[str, str] = {
    "clerk": "clerk-analysis-v2",
    "extract": "extract-v1",
    "score": "score-v1",
    "judgment": "judgment-v1",
    "chat": "chat-v1",
    "json": "json-v1",
}


def register_prompt(purpose: str, version: str) -> None:
    """注册/更新某 purpose 的 prompt 版本身份。"""
    with _lock:
        _PROMPT_VERSIONS[purpose] = version


def prompt_version(purpose: str) -> str:
    """返回 prompt-version identity；未注册 purpose 给稳定占位，不伪造。"""
    with _lock:
        return _PROMPT_VERSIONS.get(purpose, f"unversioned:{purpose}")


def snapshot() -> Dict[str, str]:
    with _lock:
        return dict(_PROMPT_VERSIONS)
