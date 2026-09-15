"""
评测混合API模拟器方案
使用标准答案数据集进行评测
"""
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from settings import settings
from core import CourtSimulatorClient, LLMClient
from core.offline import APIReconstructor, HybridAPISimulator, LLMAPISimulator
from core.offline.evaluator import APISimulatorEvaluator
from utils import DataLoader


def load_standard_dataset(data_dir: str, scenarios: List[str] = None) -> List[Dict]:
    """
    加载标准答案数据集
    
    Args:
        data_dir: 数据目录
        scenarios: 要加载的场景列表（None表示所有场景）
    
    Returns:
        标准答案数据集
    """
    data_loader = DataLoader(base_dir=data_dir)
    dataset = []
    
    target_scenarios = scenarios or ["CD", "DD", "CI"]
    
    for scenario in target_scenarios:
        # 加载测试数据（包含标准答案的dialog_history）
        test_data = data_loader.load_test_data(scenario)
        
        if not test_data:
            print(f"警告: 未找到 {scenario} 场景的测试数据")
            continue
        
        print(f"加载 {scenario} 场景: {len(test_data)} 个案例")
        
        # 转换为评测格式
        for item in test_data:
            case_id = item.get("id", "")
            dialog_history = item.get("dialog_history", [])
            input_json = item.get("input_json", None)
            
            if dialog_history:
                dataset.append({
                    "case_id": case_id,
                    "scenario": scenario,
                    "dialog_history": dialog_history,
                    "input_json": input_json,
                })
    
    return dataset


def create_hybrid_simulator(
    use_reconstructor: bool = True,
    use_llm: bool = True,
    hybrid_threshold: float = 0.7,
) -> CourtSimulatorClient:
    """
    创建混合API模拟器
    
    Args:
        use_reconstructor: 是否使用最近邻重建器
        use_llm: 是否使用LLM生成
        hybrid_threshold: 混合方案的相似度阈值
    
    Returns:
        API客户端（配置了混合模拟器）
    """
    # 初始化LLM
    llm = None
    llm_simulator = None
    
    if use_llm:
        llm = LLMClient(
            api_key=settings.llm.api_key,
            base_url=settings.llm.base_url,
            model=settings.llm.model,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
            timeout=settings.llm.timeout,
            provider=settings.llm.provider,
        )
        llm_simulator = LLMAPISimulator(llm=llm, scenario="CD")
    
    # 创建API客户端
    api_client = CourtSimulatorClient(
        base_url="http://invalid-url",  # 无效URL，强制使用模拟器
        api_key="",  # 无API key
        use_reconstructor=use_reconstructor,
        reconstructor_data_dir="./api_history",
        use_llm_simulator=use_llm and llm_simulator is not None,
        llm_simulator=llm_simulator,
        use_hybrid=use_reconstructor and use_llm,
        hybrid_threshold=hybrid_threshold,
    )
    
    return api_client


