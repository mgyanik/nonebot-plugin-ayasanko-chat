# storage/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseStorageBackend(ABC):
    """存储后端抽象基类"""

    @abstractmethod
    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        """获取指定会话的历史记录"""
        ...

    @abstractmethod
    def add_turn(
        self,
        session_id: str,
        user_msg: Any,
        assistant_msg: str,
        max_history: int = 10,
    ) -> None:
        """追加一轮会话并自动修剪"""
        ...

    @abstractmethod
    def clear(self, session_id: str | None = None) -> int:
        """清除指定会话或全部会话，返回被清除的会话数"""
        ...

    @abstractmethod
    def count_active(self) -> int:
        """获取当前活跃会话数"""
        ...

    @abstractmethod
    def cleanup_expired(self, ttl: float) -> int:
        """清理已过期失效的会话，返回清理数量"""
        ...
