"""Research layer on top of CD/DD/CI: protocols, material views, derived runs, cache.

Does not rewrite the civil state machine. Civil sessions without a research pack
are a no-op.
"""
from __future__ import annotations

import hashlib
import json
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional
from uuid import uuid4

from .base import strip_reference
from .visibility import (
    apply_visibility_grants,
    experiment_hidden_source_ids,
    natural_missing_source_ids,
    resolve_stage,
)
from .enums import (
    REFERENCE_FIELD,
    ROLE_APPLICANT,
    ROLE_AUDITOR,
    ROLE_CLAIMANT,
    ROLE_EVALUATOR,
    ROLE_RESPONDENT,
    ROLE_TRIBUNAL,
    ROLE_VIEW_EXCLUDED_FIELDS,
    StopReason,
    TaskType,
)

RESEARCH_DISCLAIMER = (
    "本仿真仅说明系统在既定实验条件下的表现；"
    "关于司法实践的判断仍须以真实裁判文书为依据。"
)

CLAIM_ACTIONS: tuple[str, ...] = (
    "assert",
    "ground",
    "rebut",
    "supplement",
    "revise",
    "withdraw",
    "admit_insufficient",
)
POST_REBUTTAL_ACTIONS: tuple[str, ...] = (
    "supplement",
    "revise",
    "withdraw",
    "admit_insufficient",
)
TRIAD_REQUIRED_ACTIONS: tuple[str, ...] = ("assert", "ground", "supplement", "revise")

CACHE_MODE_REPLAY = "replay"
CACHE_MODE_INDEPENDENT = "independent"

HIDDEN_KEYS = frozenset(ROLE_VIEW_EXCLUDED_FIELDS) | {
    REFERENCE_FIELD,
    "gold_labels",
    "acceptable_paths",
}

_ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    "Plaintiff": (ROLE_APPLICANT, ROLE_CLAIMANT),
    "plaintiff": (ROLE_APPLICANT, ROLE_CLAIMANT),
    "Client": (ROLE_APPLICANT, ROLE_CLAIMANT),
    "client": (ROLE_APPLICANT, ROLE_CLAIMANT),
    "Lawyer": (ROLE_APPLICANT, ROLE_CLAIMANT),
    "lawyer": (ROLE_APPLICANT, ROLE_CLAIMANT),
    "Defendant": (ROLE_RESPONDENT,),
    "defendant": (ROLE_RESPONDENT,),
    "Judge": (ROLE_TRIBUNAL,),
    "judge": (ROLE_TRIBUNAL,),
    "Final": (ROLE_TRIBUNAL,),
    "tribunal": (ROLE_TRIBUNAL,),
    "申请人": (ROLE_APPLICANT, ROLE_CLAIMANT),
    "被申请人": (ROLE_RESPONDENT,),
    "申请人律师": (ROLE_APPLICANT,),
    "被申请人律师": (ROLE_RESPONDENT,),
    "仲裁庭": (ROLE_TRIBUNAL,),
    "审判长": (ROLE_TRIBUNAL,),
    "claimant": (ROLE_CLAIMANT, ROLE_APPLICANT),
    ROLE_APPLICANT: (ROLE_APPLICANT, ROLE_CLAIMANT),
    ROLE_CLAIMANT: (ROLE_CLAIMANT, ROLE_APPLICANT),
    ROLE_RESPONDENT: (ROLE_RESPONDENT,),
    ROLE_TRIBUNAL: (ROLE_TRIBUNAL,),
    ROLE_AUDITOR: (ROLE_AUDITOR,),
    ROLE_EVALUATOR: (ROLE_EVALUATOR,),
}

_LIST_MATERIAL_FIELDS = (
    "documents",
    "procedural_facts",
    "party_claims",
    "court_findings",
    "legal_bases",
    "material_gaps",
    "source_anchors",
    "argument_records",
    "evidence_links",
    "rules",
)


@dataclass(frozen=True)
class RoleProtocol:
    role: str
    duties: tuple[str, ...]
    turn_order: int
    stop_conditions: tuple[str, ...]
    visible_material_kinds: tuple[str, ...] = (
        "documents",
        "procedural_facts",
        "party_claims",
        "legal_bases",
        "rules",
        "source_anchors",
        "material_gaps",
    )


