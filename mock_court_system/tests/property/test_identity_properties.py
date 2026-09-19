"""会话/资源身份隔离属性测试。

覆盖 Property 10：mediation identity/session isolation。
"""
from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import given, settings, strategies as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.store.mediation_session_store import MediationSessionStore  # noqa: E402


@given(
    ids=st.lists(
        st.text(min_size=1, max_size=24).filter(lambda s: s.strip()),
        min_size=2,
        max_size=4,
        unique=True,
    )
)
@settings(max_examples=10, deadline=None)
def test_property_10_mediation_sessions_isolated(tmp_path_factory, ids):
    store = MediationSessionStore(str(Path(tmp_path_factory.mktemp("med")) / "m.sqlite3"))
    for i, sid in enumerate(ids):
        store.save(sid, {"marker": i, "session_id": sid})
    for i, sid in enumerate(ids):
        got = store.get(sid)
        assert got is not None and got["marker"] == i
    # 删除一个不影响其他
    store.delete(ids[0])
    assert store.get(ids[0]) is None
    for i, sid in enumerate(ids[1:], start=1):
        assert store.get(sid)["marker"] == i
