"""
结果生成工具
生成提交格式的结果
"""
import json
import re
from typing import List, Dict, Any
from pathlib import Path


class ResultGenerator:
    """结果生成器"""

    def __init__(self, team_id: str = ""):
        self.team_id = team_id

    # ---------------------------
    # Internal helpers
    # ---------------------------

    @staticmethod
    def _is_valid_str(value: str) -> bool:
        return bool(value and value.strip())

    def _model_answer_is_valid(self, payload: Any) -> bool:
        """检查模型输出是否包含有效内容，若为空则跳过写入"""
        if payload is None:
            return False

        if isinstance(payload, str):
            return self._is_valid_str(payload)

        if isinstance(payload, dict):
            for _, val in payload.items():
                if val is None:
                    return False
                if isinstance(val, str) and not self._is_valid_str(val):
                    return False
                if isinstance(val, (list, tuple, set)):
                    if not val:
                        return False
                    # 对包含字符串的列表进行进一步检查
                    if all(isinstance(item, str) for item in val):
                        if not any(self._is_valid_str(item) for item in val):
                            return False
                if isinstance(val, dict) and not self._model_answer_is_valid(val):
                    return False
            return True

        if isinstance(payload, (list, tuple, set)):
            if not payload:
                return False
            return any(self._model_answer_is_valid(item) for item in payload)

        return True

    def create_cd_submission(
        self,
        case_id: str,
        dialog_history: List[Dict],
        complaint_text: str,
    ) -> Dict:
        """
        创建 CD 场景提交格式
        
        Args:
            case_id: 案例 ID
            dialog_history: 对话历史
            complaint_text: 起诉状文本
        
        Returns:
            提交格式的字典
        """
        return {
            "team_id": self.team_id,
            "case_id": case_id,
            "history": dialog_history,
            "model_answer": complaint_text,
        }

    def create_dd_submission(
        self,
        case_id: str,
        dialog_history: List[Dict],
        defense_text: str,
    ) -> Dict:
        """
        创建 DD 场景提交格式
        
        Args:
            case_id: 案例 ID
            dialog_history: 对话历史
            defense_text: 答辩状文本
        
        Returns:
            提交格式的字典
        """
        return {
            "team_id": self.team_id,
            "case_id": case_id,
            "history": dialog_history,
            "model_answer": defense_text,
        }

    def create_ci_submission(
        self,
        case_id: str,
        dialog_history: List[Dict],
        judgment: Dict[str, Any],
    ) -> Dict:
        """
        创建 CI 场景提交格式
        
        Args:
            case_id: 案例 ID
            dialog_history: 对话历史
            judgment: 判决信息（字典格式）
        
        Returns:
            提交格式的字典
        """
        return {
            "team_id": self.team_id,
            "case_id": case_id,
            "history": dialog_history,
            "model_answer": judgment,
        }

    def create_example_format_item(
        self,
        scenario: str,
        case_id: str,
        dialog_history: List[Dict],
    ) -> Dict:
        """
        创建案例格式的条目
        
        Args:
            scenario: 场景
            case_id: 案例 ID
            dialog_history: 对话历史
        
        Returns:
            案例格式的字典
        """
        return {
            "scenario": scenario,
            "team_id": self.team_id,
            "case_id": case_id,
            "dialog_history": dialog_history,
        }

    def clear_file(self, output_file: str):
        """
        清空输出文件
        
        Args:
            output_file: 输出文件路径
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            pass

    def append_submission(self, record: Dict, output_file: str):
        """
        追加提交结果 (直接追加模式，避免多进程读写冲突)
        注意：此方法不再进行去重和排序，以保证并发写入安全。
        
        Args:
            record: 单条记录
            output_file: 输出文件路径
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        model_answer = record.get("model_answer")
        if not self._model_answer_is_valid(model_answer):
            print(
                f"Skip writing case {record.get('case_id', 'UNKNOWN')} because model_answer is empty."
            )
            return

        try:
            # 使用 'a' 模式直接追加，避免读取-重写造成的竞态条件
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Error appending to output file: {e}")

    def save_submission(self, records: List[Dict], output_file: str):
        """
        保存提交结果
        
        Args:
            records: 记录列表
            output_file: 输出文件路径
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        print(f"✅ 提交结果已保存到: {output_path}")

    def sort_submission_by_case_id(self, output_file: str):
        """按照 case_id 对结果文件进行排序"""
        output_path = Path(output_file)
        if not output_path.exists():
            return

        try:
            records: List[Dict[str, Any]] = []
            with open(output_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        print("Warning: skip malformed record when sorting submissions")

            if not records:
                return

            def get_sort_key(item):
                case_id = item.get("case_id", "")
                # 提取ID中的数字部分用于排序
                numeric_part = re.search(r'\d+', str(case_id))
                if numeric_part:
                    return int(numeric_part.group())
                return -1 # or some other default for items without numbers

            records.sort(key=get_sort_key)

            with open(output_path, "w", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

            print(f"✅ 结果已按 case_id 排序: {output_path}")
        except Exception as e:
            print(f"Error sorting submission file: {e}")

    def save_example_format(self, records: List[Dict], output_file: str):
        """
        保存案例格式
        
        Args:
            records: 记录列表
            output_file: 输出文件路径
        """
        self.save_submission(records, output_file)
