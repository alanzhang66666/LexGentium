"""
Progressive RAG (P-RAG) 渐进式检索增强生成
基于 PROClaim (2603.28488) 的核心创新：

传统 RAG：一次检索 → 生成
P-RAG：  阶段1检索 → 辩论/推理 → 发现新焦点 → 阶段2检索 → 精炼证据池 → ...

在模拟法庭场景中：
- 庭审准备阶段：基于案情描述做初始法条检索
- 法庭调查阶段：基于原告诉求+被告抗辩，扩展检索范围
- 法庭辩论阶段：基于争议焦点，精确检索相关判例和法条
- 判决阶段：基于法院认定的事实，做最终法条确认检索

每个阶段的检索结果会累积到证据池中，去重并按相关性排序。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger("progressive_rag")


@dataclass
class RetrievalRecord:
    """单次检索记录"""
    stage: str
    query: str
    results: List[Dict[str, Any]]
    trigger: str  # 触发检索的原因


@dataclass
class EvidencePool:
    """累积证据池"""
    laws: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    retrieval_log: List[RetrievalRecord] = field(default_factory=list)
    _seen_queries: Set[str] = field(default_factory=set)

    def add_results(self, stage: str, query: str, results: List[Dict], trigger: str):
        """添加检索结果到证据池（自动去重）。"""
        self.retrieval_log.append(RetrievalRecord(stage, query, results, trigger))
        for r in results:
            law_id = r.get("law_id")
            if law_id is None:
                continue
            if law_id not in self.laws:
                self.laws[law_id] = {**r, "first_found_stage": stage, "relevance_stages": [stage]}
            else:
                if stage not in self.laws[law_id].get("relevance_stages", []):
                    self.laws[law_id]["relevance_stages"].append(stage)
                old_score = self.laws[law_id].get("score", 0)
                new_score = r.get("score", 0)
                if new_score > old_score:
                    self.laws[law_id]["score"] = new_score

    def get_top_k(self, k: int = 5) -> List[Dict[str, Any]]:
        """获取按综合相关性排序的前 k 条法条。"""
        ranked = sorted(
            self.laws.values(),
            key=lambda x: (len(x.get("relevance_stages", [])), x.get("score", 0)),
            reverse=True,
        )
        return ranked[:k]

    def get_stage_results(self, stage: str) -> List[Dict[str, Any]]:
        """获取特定阶段检索到的法条。"""
        return [v for v in self.laws.values() if stage in v.get("relevance_stages", [])]

    def is_query_seen(self, query: str) -> bool:
        normalized = query.strip()[:100]
        if normalized in self._seen_queries:
            return True
        self._seen_queries.add(normalized)
        return False

    def summary(self) -> Dict[str, Any]:
        return {
            "total_laws": len(self.laws),
            "retrieval_rounds": len(self.retrieval_log),
            "stages_covered": list({r.stage for r in self.retrieval_log}),
            "top_laws": [
                {"law_id": v.get("law_id"), "content": v.get("content", "")[:80],
                 "stages": v.get("relevance_stages", []), "score": v.get("score", 0)}
                for v in self.get_top_k(5)
            ],
        }


# 每个阶段的检索 query 生成 prompt
_STAGE_QUERY_PROMPTS = {
    "opening": "基于以下案件信息，生成用于检索相关法律条文的关键词查询（1-2个查询）：\n{context}",
    "investigation": "基于原告诉求和被告答辩，生成用于检索争议相关法条的查询：\n原告诉求：{plaintiff_claims}\n被告答辩：{defendant_defense}\n已检索法条：{existing_laws}",
    "debate": "基于庭审辩论中的争议焦点，生成精确的法条检索查询：\n争议焦点：{dispute_focus}\n需要补充的法律依据方向：{gaps}",
    "judgment": "基于法院认定的事实和拟判决方向，做最终法条确认检索：\n认定事实：{facts}\n拟判决：{draft_judgment}\n已有法条：{existing_laws}",
}


class ProgressiveRAG:
    """渐进式检索增强生成引擎。

    与 LawRetriever 配合使用，在庭审各阶段动态扩展证据池。
    """

    def __init__(self, law_retriever, llm_client=None):
        """
        Args:
            law_retriever: LawRetriever 实例（混合检索器）
            llm_client: LLMClient 实例（用于生成阶段性检索 query）
        """
        self.retriever = law_retriever
        self.llm = llm_client
        self.pool = EvidencePool()

    def reset(self):
        """重置证据池（新案件时调用）。"""
        self.pool = EvidencePool()

    def _generate_queries(self, stage: str, context: Dict[str, str]) -> List[str]:
        """用 LLM 生成当前阶段的检索 query。"""
        if not self.llm:
            return [context.get("raw_query", "")]

        template = _STAGE_QUERY_PROMPTS.get(stage, _STAGE_QUERY_PROMPTS["opening"])
        prompt = template.format(**{k: str(v)[:500] for k, v in context.items()})
        prompt += "\n\n请输出 1-3 个简洁的检索查询，每行一个："

        try:
            response = self.llm.chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            queries = [q.strip() for q in response.strip().split("\n") if q.strip() and len(q.strip()) > 2]
            return queries[:3] if queries else [context.get("raw_query", "法律条文")]
        except Exception as e:
            logger.warning(f"P-RAG query generation failed: {e}")
            return [context.get("raw_query", "法律条文")]

    def retrieve_for_stage(
        self,
        stage: str,
        context: Dict[str, str],
        top_k: int = 5,
        trigger: str = "auto",
    ) -> List[Dict[str, Any]]:
        """为指定庭审阶段执行检索并更新证据池。"""
        if not self.retriever:
            return []

        existing_law_ids = set(self.pool.laws.keys())
        existing_laws_text = ", ".join(
            v.get("content", "")[:40] for v in list(self.pool.laws.values())[:5]
        )
        context["existing_laws"] = existing_laws_text

        queries = self._generate_queries(stage, context)
        new_results = []

        for query in queries:
            if self.pool.is_query_seen(query):
                continue

            try:
                results = self.retriever.search(query, top_k=top_k)
                self.pool.add_results(stage, query, results, trigger)
                for r in results:
                    if r.get("law_id") not in existing_law_ids:
                        new_results.append(r)
                        existing_law_ids.add(r.get("law_id"))
            except Exception as e:
                logger.warning(f"P-RAG retrieval failed for query '{query[:50]}': {e}")

        logger.info(
            f"P-RAG [{stage}]: {len(queries)} queries → {len(new_results)} new laws "
            f"(pool total: {len(self.pool.laws)})"
        )
        return new_results

    def retrieve_opening(self, case_description: str, claims: str = "") -> List[Dict]:
        """阶段 1：开庭准备 —— 基于案情初始检索。"""
        return self.retrieve_for_stage("opening", {
            "context": case_description[:800],
            "raw_query": case_description[:200],
        }, top_k=5, trigger="case_init")

    def retrieve_investigation(
        self, plaintiff_claims: str, defendant_defense: str,
    ) -> List[Dict]:
        """阶段 2：法庭调查 —— 基于双方主张扩展检索。"""
        return self.retrieve_for_stage("investigation", {
            "plaintiff_claims": plaintiff_claims,
            "defendant_defense": defendant_defense,
            "raw_query": f"{plaintiff_claims[:100]} {defendant_defense[:100]}",
        }, top_k=5, trigger="claims_defense")

    def retrieve_debate(
        self, dispute_focus: str, gaps: str = "",
    ) -> List[Dict]:
        """阶段 3：法庭辩论 —— 基于争议焦点精确检索。"""
        return self.retrieve_for_stage("debate", {
            "dispute_focus": dispute_focus,
            "gaps": gaps or "需要更精确的法条依据",
            "raw_query": dispute_focus[:200],
        }, top_k=3, trigger="dispute_focus")

    def retrieve_judgment(
        self, facts: str, draft_judgment: str = "",
    ) -> List[Dict]:
        """阶段 4：判决 —— 最终法条确认。"""
        return self.retrieve_for_stage("judgment", {
            "facts": facts,
            "draft_judgment": draft_judgment,
            "raw_query": f"{facts[:100]} {draft_judgment[:100]}",
        }, top_k=3, trigger="judgment_confirm")

    def get_accumulated_laws(self, top_k: int = 10) -> List[Dict]:
        """获取累积证据池中的最终法条列表。"""
        return self.pool.get_top_k(top_k)

    def get_retrieval_summary(self) -> Dict[str, Any]:
        """获取检索过程摘要。"""
        return self.pool.summary()
