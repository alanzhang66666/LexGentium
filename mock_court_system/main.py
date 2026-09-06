"""
主程序入口（批处理/实验脚本）

注意：此路径依赖远程法庭模拟服务（COURT_API_BASE_URL，须在 .env 显式配置），
属于历史实验管道；日常使用与演示请走 Web 服务（api_server.py），
Web 主路径由 SimAgent 本地模拟当事人，不依赖任何远程服务。
"""
import argparse
import sys
import os
import json
from typing import Set
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import settings
from core import CourtSimulatorClient, LLMClient
from utils import DataLoader, ResultGenerator, setup_logger
from agents import CDAgent, DDAgent, CIAgent


def get_processed_ids(file_path: Path) -> Set[str]:
    """获取已处理的案例 ID 集合"""
    processed_ids = set()
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if "case_id" in data:
                            processed_ids.add(str(data["case_id"]))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"读取已处理文件失败: {e}")
    return processed_ids


def run_cd_scenario(
    api_client: CourtSimulatorClient,
    llm: LLMClient,
    result_generator: ResultGenerator,
    data_loader: DataLoader,
    limit: int = None,
    range_str: str = None,
    verbose_override: bool = None,
):
    """运行 CD 场景（起诉状生成）"""
    logger.info("=" * 60)
    logger.info("开始运行 CD 场景（起诉状生成）")
    logger.info("=" * 60)

    # 获取场景配置
    scenario_config = settings.get_scenario_config("CD")

    # 创建智能体
    cd_agent = CDAgent(
        api_client=api_client,
        llm=llm,
        max_turns=scenario_config.max_turns,
        verbose=scenario_config.verbose if verbose_override is None else verbose_override,
    )

    # 加载测试数据
    test_data = data_loader.load_test_data("CD")
    
    if range_str:
        try:
            start, end = map(int, range_str.split(":"))
            # 1-based index to 0-based slice [start-1 : end-1]
            test_data = test_data[start-1:end-1]
            logger.info(f"应用范围过滤: {start}-{end-1} (选中 {len(test_data)} 个)")
        except Exception as e:
            logger.error(f"范围格式错误: {e}")
            return

    # 准备输出文件
    output_dir = Path(settings.data.output_dir)
    submission_file = output_dir / "CD_prediction.jsonl"
    
    # 获取已处理 ID 并过滤
    processed_ids = get_processed_ids(submission_file)
    if processed_ids:
        logger.info(f"发现 {len(processed_ids)} 个已处理案例，将跳过")
        test_data = [item for item in test_data if str(item.get("id", "")) not in processed_ids]

    if limit:
        test_data = test_data[:limit]

    if not test_data:
        logger.warning("没有需要处理的 CD 测试数据")
        return

    logger.info(f"将处理 {len(test_data)} 个测试案例")

    submission_records = []

    for idx, test_item in enumerate(test_data, 1):
        full_id = test_item.get("id", "")
        case_id = full_id.replace("CD-", "") if full_id.startswith("CD-") else full_id

        logger.info(f"\n[{idx}/{len(test_data)}] 处理案例: {full_id}")

        try:
            dialog_history, agent_payload = cd_agent.run_case(case_id)

            submission_item = result_generator.create_cd_submission(
                case_id=full_id,
                dialog_history=dialog_history.get_api_format(),
                complaint_text=agent_payload["model_answer"],
            )

            result_generator.append_submission(submission_item, str(submission_file))
            submission_records.append(submission_item)

            logger.info(
                f"  ✓ 完成案例 {case_id}，轮次 {agent_payload['metadata']['turns']}"
            )

            api_errors = agent_payload.get("metadata", {}).get("api_errors")
            if api_errors:
                logger.warning("    ⚠ API错误记录：")
                for err in api_errors:
                    logger.warning(f"      - {err}")

        except Exception as e:
            logger.error(f"  ✗ 处理案例 {case_id} 时出错: {e}")
            import traceback
            traceback.print_exc()

    logger.info(f"\n✅ CD 场景完成！处理了 {len(submission_records)} 个案例")


