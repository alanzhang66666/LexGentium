"""回合内结构化书记员分析（合并原四类 LLM 抽取）。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class EvidenceHint(BaseModel):
    is_submission: bool = False
    evidence_content: str = ""
    purpose: str = ""


class ClaimHint(BaseModel):
    claim_type: Optional[str] = None
    claim_amount: Optional[float] = None
    main_request: Optional[str] = None
    facts: list = Field(default_factory=list)


class DefenseHint(BaseModel):
    admit: list = Field(default_factory=list)
    deny: list = Field(default_factory=list)
    defense_reason: Optional[str] = None
    counterclaim: Optional[Any] = None


class TurnAnalysis(BaseModel):
    identity_confirmed: bool = False
    rights_acknowledged: bool = False
    recusal_response: bool = False
    absence_acknowledged: bool = False
    stated_or_responded: bool = False
    no_more_evidence: bool = False
    fact_supplement_response: bool = False
    cross_exam_intent: str = "none"
    key_point: str = ""
    burden_holder: Optional[str] = None
    debated: bool = False
    final_statement: bool = False
    debate_intent: str = "none"
    mediation_response: str = "unknown"
    plaintiff_name: Optional[str] = None
    defendant_name: Optional[str] = None
    claim: Optional[Dict[str, Any]] = None
    defense: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None
    next_instruction: Optional[str] = None

    def to_phase_dict(self) -> Dict[str, Any]:
        return {
            "identity_confirmed": self.identity_confirmed,
            "rights_acknowledged": self.rights_acknowledged,
            "recusal_response": self.recusal_response,
            "absence_acknowledged": self.absence_acknowledged,
            "stated_or_responded": self.stated_or_responded,
            "no_more_evidence": self.no_more_evidence,
            "fact_supplement_response": self.fact_supplement_response,
            "cross_exam_intent": self.cross_exam_intent,
            "key_point": self.key_point,
            "burden_holder": self.burden_holder,
            "debated": self.debated,
            "final_statement": self.final_statement,
            "debate_intent": self.debate_intent,
            "mediation_response": self.mediation_response,
        }
