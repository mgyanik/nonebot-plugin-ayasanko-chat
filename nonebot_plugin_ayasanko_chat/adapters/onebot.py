# adapters/onebot.py
from __future__ import annotations

import re
from typing import cast

from nonebot.adapters import Bot, Event
from nonebot.log import logger

from .base import BaseAdapterHandler

try:
    from nonebot.adapters.onebot.v11 import Bot as OB11Bot
    from nonebot.adapters.onebot.v11 import MessageEvent as OB11MessageEvent

    _AVAILABLE = True
except ImportError:
    OB11Bot = None  # type: ignore[assignment, misc]
    OB11MessageEvent = None  # type: ignore[assignment, misc]
    _AVAILABLE = False


def _seg_data_get(seg: object, key: str) -> object:
    raw_data = getattr(seg, "data", {})
    if not isinstance(raw_data, dict):
        return None
    d = cast(dict[str, object], raw_data)
    return d.get(key)


class OneBotV11Handler(BaseAdapterHandler):
    """OneBot V11 协议适配器处理器"""

    bot_type = "onebot_v11"

    @classmethod
    def is_available(cls) -> bool:
        return _AVAILABLE

    def match(self, bot: Bot) -> bool:
        return OB11Bot is not None and isinstance(bot, OB11Bot)

    def get_user_id(self, _bot: Bot, event: Event) -> str:
        if OB11MessageEvent is not None and isinstance(event, OB11MessageEvent):
            return str(event.get_user_id())
        return event.get_user_id()

    def get_plain_text(self, event: Event) -> str:
        if OB11MessageEvent is not None and isinstance(event, OB11MessageEvent):
            return str(event.get_plaintext())
        return str(event.get_plaintext())

    def extract_images(self, _bot: Bot, event: Event) -> list[str]:
        images: list[str] = []
        if OB11MessageEvent is not None and isinstance(event, OB11MessageEvent):
            for seg in event.get_message():
                if getattr(seg, "type", None) == "image":
                    url = _seg_data_get(seg, "url") or _seg_data_get(seg, "file")
                    if url and isinstance(url, str) and url.startswith("http"):
                        images.append(url)

        # 检查 CQ 码中的图片
        raw_msg = str(getattr(event, "raw_message", ""))
        for match in re.finditer(r"\[CQ:image,[^\]]*url=([^,\]]+)", raw_msg):
            url = match.group(1).strip()
            if url.startswith("http") and url not in images:
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

        # 检查是否为私聊
        if OB11MessageEvent is not None and isinstance(event, OB11MessageEvent):
            if getattr(event, "message_type", None) == "private":
                return True

            for seg in event.get_message():
                seg_type = getattr(seg, "type", None)
                if seg_type == "at" and str(_seg_data_get(seg, "qq")) == str(bot_id):
                    return True

        if f"[CQ:at,qq={bot_id}]" in message_text:
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
        bot_id = bot.self_id

        if OB11MessageEvent is not None and isinstance(event, OB11MessageEvent):
            parts: list[str] = []
            for seg in event.get_message():
                seg_type = getattr(seg, "type", None)
                is_at_bot = bool(
                    seg_type == "at" and str(_seg_data_get(seg, "qq")) == str(bot_id)
                )
                if seg_type == "text" and not is_at_bot:
                    parts.append(str(seg))
            if parts:
                result = "".join(parts)

        # 剔除首个出现的机器人昵称
        for name in nicknames:
            if name and name in result:
                result = result.replace(name, "", 1).strip()
                break

        return result.strip() or message_text

    async def delete_message(self, bot: Bot, message_id: str | int) -> bool:
        if OB11Bot is not None and isinstance(bot, OB11Bot):
            try:
                msg_id = int(message_id) if isinstance(message_id, str) else message_id
                await bot.delete_msg(message_id=msg_id)
                return True
            except Exception as e:
                logger.debug(f"OneBot V11 failed to delete message {message_id}: {e}")
        return False
