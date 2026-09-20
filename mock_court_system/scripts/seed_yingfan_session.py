"""Seed a filmable Yingfan v. Amazon CI session.

Uses POST /conversation/start (scenario=CI + research triad) so freeze_role_snapshot
runs. Does not use bare POST /conversation/import as the main path. A bounded eight-turn
hearing is written after start, claims are appended, and a linked strategy game is
created without spending an LLM round.

Does not increment formal_pack_count and does not add this cluster to
TECHNICAL_FIXTURE_CLUSTER_IDS.

Usage (from mock_court_system, product venv):

    .venv/Scripts/python.exe scripts/seed_yingfan_session.py
    .venv/Scripts/python.exe scripts/seed_yingfan_session.py --in-process
    .venv/Scripts/python.exe scripts/seed_yingfan_session.py --api-base http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

DATASET_ID = "enforcement"
CLUSTER_ID = "enf-us-yingfan-amazon-001"
PACK_VERSION = "0.1.0-draft"
SCENARIO = "CI"

# tribunal is the runtime id for the procedure organizer on enforcement_nyc.
# Only applicant/respondent turns count toward the 12-turn research cap.
FROZEN_DIALOG: list[tuple[str, str]] = [
    (
        "tribunal",
        "本场仅围绕 FAA §10(a)(3) 的听证机会争议展开。演示材料是候选包 0.1.0-draft，待独立复核；"
        "系统收录的是 SDNY 意见书摘录与标注结构，Partial Final Award、Final Award、BSA 全文及邮件原件均未附。",
    ),
    (
        "applicant",
        "申请人主张拒绝延期 2025-05-20 损害赔偿听证构成仲裁员 misconduct，使其无法出示损害赔偿证据并盘问证人。"
        "该主张见 001:p11-claims、001:p16-10a3；未收录材料的具体内容保持 unknown。",
    ),
    (
        "respondent",
        "被申请人主张仲裁员已多次协调日期，并允许在听证前、听证中及当晚午夜前补充书面材料；申请人没有利用该机会。"
        "依据 001:p5-may13、001:p6-late-notice、001:p7-midnight、001:p22-eschewed。",
    ),
    (
        "tribunal",
        "程序时间线核对：4 月 30 日通知原定 5 月 15 日；5 月 7 日申请改期；5 月 13 日提供书面裁决或 5 月 19 日听证选项；"
        "5 月 16 日排定 5 月 20 日 19:00 EST。意见书同一句写有“May 19, 2026”和“the day before the hearing”，"
        "系统标记为冲突事实 CF，不自行改写成年份 2025（001:p4-notice、001:p5-may7、001:p5-may13、001:p6-may19）。",
    ),
    (
        "applicant",
        "申请人进一步主张，书面补充不能替代其现场陈述和盘问机会，因此受到实质性不利。"
        "这只是当事方论证；缺失的证据内容、证人身份及 BSA §18 全文不作推断。",
    ),
    (
        "respondent",
        "被申请人答辩称申请人曾同意仅凭书面材料处理，并在获得最后补充窗口后仍未提交。另据意见书转述，Amazon 已支付 248,844.39 美元，"
        "申请人于 2025-08-22 确认收款；支付凭证未附，保持 NR（001:p7-no-supplement、001:p11-paid）。",
    ),
    (
        "auditor",
        "证据核验完成：发言可回链至 documents/001.txt。通知渠道与到达时间、邮件原件、两份裁决全文、BSA 全文和支付明细均为 NR/unknown；"
        "日期矛盾保留为 CF。本包不以纽约公约 V(1)(b) 回填法院没有采用的裁判依据。",
    ),
    (
        "tribunal",
        "研究者对照：SDNY 因 Article III standing 驳回确认请求，未进入承认与执行实体审查；对撤销和修改请求则认为拒绝延期有合理基础，"
        "不构成 §10(a)(3) misconduct，最终全部驳回并结案（001:p13-no-standing、001:p22-reasonable、001:p33-vacate-denied）。"
        "这是法院结果对照，不是系统自动裁判。",
    ),
]

APPLICANT_CLAIM = {
    "claim_id": "enf-claim-hearing-denied",
    "role": "applicant",
    "action": "assert",
    "fact": (
        "申请人主张被拒绝延期 2025-05-20 听证，未能出示损害赔偿证据、盘问证人；"
        "Partial Final Award / Final Award / 邮件原件未附。"
    ),
    "norm": "FAA 9 U.S.C. §§ 10、10(a)(3)、11(a)。本包不回填纽约公约 V(1)(b)。",
    "reasoning": (
        "听证机会被剥夺：拒绝延期构成 §10(a)(3) misconduct；"
        "利息与费用及金额计算另构成明显漠视法律与误算主张。"
    ),
    "source_ids": ["001:p11-claims", "001:p16-10a3"],
    "payload": {
        "label": "听证机会被剥夺",
        "notice_events": ["enf-notice-01", "enf-notice-08"],
        "court_outcome": "researcher_contrast_only",
    },
}

RESPONDENT_CLAIM = {
    "claim_id": "enf-claim-notice-unused",
    "role": "respondent",
    "action": "assert",
    "fact": (
        "判决转述多次听证通知，并允许 5/20 听证前与午夜前补充；申请人未用补充机会。"
        "另转述亚马逊支付 248,844.39 美元，申请人于 2025-08-22 确认收到。支付明细未附。"
    ),
    "norm": "Article III standing；Stafford v. IBM；FAA §§ 10、11。",
    "reasoning": "多次通知且未用补充机会；已全额履行则确认请求不再构成活争议。",
    "source_ids": ["001:p11-standing-arg", "001:p22-eschewed", "001:p11-paid"],
    "payload": {
        "label": "多次通知且未用补充机会",
        "notice_events": ["enf-notice-08", "enf-notice-09"],
        "court_outcome": "researcher_contrast_only",
        "court_findings_contrast": {
            "item_ids": [
                "enf-finding-confirm-standing",
                "enf-finding-vacatur-denied",
                "enf-finding-disposition",
            ],
            "note": "法院结论仅作研究者对照材料，不是系统裁判。",
        },
    },
}

CASE_INFO = {
    "case_id": CLUSTER_ID,
    "case_name": "Shenzhen Yingfan E-Commerce Co., Ltd. v. Amazon.com Services LLC",
    "forum": "U.S. District Court for the Southern District of New York",
    "decision_date": "2026-07-21",
    "procedural_posture": "FAA confirmation, vacatur, and modification motion",
    "case_facts": (
        "Yingfan's Amazon seller account was deactivated around 2021-12-07 and "
        "$266,219.33 was withheld. Arbitration produced a 2025-06-05 final award of "
        "$248,844.39. The hearing-opportunity dispute concerns the 2025-05-20 damages hearing."
    ),
    "applicant_position": "Refusal to adjourn the damages hearing amounted to FAA §10(a)(3) misconduct.",
    "respondent_position": "Multiple scheduling and supplemental-filing opportunities were provided and unused.",
    "court_result_for_researcher_contrast": (
        "Confirmation denied for lack of Article III standing; vacatur and modification denied; case closed."
    ),
    "evidence_boundary": [
        "SDNY opinion excerpt and annotation structure are loaded.",
        "Partial Final Award, Final Award, BSA full text, original emails, and payment records are not loaded.",
        "The May 19 year conflict remains CF and is not silently corrected.",
        "The court result is comparison material, not a system-generated verdict.",
    ],
    "source_ids": [
        "001:p4-notice",
        "001:p6-may19",
        "001:p7-midnight",
        "001:p11-claims",
        "001:p13-no-standing",
        "001:p22-reasonable",
        "001:p33-disposition",
    ],
}


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(PRODUCT_ROOT / ".env")


def _api_headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    token = (os.getenv("API_TOKEN") or os.getenv("BACKEND_API_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _http_json(
    method: str,
    url: str,
    payload: Optional[dict[str, Any]] = None,
    timeout: float = 15.0,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=_api_headers(), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            body = json.loads(raw) if raw else {}
            return response.status, body
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw else {"detail": str(exc)}
        except json.JSONDecodeError:
            body = {"detail": raw or str(exc)}
        return exc.code, body
    except urllib.error.URLError as exc:
        raise ConnectionError(str(exc.reason or exc)) from exc


def pack_path() -> Path:
    return (
        PRODUCT_ROOT
        / "data"
        / "research_packs"
        / DATASET_ID
        / CLUSTER_ID
        / "pack.json"
    )


def assert_pack_present() -> None:
    path = pack_path()
    if not path.is_file():
        raise FileNotFoundError(f"research pack missing: {path}")
    pack = json.loads(path.read_text(encoding="utf-8"))
    if pack.get("cluster_id") != CLUSTER_ID:
        raise ValueError(f"unexpected cluster_id in pack.json: {pack.get('cluster_id')}")
    if pack.get("pack_version") != PACK_VERSION:
        raise ValueError(f"unexpected pack_version in pack.json: {pack.get('pack_version')}")
    events = ((pack.get("task_labels") or {}).get("notice_events") or [])
    ids = [str(item.get("event_id") or "") for item in events]
    expected = [f"enf-notice-{i:02d}" for i in range(1, 10)]
    if ids != expected:
        raise ValueError(f"notice_events mismatch: {ids}")


def start_payload() -> dict[str, str]:
    return {
        "scenario": SCENARIO,
        "case_id": CLUSTER_ID,
        "dataset_id": DATASET_ID,
        "cluster_id": CLUSTER_ID,
        "pack_version": PACK_VERSION,
    }


def try_http_start(api_base: str) -> Optional[dict[str, Any]]:
    health_url = api_base.rstrip("/") + "/health"
    start_url = api_base.rstrip("/") + "/conversation/start"
    try:
        status, _ = _http_json("GET", health_url, timeout=3.0)
    except (ConnectionError, TimeoutError, OSError) as exc:
        print(f"[seed] live API not reachable at {api_base}: {exc}")
        return None
    if status >= 400:
        print(f"[seed] live API health {status} at {health_url}")
        return None
    try:
        status, body = _http_json("POST", start_url, start_payload(), timeout=20.0)
    except (ConnectionError, TimeoutError, OSError) as exc:
        print(f"[seed] POST /conversation/start failed: {exc}")
        return None
    if status >= 400 or not isinstance(body, dict) or not body.get("session_id"):
        print(f"[seed] POST /conversation/start HTTP {status}: {body}")
        return None
    if not body.get("run_id"):
        print(
            "[seed] live /conversation/start ignored the research triad "
            f"(no run_id). Server is old or not this tree. session={body.get('session_id')}"
        )
        return None
    print(f"[seed] HTTP start ok session_id={body['session_id']} run_id={body['run_id']}")
    return body


def start_in_process() -> dict[str, Any]:
    from api.services.conversation import start_session

    result = start_session(
        SCENARIO,
        CLUSTER_ID,
        dataset_id=DATASET_ID,
        cluster_id=CLUSTER_ID,
        pack_version=PACK_VERSION,
    )
    if not result.get("run_id"):
        raise RuntimeError("in-process start_session did not freeze a research run_id")
    print(f"[seed] in-process start ok session_id={result['session_id']} run_id={result['run_id']}")
    return result


def load_record(session_id: str):
    from api import state

    record = state.conversation_store.get(session_id)
    if record is None:
        raise KeyError(f"session not in conversation store: {session_id}")
    return record


def write_frozen_dialog(record) -> None:
    from api import state

    record.dialog_history = [
        {"turn": index, "role": role, "message": message}
        for index, (role, message) in enumerate(FROZEN_DIALOG)
    ]
    for message in record.dialog_history:
        text = str(message.get("message") or "")
        if "离线演示模板" in text or text.startswith("[离线模式回复]"):
            raise RuntimeError("frozen dialog must not use offline-template wording")
    state.conversation_store.save(record)
    roles = [item["role"] for item in record.dialog_history]
    print(f"[seed] wrote {len(roles)} frozen turns: {roles}")


def write_claims_in_process(record, bodies: list[dict[str, Any]]) -> None:
    from api.services.claims import append_session_claim, register_run_from_session

    register_run_from_session(record.session_id, record.input_json)
    for body in bodies:
        result = append_session_claim(record, body)
        event = result.get("event") or {}
        print(f"[seed] in-process claim {body['claim_id']} action={event.get('action')} seq={event.get('seq')}")


def write_claims(record) -> None:
    # Claims have no public write route. The conversation and research stores share
    # the same configured SQLite files, so this remains visible to the live API.
    write_claims_in_process(record, [APPLICANT_CLAIM, RESPONDENT_CLAIM])


def game_payload(session_id: str) -> dict[str, Any]:
    return {
        "case_info": CASE_INFO,
        "session_id": session_id,
        "plaintiff_strategy": "competing",
        "defendant_strategy": "collaborating",
        "max_rounds": 3,
        "convergence_threshold": 0.05,
        "evolution_method": "llm_reflection",
        "enable_dynamic_strategy": True,
        "dispute_cause": "arbitration_hearing_procedure",
        "dispute_cause_detail": "FAA §10(a)(3) adjournment and opportunity-to-be-heard dispute",
    }


def try_http_game(api_base: str, session_id: str) -> Optional[dict[str, Any]]:
    url = api_base.rstrip("/") + "/game/create"
    try:
        status, body = _http_json("POST", url, game_payload(session_id), timeout=20.0)
    except (ConnectionError, TimeoutError, OSError) as exc:
        print(f"[seed] POST /game/create unavailable ({exc}); using in-process store")
        return None
    if status >= 400 or not isinstance(body, dict) or not body.get("game_id"):
        print(f"[seed] POST /game/create HTTP {status}: {body}; using in-process store")
        return None
    print(f"[seed] HTTP game ok game_id={body['game_id']}")
    return body


def create_game_in_process(session_id: str) -> dict[str, Any]:
    from api.schemas import GameCreateRequest
    from api.services.game import create_game

    result = create_game(GameCreateRequest(**game_payload(session_id)))
    print(f"[seed] in-process game ok game_id={result['game_id']}")
    return result


def camera_urls(frontend_base: str, session_id: str) -> dict[str, str]:
    root = frontend_base.rstrip("/")
    return {
        "research": f"{root}/research",
        "hearing_text": f"{root}/conversation/{session_id}",
        "hearing_3d": f"{root}/hearing-3d?sessionId={session_id}",
        "research_review": f"{root}/evaluation?session={session_id}&pane=research",
        "strategy_review": f"{root}/evaluation?session={session_id}&pane=strategy",
    }


def write_manifest(
    *,
    session_id: str,
    run_id: str,
    game_id: str,
    seed_mode: str,
    urls: dict[str, str],
) -> Path:
    output = PRODUCT_ROOT / "test-results" / "yingfan-demo.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": DATASET_ID,
        "cluster_id": CLUSTER_ID,
        "pack_version": PACK_VERSION,
        "review_state": "pending",
        "formal_research_pack": False,
        "session_id": session_id,
        "run_id": run_id,
        "game_id": game_id,
        "seed_mode": seed_mode,
        "urls": urls,
        "recording_sequence": [
            "research",
            "hearing_text",
            "hearing_3d",
            "strategy_review",
            "research_review",
        ],
        "notes": [
            "The transcript is frozen and source-anchored for a repeatable film path.",
            "No game round is pre-run; run one live only when the configured LLM is available.",
            "The candidate pack remains pending independent review and does not change the formal pack count.",
        ],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the Yingfan CI session for the film path")
    parser.add_argument("--api-base", default=os.getenv("API_BASE", "http://127.0.0.1:8000"))
    parser.add_argument("--frontend-base", default=os.getenv("FRONTEND_BASE", "http://127.0.0.1:3000"))
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="Skip live FastAPI and call api.services.conversation.start_session directly",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _load_env()
    assert_pack_present()

    started: Optional[dict[str, Any]] = None
    seed_mode = "in-process"
    if not args.in_process:
        started = try_http_start(args.api_base)
        if started:
            seed_mode = "http"

    if started is None:
        started = start_in_process()
        seed_mode = "in-process"

    try:
        record = load_record(started["session_id"])
    except KeyError:
        if seed_mode == "http":
            print(
                "[seed] HTTP session is not in this process's conversation store "
                "(likely a memory-backed live server). Falling back to in-process start."
            )
            started = start_in_process()
            seed_mode = "in-process"
            record = load_record(started["session_id"])
        else:
            raise

    research = (record.input_json or {}).get("research") or {}
    if research.get("cluster_id") != CLUSTER_ID or research.get("pack_version") != PACK_VERSION:
        raise RuntimeError(f"role snapshot identity mismatch: {research}")
    if not research.get("run_id"):
        raise RuntimeError("freeze_role_snapshot did not attach run_id")

    write_frozen_dialog(record)
    write_claims(record)

    session_id = record.session_id
    game = try_http_game(args.api_base, session_id) if seed_mode == "http" else None
    if game is None:
        game = create_game_in_process(session_id)
    game_id = str(game["game_id"])
    urls = camera_urls(args.frontend_base, session_id)
    manifest = write_manifest(
        session_id=session_id,
        run_id=str(research.get("run_id")),
        game_id=game_id,
        seed_mode=seed_mode,
        urls=urls,
    )
    print(f"session_id={session_id}")
    print(f"run_id={research.get('run_id')}")
    print(f"game_id={game_id}")
    print(f"seed_mode={seed_mode}")
    print("camera_urls:")
    for label, url in urls.items():
        print(f"{label}: {url}")
    print(f"manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
