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
    max_concurrent: int = Field(default=5)              # 最大并发请求数
    max_history: int = Field(default=10)                 # 最大保留上下文对话轮数
    session_ttl: int = Field(default=1800)               # 会话有效时长（秒，默认 30 分钟）
    max_sessions: int = Field(default=500)               # 最大内存活跃会话数（LRU淘汰保护）
    storage_backend: str = Field(default="memory")       # 存储后端："memory" 或 "sqlite"
    sqlite_path: str = Field(default="data/ayasanko_chat.db") # SQLite 数据库持久化路径
    system_prompt: str = Field(default="你是一位有用的AI")
    nickname: list[str] = Field(default=["猫猫"])

    # 架构与思考链支持
    stream: bool = Field(default=False)                  # 是否开启 SSE 流式接收
    show_thinking: bool = Field(default=True)            # 是否展示 DeepSeek / R1 思考过程 (reasoning_content)
    group_session_mode: str = Field(default="individual") # "individual"(群内单人独立) 或 "shared"(群内全员共享上下文)
    max_retries: int = Field(default=2)                  # 遇到网络抖动/429/5xx时的最大重试次数
    retry_delay: float = Field(default=1.5)              # 重试基础延迟时间（秒）
    rate_limit_requests: int = Field(default=10)         # 速率限制：单用户/会话在周期内的最大请求数（0 表示关闭）
    rate_limit_period: int = Field(default=60)           # 速率限制：周期窗口（秒）
    whitelist_groups: list[str] = Field(default_factory=list) # 群白名单（非空时仅白名单群生效）
    blacklist_groups: list[str] = Field(default_factory=list) # 群黑名单（黑名单内的群不响应）
    max_response_length: int = Field(default=1200)       # 单条回复最大字数，超出自动安全分段
    # fmt: on

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    @classmethod
    def _parse_str_or_list(cls, v: str | list[str] | set[str] | None, default: list[str]) -> list[str]:
        if v is None:
            return default
        if isinstance(v, (set, list)):
            return [str(item).strip() for item in v if str(item).strip()]
        v_stripped = v.strip()
        if v_stripped.startswith("[") and v_stripped.endswith("]"):
            try:
                parsed = cast(list[object], json.loads(v_stripped))
                return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass
        if "," in v_stripped:
            return [item.strip() for item in v_stripped.split(",") if item.strip()]
        return [v_stripped] if v_stripped else default

    @field_validator("nickname", mode="before")
    @classmethod
    def parse_nickname(cls, v: str | list[str] | set[str] | None) -> list[str]:
        """将环境变量中的 nickname 解析为列表"""
        return cls._parse_str_or_list(v, ["猫猫"])

    @field_validator("whitelist_groups", mode="before")
    @classmethod
    def parse_whitelist(cls, v: str | list[str] | set[str] | None) -> list[str]:
        return cls._parse_str_or_list(v, [])

    @field_validator("blacklist_groups", mode="before")
    @classmethod
    def parse_blacklist(cls, v: str | list[str] | set[str] | None) -> list[str]:
        return cls._parse_str_or_list(v, [])

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