@dataclass(frozen=True)
class TaskConfig:
    task_type: TaskType
    roles: tuple[RoleProtocol, ...]
    turn_order: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    max_argument_turns: int = 12

    def protocol_for(self, role: str) -> Optional[RoleProtocol]:
        canon = canonical_research_role(role, self.task_type)
        for entry in self.roles:
            if entry.role == canon:
                return entry
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "turn_order": list(self.turn_order),
            "stop_conditions": list(self.stop_conditions),
            "max_argument_turns": self.max_argument_turns,
            "roles": [
                {
                    "role": item.role,
                    "duties": list(item.duties),
                    "turn_order": item.turn_order,
                    "stop_conditions": list(item.stop_conditions),
                    "visible_material_kinds": list(item.visible_material_kinds),
                }
                for item in self.roles
            ],
        }


ENFORCEMENT_NYC = TaskConfig(
    task_type="enforcement_nyc",
    turn_order=(ROLE_APPLICANT, ROLE_RESPONDENT, ROLE_TRIBUNAL, ROLE_AUDITOR),
    stop_conditions=(
        "completed",
        "max_turns",
        "material_insufficient",
        "aborted",
    ),
    max_argument_turns=12,
    roles=(
        RoleProtocol(
            role=ROLE_APPLICANT,
            turn_order=0,
            duties=(
                "主张承认与执行，并同时给出事实依据、规范依据与推理",
                "对反驳作出补充、修正、撤回或承认材料不足，不得空言坚持",
                "不得使用对照层 reference / 隐藏答案",
            ),
            stop_conditions=("admit_insufficient", "withdraw", "max_turns"),
        ),
        RoleProtocol(
            role=ROLE_RESPONDENT,
            turn_order=1,
            duties=(
                "针对申请提出抗辩，主张须带事实、规范与推理",
                "反驳须指向对方具体主张",
                "材料不足时承认不足，不得编造送达或到庭事实",
            ),
            stop_conditions=("admit_insufficient", "withdraw", "max_turns"),
        ),
        RoleProtocol(
            role=ROLE_TRIBUNAL,
            turn_order=2,
            duties=(
                "按设定轮次主持双方论证，核对主张是否有依据",
                "在材料不足或轮次用尽时停止，并记录停止原因",
                "不把仿真步骤写成某一法域的真实审查程序",
            ),
            stop_conditions=("completed", "material_insufficient", "max_turns"),
        ),
        RoleProtocol(
            role=ROLE_AUDITOR,
            turn_order=3,
            duties=(
                "核验引用是否落在角色可见原文上",
                "标记未知、冲突与材料缺口，禁止回填",
            ),
            stop_conditions=("completed", "aborted"),
        ),
    ),
)

CISG_ARTICLE79 = TaskConfig(
    task_type="cisg_article79",
    turn_order=(ROLE_CLAIMANT, ROLE_RESPONDENT, ROLE_TRIBUNAL, ROLE_AUDITOR),
    stop_conditions=("completed", "max_turns", "material_insufficient", "aborted"),
    max_argument_turns=10,
    roles=(
        RoleProtocol(
            role=ROLE_CLAIMANT,
            turn_order=0,
            duties=(
                "围绕第 79 条要素主张免责或请求，须带事实、规范与推理",
                "反驳后须补充、修正、撤回或承认材料不足",
            ),
            stop_conditions=("admit_insufficient", "withdraw", "max_turns"),
        ),
        RoleProtocol(
            role=ROLE_RESPONDENT,
            turn_order=1,
            duties=("针对第 79 条要素抗辩，主张须带事实、规范与推理",),
            stop_conditions=("admit_insufficient", "withdraw", "max_turns"),
        ),
        RoleProtocol(
            role=ROLE_TRIBUNAL,
            turn_order=2,
            duties=("按要素主持论证并记录停止原因",),
            stop_conditions=("completed", "material_insufficient", "max_turns"),
        ),
        RoleProtocol(
            role=ROLE_AUDITOR,
            turn_order=3,
            duties=("核验引用与未知标记",),
            stop_conditions=("completed", "aborted"),
        ),
    ),
)

_TASK_CONFIGS: dict[str, TaskConfig] = {
    "enforcement_nyc": ENFORCEMENT_NYC,
    "cisg_article79": CISG_ARTICLE79,
}


