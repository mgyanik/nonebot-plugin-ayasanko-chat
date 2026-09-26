# tests/test_session.py
import time
from nonebot_plugin_ayasanko_chat.session import SessionManager


def test_session_lifecycle():
    manager = SessionManager(max_sessions=10, ttl=60.0)

    # 初始无历史
    assert manager.get_history("user1") == []
    assert manager.count_active() == 0

    # 添加对话
    manager.add_turn("user1", "你好", "你好呀！", max_history=5)
    hist = manager.get_history("user1")
    assert len(hist) == 2
    assert hist[0] == {"role": "user", "content": "你好"}
    assert hist[1] == {"role": "assistant", "content": "你好呀！"}
    assert manager.count_active() == 1

    # 清除单个用户
    cleared = manager.clear("user1")
    assert cleared == 1
    assert manager.get_history("user1") == []
    assert manager.count_active() == 0


def test_session_lru_eviction():
    manager = SessionManager(max_sessions=3, ttl=3600.0)

    for i in range(1, 5):
        manager.add_turn(f"user{i}", f"msg{i}", f"reply{i}", max_history=5)

    # user1 应当被最先淘汰，剩下 user2, user3, user4
    assert manager.get_history("user1") == []
    assert len(manager.get_history("user2")) == 2
    assert len(manager.get_history("user3")) == 2
    assert len(manager.get_history("user4")) == 2
    assert manager.count_active() == 3


def test_session_ttl_expiration():
    # ttl 极短
    manager = SessionManager(max_sessions=10, ttl=0.1)
    manager.add_turn("user_temp", "hello", "hi", max_history=5)
    assert len(manager.get_history("user_temp")) == 2

    time.sleep(0.15)
    # 过期后读取自动失效
    assert manager.get_history("user_temp") == []
    assert manager.count_active() == 0
