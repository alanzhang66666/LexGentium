"""会话 input_json.links 读写。"""
from __future__ import annotations

from typing import Any, Dict, Optional


LINK_KEYS = ("task_id", "game_id", "report_id")


def extract_links(input_json: Optional[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    raw = (input_json or {}).get("links")
    if not isinstance(raw, dict):
        return {key: None for key in LINK_KEYS}
    return {key: (str(raw[key]) if raw.get(key) else None) for key in LINK_KEYS}


def merge_link(input_json: Optional[Dict[str, Any]], **updates: Optional[str]) -> Dict[str, Any]:
    payload = dict(input_json or {})
    links = extract_links(payload)
    for key, value in updates.items():
        if key in LINK_KEYS and value:
            links[key] = value
    payload["links"] = {k: v for k, v in links.items() if v}
    return payload


def compact_links(input_json: Optional[Dict[str, Any]]) -> Dict[str, str]:
    return {k: v for k, v in extract_links(input_json).items() if v}
