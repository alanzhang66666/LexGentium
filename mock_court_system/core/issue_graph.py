"""
IssueGraph：庭审争点分解与法条挂载（推理优化 Phase 1）。

从 FactLedger 的事实主张生成分歧争点（disputed claim 对），为每个争点
挂载证据与法条，供 per-issue 检索与 IRAC 推理使用。

分解策略：
- LLM 可用时：由台账生成 2-5 个争点（每个争点绑定 fact_ids），结果
  严格校验（question 非空、fact_ids 必须存在于 ledger）；
- 无 LLM 或失败时：规则版兜底——按"原告主张 vs 被告反证"配对生成
  基础争点，保证争点列表永不为空（判决 dispute_focus 的下界）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.fact_ledger import FactLedger


@dataclass
class Issue:
    issue_id: str
    question: str
    fact_ids: List[str] = field(default_factory=list)
    law_ids: List[int] = field(default_factory=list)   # Verified RAG 挂载的库内法条 id
    status: str = "open"                                # open | resolved

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "question": self.question,
            "fact_ids": list(self.fact_ids),
            "law_ids": list(self.law_ids),
            "status": self.status,
        }


class IssueGraph:
    def __init__(self) -> None:
        self.issues: Dict[str, Issue] = {}
        self._counter = 0

    def add_issue(self, question: str, fact_ids: Optional[List[str]] = None) -> Issue:
        if not question or not question.strip():
            raise ValueError("issue question is empty")
        self._counter += 1
        issue = Issue(issue_id=f"I{self._counter}",
                      question=question.strip(),
                      fact_ids=[f for f in (fact_ids or []) if f])
        self.issues[issue.issue_id] = issue
        return issue

    def attach_law(self, issue_id: str, law_id: int) -> None:
        issue = self.issues.get(issue_id)
        if not issue:
            raise KeyError(f"unknown issue_id: {issue_id}")
        if law_id not in issue.law_ids:
            issue.law_ids.append(law_id)

    def resolve(self, issue_id: str) -> None:
        if issue_id in self.issues:
            self.issues[issue_id].status = "resolved"

    def open_issues(self) -> List[Issue]:
        return [i for i in self.issues.values() if i.status == "open"]

    def as_prompt_text(self, max_chars: int = 900) -> str:
        if not self.issues:
            return ""
        lines = ["【候选争议焦点（可在 dispute_focus 中采纳或改写）】"]
        for i in self.issues.values():
            lines.append(f"- [{i.issue_id}] {i.question}")
        return "\n".join(lines)[:max_chars]

    # ---------- 序列化 ----------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issues": [i.to_dict() for i in self.issues.values()],
            "counter": self._counter,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IssueGraph":
        g = cls()
        for i in data.get("issues", []):
            issue = Issue(issue_id=i["issue_id"], question=i["question"],
                          fact_ids=list(i.get("fact_ids", [])),
                          law_ids=list(i.get("law_ids", [])),
                          status=i.get("status", "open"))
            g.issues[issue.issue_id] = issue
        g._counter = int(data.get("counter", len(g.issues)))
        return g


# ---------- 分解逻辑 ----------

def decompose_rule_based(ledger: FactLedger, graph: IssueGraph) -> List[Issue]:
    """规则版兜底：原告争议主张 × 被告反证 → 基础争点。

    保证争点列表非空：即便台账只有单方主张，也生成对应确认型争点。
    """
    disputed = [c for c in ledger.claims.values() if c.status in ("alleged", "disputed")]
    plaintiff_claims = [c for c in disputed if c.party == "plaintiff"]
    defendant_claims = [c for c in disputed if c.party == "defendant"]

    created: List[Issue] = []
    for p in plaintiff_claims:
        opposing = defendant_claims[:2]
        q = f"原告主张「{p.text[:60]}」是否成立" + (
            f"（被告主张「{opposing[0].text[:40]}」）" if opposing else ""
        )
        created.append(graph.add_issue(q, fact_ids=[p.fact_id] +
                                       [o.fact_id for o in opposing]))
    for d in defendant_claims:
        q = f"被告主张「{d.text[:60]}」是否有事实与法律依据"
        created.append(graph.add_issue(q, fact_ids=[d.fact_id]))
    if not created:
        created.append(graph.add_issue("本案基本事实与法律责任认定"))
    return created


def decompose_with_llm(ledger: FactLedger, graph: IssueGraph,
                       llm, max_issues: int = 5) -> List[Issue]:
    """LLM 分解：从台账生成争点；失败时调用方应回落规则版。"""
    claims_text = "\n".join(
        f"- [{c.fact_id}] ({c.party}) {c.text[:80]} 证据:{','.join(c.evidence_ids) or '无'}"
        for c in ledger.claims.values()
    )
    prompt = f"""你是民事庭审的书记员。请根据以下事实与证据台账，归纳 2-{max_issues} 个核心争议焦点。

{claims_text}

输出严格 JSON：
{{
  "issues": [
    {{"question": "争点描述（一句话）", "fact_ids": ["F1", "F2"]}}
  ]
}}
要求：每个争点必须绑定至少一个 fact_id；fact_id 必须来自上面台账。"""
    result = llm.chat_json([{"role": "user", "content": prompt}], temperature=0.1)
    issues = result.get("issues") if isinstance(result, dict) else None
    if not isinstance(issues, list) or not issues:
        raise ValueError("LLM issue decomposition returned no issues")

    created: List[Issue] = []
    for item in issues[:max_issues]:
        if not isinstance(item, dict):
            continue
        q = str(item.get("question", "")).strip()
        if not q:
            continue
        fact_ids = [f for f in item.get("fact_ids", []) if f in ledger.claims]
        created.append(graph.add_issue(q, fact_ids=fact_ids))
    if not created:
        raise ValueError("LLM issue decomposition produced no valid issues")
    return created


def decompose(ledger: FactLedger, graph: IssueGraph,
              llm=None, max_issues: int = 5) -> List[Issue]:
    """争点分解入口：LLM 优先，规则兜底。"""
    if llm is not None:
        try:
            created = decompose_with_llm(ledger, graph, llm, max_issues=max_issues)
            if created:
                return created
        except Exception:
            pass
    return decompose_rule_based(ledger, graph)
