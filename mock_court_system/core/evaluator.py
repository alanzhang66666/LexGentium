"""
API模拟器评测框架
支持与标准答案比对，计算各种评测指标
"""
import json
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from collections import defaultdict
import jieba
from datetime import datetime


@dataclass
class EvaluationResult:
    """单次评测结果"""
    case_id: str
    scenario: str
    turn: int
    input_dialog: List[Dict]
    expected_response: str
    actual_response: str
    similarity_score: float
    method_used: str  # "nearest_neighbor", "llm_generation", "hybrid"
    match_status: str  # "exact", "similar", "different"
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ScenarioMetrics:
    """场景级别的评测指标"""
    scenario: str
    total_cases: int
    total_turns: int
    exact_matches: int
    similar_matches: int
    different_matches: int
    avg_similarity: float
    method_distribution: Dict[str, int]
    avg_similarity_by_method: Dict[str, float]
    
    @property
    def exact_match_rate(self) -> float:
        return self.exact_matches / self.total_turns if self.total_turns > 0 else 0.0
    
    @property
    def similar_match_rate(self) -> float:
        return (self.exact_matches + self.similar_matches) / self.total_turns if self.total_turns > 0 else 0.0
    
    def to_dict(self) -> Dict:
        return {
            "scenario": self.scenario,
            "total_cases": self.total_cases,
            "total_turns": self.total_turns,
            "exact_matches": self.exact_matches,
            "similar_matches": self.similar_matches,
            "different_matches": self.different_matches,
            "exact_match_rate": self.exact_match_rate,
            "similar_match_rate": self.similar_match_rate,
            "avg_similarity": self.avg_similarity,
            "method_distribution": self.method_distribution,
            "avg_similarity_by_method": self.avg_similarity_by_method,
        }


