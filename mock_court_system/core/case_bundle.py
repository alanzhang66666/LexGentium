"""
CanonicalCaseBundle：案件数据的规范化契约。

背景：实验数据集、编排器与 CIAgent 之间的字段名不一致（例如实验给
case_id/case_description/plaintiff_name，CIAgent 却读 id/claim_description/
plaintiff_info），导致案号、案由、诉请、当事人姓名和客观事实在进入判决
提示词前被静默丢弃。本模块在 API 边界一次性完成新旧字段兼容映射，
后续 Agent 一律从 bundle 读取，禁止直接访问原始字典键。

设计原则：
- 旧字段（id/case_type/claim_description/plaintiff_info/defendant_info）
  与新字段（case_id/cause/case_description/plaintiff_name/defendant_name/
  plaintiff_claims）双兼容；
- 缺失关键信息记入 warnings，而不是静默填空字符串；
- claims 统一为结构化列表（文本诉请拆分为单条）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CanonicalParty:
    name: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CanonicalClaim:
    claim_id: str
    text: str
    amount: Optional[str] = None


@dataclass
class CanonicalCaseBundle:
    """规范化后的案件信息（进入推理前的唯一可信来源）。"""

    case_id: str
    cause: str
    plaintiff: CanonicalParty
    defendant: CanonicalParty
    claims: List[CanonicalClaim] = field(default_factory=list)
    case_facts: str = ""          # 客观事实/案情描述（进入判决提示词的事实基础）
    third_party_findings: str = ""  # 第三方查明事实（若提供，优先级高于 case_facts）
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    @property
    def claims_text(self) -> str:
        """合并后的诉请文本（用于 CaseInfo.claim_description 与检索 query）。"""
        if not self.claims:
            return ""
        if len(self.claims) == 1:
            return self.claims[0].text
        return "\n".join(f"{i + 1}. {c.text}" for i, c in enumerate(self.claims))

    def validation_errors(self) -> List[str]:
        """阻断性缺失：这些字段缺失时不应继续生成判决。"""
        errors = []
        if not self.case_id:
            errors.append("missing case_id")
        if not self.claims:
            errors.append("missing plaintiff_claims/claim_description")
        if not (self.case_facts or self.third_party_findings):
            errors.append("missing case_description/third_party_findings")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "cause": self.cause,
            "plaintiff_name": self.plaintiff.name,
            "defendant_name": self.defendant.name,
            "claims": [{"claim_id": c.claim_id, "text": c.text} for c in self.claims],
            "case_facts_len": len(self.case_facts),
            "warnings": self.warnings,
        }


def _first(*values: Any) -> Any:
    """返回第一个非空（非 None/空串）的值。"""
    for v in values:
        if v is not None and str(v).strip():
            return v
    return None


def _normalize_party(payload: Dict[str, Any], side: str,
                     legacy_info_key: str, legacy_name_key: str,
                     default_name: str, warnings: List[str]) -> CanonicalParty:
    """兼容三种来源：新字段 xxx_name、旧结构 xxx_info.name、兜底默认名。"""
    name = _first(payload.get(legacy_name_key), (payload.get(legacy_info_key) or {}).get("name"))
    attributes = dict(payload.get(legacy_info_key) or {})
    if not name:
        name = default_name
        warnings.append(f"{side} name missing; defaulted to '{default_name}'")
    return CanonicalParty(name=str(name), attributes=attributes)


def normalize_case_payload(payload: Dict[str, Any]) -> CanonicalCaseBundle:
    """把原始案件字典规范化为 CanonicalCaseBundle。

    兼容字段映射：
      case_id        ← case_id | id
      cause          ← cause | case_type（缺失警告）
      plaintiff      ← plaintiff_name | plaintiff_info.name
      defendant      ← defendant_name | defendant_info.name
      claims         ← plaintiff_claims(list|str) | claim_description | claim
      case_facts     ← case_description | complaint_text（缺失警告）
      findings       ← third_party_findings
    """
    if not isinstance(payload, dict):
        raise TypeError(f"case payload must be dict, got {type(payload).__name__}")

    warnings: List[str] = []

    case_id = str(_first(payload.get("case_id"), payload.get("id")) or "")
    if not case_id:
        warnings.append("case_id missing")

    cause = str(_first(payload.get("cause"), payload.get("case_type")) or "民事纠纷")
    if not _first(payload.get("cause"), payload.get("case_type")):
        warnings.append("cause missing; defaulted to '民事纠纷'")

    plaintiff = _normalize_party(payload, "plaintiff", "plaintiff_info",
                                 "plaintiff_name", "原告", warnings)
    defendant = _normalize_party(payload, "defendant", "defendant_info",
                                 "defendant_name", "被告", warnings)

    claims: List[CanonicalClaim] = []
    raw_claims = payload.get("plaintiff_claims")
    if isinstance(raw_claims, list) and raw_claims:
        for i, c in enumerate(raw_claims):
            text = str(c).strip()
            if text:
                claims.append(CanonicalClaim(claim_id=f"C{i + 1}", text=text))
    elif isinstance(raw_claims, str) and raw_claims.strip():
        claims.append(CanonicalClaim(claim_id="C1", text=raw_claims.strip()))

    claim_desc = _first(payload.get("claim_description"), payload.get("claim"))
    if not claims and claim_desc:
        claims.append(CanonicalClaim(claim_id="C1", text=str(claim_desc).strip()))

    if not claims:
        warnings.append("plaintiff_claims/claim_description missing")

    case_facts = str(_first(payload.get("case_description"),
                            payload.get("complaint_text")) or "")
    findings = str(payload.get("third_party_findings") or "")
    if not case_facts and not findings:
        warnings.append("case_description/third_party_findings missing")

    metadata = {
        k: payload[k] for k in payload
        if k not in ("case_id", "id", "cause", "case_type", "plaintiff_name",
                     "defendant_name", "plaintiff_info", "defendant_info",
                     "plaintiff_claims", "claim_description", "claim",
                     "case_description", "complaint_text", "third_party_findings")
        and payload[k] is not None
    }

    return CanonicalCaseBundle(
        case_id=case_id,
        cause=cause,
        plaintiff=plaintiff,
        defendant=defendant,
        claims=claims,
        case_facts=case_facts,
        third_party_findings=findings,
        metadata=metadata,
        warnings=warnings,
    )
