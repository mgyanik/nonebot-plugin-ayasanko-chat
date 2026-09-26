# adapters/base.py
from __future__ import annotations

from abc import ABC, abstractmethod

from nonebot.adapters import Bot, Event


class BaseAdapterHandler(ABC):
    """适配器处理器抽象基类"""

    bot_type: str = "base"

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """检查该适配器运行依赖是否已导入"""
        ...

    @abstractmethod
    def match(self, bot: Bot) -> bool:
        """检查 Bot 实例是否归属于该适配器"""
        ...

    @abstractmethod
    def get_user_id(self, bot: Bot, event: Event) -> str:
        """统一获取消息发送者 ID"""
        ...

    def get_group_id(self, _bot: Bot, event: Event) -> str | None:
        """获取群组/频道 ID，私聊则返回 None"""
        group_id = getattr(event, "group_id", None)
        if group_id is not None:
            return str(group_id)
        channel_id = getattr(event, "channel_id", None)
        if channel_id is not None:
            return str(channel_id)
        guild_id = getattr(event, "guild_id", None)
        if guild_id is not None:
            return str(guild_id)
        return None

    def get_session_id(self, bot: Bot, event: Event, mode: str = "individual") -> str:
        """
        生成隔离的会话 ID
        mode='individual': 群内各人独立 -> group_{gid}_{uid} 或 private_{uid}
        mode='shared': 群内共享上下文 -> group_{gid}_shared 或 private_{uid}
        """
        uid = self.get_user_id(bot, event)
        gid = self.get_group_id(bot, event)
        if gid:
            if mode == "shared":
                return f"{self.bot_type}:group:{gid}:shared"
            return f"{self.bot_type}:group:{gid}:{uid}"
        return f"{self.bot_type}:private:{uid}"

    @abstractmethod
    def get_plain_text(self, event: Event) -> str:
        """统一获取纯文本消息内容"""
        ...

    def extract_images(self, _bot: Bot, _event: Event) -> list[str]:
        """提取消息中的图片 URL（多模态视觉模型支持）"""
        return []

    @abstractmethod
    def is_mentioned(
        self,
        bot: Bot,
        event: Event,
        message_text: str,
        nicknames: list[str],
    ) -> bool:
        """检查是否被 @ 或提及"""
        ...

    @abstractmethod
    def extract_actual_message(
        self,
        bot: Bot,
        event: Event,
        message_text: str,
        nicknames: list[str],
    ) -> str:
        """提取清洗掉 @ 与机器人昵称后的实际对话文本"""
        ...

    async def delete_message(self, _bot: Bot, _message_id: str | int) -> bool:
        """撤回/删除消息（默认不支持，子类按需实现）"""
        return False