@dataclass(frozen=True)
class ResearchCallContext:
    run_id: str
    role: str
    materials_hash: str
    cache_mode: str = CACHE_MODE_REPLAY
    attempt_id: str = ""
    visible_document_ids: frozenset[str] = field(default_factory=frozenset)
    visible_source_ids: frozenset[str] = field(default_factory=frozenset)
    visible_rule_ids: frozenset[str] = field(default_factory=frozenset)
    hide_source_ids: frozenset[str] = field(default_factory=frozenset)


_research_ctx: ContextVar[Optional[ResearchCallContext]] = ContextVar(
    "research_call_context", default=None
)


def get_task_config(task_type: Optional[str]) -> Optional[TaskConfig]:
    if not task_type:
        return None
    return _TASK_CONFIGS.get(str(task_type))


def canonical_research_role(role: Optional[str], task_type: Optional[str] = None) -> str:
    raw = (role or "").strip()
    if not raw:
        if task_type == "cisg_article79":
            return ROLE_CLAIMANT
        return ROLE_APPLICANT
    aliases = _ROLE_ALIASES.get(raw, (raw,))
    if task_type == "cisg_article79":
        if ROLE_CLAIMANT in aliases:
            return ROLE_CLAIMANT
        if ROLE_APPLICANT in aliases:
            return ROLE_CLAIMANT
    if task_type == "enforcement_nyc" and ROLE_CLAIMANT in aliases and ROLE_APPLICANT in aliases:
        return ROLE_APPLICANT
    return aliases[0]


def research_block(input_json: Optional[dict[str, Any]]) -> dict[str, Any]:
    raw = (input_json or {}).get("research")
    return raw if isinstance(raw, dict) else {}


def has_research(input_json: Optional[dict[str, Any]]) -> bool:
    block = research_block(input_json)
    return bool(block.get("run_id") and block.get("dataset_id") and block.get("cluster_id"))


