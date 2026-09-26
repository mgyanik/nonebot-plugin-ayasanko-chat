# storage/memory.py
from __future__ import annotations

from typing import Any

from ..session import SessionManager
from .base import BaseStorageBackend


class MemoryStorageBackend(BaseStorageBackend):
    """基于内存的 LRU + TTL 会话存储后端"""

    def __init__(self, max_sessions: int = 500, ttl: float = 1800.0) -> None:
        self._manager = SessionManager(max_sessions=max_sessions, ttl=ttl)

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        return self._manager.get_history(session_id)

    def add_turn(
        self,
        session_id: str,
        user_msg: Any,
        assistant_msg: str,
        max_history: int = 10,
    ) -> None:
        self._manager.add_turn(
            user_id=session_id,
            user_msg=user_msg,
            assistant_msg=assistant_msg,
            max_history=max_history,
        )

    def clear(self, session_id: str | None = None) -> int:
        return self._manager.clear(user_id=session_id)

    def count_active(self) -> int:
        return self._manager.count_active()

    def cleanup_expired(self, ttl: float) -> int:
        return self._manager.cleanup_expired()