def simulator_wrapper(api_client: CourtSimulatorClient):
    """
    创建模拟器包装函数，用于评测框架
    
    Args:
        api_client: API客户端
    
    Returns:
        模拟器函数
    """
    def simulate(
        scenario: str,
        case_id: str,
        dialog_history: List[Dict],
        input_json: Optional[Dict] = None,
    ) -> Dict:
        """模拟器函数"""
        if scenario == "CD":
            return api_client.simulate_cd(case_id=case_id, dialog_history=dialog_history)
        elif scenario == "DD":
            return api_client.simulate_dd(case_id=case_id, dialog_history=dialog_history)
        elif scenario == "CI":
            return api_client.simulate_ci(case_id=case_id, dialog_history=dialog_history)
        else:
            return {"response": "", "error": f"Unknown scenario: {scenario}"}
    
    return simulate


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="评测混合API模拟器方案")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="标准答案数据集目录（默认使用config中的test_dir）",
    )
    parser.add_argument(
        "--scenarios",
        type=str,
        nargs="+",
        default=["CD", "DD", "CI"],
        help="要评测的场景列表",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./evaluation_results",
        help="评测结果输出目录",
    )
    parser.add_argument(
        "--use-reconstructor",
        action="store_true",
        default=True,
        help="使用最近邻重建器",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        default=True,
        help="使用LLM生成",
    )
    parser.add_argument(
        "--hybrid-threshold",
        type=float,
        default=0.7,
        help="混合方案的相似度阈值",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="限制评测的案例数量（用于快速测试）",
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("混合API模拟器评测")
    print("=" * 60)
    
    # 确定数据目录
    data_dir = args.data_dir or settings.data.test_dir
    print(f"数据目录: {data_dir}")
    print(f"评测场景: {args.scenarios}")
    print(f"混合阈值: {args.hybrid_threshold}")
    print("=" * 60)
    
    # 加载标准答案数据集
    print("\n加载标准答案数据集...")
    dataset = load_standard_dataset(data_dir, args.scenarios)
    
    if not dataset:
        print("错误: 未加载到任何标准答案数据")
        return
    
    print(f"共加载 {len(dataset)} 个案例")
    
    # 限制数量（如果指定）
    if args.limit:
        dataset = dataset[:args.limit]
        print(f"限制为前 {args.limit} 个案例")
    
    # 创建混合模拟器
    print("\n初始化混合API模拟器...")
    api_client = create_hybrid_simulator(
        use_reconstructor=args.use_reconstructor,
        use_llm=args.use_llm,
        hybrid_threshold=args.hybrid_threshold,
    )
    
    # 创建模拟器包装函数
    simulator_func = simulator_wrapper(api_client)
    
    # 创建评测器
    evaluator = APISimulatorEvaluator(
        similarity_threshold_exact=0.95,
        similarity_threshold_similar=0.7,
    )
    
    # 执行评测
    print("\n开始评测...")
    report = evaluator.evaluate_dataset(
        dataset=dataset,
        simulator_func=simulator_func,
        scenarios=args.scenarios,
    )
    
    # 打印摘要
    evaluator.print_summary(report)
    
    # 保存报告
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = report["evaluation_time"].replace(":", "-").split(".")[0]
    report_file = output_dir / f"evaluation_report_{timestamp}.json"
    
    evaluator.save_report(report, str(report_file))
    
    # 保存简要报告（文本格式）
    summary_file = output_dir / f"evaluation_summary_{timestamp}.txt"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("混合API模拟器评测报告\n")
        f.write("=" * 60 + "\n\n")
        
        overall = report["overall_metrics"]
        f.write(f"总体指标:\n")
        f.write(f"  总轮次: {overall['total_turns']}\n")
        f.write(f"  完全匹配: {overall['exact_matches']} ({overall['exact_match_rate']*100:.1f}%)\n")
        f.write(f"  相似匹配: {overall['similar_matches']} (累计: {overall['similar_match_rate']*100:.1f}%)\n")
        f.write(f"  不同匹配: {overall['different_matches']}\n")
        f.write(f"  平均相似度: {overall['avg_similarity']:.3f}\n\n")
        
        f.write(f"方法分布:\n")
        for method, count in overall['method_distribution'].items():
            avg_sim = overall['avg_similarity_by_method'].get(method, 0.0)
            f.write(f"  {method}: {count} 次 (平均相似度: {avg_sim:.3f})\n")
        
        f.write(f"\n场景指标:\n")
        for scenario, metrics in report["scenario_metrics"].items():
            f.write(f"\n  {scenario}:\n")
            f.write(f"    案例数: {metrics['total_cases']}\n")
            f.write(f"    总轮次: {metrics['total_turns']}\n")
            f.write(f"    完全匹配率: {metrics['exact_match_rate']*100:.1f}%\n")
            f.write(f"    相似匹配率: {metrics['similar_match_rate']*100:.1f}%\n")
            f.write(f"    平均相似度: {metrics['avg_similarity']:.3f}\n")
    
    print(f"\n简要报告已保存到: {summary_file}")
    print("\n评测完成！")


if __name__ == "__main__":
    main()

