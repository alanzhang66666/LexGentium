"""File-based research pack loader. Later phases should not replace this with a database."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from .enums import DATASET_IDS, DatasetId
from .ids import PackIdentity, validate_cluster_id, validate_dataset_id, validate_document_id
from .packs import PackSummary, ResearchPack


class ResearchPackError(Exception):
    """Base error for disk pack access."""


class PackNotFoundError(ResearchPackError):
    pass


class PackVersionMismatchError(ResearchPackError):
    pass


def default_packs_root() -> Path:
    """``mock_court_system/data/research_packs``."""
    return Path(__file__).resolve().parents[2] / "data" / "research_packs"


class ResearchPackLoader:
    """List and load packs from ``data/research_packs/{dataset_id}/{cluster_id}/``."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root is not None else default_packs_root()

    def pack_dir(self, dataset_id: str, cluster_id: str) -> Path:
        dataset = validate_dataset_id(dataset_id)
        cluster = validate_cluster_id(cluster_id)
        return self.root / dataset / cluster

    def pack_json_path(self, dataset_id: str, cluster_id: str) -> Path:
        return self.pack_dir(dataset_id, cluster_id) / "pack.json"

    def document_path(self, dataset_id: str, cluster_id: str, document_id: str) -> Path:
        ordinal = validate_document_id(document_id)
        return self.pack_dir(dataset_id, cluster_id) / "documents" / f"{ordinal}.txt"

    def list_datasets(self) -> list[DatasetId]:
        if not self.root.exists():
            return []
        found: list[DatasetId] = []
        for entry in sorted(self.root.iterdir()):
            if entry.is_dir() and entry.name in DATASET_IDS:
                found.append(entry.name)  # type: ignore[arg-type]
        return found

    def list_packs(self, dataset_id: Optional[str] = None) -> list[PackSummary]:
        datasets: Iterable[str]
        if dataset_id is None:
            datasets = self.list_datasets()
        else:
            datasets = [validate_dataset_id(dataset_id)]
        summaries: list[PackSummary] = []
        for dataset in datasets:
            dataset_dir = self.root / dataset
            if not dataset_dir.is_dir():
                continue
            for cluster_dir in sorted(dataset_dir.iterdir()):
                if not cluster_dir.is_dir():
                    continue
                pack_file = cluster_dir / "pack.json"
                if not pack_file.is_file():
                    continue
                pack = self._read_pack_file(pack_file)
                summaries.append(
                    PackSummary(
                        dataset_id=pack.dataset_id,
                        cluster_id=pack.cluster_id,
                        pack_version=pack.pack_version,
                        task_type=pack.task_type,
                        case_name=pack.caption.case_name,
                        review_state=pack.review_state,
                        document_ids=[doc.document_id for doc in pack.documents],
                    )
                )
        return summaries

    def get_pack(
        self,
        dataset_id: str,
        cluster_id: str,
        pack_version: Optional[str] = None,
    ) -> ResearchPack:
        path = self.pack_json_path(dataset_id, cluster_id)
        if not path.is_file():
            raise PackNotFoundError(
                f"pack not found: dataset_id={dataset_id!r} cluster_id={cluster_id!r}"
            )
        pack = self._read_pack_file(path)
        if pack.dataset_id != dataset_id or pack.cluster_id != cluster_id:
            raise ResearchPackError(
                "pack.json identity does not match directory "
                f"({pack.dataset_id}/{pack.cluster_id} vs {dataset_id}/{cluster_id})"
            )
        if pack_version is not None and pack.pack_version != pack_version:
            raise PackVersionMismatchError(
                f"requested pack_version={pack_version!r}, file has {pack.pack_version!r}"
            )
        return pack

    def get_document_text(self, dataset_id: str, cluster_id: str, document_id: str) -> str:
        path = self.document_path(dataset_id, cluster_id, document_id)
        if not path.is_file():
            raise PackNotFoundError(
                f"document not found: {dataset_id}/{cluster_id}/{document_id}"
            )
        return path.read_text(encoding="utf-8")

    def list_document_ids(self, dataset_id: str, cluster_id: str) -> list[str]:
        pack = self.get_pack(dataset_id, cluster_id)
        return [doc.document_id for doc in pack.documents]

    def get_identity(self, dataset_id: str, cluster_id: str, pack_version: Optional[str] = None) -> PackIdentity:
        return self.get_pack(dataset_id, cluster_id, pack_version).pack_identity()

    def _read_pack_file(self, path: Path) -> ResearchPack:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ResearchPackError(f"invalid JSON: {path}") from exc
        return ResearchPack.model_validate(payload)
