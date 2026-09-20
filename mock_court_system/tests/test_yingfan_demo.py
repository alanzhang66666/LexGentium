from __future__ import annotations

import json

from api.schemas import GameCreateRequest
from scripts.seed_yingfan_session import (
    CLUSTER_ID,
    FROZEN_DIALOG,
    PACK_VERSION,
    game_payload,
    pack_path,
)


def test_candidate_pack_identity_and_review_boundary() -> None:
    pack = json.loads(pack_path().read_text(encoding="utf-8"))

    assert pack["cluster_id"] == CLUSTER_ID
    assert pack["pack_version"] == PACK_VERSION
    assert pack["review_state"] == "pending"
    assert [event["event_id"] for event in pack["task_labels"]["notice_events"]] == [
        f"enf-notice-{index:02d}" for index in range(1, 10)
    ]


def test_frozen_dialog_is_bounded_and_keeps_source_limits_visible() -> None:
    roles = [role for role, _ in FROZEN_DIALOG]
    counted_turns = sum(role in {"applicant", "respondent"} for role in roles)
    dialog_text = "\n".join(message for _, message in FROZEN_DIALOG)

    assert len(FROZEN_DIALOG) == 8
    assert roles == [
        "tribunal",
        "applicant",
        "respondent",
        "tribunal",
        "applicant",
        "respondent",
        "auditor",
        "tribunal",
    ]
    assert counted_turns <= 12
    assert "候选包 0.1.0-draft" in dialog_text
    assert "May 19, 2026" in dialog_text
    assert "系统自动裁判" in dialog_text


def test_game_request_keeps_conversation_link() -> None:
    request = GameCreateRequest(**game_payload("session-demo"))

    assert request.session_id == "session-demo"
    assert request.plaintiff_strategy == "competing"
    assert request.defendant_strategy == "collaborating"
    assert request.max_rounds == 3