def run_dd_scenario(
    api_client: CourtSimulatorClient,
    llm: LLMClient,
    result_generator: ResultGenerator,
    data_loader: DataLoader,
    limit: int = None,
    range_str: str = None,
    verbose_override: bool = None,
):
    """运行 DD 场景（答辩状生成）"""
    logger.info("=" * 60)
    logger.info("开始运行 DD 场景（答辩状生成）")
    logger.info("=" * 60)

    # 获取场景配置
    scenario_config = settings.get_scenario_config("DD")

    # 创建智能体
    dd_agent = DDAgent(
        api_client=api_client,
        llm=llm,
        max_turns=scenario_config.max_turns,
        verbose=scenario_config.verbose if verbose_override is None else verbose_override,
    )

    # 加载测试数据
    test_data = data_loader.load_test_data("DD")
    
    if range_str:
        try:
            start, end = map(int, range_str.split(":"))
            test_data = test_data[start-1:end-1]
            logger.info(f"应用范围过滤: {start}-{end-1} (选中 {len(test_data)} 个)")
        except Exception as e:
            logger.error(f"范围格式错误: {e}")
            return

    # 准备输出文件
    output_dir = Path(settings.data.output_dir)
    submission_file = output_dir / "DD_prediction.jsonl"
    
    # 获取已处理 ID 并过滤
    processed_ids = get_processed_ids(submission_file)
    if processed_ids:
        logger.info(f"发现 {len(processed_ids)} 个已处理案例，将跳过")
        test_data = [item for item in test_data if str(item.get("id", "")) not in processed_ids]

    if limit:
        test_data = test_data[:limit]

    if not test_data:
        logger.warning("没有需要处理的 DD 测试数据")
        return

    logger.info(f"将处理 {len(test_data)} 个测试案例")

    submission_records = []

    for idx, test_item in enumerate(test_data, 1):
        full_id = test_item.get("id", "")
        case_id = full_id.replace("DD-", "") if full_id.startswith("DD-") else full_id

        logger.info(f"\n[{idx}/{len(test_data)}] 处理案例: {full_id}")

        try:
            # DD 场景需要传入 input_json
            dialog_history, agent_payload = dd_agent.run_case(
                case_id=case_id,
                input_json=test_item
            )

            submission_item = result_generator.create_dd_submission(
                case_id=full_id,
                dialog_history=dialog_history.get_api_format(),
                defense_text=agent_payload["model_answer"],
            )

            result_generator.append_submission(submission_item, str(submission_file))
            submission_records.append(submission_item)

            logger.info(
                f"  ✓ 完成案例 {case_id}，轮次 {agent_payload['metadata']['turns']}"
            )

        except Exception as e:
            logger.error(f"  ✗ 处理案例 {case_id} 时出错: {e}")
            import traceback
            traceback.print_exc()

    logger.info(f"\n✅ DD 场景完成！处理了 {len(submission_records)} 个案例")


