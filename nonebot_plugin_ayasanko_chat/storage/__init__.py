# storage/__init__.py
from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseStorageBackend
from .memory import MemoryStorageBackend
from .sqlite import SqliteStorageBackend

if TYPE_CHECKING:
    from ..config import ChatConfig


def get_storage_backend(config: "ChatConfig") -> BaseStorageBackend:
    """根据配置实例化会话存储后端"""
    backend_type = (config.storage_backend or "memory").lower()

    if backend_type == "sqlite":
        return SqliteStorageBackend(
            db_path=config.sqlite_path,
            default_ttl=float(config.session_ttl),
        )

    # 默认使用内存 LRU + TTL
    return MemoryStorageBackend(
        max_sessions=config.max_sessions,
        ttl=float(config.session_ttl),
    )


__all__ = [
    "BaseStorageBackend",
    "MemoryStorageBackend",
    "SqliteStorageBackend",
    "get_storage_backend",
]
