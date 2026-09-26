# tests/test_sqlite_storage.py
import tempfile
import time
from pathlib import Path
from nonebot_plugin_ayasanko_chat.storage.sqlite import SqliteStorageBackend


def test_sqlite_storage_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_chat.db")
        storage = SqliteStorageBackend(db_path=db_path, default_ttl=60.0)

        # 初始为空
        assert storage.get_history("s1") == []
        assert storage.count_active() == 0

        # 添加会话
        storage.add_turn("s1", "你好", "你好呀！", max_history=5)
        hist = storage.get_history("s1")
        assert len(hist) == 2
        assert hist[0] == {"role": "user", "content": "你好"}
        assert hist[1] == {"role": "assistant", "content": "你好呀！"}
        assert storage.count_active() == 1

        # 清除指定会话
        cleared = storage.clear("s1")
        assert cleared == 1
        assert storage.get_history("s1") == []
        assert storage.count_active() == 0


def test_sqlite_storage_ttl():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_ttl.db")
        storage = SqliteStorageBackend(db_path=db_path, default_ttl=0.1)

        storage.add_turn("s_temp", "hello", "world", max_history=5)
        assert len(storage.get_history("s_temp")) == 2

        time.sleep(0.15)
        # 读取时自动过期判定
        assert storage.get_history("s_temp") == []
        assert storage.count_active() == 0
