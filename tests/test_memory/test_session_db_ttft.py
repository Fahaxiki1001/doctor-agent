"""test_memory/test_session_db_ttft.py — 首 token 用时持久化往返测试

覆盖本次修复：assistant 消息的 time_to_first_token 写入后可正确读取，
None 值安全落库与读取。
"""
from datetime import datetime

import pytest

from mediZJ.memory.session_db import SessionDB


@pytest.fixture
def db(tmp_path):
    SessionDB.reset()
    instance = SessionDB(str(tmp_path / "sessions.db"))
    yield instance
    SessionDB.reset()


def _save(db, ttft):
    now = datetime.now().isoformat()
    db.save_turn(
        session_id="s1",
        turn_index=0,
        user_msg={"role": "user", "content": "我发烧了", "timestamp": now},
        assistant_msg={
            "role": "assistant",
            "content": "建议多休息",
            "timestamp": now,
            "time_to_first_token": ttft,
        },
    )


def _assistant_msg(db):
    session = db.get_session("s1")
    return next(m for m in session["messages"] if m["role"] == "assistant")


class TestTimeToFirstTokenPersistence:
    def test_roundtrip_value(self, db):
        _save(db, 1.23)
        assert _assistant_msg(db)["time_to_first_token"] == pytest.approx(1.23)

    def test_roundtrip_none(self, db):
        _save(db, None)
        assert _assistant_msg(db)["time_to_first_token"] is None
