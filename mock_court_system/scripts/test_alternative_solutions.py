"""
测试替代API方案
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core import CourtSimulatorClient, LLMClient, APIReconstructor, LLMAPISimulator, HybridAPISimulator
from config import settings


def test_llm_simulator():
    """测试LLM模拟器"""
    print("=" * 60)
    print("测试LLM API模拟器")
    print("=" * 60)
    
    # 初始化LLM
    llm = LLMClient(
        api_key=settings.llm.api_key,
        base_url=settings.llm.base_url,
        model=settings.llm.model,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        timeout=settings.llm.timeout,
        provider=settings.llm.provider,
    )
    
    # 创建LLM模拟器
    llm_simulator = LLMAPISimulator(llm=llm, scenario="CD")
    
    # 测试输入
    test_dialog_history = [
        {"turn": 0, "role": "Client", "message": "您好，我想要起草起诉状。"},
        {"turn": 1, "role": "Lawyer", "message": "您好，我是您的代理律师。为了帮您起草文件，我们需要先核实双方的基本信息。请先告诉我您的姓名、性别、出生日期和民族？"},
    ]
    
    print("\n测试输入:")
    for item in test_dialog_history:
        print(f"  {item['role']}: {item['message']}")
    
    # 生成回复
    result = llm_simulator.generate_response(
        scenario="CD",
        case_id="test_001",
        dialog_history=test_dialog_history,
    )
    
    print("\n生成结果:")
    print(f"  响应: {result.get('response', '')[:200]}...")
    if result.get("error"):
        print(f"  错误: {result['error']}")


def test_hybrid_simulator():
    """测试混合模拟器"""
    print("\n" + "=" * 60)
    print("测试混合API模拟器")
    print("=" * 60)
    
    # 初始化组件
    reconstructor = APIReconstructor(data_dir="./api_history")
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
    
    # 创建混合模拟器
    hybrid_simulator = HybridAPISimulator(
        reconstructor=reconstructor,
        llm_simulator=llm_simulator,
        similarity_threshold=0.7,
    )
    
    # 测试输入（高相似度）
    test_dialog_history = [
        {"turn": 0, "role": "Client", "message": "您好，我想要起草起诉状。"},
        {"turn": 1, "role": "Lawyer", "message": "您好，我是您的代理律师。为了帮您起草文件，我们需要先核实双方的基本信息。请先告诉我您的姓名、性别、出生日期和民族？"},
    ]
    
    print("\n测试输入（高相似度）:")
    for item in test_dialog_history:
        print(f"  {item['role']}: {item['message']}")
    
    # 生成回复
    result = hybrid_simulator.generate_response(
        scenario="CD",
        case_id="test_001",
        dialog_history=test_dialog_history,
    )
    
    print("\n生成结果:")
    print(f"  方法: {result.get('_method', 'unknown')}")
    print(f"  相似度: {result.get('_similarity', 0):.3f}")
    print(f"  响应: {result.get('response', '')[:200]}...")


def test_api_client_integration():
    """测试API客户端集成"""
    print("\n" + "=" * 60)
    print("测试API客户端集成（混合模式）")
    print("=" * 60)
    
    # 初始化LLM和重建器
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
    
    # 创建API客户端（使用混合模式）
    api_client = CourtSimulatorClient(
        base_url="http://invalid-url",
        api_key="",
        use_reconstructor=True,
        reconstructor_data_dir="./api_history",
        use_llm_simulator=True,
        llm_simulator=llm_simulator,
        use_hybrid=True,
        hybrid_threshold=0.7,
    )
    
    # 测试输入
    test_dialog_history = [
        {"turn": 0, "role": "Client", "message": "您好，我想要起草起诉状。"},
        {"turn": 1, "role": "Lawyer", "message": "您好，我是您的代理律师。为了帮您起草文件，我们需要先核实双方的基本信息。请先告诉我您的姓名、性别、出生日期和民族？"},
    ]
    
    # 调用
    result = api_client.simulate_cd(
        case_id="test_001",
        dialog_history=test_dialog_history,
    )
    
    print("\nAPI客户端结果:")
    print(f"  方法: {result.get('_method', result.get('_reconstructed', 'unknown'))}")
    print(f"  响应: {result.get('response', '')[:200]}...")


if __name__ == "__main__":
    # 测试LLM模拟器
    try:
        test_llm_simulator()
    except Exception as e:
        print(f"LLM模拟器测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试混合模拟器
    try:
        test_hybrid_simulator()
    except Exception as e:
        print(f"混合模拟器测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试API客户端集成
    try:
        test_api_client_integration()
    except Exception as e:
        print(f"API客户端集成测试失败: {e}")
        import traceback
        traceback.print_exc()