def run_ci_scenario(
    api_client: CourtSimulatorClient,
    llm: LLMClient,
    result_generator: ResultGenerator,
    data_loader: DataLoader,
    limit: int = None,
    range_str: str = None,
    verbose_override: bool = None,
    parallel: int = 1,
):
    """运行 CI 场景（法庭判决）"""
    logger.info("=" * 60)
    logger.info("开始运行 CI 场景（法庭判决）")
    logger.info("=" * 60)

    # 获取场景配置
    scenario_config = settings.get_scenario_config("CI")

    # 加载测试数据
    test_data = data_loader.load_test_data("CI")
    
    if range_str:
        try:
            start, end = map(int, range_str.split(":"))
            test_data = test_data[start-1:end-1]
            logger.info(f"应用范围过滤: {start}-{end-1} (选中 {len(test_data)} 个)")
        except Exception as e:
            logger.error(f"范围格式错误: {e}")
            return

    # 准备输出文件
    output_dir = Path(settings.data.output_dir)
    submission_file = output_dir / "CI_prediction.jsonl"
    
    # 获取已处理 ID 并过滤
    processed_ids = get_processed_ids(submission_file)
    if processed_ids:
        logger.info(f"发现 {len(processed_ids)} 个已处理案例，将跳过")
        
        # 标准化已处理 ID：移除 SF-CI- 或 CI- 前缀，统一为纯数字 ID
        normalized_processed_ids = set()
        for pid in processed_ids:
            if pid.startswith("SF-CI-"):
                normalized_processed_ids.add(pid.replace("SF-CI-", ""))
            elif pid.startswith("CI-"):
                normalized_processed_ids.add(pid.replace("CI-", ""))
            else:
                normalized_processed_ids.add(pid)

        # CI 场景 ID 处理特殊，需要去掉前缀
        test_data = [
            item for item in test_data 
            if (item.get("id", "").replace("CI-", "") if item.get("id", "").startswith("CI-") else item.get("id", "")) not in normalized_processed_ids
        ]

    # 内存中去重，防止输入数据本身包含重复 ID
    unique_test_data = []
    seen_current_ids = set()
    for item in test_data:
        full_id = item.get("id", "")
        if full_id not in seen_current_ids:
            seen_current_ids.add(full_id)
            unique_test_data.append(item)
        else:
            logger.warning(f"发现重复的案例 ID: {full_id}，将跳过重复项")
    test_data = unique_test_data

    if limit:
        test_data = test_data[:limit]

    if not test_data:
        logger.warning("没有需要处理的 CI 测试数据")
        return

    logger.info(f"将处理 {len(test_data)} 个测试案例")

    def process_case(test_item):
        # 每个线程需要独立的 agent 实例，因为 agent 有内部状态
        local_agent = CIAgent(
            api_client=api_client,
            llm=llm,
            max_turns=scenario_config.max_turns,
            instruction_mode=scenario_config.instruction_mode,
            verbose=scenario_config.verbose if verbose_override is None else verbose_override,
        )
        
        full_id = test_item.get("id", "")
        case_id = full_id.replace("CI-", "") if full_id.startswith("CI-") else full_id
        
        logger.info(f"开始处理案例: {full_id}")
        
        try:
            dialog_history, agent_payload = local_agent.run_case(
                case_id=case_id,
                input_json=test_item
            )

            submission_item = result_generator.create_ci_submission(
                case_id=f"SF-CI-{case_id}",
                dialog_history=dialog_history.get_api_format(),
                judgment=agent_payload["model_answer"],
            )
            
            logger.info(f"  ✓ 完成案例 {case_id}，轮次 {agent_payload['metadata']['turns']}")
            return submission_item
        except Exception as e:
            logger.error(f"  ✗ 处理案例 {case_id} 时出错: {e}")
            import traceback
            traceback.print_exc()
            return None

    submission_records = []
    
    if parallel > 1:
        logger.info(f"启用并行处理，线程数: {parallel}")
        executor = ThreadPoolExecutor(max_workers=parallel)
        futures = []
        try:
            futures = [executor.submit(process_case, item) for item in test_data]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    result_generator.append_submission(result, str(submission_file))
                    submission_records.append(result)
        except KeyboardInterrupt:
            logger.warning("\n⚠️ 检测到用户中断 (Ctrl+C)，正在停止所有任务...")
            # 尝试取消所有未完成的任务
            for f in futures:
                f.cancel()
            
            # 尝试强制关闭
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                # Python < 3.9 不支持 cancel_futures
                executor.shutdown(wait=False)
            
            logger.warning("已停止。")
            # 使用 os._exit(1) 强制立即退出，不等待子线程结束
            os._exit(1)
        finally:
            # 确保资源释放 (正常结束时)
            executor.shutdown(wait=True)
    else:
        for test_item in test_data:
            result = process_case(test_item)
            if result:
                result_generator.append_submission(result, str(submission_file))
                submission_records.append(result)

    # 将结果文件按 case_id 排序，确保输出稳定
    result_generator.sort_submission_by_case_id(str(submission_file))

    logger.info(f"\n✅ CI 场景完成！处理了 {len(submission_records)} 个案例")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="模拟法庭多智能体系统")
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["CD", "DD", "CI"],
        help="运行指定场景 (CD/DD/CI)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="运行所有场景",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="限制处理的案例数量",
    )
    parser.add_argument(
        "--range",
        type=str,
        default=None,
        help="指定运行的案例范围 (例如 1:5 表示运行第1到第4个案例)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="配置文件路径",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="开启详细日志输出并强制代理 verbose 模式",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="启用本地 mock 模式，避免调用远端 API",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="并行运行的线程数 (默认为 1，即串行)",
    )
    parser.add_argument(
        "--use-reconstructor",
        action="store_true",
        help="启用API重建器（基于历史数据的最近邻匹配）",
    )
    parser.add_argument(
        "--reconstructor-data-dir",
        type=str,
        default="./api_history",
        help="API重建器的历史数据目录",
    )

    args = parser.parse_args()

    # 设置日志
    global logger
    log_level = settings.logging.level
    if args.verbose:
        log_level = "DEBUG"
    logger = setup_logger(
        level=log_level,
        log_file=settings.logging.file,
        log_format=settings.logging.format,
    )

    logger.info("模拟法庭多智能体系统启动")
    logger.info(f"配置文件: {args.config}")

    # 初始化组件
    api_client = CourtSimulatorClient(
        base_url=settings.api.base_url,
        api_key=settings.api.api_key,
        scenario_prefix=settings.api.scenario_prefix,
        timeout=settings.api.timeout,
        use_reconstructor=args.use_reconstructor,
        reconstructor_data_dir=args.reconstructor_data_dir,
    )

    # enable mock if requested
    if args.mock:
        # simple canned replies to help CI flow
        mock_responses = {
            "Plaintiff": "原告陈述：我主张如下……（证据A）",
            "Defendant": "被告答辩：我不同意原告诉求，理由是……（证据B）",
            "Client": "客户端：请开始。",
            "Judge": "审判长：现在开庭。对原告说：请陈述。",
        }
        api_client.enable_mock(mock_responses)

    llm = LLMClient(
        api_key=settings.llm.api_key,
        base_url=settings.llm.base_url,
        model=settings.llm.model,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        timeout=settings.llm.timeout,
        provider=settings.llm.provider,
    )
    # If mock requested, disable external LLM usage and enable mock behavior
    if args.mock:
        llm = LLMClient(
            api_key=None,
            base_url=None,
            model=None,
            temperature=0,
            max_tokens=512,
            timeout=5,
            provider="mock",
        )
        llm.enable_mock()

    result_generator = ResultGenerator(team_id=settings.team.team_id)

    # 使用相对于配置的数据目录
    data_loader = DataLoader(base_dir=settings.data.test_dir)

    # 健康检查
    health = api_client.health_check()
    logger.info(f"API 健康检查: {health}")

    # 运行场景
    if args.all:
        run_cd_scenario(api_client, llm, result_generator, data_loader, args.limit, args.range, args.verbose or None)
        run_dd_scenario(api_client, llm, result_generator, data_loader, args.limit, args.range, args.verbose or None)
        run_ci_scenario(api_client, llm, result_generator, data_loader, args.limit, args.range, args.verbose or None, parallel=args.parallel)
    elif args.scenario:
        scenario = args.scenario.upper()
        if scenario == "CD":
            run_cd_scenario(
                api_client, llm, result_generator, data_loader, args.limit, args.range, args.verbose or None
            )
        elif scenario == "DD":
            run_dd_scenario(
                api_client, llm, result_generator, data_loader, args.limit, args.range, args.verbose or None
            )
        elif scenario == "CI":
            run_ci_scenario(
                api_client, llm, result_generator, data_loader, args.limit, args.range, args.verbose or None, parallel=args.parallel
            )
    else:
        logger.error("请指定 --scenario 或 --all")
        parser.print_help()

    logger.info("程序执行完成")


if __name__ == "__main__":
    main()
