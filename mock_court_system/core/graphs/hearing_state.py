"""HearingSubgraph 状态定义。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class HearingState(TypedDict, total=False):
    session_id: str
    case_info: Dict[str, Any]
    messages: List[Dict[str, Any]]
    sm: Dict[str, Any]
    extracted: Dict[str, Any]
    evidences: List[Dict[str, Any]]
    summary: str
    mode: str  # "live" | "auto"
    strategy: Dict[str, Any]
    last_analysis: Optional[Dict[str, Any]]
    finished: bool
    last_party_role: str
    last_party_content: str
    last_judge_text: str
    case_id: str
    input_json: Dict[str, Any]


def empty_hearing_state(session_id: str, mode: str = "live") -> HearingState:
    return HearingState(
        session_id=session_id,
        case_info={},
        messages=[],
        sm={},
        extracted={"plaintiff_claim": {}, "defendant_defense": {}, "summary": ""},
        evidences=[],
        summary="",
        mode=mode,
        strategy={"plaintiff": None, "defendant": None},
        last_analysis=None,
        finished=False,
        last_party_role="",
        last_party_content="",
        last_judge_text="",
        case_id="",
        input_json={},
    )