class APISimulatorEvaluator:
    """API模拟器评测器"""
    
    def __init__(
        self,
        similarity_threshold_exact: float = 0.95,
        similarity_threshold_similar: float = 0.7,
    ):
        """
        初始化评测器
        
        Args:
            similarity_threshold_exact: 完全匹配的相似度阈值
            similarity_threshold_similar: 相似匹配的相似度阈值
        """
        self.similarity_threshold_exact = similarity_threshold_exact
        self.similarity_threshold_similar = similarity_threshold_similar
    
    def evaluate_single_response(
        self,
        expected: str,
        actual: str,
        method_used: str = "unknown",
    ) -> EvaluationResult:
        """
        评测单个回复
        
        Args:
            expected: 期望的回复（标准答案）
            actual: 实际的回复
            method_used: 使用的方法
        
        Returns:
            评测结果
        """
        similarity = self._calculate_similarity(expected, actual)
        
        if similarity >= self.similarity_threshold_exact:
            match_status = "exact"
        elif similarity >= self.similarity_threshold_similar:
            match_status = "similar"
        else:
            match_status = "different"
        
        return EvaluationResult(
            case_id="",
            scenario="",
            turn=0,
            input_dialog=[],
            expected_response=expected,
            actual_response=actual,
            similarity_score=similarity,
            method_used=method_used,
            match_status=match_status,
        )
    
    def evaluate_case(
        self,
        case_id: str,
        scenario: str,
        standard_dialog: List[Dict],
        simulator_func,
        input_json: Optional[Dict] = None,
    ) -> List[EvaluationResult]:
        """
        评测单个案例
        
        Args:
            case_id: 案例ID
            scenario: 场景标识
            standard_dialog: 标准对话历史（包含期望的回复）
            simulator_func: 模拟器函数，接受(scenario, case_id, dialog_history, input_json)返回response
            input_json: 案例输入信息
        
        Returns:
            评测结果列表
        """
        results = []
        
        # 遍历标准对话，逐步构建输入并评测
        current_dialog = []
        
        for i, turn in enumerate(standard_dialog):
            role = turn.get("role", "")
            message = turn.get("message", "")
            
            # 如果是API应该回复的角色（Client/Plaintiff/Defendant）
            if self._is_api_response_role(role, scenario):
                # 当前对话历史作为输入
                input_dialog = current_dialog.copy()
                
                # 调用模拟器生成回复
                try:
                    api_response = simulator_func(
                        scenario=scenario,
                        case_id=case_id,
                        dialog_history=input_dialog,
                        input_json=input_json,
                    )
                    
                    actual_response = api_response.get("response", "")
                    method_used = api_response.get("_method", api_response.get("_reconstructed", "unknown"))
                    if method_used == True:
                        method_used = "nearest_neighbor"
                    
                    # 评测
                    similarity = self._calculate_similarity(message, actual_response)
                    
                    if similarity >= self.similarity_threshold_exact:
                        match_status = "exact"
                    elif similarity >= self.similarity_threshold_similar:
                        match_status = "similar"
                    else:
                        match_status = "different"
                    
                    result = EvaluationResult(
                        case_id=case_id,
                        scenario=scenario,
                        turn=i,
                        input_dialog=input_dialog,
                        expected_response=message,
                        actual_response=actual_response,
                        similarity_score=similarity,
                        method_used=str(method_used),
                        match_status=match_status,
                    )
                    results.append(result)
                    
                except Exception as e:
                    # 生成失败
                    result = EvaluationResult(
                        case_id=case_id,
                        scenario=scenario,
                        turn=i,
                        input_dialog=input_dialog,
                        expected_response=message,
                        actual_response=f"[ERROR: {str(e)}]",
                        similarity_score=0.0,
                        method_used="error",
                        match_status="different",
                    )
                    results.append(result)
            
            # 添加到当前对话历史
            current_dialog.append(turn)
        
        return results
    
    def evaluate_dataset(
        self,
        dataset: List[Dict],
        simulator_func,
        scenarios: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        评测整个数据集
        
        Args:
            dataset: 数据集，每项包含case_id, scenario, dialog_history, input_json等
            simulator_func: 模拟器函数
            scenarios: 要评测的场景列表（None表示所有场景）
        
        Returns:
            评测报告字典
        """
        all_results = []
        scenario_results = defaultdict(list)
        
        print(f"开始评测数据集，共 {len(dataset)} 个案例...")
        
        for idx, case_data in enumerate(dataset, 1):
            case_id = case_data.get("case_id", f"case_{idx}")
            scenario = case_data.get("scenario", "")
            dialog_history = case_data.get("dialog_history", [])
            input_json = case_data.get("input_json", None)
            
            if scenarios and scenario not in scenarios:
                continue
            
            print(f"  评测案例 {idx}/{len(dataset)}: {case_id} ({scenario})")
            
            # 评测单个案例
            case_results = self.evaluate_case(
                case_id=case_id,
                scenario=scenario,
                standard_dialog=dialog_history,
                simulator_func=simulator_func,
                input_json=input_json,
            )
            
            all_results.extend(case_results)
            scenario_results[scenario].extend(case_results)
        
        # 计算指标
        metrics = self._calculate_metrics(all_results, scenario_results)
        
        return {
            "evaluation_time": datetime.now().isoformat(),
            "total_cases": len(dataset),
            "total_turns": len(all_results),
            "overall_metrics": metrics["overall"],
            "scenario_metrics": metrics["scenarios"],
            "detailed_results": [r.to_dict() for r in all_results],
        }
    
    def _calculate_metrics(
        self,
        all_results: List[EvaluationResult],
        scenario_results: Dict[str, List[EvaluationResult]],
    ) -> Dict[str, Any]:
        """计算评测指标"""
        # 总体指标
        total_turns = len(all_results)
        exact_matches = sum(1 for r in all_results if r.match_status == "exact")
        similar_matches = sum(1 for r in all_results if r.match_status == "similar")
        different_matches = sum(1 for r in all_results if r.match_status == "different")
        avg_similarity = sum(r.similarity_score for r in all_results) / total_turns if total_turns > 0 else 0.0
        
        # 方法分布
        method_distribution = defaultdict(int)
        method_similarities = defaultdict(list)
        for r in all_results:
            method_distribution[r.method_used] += 1
            method_similarities[r.method_used].append(r.similarity_score)
        
        avg_similarity_by_method = {
            method: sum(scores) / len(scores) if scores else 0.0
            for method, scores in method_similarities.items()
        }
        
        overall_metrics = {
            "total_turns": total_turns,
            "exact_matches": exact_matches,
            "similar_matches": similar_matches,
            "different_matches": different_matches,
            "exact_match_rate": exact_matches / total_turns if total_turns > 0 else 0.0,
            "similar_match_rate": (exact_matches + similar_matches) / total_turns if total_turns > 0 else 0.0,
            "avg_similarity": avg_similarity,
            "method_distribution": dict(method_distribution),
            "avg_similarity_by_method": avg_similarity_by_method,
        }
        
        # 场景级别指标
        scenario_metrics = {}
        for scenario, results in scenario_results.items():
            total = len(results)
            exact = sum(1 for r in results if r.match_status == "exact")
            similar = sum(1 for r in results if r.match_status == "similar")
            different = sum(1 for r in results if r.match_status == "different")
            avg_sim = sum(r.similarity_score for r in results) / total if total > 0 else 0.0
            
            method_dist = defaultdict(int)
            method_sims = defaultdict(list)
            for r in results:
                method_dist[r.method_used] += 1
                method_sims[r.method_used].append(r.similarity_score)
            
            avg_sim_by_method = {
                method: sum(scores) / len(scores) if scores else 0.0
                for method, scores in method_sims.items()
            }
            
            scenario_metrics[scenario] = ScenarioMetrics(
                scenario=scenario,
                total_cases=len(set(r.case_id for r in results)),
                total_turns=total,
                exact_matches=exact,
                similar_matches=similar,
                different_matches=different,
                avg_similarity=avg_sim,
                method_distribution=dict(method_dist),
                avg_similarity_by_method=avg_sim_by_method,
            ).to_dict()
        
        return {
            "overall": overall_metrics,
            "scenarios": scenario_metrics,
        }
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度"""
        if not text1 or not text2:
            return 0.0
        
        # 使用Jaccard相似度
        tokens1 = set(jieba.cut(text1))
        tokens2 = set(jieba.cut(text2))
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        
        jaccard = intersection / union if union > 0 else 0.0
        
        # 结合编辑距离相似度
        edit_sim = self._edit_similarity(text1, text2)
        
        # 综合相似度
        return (jaccard * 0.6 + edit_sim * 0.4)
    
    def _edit_similarity(self, text1: str, text2: str) -> float:
        """计算编辑距离相似度"""
        if not text1 or not text2:
            return 0.0
        
        if text1 == text2:
            return 1.0
        
        # 简化的编辑距离计算
        len1, len2 = len(text1), len(text2)
        max_len = max(len1, len2)
        
        if max_len == 0:
            return 1.0
        
        # 计算最长公共子序列长度
        lcs = self._lcs_length(text1, text2)
        
        return lcs / max_len
    
    def _lcs_length(self, s1: str, s2: str) -> int:
        """计算最长公共子序列长度"""
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        
        return dp[m][n]
    
    def _is_api_response_role(self, role: str, scenario: str) -> bool:
        """判断角色是否是API应该回复的角色"""
        if scenario in ["CD", "DD"]:
            return role == "Client"
        elif scenario == "CI":
            return role in ["Plaintiff", "Defendant"]
        return False
    
    def save_report(self, report: Dict, output_path: str):
        """保存评测报告"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n评测报告已保存到: {output_file}")
    
    def print_summary(self, report: Dict):
        """打印评测摘要"""
        print("\n" + "=" * 60)
        print("评测摘要")
        print("=" * 60)
        
        overall = report["overall_metrics"]
        print(f"\n总体指标:")
        print(f"  总轮次: {overall['total_turns']}")
        print(f"  完全匹配: {overall['exact_matches']} ({overall['exact_match_rate']*100:.1f}%)")
        print(f"  相似匹配: {overall['similar_matches']} (累计: {overall['similar_match_rate']*100:.1f}%)")
        print(f"  不同匹配: {overall['different_matches']}")
        print(f"  平均相似度: {overall['avg_similarity']:.3f}")
        
        print(f"\n方法分布:")
        for method, count in overall['method_distribution'].items():
            avg_sim = overall['avg_similarity_by_method'].get(method, 0.0)
            print(f"  {method}: {count} 次 (平均相似度: {avg_sim:.3f})")
        
        print(f"\n场景指标:")
        for scenario, metrics in report["scenario_metrics"].items():
            print(f"\n  {scenario}:")
            print(f"    案例数: {metrics['total_cases']}")
            print(f"    总轮次: {metrics['total_turns']}")
            print(f"    完全匹配率: {metrics['exact_match_rate']*100:.1f}%")
            print(f"    相似匹配率: {metrics['similar_match_rate']*100:.1f}%")
            print(f"    平均相似度: {metrics['avg_similarity']:.3f}")

