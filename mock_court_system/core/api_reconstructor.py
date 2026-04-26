"""
API重建器 - 基于历史数据的最近邻匹配
实现方案：给定新输入x'，找到最相近的历史输入x，返回f(x)

当前版本策略（重要）：
1) 严格硬路由：传入case_id后，只在对应case桶内检索，绝不跨case；
2) case_id 规范化：支持 "CD-2" / "DD-12" / "2" 这类格式，统一规范化为 "2"；
3) 若对应case桶不存在 -> 直接拒答（不fallback到其它case导致串案）；
4) 桶内匹配失败（相似度低于阈值）时：
   - 优先走“脚本回放（cursor replay）”：在同一case桶内按turn_count顺序推进，返回下一条历史response；
   - 若回放已结束/无法回放，再执行拒答。
"""

import json
import re
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
from dataclasses import dataclass
import jieba
from rank_bm25 import BM25Okapi
from collections import defaultdict


@dataclass
class APIInteraction:
    """API交互记录"""
    scenario: str
    case_id: str
    dialog_history: List[Dict]
    response: Dict
    # 用于快速匹配的摘要信息
    dialog_summary: str = ""
    last_message: str = ""
    turn_count: int = 0

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "scenario": self.scenario,
            "case_id": self.case_id,
            "dialog_history": self.dialog_history,
            "response": self.response,
            "dialog_summary": self.dialog_summary,
            "last_message": self.last_message,
            "turn_count": self.turn_count,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "APIInteraction":
        """从字典创建"""
        return cls(
            scenario=data["scenario"],
            case_id=data["case_id"],
            dialog_history=data["dialog_history"],
            response=data["response"],
            dialog_summary=data.get("dialog_summary", ""),
            last_message=data.get("last_message", ""),
            turn_count=data.get("turn_count", 0),
        )


