"""
Per-issue IRAC 推理器（推理优化 Phase 1）。

对 IssueGraph 中的每个争点独立执行：
  Issue（争点）→ Rule（检索法条，白名单=库内命中）→ Application（结合台账事实）
  → Conclusion（裁判倾向 + 对应诉请）

输出结构化 IssueAnalysis，供判决提示词注入与 disposition 校验使用。
与一次性整篇判决的区别：每个争点的法条来自独立检索（可回查）、
事实来自台账绑定（可回指）、结论自带诉请指向（可校验覆盖）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.fact_ledger import FactLedger
from core.issue_graph import Issue, IssueGraph

logger = logging.getLogger("irac")


_IRAC_PROMPT = """你是民事法官助理。请针对以下单个争议焦点，基于给定事实与法条进行 IRAC 推理。

【争议焦点】
{question}

【相关事实（来自庭审台账）】
{facts}

【可用法条（只允许引用下列法条，不得引用其他法条）】
{laws}

请输出严格 JSON：
{{
  "application": "把法条适用于上述事实的分析（150字以内，须提及具体事实与法条）",
  "conclusion": "该争点的裁判倾向结论（一句话）",
  "disposition_hints": [
    {{"claim_text": "对应的原告诉请（可用'无对应诉请'）", "result": "支持/部分支持/驳回"}}
  ]
}}"""


@dataclass
class IssueAnalysis:
    issue_id: str
    question: str
    fact_ids: List[str] = field(default_factory=list)
    law_refs: List[str] = field(default_factory=list)      # 库内命中的法条引用文本
    law_ids: List[int] = field(default_factory=list)       # 库内 law_id（可回查）
    application: str = ""
    conclusion: str = ""
    disposition_hints: List[Dict[str, str]] = field(default_factory=list)
    status: str = "ok"                                     # ok | degraded | failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id, "question": self.question,
            "fact_ids": list(self.fact_ids), "law_refs": list(self.law_refs),
            "law_ids": list(self.law_ids), "application": self.application,
            "conclusion": self.conclusion,
            "disposition_hints": list(self.disposition_hints),
            "status": self.status,
        }


class IssueIRACReasoner:
    def __init__(self, law_retriever, llm) -> None:
        self.retriever = law_retriever
        self.llm = llm

    # ---------- 单争点 ----------

    def reason_issue(self, issue: Issue, ledger: FactLedger,
                     top_k: int = 3) -> IssueAnalysis:
        analysis = IssueAnalysis(
            issue_id=issue.issue_id, question=issue.question,
            fact_ids=list(issue.fact_ids),
        )

        # 1) Rule：按争点独立检索（库内命中即白名单）
        laws_text = "（无可用法条——如确无法律依据应如实说明）"
        if self.retriever:
            query = issue.question
            bound_texts = [ledger.claims[f].text for f in issue.fact_ids if f in ledger.claims]
            if bound_texts:
                query = f"{issue.question} {' '.join(t[:80] for t in bound_texts[:2])}"
            try:
                results = self.retriever.search(query, top_k=top_k)
                law_lines = []
                for r in results:
                    ref = f"《{r.get('law_name', '')}》第{r.get('article_number', '')}条：{r.get('content', '')[:80]}"
                    law_lines.append(f"- {ref}")
                    analysis.law_refs.append(ref)
                    if "law_id" in r:
                        analysis.law_ids.append(int(r["law_id"]))
                if law_lines:
                    laws_text = "\n".join(law_lines)
            except Exception as e:
                logger.warning("IRAC retrieval failed for %s: %s", issue.issue_id, e)

        # 2) Facts：台账绑定事实原文（附证据内容，推理需要证据细节）
        fact_lines = []
        for fid in issue.fact_ids:
            c = ledger.claims.get(fid)
            if not c:
                continue
            ev_parts = []
            for eid in c.evidence_ids:
                ev_entry = ledger.evidence.get(eid)
                if ev_entry:
                    ev_parts.append(f"[{eid}] {ev_entry.content[:60]}")
            ev_text = "；".join(ev_parts) or "无证据"
            fact_lines.append(f"- [{fid}] {c.text}（证据：{ev_text}）")
        facts_text = "\n".join(fact_lines) or "（无绑定事实）"

        # 3) Application + Conclusion：LLM IRAC
        prompt = _IRAC_PROMPT.format(question=issue.question,
                                     facts=facts_text, laws=laws_text)
        try:
            result = self.llm.chat_json([{"role": "user", "content": prompt}],
                                        temperature=0.1)
        except Exception as e:
            logger.warning("IRAC LLM failed for %s: %s", issue.issue_id, e)
            result = None

        if not isinstance(result, dict):
            analysis.status = "failed"   # LLM 完全失败（区别于缺字段 degraded）
            return analysis

        if str(result.get("application") or "").strip():
            analysis.application = str(result["application"]).strip()
            analysis.conclusion = str(result.get("conclusion", "")).strip()
            hints = result.get("disposition_hints")
            if isinstance(hints, list):
                analysis.disposition_hints = [
                    h for h in hints
                    if isinstance(h, dict) and h.get("claim_text") and h.get("result")
                ]
            analysis.status = "ok" if analysis.conclusion else "degraded"
        else:
            analysis.status = "degraded"
            analysis.application = ""
            analysis.conclusion = ""

        return analysis

    # ---------- 批量 ----------

    def reason_all(self, graph: IssueGraph, ledger: FactLedger,
                   top_k: int = 3) -> List[IssueAnalysis]:
        analyses: List[IssueAnalysis] = []
        for issue in graph.issues.values():
            analyses.append(self.reason_issue(issue, ledger, top_k=top_k))
        return analyses

    @staticmethod
    def render(analyses: List[IssueAnalysis], max_chars: int = 2600) -> str:
        """渲染为判决提示词可注入的逐争点 IRAC 文本。"""
        lines = ["【逐争点 IRAC 分析（dispute_focus 与 legal_analysis 应与之一致）】"]
        for a in analyses:
            if a.status == "failed":
                lines.append(f"- [{a.issue_id}] {a.question}\n  （分析生成失败，请按台账事实与法条自行推理）")
                continue
            lines.append(f"- [{a.issue_id}] {a.question}")
            if a.law_refs:
                lines.append(f"  法条：{'；'.join(a.law_refs[:2])}")
            if a.application:
                lines.append(f"  适用：{a.application}")
            if a.conclusion:
                lines.append(f"  倾向结论：{a.conclusion}")
            for h in a.disposition_hints[:3]:
                lines.append(f"  → 诉请「{h['claim_text'][:40]}」：{h['result']}")
        text = "\n".join(lines)
        return text[:max_chars]
