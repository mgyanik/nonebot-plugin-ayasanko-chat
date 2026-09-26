# adapters/qq.py
from __future__ import annotations

from typing import cast

from nonebot.adapters import Bot, Event

from .base import BaseAdapterHandler

try:
    from nonebot.adapters.qq import Bot as QQBot
    from nonebot.adapters.qq import MessageEvent as QQMessageEvent

    _AVAILABLE = True
except ImportError:
    QQBot = None  # type: ignore[assignment, misc]
    QQMessageEvent = None  # type: ignore[assignment, misc]
    _AVAILABLE = False


def _seg_data_get(seg: object, key: str) -> object:
    raw_data = getattr(seg, "data", {})
    if not isinstance(raw_data, dict):
        return None
    d = cast(dict[str, object], raw_data)
    return d.get(key)


class QQOfficialHandler(BaseAdapterHandler):
    """QQ 官方开放平台适配器处理器"""

    bot_type = "qq_official"

    @classmethod
    def is_available(cls) -> bool:
        return _AVAILABLE

    def match(self, bot: Bot) -> bool:
        return QQBot is not None and isinstance(bot, QQBot)

    def get_user_id(self, _bot: Bot, event: Event) -> str:
        if QQMessageEvent is not None and isinstance(event, QQMessageEvent):
            return str(event.get_user_id())
        return event.get_user_id()

    def get_plain_text(self, event: Event) -> str:
        if QQMessageEvent is not None and isinstance(event, QQMessageEvent):
            return str(event.get_plaintext())
        return str(event.get_plaintext())

    def extract_images(self, _bot: Bot, event: Event) -> list[str]:
        images: list[str] = []
        if QQMessageEvent is not None and isinstance(event, QQMessageEvent):
            for seg in event.get_message():
                if getattr(seg, "type", None) == "image":
                    url = _seg_data_get(seg, "url")
                    if url and isinstance(url, str) and url.startswith("http"):
                        images.append(url)
            # 兼容 attachments 列表
            attachments = getattr(event, "attachments", None)
            if isinstance(attachments, list):
                for att in attachments:
                    url = getattr(att, "url", None)
                    if url and isinstance(url, str) and url.startswith("http") and url not in images:
                        images.append(url)
        return images

    def is_mentioned(
        self,
        bot: Bot,
        event: Event,
        message_text: str,
        nicknames: list[str],
    ) -> bool:
        bot_id = bot.self_id

        if QQMessageEvent is not None and isinstance(event, QQMessageEvent):
            for seg in event.get_message():
                seg_type = getattr(seg, "type", None)
                if seg_type == "mention" and str(_seg_data_get(seg, "user_id")) == str(bot_id):
                    return True

        for name in nicknames:
            if name and name in message_text:
                return True

        return False

    def extract_actual_message(
        self,
        bot: Bot,
        event: Event,
        message_text: str,
        nicknames: list[str],
    ) -> str:
        result = message_text

        for name in nicknames:
            if name and name in result:
                result = result.replace(name, "", 1).strip()
                break

        return result.strip() or message_text
