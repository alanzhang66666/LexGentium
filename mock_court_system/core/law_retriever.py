import os
import logging
import sqlite3
import numpy as np
import faiss
import dashscope
import jieba
from rank_bm25 import BM25Okapi
from dashscope import TextEmbedding, TextReRank
from typing import List, Dict, Tuple
from pathlib import Path

logger = logging.getLogger("law_retriever")


def get_dashscope_api_key() -> str:
    """Return the configured DashScope key without hard-coding secrets."""
    return (
        os.getenv("DASHSCOPE_API_KEY", "").strip()
        or os.getenv("LLM_API_KEY", "").strip()
    )


def get_database_dir() -> str:
    """法条数据库目录，以本文件位置锚定（mock_court_system/database），
    避免从非项目根目录启动时因 CWD 不同导致检索静默失效。"""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database"
    )


class LawRetriever:
    def __init__(self, db_path: str, index_path: str, mapping_path: str, api_key: str):
        self.db_path = db_path
        self.index_path = index_path
        self.mapping_path = mapping_path
        self.api_key = api_key or ""
        
        # Check if files exist
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
        if not os.path.exists(self.index_path):
            raise FileNotFoundError(f"Index file not found: {self.index_path}")
        if not os.path.exists(self.mapping_path):
            raise FileNotFoundError(f"Mapping file not found: {self.mapping_path}")

        # Load resources
        # Workaround for FAISS on Windows with non-ASCII paths
        try:
            index_abs_path = os.path.abspath(self.index_path)
            index_dir = os.path.dirname(index_abs_path)
            index_name = os.path.basename(index_abs_path)
            
            cwd = os.getcwd()
            os.chdir(index_dir)
            try:
                self.index = faiss.read_index(index_name)
            finally:
                os.chdir(cwd)
        except Exception as e:
            logger.warning("Failed to load FAISS index with chdir workaround: %s", e)
            # Fallback to original method
            self.index = faiss.read_index(self.index_path)

        # id 映射为纯 int64 数组，禁止 pickle 协议（.npy 的 pickle 可携带任意代码）
        self.id_mapping = np.load(self.mapping_path, allow_pickle=False)
        
        if self.api_key:
            dashscope.api_key = self.api_key
        
        # Initialize BM25
        self._init_bm25()

    def _init_bm25(self):
        """Initialize BM25 index from database"""
        logger.info("Initializing BM25 index...")
        self.bm25_corpus = []
        self.bm25_ids = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, content FROM articles")
            rows = cursor.fetchall()
            
            tokenized_corpus = []
            for r in rows:
                self.bm25_ids.append(r[0])
                # Use jieba for Chinese tokenization
                tokens = list(jieba.cut(r[1]))
                tokenized_corpus.append(tokens)
                self.bm25_corpus.append(r[1])
            
            self.bm25 = BM25Okapi(tokenized_corpus)
            conn.close()
            logger.info("BM25 index initialized with %d documents.", len(self.bm25_ids))
        except Exception as e:
            logger.warning("Failed to initialize BM25: %s", e)
            self.bm25 = None

    def _get_embedding(self, text: str) -> List[float]:
        try:
            if not self.api_key:
                return []
            if not text:
                return []

            max_len = 2048
            sanitized = text.strip()
            if len(sanitized) > max_len:
                sanitized = sanitized[:max_len]

            resp = TextEmbedding.call(
                model=TextEmbedding.Models.text_embedding_v2,
                input=sanitized
            )
            if resp.status_code == 200:
                return resp.output["embeddings"][0]["embedding"]
            else:
                logger.warning("Embedding failed: %s", resp.message)
                return []
        except Exception as e:
            logger.warning("Embedding exception: %s", e)
            return []

    def _vector_search(self, query: str, top_k: int) -> List[Dict]:
        """Perform vector search using Faiss"""
        embedding = self._get_embedding(query)
        if not embedding:
            return []
        
        query_vector = np.array([embedding], dtype=np.float32)
        distances, indices = self.index.search(query_vector, top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1: continue
            if idx < len(self.id_mapping):
                law_id = self.id_mapping[idx]
                results.append({
                    "law_id": int(law_id),
                    "score": float(distances[0][i]), # L2 distance (lower is better)
                    "source": "vector"
                })
        return results

    def _bm25_search(self, query: str, top_k: int) -> List[Dict]:
        """Perform keyword search using BM25"""
        if not self.bm25:
            return []
            
        tokenized_query = list(jieba.cut(query))
        # Get top_k scores
        scores = self.bm25.get_scores(tokenized_query)
        top_n_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_n_indices:
            if scores[idx] > 0:
                results.append({
                    "law_id": int(self.bm25_ids[idx]),
                    "score": float(scores[idx]), # BM25 score (higher is better)
                    "source": "bm25"
                })
        return results

    def _rrf_fusion(self, vector_results: List[Dict], bm25_results: List[Dict], k: int = 60) -> List[Dict]:
        """Reciprocal Rank Fusion"""
        fused_scores = {}
        
        # Process vector results
        for rank, item in enumerate(vector_results):
            doc_id = item['law_id']
            if doc_id not in fused_scores:
                fused_scores[doc_id] = 0
            fused_scores[doc_id] += 1 / (k + rank + 1)
            
        # Process BM25 results
        for rank, item in enumerate(bm25_results):
            doc_id = item['law_id']
            if doc_id not in fused_scores:
                fused_scores[doc_id] = 0
            fused_scores[doc_id] += 1 / (k + rank + 1)
            
        # Sort by fused score
        sorted_ids = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        
        return [{"law_id": doc_id, "score": score} for doc_id, score in sorted_ids]

    def _rerank_model(self, query: str, candidates: List[Dict], top_k: int) -> List[Dict]:
        """
        Use DashScope TextReRank model to re-rank candidates.
        """
        if not candidates:
            return []
            
        # Prepare documents for reranking
        # We need content for reranking, so we might need to fetch it first if not present
        # But candidates from RRF only have law_id. We need to fetch content.
        
        # 1. Fetch content for candidates
        candidate_ids = [c['law_id'] for c in candidates]
        id_to_details = {}
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            placeholders = ','.join(['?'] * len(candidate_ids))
            cursor.execute(f"SELECT id, content, law_name, article_number FROM articles WHERE id IN ({placeholders})", candidate_ids)
            rows = cursor.fetchall()
            for r in rows:
                id_to_details[r[0]] = {
                    "content": r[1],
                    "law_name": r[2],
                    "article_number": r[3]
                }
            conn.close()
        except Exception as e:
            logger.warning("DB error in rerank: %s", e)
            return candidates[:top_k] # Fallback
            
        # 2. Construct input for reranker
        docs = []
        valid_candidates = []
        for c in candidates:
            details = id_to_details.get(c['law_id'])
            if details:
                docs.append(details['content'])
                c.update(details)
                valid_candidates.append(c)
        
        if not docs:
            return []

        if not self.api_key:
            for i, c in enumerate(valid_candidates[:top_k]):
                c['content'] = docs[i]
                c['source'] = c.get('source', 'bm25')
            return valid_candidates[:top_k]

        try:
            # DashScope TextReRank limit is usually 10-20 docs per request depending on model
            # We'll rerank top 20 from RRF
            rerank_limit = 20
            docs_to_rank = docs[:rerank_limit]
            
            resp = TextReRank.call(
                model=TextReRank.Models.gte_rerank,
                query=query,
                documents=docs_to_rank,
                top_n=top_k
            )
            
            if resp.status_code == 200:
                reranked_results = []
                for item in resp.output.results:
                    original_idx = item.index
                    new_score = item.relevance_score
                    
                    candidate = valid_candidates[original_idx]
                    candidate['score'] = new_score
                    candidate['content'] = docs_to_rank[original_idx] # Cache content
                    candidate['source'] = 'rerank'
                    reranked_results.append(candidate)
                return reranked_results
            else:
                logger.warning("Rerank failed: %s", resp.message)
                # Fallback: return top_k from RRF with content fetched
                for i, c in enumerate(valid_candidates[:top_k]):
                    c['content'] = docs[i]
                return valid_candidates[:top_k]
                
        except Exception as e:
            logger.warning("Rerank exception: %s", e)
            # Fallback
            for i, c in enumerate(valid_candidates[:top_k]):
                c['content'] = docs[i]
            return valid_candidates[:top_k]

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        Hybrid search with Vector + BM25 -> RRF Fusion -> Model Rerank.
        """
        # 1. Expand recall for fusion
        recall_k = top_k * 5 # Fetch more for RRF
        
        # 2. Parallel retrieval
        vec_results = self._vector_search(query, top_k=recall_k)
        bm25_results = self._bm25_search(query, top_k=recall_k)
        
        # 3. Fusion
        fused_results = self._rrf_fusion(vec_results, bm25_results)
        
        # 4. Model-based Re-ranking
        # Rerank top 20 from fusion results
        rerank_candidates = fused_results[:20]
        final_results = self._rerank_model(query, rerank_candidates, top_k)
        
        # If rerank failed or returned fewer results (shouldn't happen with fallback), 
        # ensure we have content for results
        for res in final_results:
            if 'content' not in res:
                # Fetch content if missing (e.g. if fallback path didn't fill it)
                try:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT content FROM articles WHERE id = ?", (res['law_id'],))
                    row = cursor.fetchone()
                    if row:
                        res['content'] = row[0]
                    conn.close()
                except:
                    pass
                    
        return final_results


_shared_law_retriever: "LawRetriever | None" = None


def get_shared_law_retriever() -> "LawRetriever":
    """LawRetriever 模块级单例。

    BM25 全量分词与 FAISS 索引加载代价较高，全部调用方
    （各 Agent、检索接口）共享同一实例，避免重复初始化。
    """
    global _shared_law_retriever
    if _shared_law_retriever is None:
        db_dir = get_database_dir()
        _shared_law_retriever = LawRetriever(
            db_path=os.path.join(db_dir, "legal_articles.db"),
            index_path=os.path.join(db_dir, "legal_articles.index"),
            mapping_path=os.path.join(db_dir, "legal_articles_id_map.npy"),
            api_key=get_dashscope_api_key(),
        )
    return _shared_law_retriever
