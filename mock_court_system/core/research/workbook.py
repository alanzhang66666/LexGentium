"""Read-only checks against the legal annotation workbook.

Legal staff keep writing Excel. This module never writes cells, never
fills NR/UV/NA/CF as “yes”, and never changes a legal conclusion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .enums import MISSING_CODES


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

DEFAULT_WORKBOOK = (
    Path(__file__).resolve().parents[3]
    / "法学材料"
    / "指南与工作簿"
    / "LexGentium_两组法律数据标注工作簿_v1.0.xlsx"
)

REQUIRED_SHEET_PREFIXES: tuple[str, ...] = (
    "00",
    "01",
    "03",
    "04",
    "05",
    "10",
    "12",
    "13",
    "14",
    "16",
    "20",
    "21",
    "22",
    "23",
)

# Chinese label → runtime token. Used when an importer later reads a row.
SPEAKER_FROM_WORKBOOK: dict[str, str] = {
    "申请人": "applicant",
    "被申请人": "respondent",
    "法院或仲裁庭": "tribunal",
    "其他主体": "other",
    "研究者": "researcher",
    "模型": "system",
    "NR": "NR",
    "UV": "UV",
}
SPEECH_FROM_WORKBOOK: dict[str, str] = {
    "当事人主张": "party_claim",
    "法院事实认定": "court_finding",
    "双方不争议事项": "undisputed",
    "裁判理由": "court_reasons",
    "裁判主文": "court_operative",
    "程序记载": "procedural_record",
    "研究判断": "researcher_judgment",
}
SUPPORT_FROM_WORKBOOK: dict[str, str] = {
    "原文直接记载": "direct",
    "原文间接支持": "indirect",
    "尚无材料支持": "unsupported",
    "来源冲突": "conflict",
}
ARGUMENT_KIND_FROM_WORKBOOK: dict[str, str] = {
    "历史主张": "historical",
    "研究重构": "researcher",
    "模型输出": "system",
    "教学示例": "teaching",
}
ARGUMENT_ACTION_FROM_WORKBOOK: dict[str, str] = {
    "首次提出": "first_raised",
    "维持": "maintain",
    "补充": "supplement",
    "修正": "correct",
    "撤回": "withdraw",
    "承认材料不足": "admit_insufficient",
}
VISIBILITY_FROM_WORKBOOK: dict[str, str] = {
    "可见": "visible",
    "不可见": "hidden",
    "阶段开放": "stage_open",
    "仅评价侧": "evaluator_only",
}
AVAILABILITY_FROM_WORKBOOK: dict[str, str] = {
    "已具备": "available",
    "自然缺失": "natural_missing",
    "人为遮蔽": "experimentally_hidden",
}
CONDITION_FROM_WORKBOOK: dict[str, str] = {
    "基线": "baseline",
    "增加反方意见": "add_counterparty",
    "材料遮蔽": "hide_materials",
    "引入来源核验": "enable_audit",
    "其他研究条件": "other",
}

_LABEL_MAPS: dict[str, dict[str, str]] = {
    "actor": SPEAKER_FROM_WORKBOOK,
    "nature": SPEECH_FROM_WORKBOOK,
    "support": SUPPORT_FROM_WORKBOOK,
    "argumentkind": ARGUMENT_KIND_FROM_WORKBOOK,
    "action": ARGUMENT_ACTION_FROM_WORKBOOK,
    "visibility": VISIBILITY_FROM_WORKBOOK,
    "availability": AVAILABILITY_FROM_WORKBOOK,
    "condition": CONDITION_FROM_WORKBOOK,
}


@dataclass(frozen=True)
class WorkbookIssue:
    severity: str
    code: str
    message: str
    sheet: str = ""
    cell: str = ""


@dataclass
class WorkbookReport:
    path: Path
    sheets: list[str] = field(default_factory=list)
    field_keys: list[str] = field(default_factory=list)
    issues: list[WorkbookIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[WorkbookIssue]:
        return [item for item in self.issues if item.severity == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors


def default_workbook_path() -> Path:
    return DEFAULT_WORKBOOK


def map_workbook_label(tag_set: str, value: str) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return None
    if tag_set == "missing" and text in MISSING_CODES:
        return text
    mapping = _LABEL_MAPS.get(tag_set, {})
    return mapping.get(text)


def _colrow(cell_ref: str) -> tuple[int, int]:
    col, row = "", ""
    for char in cell_ref:
        if char.isalpha():
            col += char
        else:
            row += char
    number = 0
    for char in col:
        number = number * 26 + (ord(char.upper()) - 64)
    return number, int(row)


def _cell_ref(col: int, row: int) -> str:
    name = ""
    current = col
    while current:
        current, rem = divmod(current - 1, 26)
        name = chr(65 + rem) + name
    return f"{name}{row}"


def _shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("m:si", NS):
        texts = [
            node.text or ""
            for node in item.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        ]
        values.append("".join(texts))
    return values


def _sheet_targets(archive: ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    sheets: list[tuple[str, str]] = []
    for sheet in workbook.findall("m:sheets/m:sheet", NS):
        name = sheet.attrib.get("name") or ""
        rid = sheet.attrib.get(f"{REL_NS}id") or ""
        target = rid_to_target.get(rid, "")
        target = target.lstrip("/")
        if target.startswith("worksheets/"):
            target = "xl/" + target
        elif target and not target.startswith("xl/"):
            target = "xl/" + target
        target = target.replace("xl/xl/", "xl/")
        sheets.append((name, target))
    return sheets


def _sheet_rows(archive: ZipFile, target: str, shared: list[str]) -> dict[int, dict[int, str]]:
    root = ET.fromstring(archive.read(target))
    rows: dict[int, dict[int, str]] = {}
    for cell in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
        ref = cell.attrib.get("r")
        if not ref:
            continue
        col, row = _colrow(ref)
        kind = cell.attrib.get("t")
        value_node = cell.find("m:v", NS)
        inline = cell.find("m:is", NS)
        text = ""
        if kind == "s" and value_node is not None and value_node.text:
            text = shared[int(value_node.text)]
        elif kind == "inlineStr" and inline is not None:
            text = "".join(
                node.text or ""
                for node in inline.iter(
                    "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
                )
            )
        elif value_node is not None and value_node.text:
            text = value_node.text
        rows.setdefault(row, {})[col] = text
    return rows


def _sheet_by_prefix(sheets: Iterable[tuple[str, str]], prefix: str) -> Optional[tuple[str, str]]:
    for name, target in sheets:
        if name.startswith(prefix):
            return name, target
    return None


def validate_workbook(path: Optional[Path] = None) -> WorkbookReport:
    workbook_path = Path(path) if path is not None else default_workbook_path()
    report = WorkbookReport(path=workbook_path)
    if not workbook_path.is_file():
        report.issues.append(
            WorkbookIssue(
                severity="error",
                code="workbook_missing",
                message=f"annotation workbook not found: {workbook_path}",
            )
        )
        return report

    with ZipFile(workbook_path) as archive:
        sheets = _sheet_targets(archive)
        report.sheets = [name for name, _ in sheets]
        shared = _shared_strings(archive)
        for prefix in REQUIRED_SHEET_PREFIXES:
            if _sheet_by_prefix(sheets, prefix) is None:
                report.issues.append(
                    WorkbookIssue(
                        severity="error",
                        code="sheet_missing",
                        message=f"required sheet prefix {prefix!r} is missing",
                        sheet=prefix,
                    )
                )

        dict_sheet = _sheet_by_prefix(sheets, "20")
        if dict_sheet:
            name, target = dict_sheet
            rows = _sheet_rows(archive, target, shared)
            header = rows.get(1, {})
            keys = [header.get(col, "").strip() for col in sorted(header)]
            if "字段键" not in keys:
                report.issues.append(
                    WorkbookIssue(
                        severity="error",
                        code="dictionary_header",
                        message="sheet 20 must have a 字段键 column",
                        sheet=name,
                        cell="1",
                    )
                )
            field_keys: list[str] = []
            for row_num, cols in sorted(rows.items()):
                if row_num == 1:
                    continue
                key = (cols.get(3) or "").strip()
                if key:
                    field_keys.append(key)
            report.field_keys = field_keys
            if "raw_locator" not in field_keys:
                report.issues.append(
                    WorkbookIssue(
                        severity="error",
                        code="dictionary_raw_locator",
                        message="sheet 20 must include raw_locator",
                        sheet=name,
                    )
                )

        tags_sheet = _sheet_by_prefix(sheets, "21")
        if tags_sheet:
            name, target = tags_sheet
            rows = _sheet_rows(archive, target, shared)
            missing_values: list[str] = []
            seen_sets: dict[str, list[str]] = {}
            for row_num, cols in sorted(rows.items()):
                if row_num == 1:
                    continue
                tag_set = (cols.get(1) or "").strip()
                allowed = (cols.get(3) or "").strip()
                if not tag_set or not allowed:
                    continue
                seen_sets.setdefault(tag_set, []).append(allowed)
                if tag_set == "missing":
                    missing_values.append(allowed)
                    cell = _cell_ref(3, row_num)
                    if allowed not in MISSING_CODES:
                        report.issues.append(
                            WorkbookIssue(
                                severity="error",
                                code="unknown_missing_code",
                                message=f"missing code {allowed!r} is not NR/UV/NA/CF",
                                sheet=name,
                                cell=cell,
                            )
                        )
            if tuple(missing_values) != MISSING_CODES:
                report.issues.append(
                    WorkbookIssue(
                        severity="error",
                        code="missing_codes",
                        message=f"sheet 21 missing set must be {MISSING_CODES}, got {tuple(missing_values)}",
                        sheet=name,
                    )
                )
            for tag_set, mapping in _LABEL_MAPS.items():
                workbook_values = set(seen_sets.get(tag_set, []))
                mapped = set(mapping)
                extra = workbook_values - mapped
                missing = mapped - workbook_values
                if extra:
                    report.issues.append(
                        WorkbookIssue(
                            severity="warning",
                            code="unmapped_label",
                            message=f"tag set {tag_set} has unmapped values {sorted(extra)}",
                            sheet=name,
                        )
                    )
                if missing:
                    report.issues.append(
                        WorkbookIssue(
                            severity="warning",
                            code="unused_runtime_label",
                            message=f"tag set {tag_set} runtime tokens not in workbook {sorted(missing)}",
                            sheet=name,
                        )
                    )
    return report


def validate_workbook_or_raise(path: Optional[Path] = None) -> WorkbookReport:
    report = validate_workbook(path)
    if not report.ok:
        first = report.errors[0]
        location = f"{first.sheet} {first.cell}".strip()
        raise ValueError(f"{first.code}: {first.message} ({location})")
    return report
