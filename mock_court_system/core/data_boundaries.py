"""Civil / Research 数据分轨分类器与导入边界（design.md §11）。

- 以显式 schema discriminator 区分 ``civil_case/v1`` 与 ``research_pack/v1``，
  不以文件路径猜测。
- 两个 import boundary 在 parse 前后都验证 discriminator；错轨返回
  ``wrong_data_track``（映射 422），两条轨的 State_Fingerprint 都不变。
- 评测命名空间固定分轨：``civil.lexeval|civil.j1|civil.cadd`` 与
  ``research.<rubric_version>``。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

from core.research.enums import CIVIL_DATASET_ID, DATASET_IDS, TASK_TYPES

TRACK_CIVIL = "civil"
TRACK_RESEARCH = "research"
TRACK_UNKNOWN = "unknown"

CIVIL_DISCRIMINATOR = "civil_case/v1"
RESEARCH_DISCRIMINATOR = "research_pack/v1"

#: 评测命名空间分轨
CIVIL_EVAL_NAMESPACES = ("civil.lexeval", "civil.j1", "civil.cadd")
RESEARCH_EVAL_NAMESPACE_PREFIX = "research."


def research_eval_namespace(rubric_version: str) -> str:
    return f"{RESEARCH_EVAL_NAMESPACE_PREFIX}{rubric_version}"


def eval_track_of_namespace(namespace: str) -> str:
    if namespace in CIVIL_EVAL_NAMESPACES:
        return TRACK_CIVIL
    if namespace.startswith(RESEARCH_EVAL_NAMESPACE_PREFIX):
        return TRACK_RESEARCH
    return TRACK_UNKNOWN


class WrongDataTrackError(Exception):
    """提交内容属于另一条数据轨；对应 HTTP 422 ``wrong_data_track``。"""

    code = "wrong_data_track"

    def __init__(self, expected_track: str, actual_track: str):
        super().__init__(
            f"wrong data track: expected {expected_track}, got {actual_track}"
        )
        self.expected_track = expected_track
        self.actual_track = actual_track


_DISCRIMINATOR_KEYS = ("data_track", "record_kind", "schema_kind", "track")

#: civil payload 结构信号（无显式 discriminator 时按 schema 形状判断）
_RESEARCH_STRUCT_KEYS = {"cluster_id", "pack_version", "task_type", "visible_materials"}
_CIVIL_STRUCT_KEYS = {"case_id", "cause", "case_description", "plaintiff_claims"}


class DataBoundaryClassifier:
    """按显式 discriminator（优先）与 schema 形状（兜底）分类数据轨。"""

    def classify(self, payload: Any) -> str:
        if not isinstance(payload, Mapping):
            return TRACK_UNKNOWN

        declared = self._declared_discriminator(payload)
        if declared == CIVIL_DISCRIMINATOR:
            return TRACK_CIVIL
        if declared == RESEARCH_DISCRIMINATOR:
            return TRACK_RESEARCH
        if declared is not None:
            # 声明了但未识别的 discriminator：不得猜测归轨
            return TRACK_UNKNOWN

        dataset_id = payload.get("dataset_id")
        if dataset_id == CIVIL_DATASET_ID:
            return TRACK_CIVIL
        if dataset_id in DATASET_IDS:
            return TRACK_RESEARCH
        if payload.get("task_type") in TASK_TYPES:
            return TRACK_RESEARCH
        if _RESEARCH_STRUCT_KEYS.issubset(payload.keys()):
            return TRACK_RESEARCH
        if _CIVIL_STRUCT_KEYS.issubset(payload.keys()):
            return TRACK_CIVIL
        return TRACK_UNKNOWN

    def assert_track(self, payload: Any, expected_track: str) -> str:
        """验证 payload 属于 expected_track；错轨抛 ``WrongDataTrackError``。"""
        actual = self.classify(payload)
        if actual != expected_track:
            raise WrongDataTrackError(expected_track, actual)
        return actual

    @staticmethod
    def _declared_discriminator(payload: Mapping) -> Optional[str]:
        for key in _DISCRIMINATOR_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None


@dataclass(frozen=True)
class ImportBoundary:
    """单侧导入边界：parse 前后两次验证 discriminator，错轨拒绝且零写入。"""

    expected_track: str
    classifier: DataBoundaryClassifier = DataBoundaryClassifier()

    def validate_before_parse(self, payload: Any) -> str:
        """parse 前验证：显式 discriminator 错轨立即拒绝。"""
        return self.classifier.assert_track(payload, self.expected_track)

    def validate_after_parse(self, parsed: Any) -> str:
        """parse 后验证：结构化结果仍需属于本轨。"""
        payload = parsed if isinstance(parsed, Mapping) else getattr(parsed, "__dict__", parsed)
        if hasattr(parsed, "model_dump"):
            payload = parsed.model_dump()
        return self.classifier.assert_track(payload, self.expected_track)


CIVIL_IMPORT_BOUNDARY = ImportBoundary(expected_track=TRACK_CIVIL)
RESEARCH_IMPORT_BOUNDARY = ImportBoundary(expected_track=TRACK_RESEARCH)


def session_has_research_identity(session_input: Optional[Mapping]) -> bool:
    """会话输入是否携带研究身份（dataset/cluster/pack_version/run_id）。"""
    if not session_input:
        return False
    research = session_input.get("research")
    if isinstance(research, Mapping):
        return any(research.get(k) for k in ("dataset_id", "cluster_id", "pack_version", "run_id"))
    return False


def assert_no_research_context(session_input: Optional[Mapping]) -> None:
    """无研究身份的 civil session 不得出现 research context/标识。"""
    if not session_input:
        return
    if "research" in session_input and not session_has_research_identity(session_input):
        raise WrongDataTrackError(TRACK_CIVIL, TRACK_RESEARCH)
