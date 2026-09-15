"""Six-dimension research rubric. Machine checks are not legal quality."""
from __future__ import annotations

from typing import Any, Iterable, Optional

RUBRIC_VERSION = "research-6d-1.0"

DIMENSIONS: tuple[str, ...] = (
    "issue_spotting",
    "fact_support",
    "norm_application",
    "rebuttal_response",
    "citation_accuracy",
    "unknown_handling",
)

REASONING_INDEPENDENCE_CAP = 0.35
PASS_THRESHOLD = 0.55


def _norm(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _overlap(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = {_norm(item) for item in left if _norm(item)}
    right_set = {_norm(item) for item in right if _norm(item)}
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    hay = _norm(text)
    return any(_norm(needle) and _norm(needle) in hay for needle in needles)


def _claim_blob(claims: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for claim in claims:
        for key in ("fact", "norm", "reasoning", "status"):
            if claim.get(key):
                parts.append(str(claim[key]))
        for event in claim.get("events") or []:
            if isinstance(event, dict):
                parts.append(str(event.get("reasoning") or ""))
    return "\n".join(parts)


def _predicted_conclusion(output: dict[str, Any], claims: list[dict[str, Any]]) -> str:
    for key in ("conclusion", "outcome", "predicted_outcome", "label"):
        value = output.get(key)
        if value:
            return str(value)
    blob = _claim_blob(claims) + " " + str(output.get("text") or "")
    lowered = _norm(blob)
    if "refuse" in lowered or "拒绝承认" in lowered or "不予承认" in lowered:
        return "refuse_enforcement"
    if "grant" in lowered or "承认并执行" in lowered or "准予承认" in lowered:
        return "grant_enforcement"
    if "exempt" in lowered or "免除" in lowered:
        return "exempt"
    if "not_exempt" in lowered or "不予免除" in lowered:
        return "not_exempt"
    return "unknown"


def _predicted_reasons(output: dict[str, Any], claims: list[dict[str, Any]]) -> list[str]:
    reasons = _as_list(output.get("reasons")) + _as_list(output.get("reason"))
    for claim in claims:
        if claim.get("reasoning"):
            reasons.append(str(claim["reasoning"]))
        if claim.get("norm"):
            reasons.append(str(claim["norm"]))
    return reasons


def _acceptable_path_match(
    conclusion: str,
    reasons: list[str],
    paths: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    for path in paths:
        if not isinstance(path, dict):
            continue
        path_label = str(path.get("conclusion_label") or path.get("conclusion") or "")
        if path_label and _norm(path_label) != _norm(conclusion):
            continue
        required = _as_list(path.get("requires"))
        required_any = _as_list(path.get("requires_any"))
        reason_blob = " ".join(reasons)
        if required and not all(_contains_any(reason_blob, [item]) for item in required):
            continue
        if required_any and not _contains_any(reason_blob, required_any):
            continue
        if path_label or required or required_any:
            return path
    return None


def _machine_checks(
    claims: list[dict[str, Any]],
    output: dict[str, Any],
    *,
    leaked_reference: bool,
) -> dict[str, Any]:
    events = [event for claim in claims for event in (claim.get("events") or [claim])]
    triad_ok = True
    for event in events:
        action = str(event.get("action") or event.get("status") or "")
        if action in ("assert", "ground", "supplement", "revise"):
            if not (
                str(event.get("fact") or "").strip()
                and str(event.get("norm") or "").strip()
                and str(event.get("reasoning") or "").strip()
            ):
                triad_ok = False
    citations = []
    for claim in claims:
        citations.extend(claim.get("source_ids") or [])
        for event in claim.get("events") or []:
            if isinstance(event, dict):
                citations.extend(event.get("source_ids") or [])
    unknown_marked = any(
        "unknown" in _norm(claim.get("fact") or "")
        or "unknown" in _norm(claim.get("reasoning") or "")
        or claim.get("status") == "admit_insufficient"
        for claim in claims
    ) or bool(output.get("unknown_marked"))
    rebuttals = [
        claim
        for claim in claims
        if claim.get("status") in ("rebut", "supplement", "revise", "withdraw", "admit_insufficient")
        or any(
            isinstance(event, dict) and event.get("action") == "rebut"
            for event in (claim.get("events") or [])
        )
    ]
    return {
        "claim_triad_present": triad_ok and bool(claims or output.get("text")),
        "citation_present": bool(citations) or bool(output.get("source_ids")),
        "reference_isolated": not leaked_reference,
        "unknown_marked": unknown_marked,
        "rebuttal_logged": bool(rebuttals) or bool(output.get("rebuttal_response")),
        "event_count": sum(len(claim.get("events") or []) for claim in claims),
    }


def claim_action(event: dict[str, Any]) -> str:
    return str(event.get("action") or event.get("status") or "")


def score_research_output(
    *,
    output: Optional[dict[str, Any]] = None,
    claims: Optional[list[dict[str, Any]]] = None,
    reference: Optional[dict[str, Any]] = None,
    leaked_reference: bool = False,
) -> dict[str, Any]:
    """Score one run. Same conclusion + wrong reasons is capped low."""
    output = output or {}
    claims = claims or []
    reference = reference or {}
    gold = reference.get("gold_labels") if isinstance(reference.get("gold_labels"), dict) else {}
    paths = list(reference.get("acceptable_paths") or [])
    gold_conclusion = str(
        gold.get("outcome")
        or gold.get("conclusion")
        or gold.get("conclusion_label")
        or ""
    )
    gold_reasons = _as_list(gold.get("reasons")) + _as_list(gold.get("reason"))
    if gold.get("convention_issue"):
        gold_reasons.append(str(gold["convention_issue"]))

    predicted = _predicted_conclusion(output, claims)
    reasons = _predicted_reasons(output, claims)
    reason_blob = " ".join(reasons) + " " + str(output.get("text") or "")
    path_hit = _acceptable_path_match(predicted, reasons, paths)

    conclusion_match = bool(gold_conclusion) and _norm(predicted) == _norm(gold_conclusion)
    if gold_conclusion and _norm(gold_conclusion) == "unknown":
        conclusion_match = predicted == "unknown" or bool(output.get("unknown_marked"))

    reason_overlap = _overlap(gold_reasons, reasons) if gold_reasons else (
        0.5 if reasons else 0.0
    )
    if gold_reasons:
        reason_supported = any(_contains_any(reason_blob, [item]) for item in gold_reasons)
    else:
        reason_supported = bool(reasons)

    wrong_reasons = bool(gold_conclusion) and conclusion_match and gold_reasons and not reason_supported
    alt_path_ok = path_hit is not None and not conclusion_match

    issue_spotting = 0.85 if (
        conclusion_match or alt_path_ok or _contains_any(reason_blob, gold_reasons[:1] or [predicted])
    ) else (0.4 if predicted != "unknown" else 0.25)
    if gold.get("convention_issue") and _contains_any(reason_blob, [str(gold["convention_issue"])]):
        issue_spotting = max(issue_spotting, 0.8)

    fact_support = 0.8 if any(str(claim.get("fact") or "").strip() for claim in claims) else 0.35
    if output.get("facts_supported") is True:
        fact_support = max(fact_support, 0.75)
    if output.get("facts_supported") is False:
        fact_support = min(fact_support, 0.3)

    norm_application = 0.8 if any(str(claim.get("norm") or "").strip() for claim in claims) else 0.35
    if reason_supported:
        norm_application = max(norm_application, 0.75)
    if wrong_reasons:
        norm_application = min(norm_application, 0.25)

    rebuttal_response = 0.7 if _machine_checks(claims, output, leaked_reference=False)["rebuttal_logged"] else 0.4
    if output.get("rebuttal_response") is False:
        rebuttal_response = 0.2

    citation_accuracy = 0.75 if (
        any(claim.get("source_ids") for claim in claims) or output.get("citations_ok")
    ) else 0.35
    if output.get("citations_ok") is False:
        citation_accuracy = 0.2

    unknown_handling = 0.8 if (
        predicted == "unknown"
        or any(claim.get("status") == "admit_insufficient" for claim in claims)
        or output.get("unknown_marked")
    ) else 0.45
    if output.get("invented_facts"):
        unknown_handling = 0.15

    scores = {
        "issue_spotting": issue_spotting,
        "fact_support": fact_support,
        "norm_application": norm_application,
        "rebuttal_response": rebuttal_response,
        "citation_accuracy": citation_accuracy,
        "unknown_handling": unknown_handling,
    }

    penalties: dict[str, Any] = {}
    if wrong_reasons:
        penalties["reasoning_independence"] = {
            "applied": True,
            "cap": REASONING_INDEPENDENCE_CAP,
            "note": "same conclusion with unsupported / wrong reasons",
        }
        for key in scores:
            scores[key] = min(scores[key], REASONING_INDEPENDENCE_CAP)

    if leaked_reference:
        penalties["reference_leak"] = {"applied": True, "note": "hidden answers entered model input"}
        for key in scores:
            scores[key] = min(scores[key], 0.2)

    overall = sum(scores.values()) / len(DIMENSIONS)
    if wrong_reasons:
        overall = min(overall, REASONING_INDEPENDENCE_CAP)

    disagreements: list[dict[str, Any]] = []
    undecidable: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    if gold_conclusion and _norm(gold_conclusion) == "unknown":
        undecidable.append(
            {
                "code": "gold_unknown",
                "note": "reference outcome is unknown; do not invent a judicial result",
            }
        )
    if alt_path_ok:
        disagreements.append(
            {
                "code": "acceptable_path",
                "path_id": path_hit.get("path_id") if path_hit else "",
                "note": "justified alternative path; may pass review",
            }
        )
    if wrong_reasons:
        failures.append(
            {
                "code": "wrong_reasons",
                "note": "conclusion matches gold but reasons do not",
            }
        )
    if leaked_reference:
        failures.append({"code": "reference_leak", "note": "reference entered model input"})
    if overall < PASS_THRESHOLD and not alt_path_ok:
        failures.append({"code": "below_threshold", "score": overall})

    legal_pass = (overall >= PASS_THRESHOLD and not wrong_reasons) or alt_path_ok
    if leaked_reference:
        legal_pass = False

    machine = _machine_checks(claims, output, leaked_reference=leaked_reference)
    return {
        "rubric_version": RUBRIC_VERSION,
        "dimensions": scores,
        "overall": round(overall, 4),
        "machine_checks": machine,
        "legal_quality": {
            "overall": round(overall, 4),
            "conclusion": predicted,
            "gold_conclusion": gold_conclusion or None,
            "conclusion_match": conclusion_match,
            "reason_overlap": round(reason_overlap, 4),
            "wrong_reasons": wrong_reasons,
            "acceptable_path": path_hit.get("path_id") if path_hit else None,
            "passed_review_gate": legal_pass,
            "note": "machine_checks are not legal quality",
        },
        "penalties": penalties,
        "failures": failures,
        "disagreements": disagreements,
        "undecidable": undecidable,
        "disclaimer": (
            "本仿真仅说明系统在既定实验条件下的表现；"
            "关于司法实践的判断仍须以真实裁判文书为依据。"
        ),
    }
