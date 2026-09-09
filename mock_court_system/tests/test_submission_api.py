"""旧 submission.json 探测脚本已退役，不再作为 API 回归。"""
import pytest

pytestmark = pytest.mark.skip(reason="submission.json 已废弃，勿复活；请用 /health 与 /conversation/start")


def test_submission_api_retired():
    pytest.skip("submission.json retired; use current /health and conversation APIs")
