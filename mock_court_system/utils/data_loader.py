"""
数据加载工具
加载测试集和案例数据
"""
import json
import jsonlines
from pathlib import Path
from typing import List, Dict, Optional


class DataLoader:
    """数据加载器"""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir) if base_dir else Path(".")

    def load_jsonl(self, file_path: str) -> List[Dict]:
        """
        加载 JSONL 文件
        
        Args:
            file_path: 文件路径
        
        Returns:
            数据列表
        """
        data = []
        path = Path(file_path)
        if not path.is_absolute():
            path = self.base_dir / path

        if not path.exists():
            print(f"⚠️ 文件不存在: {path}")
            return []

        try:
            with jsonlines.open(path, "r") as reader:
                for obj in reader:
                    data.append(obj)
        except Exception as e:
            # 尝试按普通 JSON Lines 格式读取
            print(f"⚠️ jsonlines 读取失败，尝试普通方式: {e}")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            data.append(json.loads(line))
            except Exception as e2:
                print(f"❌ 读取失败: {e2}")
                return []

        return data

    def load_test_data(self, scenario: str) -> List[Dict]:
        """
        加载测试数据
        
        Args:
            scenario: 场景 (CD/DD/CI)
        
        Returns:
            测试数据列表
        """
        test_file_map = {
            "CD": "CD_test.jsonl",
            "DD": "DD_test.jsonl",
            "CI": "CI_test.jsonl",
        }

        filename = test_file_map.get(scenario.upper())
        if not filename:
            print(f"❌ 未知场景: {scenario}")
            return []

        # 尝试多个可能的路径
        possible_paths = [
            self.base_dir / filename,
            self.base_dir / "测试集" / filename,
            self.base_dir / ".." / "模拟法庭-初赛-数据集" / "测试集" / filename,
            Path("D:/CAIL/模拟法庭/cail2025_智能体模拟法庭-复赛阶段-数据集") / filename,
        ]

        for path in possible_paths:
            if path.exists():
                return self.load_jsonl(str(path.resolve()))

        print(f"❌ 未找到测试文件: {filename}")
        print(f"   尝试的路径: {[str(p) for p in possible_paths]}")
        return []

    def load_example_data(self, scenario: str) -> List[Dict]:
        """
        加载案例数据
        
        Args:
            scenario: 场景 (CD/DD/CI)
        
        Returns:
            案例数据列表
        """
        example_file_map = {
            "CD": "CD_example.jsonl",
            "DD": "DD_example.jsonl",
            "CI": "CI_example.jsonl",
        }

        filename = example_file_map.get(scenario.upper())
        if not filename:
            print(f"❌ 未知场景: {scenario}")
            return []

        # 尝试多个可能的路径
        possible_paths = [
            self.base_dir / filename,
            self.base_dir / "案例数据" / filename,
            self.base_dir / ".." / "模拟法庭-初赛-数据集" / "案例数据" / filename,
        ]

        for path in possible_paths:
            if path.exists():
                return self.load_jsonl(str(path.resolve()))

        print(f"❌ 未找到案例文件: {filename}")
        return []

    def save_jsonl(self, data: List[Dict], file_path: str):
        """
        保存为 JSONL 文件
        
        Args:
            data: 数据列表
            file_path: 文件路径
        """
        path = Path(file_path)
        if not path.is_absolute():
            path = self.base_dir / path

        # 确保目录存在
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        print(f"✅ 数据已保存到: {path}")