def hash_payload(payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def strip_hidden_fields(payload: Any) -> Any:
    """Drop reference / gold answers anywhere in a nested payload."""
    if isinstance(payload, dict):
        return {
            key: strip_hidden_fields(value)
            for key, value in payload.items()
            if key not in HIDDEN_KEYS
        }
    if isinstance(payload, list):
        return [strip_hidden_fields(item) for item in payload]
    return payload


def _as_id_set(values: Any) -> set[str]:
    if not values:
        return set()
    return {str(item) for item in values if str(item).strip()}


def resolve_visible_materials(
    research: dict[str, Any],
    role: str,
    stage: Optional[str] = None,
) -> dict[str, list[str]]:
    empty = {"document_ids": [], "source_ids": [], "rule_ids": []}
    canon = canonical_research_role(role, research.get("task_type"))
    current_stage = resolve_stage(research, stage)
    table = research.get("visible_materials") or {}
    if not isinstance(table, dict):
        table = {}
    base = empty
    if canon == ROLE_EVALUATOR:
        auditor = table.get(ROLE_AUDITOR)
        base = dict(auditor) if isinstance(auditor, dict) else empty
    else:
        aliases = _ROLE_ALIASES.get(role, (canon,))
        for key in (canon, *aliases, role):
            row = table.get(key)
            if isinstance(row, dict):
                base = {
                    "document_ids": list(row.get("document_ids") or []),
                    "source_ids": list(row.get("source_ids") or []),
                    "rule_ids": list(row.get("rule_ids") or []),
                }
                break
    granted = apply_visibility_grants(
        base,
        research.get("visibility_grants") or [],
        role=canon,
        stage=current_stage,
    )
    hidden = _hide_source_ids(research)
    granted["source_ids"] = [item for item in granted["source_ids"] if item not in hidden]
    return granted


def _hide_source_ids(research: dict[str, Any]) -> set[str]:
    return experiment_hidden_source_ids(research) | natural_missing_source_ids(research)


def _item_source_ids(item: dict[str, Any]) -> set[str]:
    ids = _as_id_set(item.get("source_ids"))
    if item.get("source_id"):
        ids.add(str(item["source_id"]))
    return ids


def _item_document_id(item: dict[str, Any]) -> str:
    return str(item.get("document_id") or "")


def _item_visible(
    item: dict[str, Any],
    *,
    documents: set[str],
    sources: set[str],
    rules: set[str],
    hidden: set[str],
) -> bool:
    item_sources = _item_source_ids(item)
    if item_sources & hidden:
        return False
    doc = _item_document_id(item)
    rule = str(item.get("rule_id") or "")
    if rule and rule not in rules:
        return False
    if doc and doc not in documents:
        return False
    if item_sources and not item_sources.issubset(sources):
        return False
    # Unanchored text has no auditable basis for being exposed to a role.
    return bool(item_sources or doc or rule)


def filter_materials_for_role(
    research: dict[str, Any],
    role: str,
    stage: Optional[str] = None,
) -> dict[str, Any]:
    """Role-visible pack slice. Never includes reference or hidden answers."""
    cleaned = strip_hidden_fields(strip_reference(research))
    visible = resolve_visible_materials(research, role, stage=stage)
    hidden = _hide_source_ids(research)
    documents = _as_id_set(visible.get("document_ids"))
    sources = _as_id_set(visible.get("source_ids")) - hidden
    rules = _as_id_set(visible.get("rule_ids"))

    filtered = dict(cleaned)
    for field_name in _LIST_MATERIAL_FIELDS:
        rows = cleaned.get(field_name)
        if not isinstance(rows, list):
            continue
        kept: list[Any] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if field_name == "documents":
                doc_id = str(row.get("document_id") or "")
                if not doc_id or doc_id not in documents:
                    continue
                kept.append(dict(row))
                continue
            if field_name == "source_anchors":
                source_id = str(row.get("source_id") or "")
                if not source_id or source_id in hidden or source_id not in sources:
                    continue
                if _item_document_id(row) and _item_document_id(row) not in documents:
                    continue
                kept.append(dict(row))
                continue
            if field_name == "evidence_links":
                kept.append(dict(row))
                continue
            if field_name == "rules":
                if not _item_visible(
                    row, documents=documents, sources=sources, rules=rules, hidden=hidden
                ):
                    continue
                kept.append(dict(row))
                continue
            if _item_visible(
                row, documents=documents, sources=sources, rules=rules, hidden=hidden
            ):
                kept.append(dict(row))
        filtered[field_name] = kept

    labels = filtered.get("task_labels")
    if isinstance(labels, dict):
        labels = dict(labels)
        for key, values in list(labels.items()):
            if isinstance(values, list) and values and all(isinstance(row, dict) for row in values):
                labels[key] = [
                    dict(row)
                    for row in values
                    if _item_visible(
                        row, documents=documents, sources=sources, rules=rules, hidden=hidden
                    )
                ]
        filtered["task_labels"] = labels

    kept_ids: set[str] = set()
    for field_name in _LIST_MATERIAL_FIELDS:
        for row in filtered.get(field_name) or []:
            if not isinstance(row, dict):
                continue
            for key in ("item_id", "argument_id", "gap_id", "source_id", "rule_id", "document_id"):
                if row.get(key):
                    kept_ids.add(str(row[key]))
    labels = filtered.get("task_labels")
    if isinstance(labels, dict):
        for event in labels.get("notice_events") or []:
            if isinstance(event, dict) and event.get("event_id"):
                kept_ids.add(str(event["event_id"]))
        for row in labels.get("judgments") or []:
            if isinstance(row, dict) and row.get("judgment_id"):
                kept_ids.add(str(row["judgment_id"]))
    links = filtered.get("evidence_links")
    if isinstance(links, list):
        filtered["evidence_links"] = [
            dict(link)
            for link in links
            if isinstance(link, dict)
            and str(link.get("object_id") or "") in kept_ids
            and str(link.get("evidence_id") or "") in kept_ids
        ]

    filtered["visible_materials"] = {
        canonical_research_role(role, research.get("task_type")): {
            "document_ids": sorted(documents),
            "source_ids": sorted(sources),
            "rule_ids": sorted(rules),
        }
    }
    return strip_hidden_fields(filtered)


def filter_retrieval_snippets(
    snippets: Optional[Iterable[Any]],
    ctx: Optional[ResearchCallContext] = None,
) -> list[Any]:
    """Drop snippets that cite hidden docs/sources or leak reference text."""
    context = ctx or current_research_context()
    rows = list(snippets or [])
    if context is None:
        return rows

    kept: list[Any] = []
    for item in rows:
        if _snippet_leaks_reference(item):
            continue
        if not isinstance(item, dict):
            continue
        doc = str(item.get("document_id") or "")
        sources = _item_source_ids(item)
        rule = str(item.get("rule_id") or "")
        if sources and (sources & context.hide_source_ids or not sources.issubset(context.visible_source_ids)):
            continue
        if doc and doc not in context.visible_document_ids:
            continue
        if rule and rule not in context.visible_rule_ids:
            continue
        if not (sources or doc or rule):
            continue
        kept.append(item)
    return kept


def _snippet_leaks_reference(item: Any) -> bool:
    text = ""
    if isinstance(item, dict):
        if any(key in item for key in HIDDEN_KEYS):
            return True
        text = " ".join(
            str(item.get(key) or "")
            for key in ("content", "quote", "text", "excerpt", "law")
        )
    else:
        text = str(item)
    markers = ("gold_labels", "acceptable_paths", "本层不得写入", '"reference"')
    return any(marker in text for marker in markers)


def filter_shared_memory_text(text: Optional[str], ctx: Optional[ResearchCallContext] = None) -> str:
    """Summaries / shared memory must not carry hidden answers."""
    value = text or ""
    if not value:
        return ""
    if _snippet_leaks_reference(value):
        return ""
    context = ctx or current_research_context()
    if context is None:
        return value
    for source_id in context.hide_source_ids:
        if source_id and source_id in value:
            value = value.replace(source_id, "[hidden-source]")
    return value


def project_visible_case_fields(filtered: dict[str, Any]) -> dict[str, Any]:
    """Map a role view onto the civil-shaped keys agents already read."""
    caption = filtered.get("caption") if isinstance(filtered.get("caption"), dict) else {}
    documents = [
        doc for doc in (filtered.get("documents") or []) if isinstance(doc, dict)
    ]
    texts = [str(doc.get("text") or "").strip() for doc in documents]
    texts = [text for text in texts if text]
    facts = [
        str(item.get("value") or "").strip()
        for item in (filtered.get("procedural_facts") or [])
        if isinstance(item, dict) and str(item.get("value") or "").strip()
    ]
    claims = [
        str(item.get("claim_text") or "").strip()
        for item in (filtered.get("party_claims") or [])
        if isinstance(item, dict) and str(item.get("claim_text") or "").strip()
    ]
    case_name = str(caption.get("case_name") or filtered.get("cluster_id") or "")
    description = "\n\n".join(texts) if texts else "\n".join(facts)
    applicant = "申请人"
    respondent = "被申请人"
    if filtered.get("task_type") == "cisg_article79":
        applicant = "卖方/主张方"
        respondent = "相对方"
    return {
        "case_description": description,
        "claim_description": "；".join(claims) or description[:800],
        "plaintiff_claims": claims,
        "plaintiff_name": applicant,
        "defendant_name": respondent,
        "case_type": case_name or str(filtered.get("task_type") or ""),
        "third_party_findings": description,
        "plaintiff_info": {"name": applicant},
        "defendant_info": {"name": respondent},
        "case_info": {
            "case_id": filtered.get("cluster_id"),
            "case_name": case_name,
            "facts": facts,
        },
    }


def role_model_input(
    input_json: Optional[dict[str, Any]],
    role: Optional[str] = None,
) -> dict[str, Any]:
    """Agent / prompt payload. Civil path is unchanged when there is no research pack."""
    payload = dict(input_json or {})
    payload.pop(REFERENCE_FIELD, None)
    if not has_research(payload):
        return strip_hidden_fields(payload)

    research = research_block(payload)
    canon = canonical_research_role(role, research.get("task_type"))
    filtered = filter_materials_for_role(research, canon)
    projected = project_visible_case_fields(filtered)
    session_id = payload.get("_session_id")
    out = strip_hidden_fields(payload)
    out.update(projected)
    out["research"] = filtered
    if session_id:
        out["_session_id"] = session_id
    return out


def material_context_message(
    filtered_input: dict[str, Any], role: Optional[str] = None
) -> Optional[dict[str, Any]]:
    research = research_block(filtered_input)
    if not research:
        return None
    description = str(filtered_input.get("case_description") or "").strip()
    if not description:
        return None
    protocol = get_task_config(research.get("task_type"))
    duties = []
    if protocol:
        active_role = role
        if not active_role:
            visible = research.get("visible_materials")
            if isinstance(visible, dict) and len(visible) == 1:
                active_role = next(iter(visible))
        if active_role:
            entry = protocol.protocol_for(
                canonical_research_role(active_role, research.get("task_type"))
            )
            duties = list(entry.duties) if entry else []
    lines = [
        "【角色可见材料】以下内容已按可见材料过滤，不含对照答案。",
        description[:6000],
    ]
    if duties:
        lines.append("【职责】" + "；".join(duties))
    lines.append(RESEARCH_DISCLAIMER)
    return {"role": "System", "message": "\n".join(lines)}


def inject_material_context(
    dialog_history: list[dict[str, Any]],
    filtered_input: dict[str, Any],
    scenario: str,
    role: Optional[str] = None,
) -> list[dict[str, Any]]:
    """CD/DD can take a System preface. CI reads projected case fields instead."""
    if scenario not in ("CD", "DD"):
        return list(dialog_history)
    preface = material_context_message(filtered_input, role=role)
    if not preface:
        return list(dialog_history)
    return [preface, *dialog_history]


def condition_fingerprint(research: dict[str, Any]) -> str:
    rules = [
        {
            "rule_id": item.get("rule_id"),
            "rule_version": item.get("rule_version"),
        }
        for item in (research.get("rules") or [])
        if isinstance(item, dict)
    ]
    payload = {
        "materials_hash": research.get("materials_hash") or "",
        "visible_materials": research.get("visible_materials") or {},
        "visibility_grants": research.get("visibility_grants") or [],
        "experiment_conditions": research.get("experiment_conditions") or {},
        "model_config": research.get("model_config") or research.get("model_config_snapshot") or {},
        "pack_version": research.get("pack_version") or "",
        "rules": rules,
    }
    return hash_payload(payload)


def merge_condition_overrides(
    research: dict[str, Any],
    *,
    visible_materials: Optional[dict[str, Any]] = None,
    experiment_conditions: Optional[dict[str, Any]] = None,
    model_config: Optional[dict[str, Any]] = None,
    visibility_grants: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    merged = dict(research)
    if visible_materials:
        merged["visible_materials"] = visible_materials
    if visibility_grants is not None:
        merged["visibility_grants"] = visibility_grants
    if experiment_conditions:
        current = dict(merged.get("experiment_conditions") or {})
        current.update(experiment_conditions)
        merged["experiment_conditions"] = current
    if model_config:
        merged["model_config"] = model_config
    return merged


def conditions_changed(
    current: dict[str, Any],
    proposed: dict[str, Any],
) -> bool:
    return condition_fingerprint(current) != condition_fingerprint(proposed)


def bind_research_context(
    input_json: Optional[dict[str, Any]],
    role: Optional[str] = None,
    *,
    cache_mode: str = CACHE_MODE_REPLAY,
    attempt_id: Optional[str] = None,
) -> Optional[object]:
    """Bind per-call research context. Returns a reset token or None."""
    if not has_research(input_json):
        return None
    research = research_block(input_json)
    canon = canonical_research_role(role, research.get("task_type"))
    visible = resolve_visible_materials(research, canon)
    hidden = _hide_source_ids(research)
    mode = cache_mode if cache_mode in (CACHE_MODE_REPLAY, CACHE_MODE_INDEPENDENT) else CACHE_MODE_REPLAY
    ctx = ResearchCallContext(
        run_id=str(research.get("run_id") or ""),
        role=canon,
        materials_hash=str(research.get("materials_hash") or ""),
        cache_mode=mode,
        attempt_id=attempt_id or (uuid4().hex if mode == CACHE_MODE_INDEPENDENT else ""),
        visible_document_ids=frozenset(_as_id_set(visible.get("document_ids"))),
        visible_source_ids=frozenset(_as_id_set(visible.get("source_ids")) - hidden),
        visible_rule_ids=frozenset(_as_id_set(visible.get("rule_ids"))),
        hide_source_ids=frozenset(hidden),
    )
    return _research_ctx.set(ctx)


def reset_research_context(token: Optional[object]) -> None:
    if token is None:
        return
    _research_ctx.reset(token)  # type: ignore[arg-type]


def current_research_context() -> Optional[ResearchCallContext]:
    return _research_ctx.get()


def research_cache_namespace() -> Optional[dict[str, Any]]:
    """Included in LLM cache keys. Replay ≠ independent attempt."""
    ctx = current_research_context()
    if ctx is None or not ctx.run_id:
        return None
    payload: dict[str, Any] = {
        "run_id": ctx.run_id,
        "role": ctx.role,
        "materials_hash": ctx.materials_hash,
        "cache_mode": ctx.cache_mode,
        "visible_document_ids": sorted(ctx.visible_document_ids),
        "visible_source_ids": sorted(ctx.visible_source_ids),
        "visible_rule_ids": sorted(ctx.visible_rule_ids),
    }
    if ctx.cache_mode == CACHE_MODE_INDEPENDENT:
        payload["attempt_id"] = ctx.attempt_id
    return payload


PARTY_ARGUMENT_ROLES = frozenset({ROLE_APPLICANT, ROLE_RESPONDENT, ROLE_CLAIMANT})
# Civil aliases that are actual party speech. Lawyer / Client / Judge stay out
# so CD/DD openers and the civil clerk ritual do not burn the research budget.
PARTY_ARGUMENT_RAW = PARTY_ARGUMENT_ROLES | frozenset({
    "Plaintiff",
    "plaintiff",
    "Defendant",
    "defendant",
    "申请人",
    "被申请人",
})


def count_argument_turns(
    dialog_history: Optional[Iterable[dict[str, Any]]],
    task_type: Optional[str] = None,
) -> int:
    """Party argument utterances only, deduplicated by Operation ID.

    Judge / auditor / lawyer-openers do not count. An utterance carrying an
    ``operation_id`` counts once per unique value, so a retried operation
    replaying the same ID cannot inflate the research budget.
    """
    del task_type
    total = 0
    seen_operations: set[str] = set()
    for item in dialog_history or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        if role not in PARTY_ARGUMENT_RAW:
            continue
        operation_id = str(item.get("operation_id") or "")
        if operation_id:
            if operation_id in seen_operations:
                continue
            seen_operations.add(operation_id)
        total += 1
    return total


def evaluate_stop_reason(
    *,
    task_type: Optional[str],
    claim_actions: Iterable[str],
    argument_turns: int,
    finished: bool = False,
) -> Optional[StopReason]:
    config = get_task_config(task_type)
    actions = list(claim_actions)
    if finished:
        return "completed"
    if "admit_insufficient" in actions:
        return "material_insufficient"
    if config and argument_turns >= config.max_argument_turns:
        return "max_turns"
    return None


def session_stop_reason(
    *,
    task_type: Optional[str],
    dialog_history: Optional[Iterable[dict[str, Any]]] = None,
    claim_actions: Iterable[str] = (),
    finished: bool = False,
) -> Optional[StopReason]:
    actions = list(claim_actions)
    turns = max(count_argument_turns(dialog_history, task_type), len(actions))
    return evaluate_stop_reason(
        task_type=task_type,
        claim_actions=actions,
        argument_turns=turns,
        finished=finished,
    )


def research_stop_notice(reason: Optional[StopReason]) -> str:
    if reason == "material_insufficient":
        return "材料不足，按研究协议停止。未知事实不得补造。"
    if reason == "max_turns":
        return "研究论证轮次已达协议上限，本场停止。"
    return "本场已按研究协议停止。"


def research_llm_blocked(
    input_json: Optional[dict[str, Any]],
    dialog_history: Optional[Iterable[dict[str, Any]]] = None,
    claim_actions: Iterable[str] = (),
) -> Optional[StopReason]:
    """Civil sessions without a research pack stay open. Research hits the protocol cap."""
    if not has_research(input_json):
        return None
    return session_stop_reason(
        task_type=research_block(input_json).get("task_type"),
        dialog_history=dialog_history,
        claim_actions=claim_actions,
    )


def compact_research_meta(input_json: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    research = research_block(input_json)
    if not research:
        return None
    return {
        "run_id": research.get("run_id"),
        "derived_from": research.get("derived_from"),
        "dataset_id": research.get("dataset_id"),
        "cluster_id": research.get("cluster_id"),
        "pack_version": research.get("pack_version"),
        "task_type": research.get("task_type"),
        "materials_hash": research.get("materials_hash"),
        "visible_materials": research.get("visible_materials"),
        "visibility_grants": research.get("visibility_grants"),
        "experiment_conditions": research.get("experiment_conditions"),
        "model_config": research.get("model_config") or research.get("model_config_snapshot"),
        "caption": research.get("caption"),
        "disclaimer": RESEARCH_DISCLAIMER,
    }
