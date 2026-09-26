# processor.py
"""
兼容层：向前兼容旧版 ChatProcessor 导入与调用接口
内部全面委托给高性能 ChatEngine 与 StorageBackend
"""
from __future__ import annotations

from typing import Any

from nonebot.adapters import Bot, Event

from .config import ChatConfig
from .engine import ChatEngine, ChatTask


class ChatProcessor:
    """旧版 ChatProcessor 兼容适配器"""

    def __init__(self, config: ChatConfig) -> None:
        self.config = config
        self._engine = ChatEngine(config)

    @property
    def engine(self) -> ChatEngine:
        return self._engine

    @property
    def user_queues(self) -> dict[str, Any]:
        return self._engine.user_queues

    @property
    def semaphore(self) -> Any:
        return self._engine.semaphore

    def get_history(self, user_id: str) -> list[dict[str, Any]]:
        return self._engine.session_manager.get_history(user_id)

    async def process_message(
        self,
        message: str,
        user_id: str,
        bot: Bot,
        event: Event,
        images: list[str] | None = None,
    ) -> str:
        return await self._engine.process_message(
            message=message,
            user_id=user_id,
            _bot=bot,
            _event=event,
            images=images,
        )

    async def call_bigmodel_api(
        self,
        message: str,
        history: list[dict[str, Any]] | None = None,
    ) -> str:
        return await self._engine.call_api(message, history=history)

    async def get_queue_length(self, user_id: str) -> int:
        if user_id not in self._engine.user_queues:
            return 0
        return self._engine.user_queues[user_id].queue.qsize()

    def get_metrics(self) -> dict[str, Any]:
        return self._engine.get_metrics()

    def cleanup_expired_queues(self) -> None:
        self._engine.cleanup_idle_queues()
        self._engine.session_manager.cleanup_expired(float(self.config.session_ttl))


__all__ = ["ChatProcessor", "ChatTask"]
