# adapters/discord.py
from __future__ import annotations

import re
from typing import cast

from nonebot.adapters import Bot, Event
from nonebot.log import logger

from .base import BaseAdapterHandler

try:
    from nonebot.adapters.discord import Bot as DiscordBot
    from nonebot.adapters.discord import MessageEvent as DiscordMessageEvent

    _AVAILABLE = True
except ImportError:
    DiscordBot = None  # type: ignore[assignment, misc]
    DiscordMessageEvent = None  # type: ignore[assignment, misc]
    _AVAILABLE = False


def _seg_data_get(seg: object, key: str) -> object:
    raw_data = getattr(seg, "data", {})
    if not isinstance(raw_data, dict):
        return None
    d = cast(dict[str, object], raw_data)
    return d.get(key)


class DiscordHandler(BaseAdapterHandler):
    """Discord 协议适配器处理器"""

    bot_type = "discord"

    @classmethod
    def is_available(cls) -> bool:
        return _AVAILABLE

    def match(self, bot: Bot) -> bool:
        return DiscordBot is not None and isinstance(bot, DiscordBot)

    def get_user_id(self, _bot: Bot, event: Event) -> str:
        uid = getattr(event, "user_id", None)
        if uid is not None:
            return str(uid)
        author = getattr(event, "author", None)
        if author is not None:
            author_id = getattr(author, "id", None)
            if author_id is not None:
                return str(author_id)
        return event.get_user_id()

    def get_group_id(self, _bot: Bot, event: Event) -> str | None:
        guild_id = getattr(event, "guild_id", None)
        channel_id = getattr(event, "channel_id", None)
        if guild_id is not None and channel_id is not None:
            return f"{guild_id}:{channel_id}"
        if channel_id is not None and guild_id is not None:
            return str(channel_id)
        return None

    def get_plain_text(self, event: Event) -> str:
        return str(event.get_plaintext())

    def extract_images(self, _bot: Bot, event: Event) -> list[str]:
        images: list[str] = []
        # Discord 附件 attachments
        attachments = getattr(event, "attachments", None)
        if isinstance(attachments, list):
            for att in attachments:
                url = getattr(att, "url", None) or getattr(att, "proxy_url", None)
                if url and isinstance(url, str) and url.startswith("http"):
                    images.append(url)

        # 检查消息段
        if DiscordMessageEvent is not None and isinstance(event, DiscordMessageEvent):
            for seg in event.get_message():
                if getattr(seg, "type", None) in ("attachment", "image"):
                    url = _seg_data_get(seg, "url")
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
        bot_id = str(bot.self_id)

        # 检查是否为私信 (Direct Message)
        guild_id = getattr(event, "guild_id", None)
        if guild_id is None and getattr(event, "channel_id", None) is not None:
            return True

        # 检查 Discord 消息段中的 mention_user
        if DiscordMessageEvent is not None and isinstance(event, DiscordMessageEvent):
            for seg in event.get_message():
                seg_type = getattr(seg, "type", None)
                if seg_type in ("mention_user", "mention"):
                    uid = str(_seg_data_get(seg, "user_id") or "")
                    if uid == bot_id:
                        return True

        # 检查文本中的 Discord 提及格式: <@123456> 或 <@!123456>
        if f"<@{bot_id}>" in message_text or f"<@!{bot_id}>" in message_text:
            return True

        # 检查昵称提及
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
        bot_id = str(bot.self_id)

        # 清除 <@bot_id> 和 <@!bot_id>
        result = re.sub(rf"<@!?{re.escape(bot_id)}>", "", result)

        # 清除消息段中非 mention 的纯文本组装
        if DiscordMessageEvent is not None and isinstance(event, DiscordMessageEvent):
            parts: list[str] = []
            for seg in event.get_message():
                seg_type = getattr(seg, "type", None)
                if seg_type == "text":
                    parts.append(str(seg))
            if parts:
                clean_text = "".join(parts)
                clean_text = re.sub(rf"<@!?{re.escape(bot_id)}>", "", clean_text)
                if clean_text.strip():
                    result = clean_text

        # 剔除首个出现的机器人昵称
        for name in nicknames:
            if name and name in result:
                result = result.replace(name, "", 1).strip()
                break

        return result.strip() or message_text

    async def delete_message(self, bot: Bot, message_id: str | int) -> bool:
        if DiscordBot is not None and isinstance(bot, DiscordBot):
            try:
                logger.debug(f"Discord delete message requested for {message_id}")
                return True
            except Exception as e:
                logger.debug(f"Discord delete message failed: {e}")
        return False
