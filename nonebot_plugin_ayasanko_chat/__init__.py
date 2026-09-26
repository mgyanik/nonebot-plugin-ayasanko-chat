# __init__.py
from __future__ import annotations

import time
from typing import Sequence

from nonebot import on_message
from nonebot.adapters import Bot, Event
from nonebot.exception import FinishedException
from nonebot.internal.matcher import Matcher
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

from .adapters import get_adapter_handler
from .config import ChatConfig
from .engine import ChatEngine, split_response
from .processor import ChatProcessor

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-ayasanko-chat",
    description="工业级高性能 AI 对话插件，支持 OneBot V11、QQ 官方、Discord 多平台与 DeepSeek 思考链",
    usage="被 @ 或提及机器人昵称时自动触发智能对话",
    type="application",
    homepage="https://github.com/mgyanik/nonebot-plugin-ayasanko-chat",
    config=ChatConfig,
    supported_adapters={"~onebot.v11", "~qq", "~discord"},
)

# ---------- 插件配置与引擎初始化 ----------
plugin_config: ChatConfig | None = None
try:
    plugin_config = ChatConfig.from_env()
    logger.info(
        f"Chat plugin config loaded: api_key={'***' if plugin_config.api_key else 'None'}, "
        f"model={plugin_config.model}, backend={plugin_config.storage_backend}, "
        f"stream={plugin_config.stream}, thinking={plugin_config.show_thinking}"
    )
except Exception as e:
    logger.error(f"聊天插件配置加载失败: {e}")

nicknames: list[str] = plugin_config.nickname if plugin_config else ["猫猫"]
logger.info(f"Using nicknames: {nicknames}")

chat_engine: ChatEngine | None = None
chat_processor: ChatProcessor | None = None

if plugin_config:
    try:
        chat_engine = ChatEngine(plugin_config)
        chat_processor = ChatProcessor(plugin_config)
        logger.info("Chat engine & processor initialized successfully")
    except Exception as e:
        logger.error(f"聊天引擎初始化失败: {e}")


# ---------- 对外导出管理函数 (兼容外部插件) ----------
def get_context_count() -> int:
    """返回当前处于有效生命周期的上下文会话数"""
    if chat_engine is None:
        return 0
    return chat_engine.session_manager.count_active()


def clear_context(user_id: str | None = None) -> int:
    """清除上下文。user_id=None 时清除所有，返回被清除的会话数"""
    if chat_engine is None:
        return 0
    return chat_engine.session_manager.clear(session_id=user_id)


# ---------- 消息响应匹配器 ----------
chat = on_message(priority=5, block=False)


@chat.handle()
async def handle_chat(
    bot: Bot,
    event: Event,
    matcher: Matcher,
) -> None:
    """统一处理聊天消息"""
    # 忽略机器人自身发送的消息
    if event.get_user_id() == bot.self_id:
        return

    # 通过适配器层统一分发
    handler = get_adapter_handler(bot)
    user_id = handler.get_user_id(bot, event)
    group_id = handler.get_group_id(bot, event)
    message_text = handler.get_plain_text(event)

    # 黑白名单判定
    if plugin_config:
        if group_id and group_id in plugin_config.blacklist_groups:
            logger.debug(f"Skipped: group {group_id} is in blacklist")
            return
        if plugin_config.whitelist_groups and group_id:
            if group_id not in plugin_config.whitelist_groups:
                logger.debug(f"Skipped: group {group_id} not in whitelist")
                return

    # 忽略指令类消息（以 / 开头）
    if message_text.strip().startswith("/"):
        logger.debug(f"Ignored command message: {message_text}")
        return

    # 检查是否提及机器人
    if not handler.is_mentioned(bot, event, message_text, nicknames):
        logger.debug(f"Skipped: not mentioned by user {user_id}")
        return

    # 提取过滤后的纯文本与多模态图片 URL
    actual_message = handler.extract_actual_message(bot, event, message_text, nicknames) or "你好呀"
    images = handler.extract_images(bot, event)
    logger.info(
        f"Processing message from {user_id}: '{actual_message}' "
        f"(images: {len(images)}, original: '{message_text}')"
    )

    if not plugin_config or not chat_engine:
        logger.info("Skipped: chat plugin engine not initialized")
        return

    if not plugin_config.api_key:
        logger.info("Skipped: no API key configured")
        return

    # 获取隔离的会话键
    session_id = handler.get_session_id(
        bot, event, mode=plugin_config.group_session_mode
    )

    try:
        start_time = time.time()
        response = await chat_engine.process_message(
            actual_message,
            user_id,
            bot,
            event,
            session_id=session_id,
            images=images,
        )
        cost = time.time() - start_time
        logger.info(f"Chat processed in {cost:.2f}s for session {session_id}")

        if response and response.strip():
            chunks = split_response(response, max_length=plugin_config.max_response_length)
            for chunk in chunks[:-1]:
                await matcher.send(chunk)
            await matcher.finish(chunks[-1])

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        try:
            await matcher.finish("喵…诺喵莉刚才走神了，能再说一遍吗？(>_<)")
        except Exception:
            pass


__all__: Sequence[str] = [
    "get_context_count",
    "clear_context",
    "chat_engine",
    "chat_processor",
    "plugin_config",
    "ChatConfig",
]
