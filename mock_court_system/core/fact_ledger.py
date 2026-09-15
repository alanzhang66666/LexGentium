"""
Fact-Evidence Ledger：事实主张与证据的结构化台账（推理优化 Phase 1）。

目标：让判决中每一条"本院查明"的事实都能回指到具体证据，
无证据支持的争议事实被显式暴露（幻觉风险清单），而不是混在
自然语言对话里靠关键词抽取和 LLM 记忆。

设计：
- EvidenceLedger：证据账本（提交去重、质证状态、提交次数）。
  重复提交只计数/提示，不再被当作"举证完毕"的依据。
- FactLedger：事实主张账本。证据提交时自动创建占位事实主张
  （text 以证据目的表达），支持显式添加；disputed_without_evidence()
  暴露"有争议且无任何证据支持"的事实——这些事实在判决里
  不应被自动写成"本院查明"。
- 两者均可完整序列化（进 ReasoningState 随会话持久化）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _normalize(text: str) -> str:
    """证据/事实文本规范化（去空白与常见标点差异，用于包含式去重）。"""
    return re.sub(r"[\s，。；：、！？「」『』（）()【】\[\]""'']+", "", text or "")


# ---------- 证据账本 ----------

@dataclass
class EvidenceEntry:
    evidence_id: str
    provider: str                 # plaintiff | defendant
    content: str
    purpose: str = ""
    submissions_count: int = 1    # 含重复提交次数（重复不再触发"举证完毕"）
    contested: bool = False       # 对方质证提出异议

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "provider": self.provider,
            "content": self.content,
            "purpose": self.purpose,
            "submissions_count": self.submissions_count,
            "contested": self.contested,
        }


class EvidenceLedger:
    """证据账本：按内容规范化去重，重复提交只累加计数。"""

    def __init__(self) -> None:
        self.entries: Dict[str, EvidenceEntry] = {}
        self._norm_index: Dict[str, str] = {}   # normalized content -> evidence_id
        self._counter = 0

    def submit(self, provider: str, content: str, purpose: str = "") -> "tuple[Optional[EvidenceEntry], bool]":
        """提交证据。返回 (entry, is_new)。重复提交返回既有条目并累加计数。"""
        norm = _normalize(content)
        if not norm:
            return None, False
        existing_id = self._norm_index.get(norm)
        # 包含式兜底：新内容包含或被包含于已有证据内容
        if not existing_id:
            for norm_k, eid in self._norm_index.items():
                if norm_k in norm or norm in norm_k:
                    existing_id = eid
                    break
        if existing_id:
            entry = self.entries[existing_id]
            entry.submissions_count += 1
            return entry, False

        self._counter += 1
        eid = f"E_{provider}_{self._counter}"
        entry = EvidenceEntry(evidence_id=eid, provider=provider,
                              content=content, purpose=purpose)
        self.entries[eid] = entry
        self._norm_index[norm] = eid
        return entry, True

    def mark_contested(self, evidence_id: str) -> None:
        if evidence_id in self.entries:
            self.entries[evidence_id].contested = True

    def get(self, evidence_id: str) -> Optional[EvidenceEntry]:
        return self.entries.get(evidence_id)

    def __len__(self) -> int:
        return len(self.entries)

    # ---------- 序列化 ----------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entries": [e.to_dict() for e in self.entries.values()],
            "counter": self._counter,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceLedger":
        ledger = cls()
        for e in data.get("entries", []):
            entry = EvidenceEntry(
                evidence_id=e["evidence_id"], provider=e["provider"],
                content=e["content"], purpose=e.get("purpose", ""),
                submissions_count=int(e.get("submissions_count", 1)),
                contested=bool(e.get("contested", False)),
            )
            ledger.entries[entry.evidence_id] = entry
            ledger._norm_index[_normalize(entry.content)] = entry.evidence_id
        ledger._counter = int(data.get("counter", len(ledger.entries)))
        return ledger


# ---------- 事实账本 ----------

@dataclass
class FactClaim:
    fact_id: str
    text: str
    party: str                     # plaintiff | defendant | court
    burden: str                    # 举证责任方
    status: str = "alleged"        # alleged | admitted | disputed | adjudicated
    evidence_ids: List[str] = field(default_factory=list)     # 支持证据
    counter_evidence_ids: List[str] = field(default_factory=list)  # 反证
    adjudication: Optional[Dict[str, Any]] = None             # {adopted, reason}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_id": self.fact_id, "text": self.text, "party": self.party,
            "burden": self.burden, "status": self.status,
            "evidence_ids": list(self.evidence_ids),
            "counter_evidence_ids": list(self.counter_evidence_ids),
            "adjudication": self.adjudication,
        }


class FactLedger:
    """事实主张账本。"""

    def __init__(self, evidence_ledger: Optional[EvidenceLedger] = None) -> None:
        self.claims: Dict[str, FactClaim] = {}
        self.evidence = evidence_ledger or EvidenceLedger()
        self._counter = 0

    # --- 事实主张 ---

    def add_claim(self, text: str, party: str, burden: Optional[str] = None,
                  evidence_id: Optional[str] = None) -> "tuple[FactClaim, bool]":
        """添加事实主张（规范化去重：包含式合并）。返回 (claim, is_new)。"""
        norm = _normalize(text)
        if not norm:
            raise ValueError("fact text is empty")
        for claim in self.claims.values():
            norm_existing = _normalize(claim.text)
            if norm in norm_existing or norm_existing in norm:
                if evidence_id and evidence_id not in claim.evidence_ids:
                    claim.evidence_ids.append(evidence_id)
                return claim, False
        self._counter += 1
        fid = f"F{self._counter}"
        claim = FactClaim(
            fact_id=fid, text=text.strip(), party=party,
            burden=burden or party, status="alleged",
        )
        if evidence_id:
            claim.evidence_ids.append(evidence_id)
        self.claims[fid] = claim
        return claim, True

    def attach_evidence(self, fact_id: str, evidence_id: str,
                        stance: str = "support") -> None:
        claim = self.claims.get(fact_id)
        if not claim:
            raise KeyError(f"unknown fact_id: {fact_id}")
        target = claim.evidence_ids if stance == "support" else claim.counter_evidence_ids
        if evidence_id not in target:
            target.append(evidence_id)

    def set_status(self, fact_id: str, status: str) -> None:
        if status not in ("alleged", "admitted", "disputed", "adjudicated"):
            raise ValueError(f"invalid status: {status}")
        self.claims[fact_id].status = status

    def adjudicate(self, fact_id: str, adopted: bool, reason: str = "") -> None:
        claim = self.claims[fact_id]
        claim.status = "adjudicated"
        claim.adjudication = {"adopted": adopted, "reason": reason}

    # --- 风险视图 ---

    def disputed_without_evidence(self) -> List[FactClaim]:
        """有争议且无任何支持证据的事实——判决不应自动采信。"""
        return [
            c for c in self.claims.values()
            if c.status in ("alleged", "disputed") and not c.evidence_ids
        ]

    def unadjudicated(self) -> List[FactClaim]:
        return [c for c in self.claims.values() if c.status != "adjudicated"]

    def mark_contested(self, evidence_id: str) -> None:
        """标记证据被质证异议（代理到证据账本）。"""
        self.evidence.mark_contested(evidence_id)

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceEntry]:
        """按编号取证据条目（代理到证据账本）。"""
        return self.evidence.get(evidence_id)

    def as_prompt_text(self, max_chars: int = 1800) -> str:
        """渲染为判决提示词可注入的台账文本。"""
        if not self.claims:
            return ""
        lines = ["【事实与证据台账（判决中每条查明事实须引用对应 F/E 编号）】"]
        for c in self.claims.values():
            ev = ", ".join(c.evidence_ids) or "无"
            counter = ", ".join(c.counter_evidence_ids) or "无"
            lines.append(
                f"- [{c.fact_id}] {c.text}（主张方：{c.party}；举证责任：{c.burden}；"
                f"状态：{c.status}；支持证据：{ev}；反证：{counter}）"
            )
        text = "\n".join(lines)
        return text[:max_chars]

    # --- 序列化 ---

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claims": [c.to_dict() for c in self.claims.values()],
            "evidence": self.evidence.to_dict(),
            "counter": self._counter,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FactLedger":
        ledger = cls()
        ledger.evidence = EvidenceLedger.from_dict(data.get("evidence", {}))
        for c in data.get("claims", []):
            claim = FactClaim(
                fact_id=c["fact_id"], text=c["text"], party=c["party"],
                burden=c.get("burden", c["party"]), status=c.get("status", "alleged"),
                evidence_ids=list(c.get("evidence_ids", [])),
                counter_evidence_ids=list(c.get("counter_evidence_ids", [])),
                adjudication=c.get("adjudication"),
            )
            ledger.claims[claim.fact_id] = claim
        ledger._counter = int(data.get("counter", len(ledger.claims)))
        return ledger
