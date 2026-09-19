"""Research Governance：FormalReviewV2 与 Pack Codec（design §11，Task 7.2）。

- 两个 SAMPLE 固定 ``technical_fixture``，永不计入正式研究包。
- formal 资格要求完整 ``FormalReviewRecordV2`` 五字段（独立复核人、
  时间戳、被复核 pack_version、outcome=approved、被复核内容 digest）
  且 digest 与当前 pack 内容一致。
- PackCodec 提供严格 parse/pretty-print/register/compare；unknown 与
  anchor 状态在往返中保持不变。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Literal, Optional, Tuple

from .packs import ResearchPack

try:  # core/__init__ 依赖重（LLM/jieba）；单独导入 research 包时用本地实现
    from core.fingerprint import canonical_digest  # type: ignore
except Exception:  # pragma: no cover

    def canonical_digest(obj: Any) -> str:
        return hashlib.sha256(
            json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()

PackClassification = Literal["technical_fixture", "formal", "candidate"]
ReviewOutcome = Literal["approved", "rejected", "changes_required"]

#: 固定技术夹具身份（inventory.yaml 声明；不自动注册为 formal）
TECHNICAL_FIXTURE_CLUSTER_IDS = frozenset(
    {"enf-cn-notice-001", "cisg-art79-sample-001"}
)


class GovernanceError(Exception):
    """治理违规：缺字段复核、fixture 冒充 formal、digest 不匹配等。"""


@dataclass(frozen=True)
class FormalReviewRecordV2:
    """独立复核记录 V2：五字段齐全才能支撑 formal 资格。"""

    independent_reviewer_id: str
    review_timestamp: str
    reviewed_pack_version: str
    outcome: str  # approved|rejected|changes_required
    reviewed_content_digest: str

    def is_complete(self) -> bool:
        return all(
            [
                self.independent_reviewer_id.strip(),
                self.review_timestamp.strip(),
                self.reviewed_pack_version.strip(),
                self.outcome in ("approved", "rejected", "changes_required"),
                self.reviewed_content_digest.strip(),
            ]
        )


def pack_content_digest(pack: ResearchPack) -> str:
    """pack 内容 canonical digest（不含易变索引字段）。"""
    return canonical_digest(pack.model_dump(mode="json"))


def classify_pack(
    pack: ResearchPack,
    reviews: Iterable[FormalReviewRecordV2] = (),
) -> PackClassification:
    """technical_fixture > formal（完整 approved 复核）> candidate。"""
    if pack.cluster_id in TECHNICAL_FIXTURE_CLUSTER_IDS:
        return "technical_fixture"
    if is_formal_eligible(pack, reviews):
        return "formal"
    return "candidate"


def is_formal_eligible(
    pack: ResearchPack,
    reviews: Iterable[FormalReviewRecordV2],
) -> bool:
    """恰一条完整 approved V2 复核绑定当前版本与内容 digest。"""
    digest = pack_content_digest(pack)
    for record in reviews:
        if not record.is_complete():
            continue
        if record.outcome != "approved":
            continue
        if record.reviewed_pack_version != pack.pack_version:
            continue
        if record.reviewed_content_digest != digest:
            continue
        return True
    return False


def formal_pack_count(
    packs: Iterable[Tuple[ResearchPack, Iterable[FormalReviewRecordV2]]],
) -> int:
    """正式研究包数：只有 classify == formal 才计入。"""
    return sum(
        1 for pack, reviews in packs if classify_pack(pack, reviews) == "formal"
    )


def summarize_pack_inventory(packs: Iterable[dict]) -> dict:
    """列表级治理摘要：就地写 classification，返回计数。

    无 formal pack 时 ``formal_status == "no_formal_pack"`` —— 调用方
    不得回退选择 SAMPLE 夹具。
    """
    packs = list(packs)
    for pack in packs:
        pack["classification"] = (
            "technical_fixture"
            if pack.get("cluster_id") in TECHNICAL_FIXTURE_CLUSTER_IDS
            else "candidate"
        )
    formal = sum(1 for p in packs if p["classification"] == "formal")
    return {
        "formal_pack_count": formal,
        "formal_status": "ok" if formal else "no_formal_pack",
        "fixture_count": sum(1 for p in packs if p["classification"] == "technical_fixture"),
        "candidate_count": sum(1 for p in packs if p["classification"] == "candidate"),
    }


class PackCodec:
    """严格 parse/pretty-print/register/compare。"""

    @staticmethod
    def parse(text: str) -> ResearchPack:
        """严格解析：schema/identity/锚点不一致即抛错。"""
        return ResearchPack.model_validate_json(text)

    @staticmethod
    def pretty_print(pack: ResearchPack) -> str:
        """canonical JSON 输出；往返保持全部字段含 unknown/anchor 状态。"""
        return json.dumps(
            pack.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            indent=1,
        )

    @staticmethod
    def register(
        pack: ResearchPack,
        reviews: Iterable[FormalReviewRecordV2] = (),
    ) -> dict:
        """注册入口：返回 identity + classification；fixture 不可注册为 formal。"""
        classification = classify_pack(pack, reviews)
        return {
            "dataset_id": pack.dataset_id,
            "cluster_id": pack.cluster_id,
            "pack_version": pack.pack_version,
            "classification": classification,
            "formal_eligible": classification == "formal",
            "content_digest": pack_content_digest(pack),
        }

    @staticmethod
    def compare(a: ResearchPack, b: ResearchPack) -> bool:
        """语义比较：canonical digest 相等。"""
        return pack_content_digest(a) == pack_content_digest(b)

    @staticmethod
    def round_trip(text: str) -> str:
        """parse → pretty_print；测试用不变量通道。"""
        return PackCodec.pretty_print(PackCodec.parse(text))
