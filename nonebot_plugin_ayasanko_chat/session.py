# session.py
from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


@dataclass
class UserSession:
    """单个用户的上下文会话"""

    user_id: str
    history: list[ChatMessage] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)

    def is_expired(self, ttl: float) -> bool:
        if ttl <= 0:
            return False
        return (time.time() - self.last_active) > ttl

    def touch(self) -> None:
        self.last_active = time.time()


class SessionManager:
    """带 LRU 淘汰与 TTL 自动失效的会话管理器"""

    def __init__(self, max_sessions: int = 500, ttl: float = 1800.0) -> None:
        self.max_sessions: int = max(max_sessions, 1)
        self.ttl: float = ttl
        self._sessions: OrderedDict[str, UserSession] = OrderedDict()

    def _evict_expired(self) -> None:
        """淘汰已过期的旧会话"""
        if self.ttl <= 0:
            return
        now = time.time()
        expired_keys = [
            uid for uid, sess in self._sessions.items()
            if (now - sess.last_active) > self.ttl
        ]
        for uid in expired_keys:
            self._sessions.pop(uid, None)

    def _ensure_capacity(self) -> None:
        """确保会话数量在最大限制以内（LRU 弹出最久未访问项）"""
        while len(self._sessions) > self.max_sessions:
            self._sessions.popitem(last=False)

    def get_session(self, user_id: str) -> UserSession:
        """获取或创建用户会话，并刷新访问时间"""
        self._evict_expired()

        if user_id in self._sessions:
            sess = self._sessions[user_id]
            sess.touch()
            self._sessions.move_to_end(user_id)
            return sess

        sess = UserSession(user_id=user_id)
        self._sessions[user_id] = sess
        self._sessions.move_to_end(user_id)
        self._ensure_capacity()
        return sess

    def get_history(self, user_id: str) -> list[dict[str, str]]:
        """获取用户的对话历史（若已过期则清空）"""
        sess = self._sessions.get(user_id)
        if sess is None:
            return []
        if sess.is_expired(self.ttl):
            self._sessions.pop(user_id, None)
            return []
        sess.touch()
        self._sessions.move_to_end(user_id)
        return list(sess.history)

    def add_turn(
        self,
        user_id: str,
        user_msg: str,
        assistant_msg: str,
        max_history: int = 10,
    ) -> None:
        """向会话中追加一轮对话并修剪超出部分"""
        sess = self.get_session(user_id)
        sess.history.append({"role": "user", "content": user_msg})
        sess.history.append({"role": "assistant", "content": assistant_msg})
        sess.touch()

        max_entries = max_history * 2
        if len(sess.history) > max_entries:
            sess.history = sess.history[-max_entries:]

    def count_active(self) -> int:
        """统计当前仍有效的活跃会话数"""
        self._evict_expired()
        return sum(1 for sess in self._sessions.values() if sess.history)

    def clear(self, user_id: str | None = None) -> int:
        """清除指定用户或全部用户的会话，返回被清除的数量"""
        if user_id is not None:
            sess = self._sessions.pop(user_id, None)
            return 1 if (sess and sess.history) else 0

        count = sum(1 for sess in self._sessions.values() if sess.history)
        self._sessions.clear()
        return count

    def cleanup_expired(self) -> int:
        """手动触发过期清理，返回清理的会话数"""
        if self.ttl <= 0:
            return 0
        now = time.time()
        expired_keys = [
            uid for uid, sess in self._sessions.items()
            if (now - sess.last_active) > self.ttl
        ]
        for uid in expired_keys:
            self._sessions.pop(uid, None)
        return len(expired_keys)