class APIReconstructor:
    """API重建器 - 基于历史数据的最近邻匹配"""

    def __init__(
        self,
        data_dir: str = "./api_history",
        use_embedding: bool = False,
        embedding_model: Optional[Any] = None,
    ):
        """
        初始化API重建器

        Args:
            data_dir: 历史数据存储目录
            use_embedding: 是否使用向量嵌入进行相似度计算（当前未实现）
            embedding_model: 嵌入模型（如果使用）
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.use_embedding = use_embedding
        self.embedding_model = embedding_model

        # 存储历史交互数据
        self.interactions: List[APIInteraction] = []

        # 按场景索引：scenario -> [interaction_idx...]
        self.scenario_index: Dict[str, List[int]] = defaultdict(list)

        # 按场景+case桶索引（硬路由）
        # scenario_case_index[scenario][case_key] -> [interaction_idx...]
        self.scenario_case_index: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))

        # BM25索引（按场景+case桶建）
        # bm25_indices_case[(scenario, case_key)] = BM25Okapi(corpus_tokens)
        self.bm25_indices_case: Dict[Tuple[str, str], BM25Okapi] = {}
        # 可选：记录corpus文本（调试用）
        self.bm25_corpus_case: Dict[Tuple[str, str], List[str]] = {}

        # Case Lock（现阶段硬路由后基本不跨case，保留用于调试/扩展）
        # key=(scenario, target_case_id) -> source_case_id（历史interaction.case_id）
        self.case_locks: Dict[Tuple[str, str], str] = {}

        # 脚本回放游标：对每个(场景, 目标case_id)维护一个桶内推进指针
        # key=(scenario, target_case_id) -> cursor（0..len(ordered_case_indices)-1）
        self.case_cursors: Dict[Tuple[str, str], int] = {}

        # 桶内按turn_count排序后的interaction_idx列表
        # key=(scenario, case_key) -> [interaction_idx...]
        self.ordered_case_indices: Dict[Tuple[str, str], List[int]] = {}

        # 相似度阈值：低于阈值不直接拒答，而是优先脚本回放；回放失败才拒答
        self.default_min_similarity: float = 0.35
        self.min_similarity_by_scenario: Dict[str, float] = {
            "CD": 0.35,
            "DD": 0.35,
            "CI": 0.30,
        }

        # 回放模式：是否在低相似时启用脚本回放兜底
        self.enable_cursor_replay: bool = True

        # 加载已有数据
        self._load_data()

    # ------------------------
    # case_id 规范化与路由
    # ------------------------
    def _canon_case_id(self, case_id: str) -> str:
        """
        将传入的case_id统一规范化为“桶key”。
        目标：让 "CD-2" / "DD-2" / "2" 都映射到 "2"（与历史库中常见的数字case_id对齐）。
        若无法提取数字，则退化为原字符串（去除空白）。
        """
        if case_id is None:
            return ""
        s = str(case_id).strip()
        if not s:
            return ""

        # 常见形式：CD-2 / DD-12 / CI-003
        m = re.search(r"(\d+)$", s)
        if m:
            # 去掉前导0（"003" -> "3"），但保留 "0"
            num = m.group(1).lstrip("0")
            return num if num != "" else "0"

        # 如果不是以数字结尾，但包含 '-'，取最后段
        if "-" in s:
            tail = s.split("-")[-1].strip()
            if tail:
                return tail

        return s

    def _get_candidate_indices_strict(self, scenario: str, case_id: str) -> List[int]:
        """严格候选集：必须命中 (scenario, case_key) 桶，否则返回空。"""
        case_key = self._canon_case_id(case_id)
        if not case_key:
            return []
        bucket = self.scenario_case_index.get(scenario, {}).get(case_key, [])
        return bucket[:] if bucket else []

    # ------------------------
    # 数据加载与索引构建
    # ------------------------
    def _load_data(self):
        """从文件加载历史数据"""
        data_file = self.data_dir / "interactions.jsonl"
        if not data_file.exists():
            print(f"历史数据文件不存在: {data_file}")
            return

        print(f"加载历史数据: {data_file}")
        count = 0
        with open(data_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    interaction = APIInteraction.from_dict(data)
                    self.interactions.append(interaction)
                    count += 1
                except Exception as e:
                    print(f"加载数据行失败: {e}")

        print(f"已加载 {count} 条历史交互记录")
        self._build_indices()

    def _build_indices(self):
        """构建索引以加速查找（按场景+case桶）"""
        self.scenario_index.clear()
        self.scenario_case_index.clear()
        self.bm25_indices_case.clear()
        self.bm25_corpus_case.clear()
        self.ordered_case_indices.clear()

        # 1) 建 bucket 索引
        for idx, interaction in enumerate(self.interactions):
            self.scenario_index[interaction.scenario].append(idx)
            case_key = self._canon_case_id(interaction.case_id)
            if case_key:
                self.scenario_case_index[interaction.scenario][case_key].append(idx)

        # 2) 为每个 (scenario, case_key) 建 BM25
        for scenario, case_map in self.scenario_case_index.items():
            for case_key, indices in case_map.items():
                corpus_tokens = []
                corpus_text = []
                for idx in indices:
                    it = self.interactions[idx]
                    doc = f"{it.dialog_summary} {it.last_message}"
                    tokens = list(jieba.cut(doc))
                    corpus_tokens.append(tokens)
                    corpus_text.append(" ".join(tokens))
                if corpus_tokens:
                    key = (scenario, case_key)
                    self.bm25_indices_case[key] = BM25Okapi(corpus_tokens)
                    self.bm25_corpus_case[key] = corpus_text

        # 3) 桶内按 turn_count 排序，用于脚本回放
        for scenario, case_map in self.scenario_case_index.items():
            for case_key, indices in case_map.items():
                key = (scenario, case_key)
                self.ordered_case_indices[key] = sorted(
                    indices,
                    key=lambda i: self.interactions[i].turn_count
                )

        print(
            f"已构建索引: {len(self.scenario_index)} 个场景，"
            f"{sum(len(v) for v in self.scenario_case_index.values())} 个case桶"
        )

    # ------------------------
    # 写入（如需要动态扩展历史库）
    # ------------------------
    def add_interaction(
        self,
        scenario: str,
        case_id: str,
        dialog_history: List[Dict],
        response: Dict,
        save: bool = True,
    ):
        """添加新的交互记录"""
        dialog_summary = self._compute_summary(dialog_history)
        last_message = self._get_last_message(dialog_history)
        turn_count = len(dialog_history)

        interaction = APIInteraction(
            scenario=scenario,
            case_id=case_id,
            dialog_history=dialog_history,
            response=response,
            dialog_summary=dialog_summary,
            last_message=last_message,
            turn_count=turn_count,
        )

        self.interactions.append(interaction)

        idx = len(self.interactions) - 1
        self.scenario_index[scenario].append(idx)

        case_key = self._canon_case_id(case_id)
        if case_key:
            self.scenario_case_index[scenario][case_key].append(idx)
            if save:
                self._save_interaction(interaction)
            # 重建该桶BM25与回放序列（桶很小，重建成本可接受）
            self._rebuild_case_index(scenario, case_key)
        else:
            if save:
                self._save_interaction(interaction)

    def _compute_summary(self, dialog_history: List[Dict]) -> str:
        """计算对话摘要"""
        if not dialog_history:
            return ""
        messages = []
        for item in dialog_history[-10:]:
            role = item.get("role", "")
            message = item.get("message", "")
            messages.append(f"{role}: {message[:100]}")
        return " | ".join(messages)

    def _get_last_message(self, dialog_history: List[Dict]) -> str:
        """获取最后一条消息"""
        if not dialog_history:
            return ""
        return dialog_history[-1].get("message", "")

    def _save_interaction(self, interaction: APIInteraction):
        """保存交互记录到文件"""
        data_file = self.data_dir / "interactions.jsonl"
        with open(data_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(interaction.to_dict(), ensure_ascii=False) + "\n")

    def _rebuild_case_index(self, scenario: str, case_key: str):
        """重建指定(场景, case桶)的BM25索引 + 回放序列"""
        indices = self.scenario_case_index.get(scenario, {}).get(case_key, [])
        key = (scenario, case_key)

        if not indices:
            self.bm25_indices_case.pop(key, None)
            self.bm25_corpus_case.pop(key, None)
            self.ordered_case_indices.pop(key, None)
            return

        corpus_tokens = []
        corpus_text = []
        for idx in indices:
            it = self.interactions[idx]
            doc = f"{it.dialog_summary} {it.last_message}"
            tokens = list(jieba.cut(doc))
            corpus_tokens.append(tokens)
            corpus_text.append(" ".join(tokens))

        self.bm25_indices_case[key] = BM25Okapi(corpus_tokens)
        self.bm25_corpus_case[key] = corpus_text

        self.ordered_case_indices[key] = sorted(
            indices,
            key=lambda i: self.interactions[i].turn_count
        )

    # ------------------------
    # 脚本回放（桶内推进）
    # ------------------------
    def _next_response_by_cursor(
        self,
        scenario: str,
        target_case_id: str,
    ) -> Optional[Dict]:
        """
        在严格路由到的case桶内，按turn_count顺序推进，返回下一条历史response。

        注意：
        - target_case_id 是运行时传入的，比如 "CD-2"；
        - 内部会 normalize 成 case_key="2" 找桶；
        - 每个 (scenario, target_case_id) 维护独立cursor，互不干扰。
        """
        case_key = self._canon_case_id(target_case_id)
        if not case_key:
            return None

        ordered = self.ordered_case_indices.get((scenario, case_key))
        if not ordered:
            return None

        cursor_key = (scenario, target_case_id)
        cur = self.case_cursors.get(cursor_key, 0)

        if cur >= len(ordered):
            return None

        idx = ordered[cur]
        self.case_cursors[cursor_key] = cur + 1
        return self.interactions[idx].response

    def reset_case_cursor(self, scenario: str, case_id: str) -> None:
        """重置某个目标case的回放游标（用于重跑/调试）。"""
        self.case_cursors.pop((scenario, case_id), None)

    # ------------------------
    # 检索与打分（严格按案号桶）
    # ------------------------
    def find_nearest(
        self,
        scenario: str,
        case_id: str,
        dialog_history: List[Dict],
        top_k: int = 1,
        min_similarity: float = 0.0,
    ) -> List[Tuple[APIInteraction, float]]:
        """找到最相似的历史交互（严格：仅在指定case桶内）"""
        candidate_indices = self._get_candidate_indices_strict(scenario, case_id)
        if not candidate_indices:
            return []

        query_summary = self._compute_summary(dialog_history)
        query_last = self._get_last_message(dialog_history)
        query_text = f"{query_summary} {query_last}"
        query_tokens = list(jieba.cut(query_text))

        case_key = self._canon_case_id(case_id)
        bm25_key = (scenario, case_key)
        bm25 = self.bm25_indices_case.get(bm25_key)

        similarities: List[Tuple[APIInteraction, float]] = []

        if bm25 is not None:
            bm25_scores = bm25.get_scores(query_tokens)

            for local_i, idx in enumerate(candidate_indices):
                interaction = self.interactions[idx]

                bm25_score = float(bm25_scores[local_i])
                normalized_score = min(1.0, bm25_score / 10.0)

                turn_diff = abs(interaction.turn_count - len(dialog_history))
                turn_similarity = 1.0 / (1.0 + turn_diff * 0.1)

                last_sim = self._text_similarity(query_last, interaction.last_message)

                final_score = (
                    normalized_score * 0.5 +
                    turn_similarity * 0.2 +
                    last_sim * 0.3
                )

                if final_score >= min_similarity:
                    similarities.append((interaction, final_score))
        else:
            for idx in candidate_indices:
                interaction = self.interactions[idx]
                score = self._simple_similarity(dialog_history, interaction.dialog_history)
                if score >= min_similarity:
                    similarities.append((interaction, score))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def _text_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度（Jaccard over jieba tokens）"""
        if not text1 or not text2:
            return 0.0

        tokens1 = set(jieba.cut(text1))
        tokens2 = set(jieba.cut(text2))
        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        return intersection / union if union > 0 else 0.0

    def _simple_similarity(self, history1: List[Dict], history2: List[Dict]) -> float:
        """简单的对话历史相似度计算"""
        if not history1 or not history2:
            return 0.0

        n = min(3, len(history1), len(history2))
        last1 = history1[-n:]
        last2 = history2[-n:]

        total_sim = 0.0
        for h1, h2 in zip(last1, last2):
            msg1 = h1.get("message", "")
            msg2 = h2.get("message", "")
            total_sim += self._text_similarity(msg1, msg2)

        return total_sim / n if n > 0 else 0.0

    def predict(
        self,
        scenario: str,
        case_id: str,
        dialog_history: List[Dict],
        return_all: bool = False,
    ) -> Optional[Dict]:
        """
        预测API响应（严格案号桶路由 + 低相似时优先脚本回放）

        行为优先级：
        A) 桶不存在 -> 拒答
        B) 桶存在：
           B1) 若最佳相似度 >= 阈值 -> 返回匹配到的历史response
           B2) 若最佳相似度 < 阈值 -> 若开启回放，返回桶内下一条脚本response
           B3) 回放失败（到头/无序列） -> 拒答
        """
        # 先检查桶是否存在（严格路由语义）
        if not self._get_candidate_indices_strict(scenario, case_id):
            return self._refusal_response(scenario, dialog_history)

        results = self.find_nearest(
            scenario=scenario,
            case_id=case_id,
            dialog_history=dialog_history,
            top_k=1 if not return_all else 5,
            min_similarity=0.0,
        )

        threshold = self.min_similarity_by_scenario.get(scenario, self.default_min_similarity)

        if not results:
            if self.enable_cursor_replay:
                scripted = self._next_response_by_cursor(scenario, case_id)
                if scripted is not None:
                    return scripted
            return self._refusal_response(scenario, dialog_history)

        best_interaction, best_score = results[0]

        if best_score < threshold:
            if self.enable_cursor_replay:
                scripted = self._next_response_by_cursor(scenario, case_id)
                if scripted is not None:
                    # return_all 模式下给调试信息（不会影响主流程）
                    if return_all:
                        return {
                            **scripted,
                            "_replay": True,
                            "best_similarity": best_score,
                            "threshold": threshold,
                            "routed_case_key": self._canon_case_id(case_id),
                            "all_candidates": [
                                {
                                    "response": r[0].response.get("response", ""),
                                    "similarity": r[1],
                                    "case_id": r[0].case_id,
                                }
                                for r in results
                            ],
                        }
                    return scripted

            refusal = self._refusal_response(scenario, dialog_history)
            if return_all:
                return {
                    **refusal,
                    "best_similarity": best_score,
                    "threshold": threshold,
                    "routed_case_key": self._canon_case_id(case_id),
                    "all_candidates": [
                        {
                            "response": r[0].response.get("response", ""),
                            "similarity": r[1],
                            "case_id": r[0].case_id,
                        }
                        for r in results
                    ],
                }
            return refusal

        # 记录锁（可选调试信息）
        lock_key = (scenario, case_id)
        if lock_key not in self.case_locks:
            self.case_locks[lock_key] = best_interaction.case_id

        if return_all:
            return {
                "response": best_interaction.response.get("response", ""),
                "best_similarity": best_score,
                "threshold": threshold,
                "routed_case_key": self._canon_case_id(case_id),
                "all_candidates": [
                    {
                        "response": r[0].response.get("response", ""),
                        "similarity": r[1],
                        "case_id": r[0].case_id,
                    }
                    for r in results
                ],
            }

        return best_interaction.response

    def reset_case_lock(self, scenario: str, case_id: str) -> None:
        """清除指定(场景, 目标case_id)的锁定（用于重跑或调试）。"""
        self.case_locks.pop((scenario, case_id), None)

    def _refusal_response(self, scenario: str, dialog_history: List[Dict]) -> Dict:
        """当相似度不足或无候选时的保守回复。"""
        last = self._get_last_message(dialog_history)
        templates = [
            "我不清楚这个问题。",
            "我不了解具体情况。",
            "这部分信息我暂时无法确定。",
            "我现在无法给出准确答复。",
        ]
        idx = abs(hash(f"{scenario}::{last}")) % len(templates)
        return {"response": templates[idx], "_refusal": True}

    def get_stats(self) -> Dict:
        """获取统计信息（增加case桶统计，便于排查case桶是否齐全）"""
        stats = {
            "total_interactions": len(self.interactions),
            "by_scenario": {},
            "by_scenario_case": {},
            "replay_enabled": self.enable_cursor_replay,
        }

        for scenario, indices in self.scenario_index.items():
            stats["by_scenario"][scenario] = len(indices)

        for scenario, case_map in self.scenario_case_index.items():
            stats["by_scenario_case"][scenario] = {
                case_key: len(idxs) for case_key, idxs in case_map.items()
            }

        return stats
