# adapters/__init__.py
from __future__ import annotations

from typing import Sequence

from nonebot.adapters import Bot, Event

from .base import BaseAdapterHandler
from .discord import DiscordHandler
from .onebot import OneBotV11Handler
from .qq import QQOfficialHandler


class FallbackHandler(BaseAdapterHandler):
    """通用未知适配器兜底处理器"""

    bot_type = "unknown"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def match(self, _bot: Bot) -> bool:
        return True

    def get_user_id(self, _bot: Bot, event: Event) -> str:
        return event.get_user_id()

    def get_plain_text(self, event: Event) -> str:
        return str(event.get_plaintext())

    def is_mentioned(
        self,
        _bot: Bot,
        _event: Event,
        message_text: str,
        nicknames: list[str],
    ) -> bool:
        for name in nicknames:
            if name and name in message_text:
                return True
        return False

    def extract_actual_message(
        self,
        _bot: Bot,
        _event: Event,
        message_text: str,
        nicknames: list[str],
    ) -> str:
        result = message_text
        for name in nicknames:
            if name and name in result:
                result = result.replace(name, "", 1).strip()
                break
        return result.strip() or message_text


_HANDLERS: list[BaseAdapterHandler] = []
if OneBotV11Handler.is_available():
    _HANDLERS.append(OneBotV11Handler())
if QQOfficialHandler.is_available():
    _HANDLERS.append(QQOfficialHandler())
if DiscordHandler.is_available():
    _HANDLERS.append(DiscordHandler())

_FALLBACK_HANDLER = FallbackHandler()


def get_adapter_handler(bot: Bot) -> BaseAdapterHandler:
    """根据 Bot 实例获取匹配的适配器处理器"""
    for handler in _HANDLERS:
        if handler.match(bot):
            return handler
    return _FALLBACK_HANDLER


__all__: Sequence[str] = [
    "BaseAdapterHandler",
    "OneBotV11Handler",
    "QQOfficialHandler",
    "DiscordHandler",
    "get_adapter_handler",
]
