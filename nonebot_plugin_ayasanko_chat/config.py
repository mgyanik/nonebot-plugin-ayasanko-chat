# config.py
from __future__ import annotations

import json
import os
from typing import ClassVar, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator
from nonebot import get_driver
from nonebot.log import logger


class ChatConfig(BaseModel):
    """聊天插件配置（自动从 NoneBot 全局配置加载）"""

    # fmt: off
    api_key: str | None = Field(default=None)
    api_base: str = Field(default="https://open.bigmodel.cn/api/paas/v4")
    model: str = Field(default="glm-4.5-air")
    max_tokens: int = Field(default=1000)
    temperature: float = Field(default=1.0)
    timeout: int = Field(default=30)
    max_concurrent: int = Field(default=5) # 最大并发请求数
    max_history: int = Field(default=10) # 最大上下文数量
    storage_backend: str = Field(default="memory") # 存储上下文的方法，"memory"则表示使用内存存储
    system_prompt: str = Field(default="你是一位有用的AI")
    nickname: list[str] = Field(default=["猫猫"])
    # fmt: on
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    @field_validator("nickname", mode="before")
    @classmethod
    def parse_nickname(cls, v: str | list[str] | set[str] | None) -> list[str]:
        """将环境变量中的 nickname 解析为列表（支持 JSON 数组、普通字符串或集合）"""
        if v is None:
            return ["猫猫"]
        if isinstance(v, set):
            return [str(item) for item in v]
        if isinstance(v, list):
            return [str(item) for item in v]
        v_stripped = v.strip()
        if v_stripped.startswith("[") and v_stripped.endswith("]"):
            try:
                parsed = cast(list[object], json.loads(v_stripped))
                return [str(item) for item in parsed]
            except json.JSONDecodeError:
                pass
        return [v_stripped]

    @field_validator("system_prompt", mode="before")
    @classmethod
    def fallback_system_prompt(cls, v: str | None) -> str:
        """如果 CHAT__SYSTEM_PROMPT 未设置，则尝试使用 SYSTEM_PROMPT 环境变量"""
        if v is not None:
            return v
        fallback = os.getenv("SYSTEM_PROMPT")
        if fallback:
            logger.info("Using fallback SYSTEM_PROMPT from environment")
            return fallback
        return "你是一位有用的AI"

    @classmethod
    def from_env(cls) -> ChatConfig:
        """从 NoneBot 全局配置创建实例（自动加载 .env 文件）"""
        global_config = get_driver().config
        dumped = global_config.model_dump()
        chat_data = cast(dict[str, object], dumped.get("chat", {}))
        return cls.model_validate(chat_data)
