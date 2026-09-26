# __init__.py
# fmt: off
from __future__ import annotations

import time
from typing import TypedDict, TypeGuard, cast

from nonebot import on_message
from nonebot.adapters import Bot as BaseBot, Event
from nonebot.exception import FinishedException
from nonebot.internal.matcher import Matcher
from nonebot.log import logger

from .config import ChatConfig
from .processor import ChatProcessor

# ---------- 运行时适配器类（模块级，避免函数内重复 import） ----------
try:
    from nonebot.adapters.qq import Bot as _QQBotCls
    from nonebot.adapters.qq import MessageEvent as _QQMsgEventCls
    _qq_available = True
except ImportError:
    _QQBotCls = None       # type: ignore[assignment, misc]
    _QQMsgEventCls = None  # type: ignore[assignment, misc]
    _qq_available = False

try:
    from nonebot.adapters.onebot.v11 import Bot as _OB11BotCls
    from nonebot.adapters.onebot.v11 import MessageEvent as _OB11MsgEventCls
    _onebot_v11_available = True
except ImportError:
    _OB11BotCls = None       # type: ignore[assignment, misc]
    _OB11MsgEventCls = None  # type: ignore[assignment, misc]
    _onebot_v11_available = False


# ---------- API 响应类型定义 ----------
class ChoiceMessage(TypedDict):
    content: str

class Choice(TypedDict):
    message: ChoiceMessage

class ApiResponse(TypedDict):
    choices: list[Choice]

class SendResponse(TypedDict):
    message_id: str | int


# ---------- 类型守卫 ----------
def is_send_response(obj: object) -> TypeGuard[SendResponse]:
    """判断对象是否为包含 message_id 的发送响应字典"""
    return isinstance(obj, dict) and "message_id" in obj


def is_api_response(obj: object) -> TypeGuard[ApiResponse]:
    if not isinstance(obj, dict):
        return False
    # cast 后 .get() 的返回类型变为 object | None，消除 reportUnknownMemberType
    d = cast(dict[str, object], obj)
    choices = d.get("choices")
    if not isinstance(choices, list) or not choices:
        return False
    first_choice: object = choices[0]  # pyright: ignore[reportUnknownVariableType]
    if not isinstance(first_choice, dict):
        return False
    fd = cast(dict[str, object], first_choice)
    message = fd.get("message")
    if not isinstance(message, dict):
        return False
    md = cast(dict[str, object], message)
    content = md.get("content")
    return isinstance(content, str)


# ---------- 消息匹配器 ----------
chat = on_message(priority=5, block=False)

# ---------- 插件初始化 ----------
plugin_config: ChatConfig | None = None
try:
    plugin_config = ChatConfig.from_env()
    logger.info(
        f"Plugin config loaded: api_key={'***' if plugin_config.api_key else 'None'}"
    )
except Exception as e:
    logger.error(f"聊天插件配置加载失败: {e}")

nicknames: list[str] = plugin_config.nickname if plugin_config else ["猫猫"]
logger.info(f"Using nicknames: {nicknames}")

chat_processor: ChatProcessor | None = None
if plugin_config:
    try:
        chat_processor = ChatProcessor(plugin_config)
        logger.info(f"Chat processor initialized: {bool(chat_processor)}")
    except Exception as e:
        logger.error(f"聊天处理器初始化失败: {e}")


# ---------- 协议检测函数 ----------
def get_bot_type(bot: BaseBot) -> str:
    """检测机器人类型"""
    if _QQBotCls is not None and isinstance(bot, _QQBotCls):
        return "qq_official"
    if _OB11BotCls is not None and isinstance(bot, _OB11BotCls):
        return "onebot_v11"
    return "unknown"


def get_user_id(_bot: BaseBot, event: Event, bot_type: str) -> str:
    """统一获取用户ID（_bot 保留以维持接口一致性）"""
    if bot_type == "qq_official" and _QQMsgEventCls is not None:
        if isinstance(event, _QQMsgEventCls):
            return event.get_user_id()
    elif bot_type == "onebot_v11" and _OB11MsgEventCls is not None:
        if isinstance(event, _OB11MsgEventCls):
            return str(event.get_user_id())
    return event.get_user_id()


def get_plain_text(event: Event, bot_type: str) -> str:
    """统一获取纯文本内容"""
    if bot_type == "qq_official" and _QQMsgEventCls is not None:
        if isinstance(event, _QQMsgEventCls):
            return str(event.get_plaintext())
    elif bot_type == "onebot_v11" and _OB11MsgEventCls is not None:
        if isinstance(event, _OB11MsgEventCls):
            return str(event.get_plaintext())
    return str(event.get_plaintext())


def _seg_data_get(seg: object, key: str) -> object:
    """安全地从消息段的 data 字典中取值，消除 seg.data.get() 的类型未知问题"""
    raw_data = getattr(seg, "data", {})
    if not isinstance(raw_data, dict):
        return None
    d = cast(dict[str, object], raw_data)
    return d.get(key)


def is_mentioned(bot: BaseBot, event: Event, bot_type: str, message_text: str) -> bool:
    """检查是否@了机器人 或 提到了机器人昵称"""
    bot_id = bot.self_id

    if bot_type == "qq_official" and _QQMsgEventCls is not None:
        if isinstance(event, _QQMsgEventCls):
            for seg in event.get_message():
                seg_type: object = getattr(seg, "type", None)
                if seg_type == "mention" and _seg_data_get(seg, "user_id") == bot_id:
                    logger.debug("Triggered by @mention (QQ official)")
                    return True

    elif bot_type == "onebot_v11" and _OB11MsgEventCls is not None:
        if isinstance(event, _OB11MsgEventCls):
            for seg in event.get_message():
                seg_type = getattr(seg, "type", None)
                if seg_type == "at" and _seg_data_get(seg, "qq") == bot_id:
                    logger.debug("Triggered by @mention (OneBot V11)")
                    return True

    if f"[CQ:at,qq={bot_id}]" in message_text:
        logger.debug("Triggered by @mention CQ code")
        return True

    for nickname in nicknames:
        if nickname in message_text:
            logger.debug(f"Triggered by nickname: {nickname}")
            return True

    if bot_type == "onebot_v11" and _OB11MsgEventCls is not None:
        if isinstance(event, _OB11MsgEventCls):
            if getattr(event, "message_type", None) == "private":
                logger.debug("Triggered by private message (OneBot V11)")
                return True

    return False


def extract_actual_message(
    bot: BaseBot, event: Event, bot_type: str, message_text: str
) -> str:
    """提取去除@和昵称后的实际消息内容"""
    result = message_text
    bot_id = bot.self_id

    if bot_type == "onebot_v11" and _OB11MsgEventCls is not None:
        if isinstance(event, _OB11MsgEventCls):
            parts: list[str] = []
            for seg in event.get_message():
                seg_type: object = getattr(seg, "type", None)
                # bool() 包裹确保 is_at_bot 类型为 bool，消除 reportUnknownVariableType
                is_at_bot = bool(
                    seg_type == "at" and _seg_data_get(seg, "qq") == bot_id
                )
                if seg_type == "text" and not is_at_bot:
                    parts.append(str(seg))
            if parts:
                result = "".join(parts)

    for nickname in nicknames:
        if nickname in result:
            result = result.replace(nickname, "", 1).strip()
            break

    return result.strip() or message_text


async def delete_message(bot: BaseBot, message_id: str | int) -> bool:
    """统一删除消息"""
    try:
        if _OB11BotCls is not None and isinstance(bot, _OB11BotCls):
            if isinstance(message_id, str):
                if not message_id.isdigit():
                    logger.warning(f"Invalid message_id format for delete: {message_id}")
                    return False
                msg_id = int(message_id)
            else:
                msg_id = message_id
            await bot.delete_msg(message_id=msg_id)
            return True
    except Exception as e:
        logger.debug(f"Failed to delete message: {e}")
    return False

def get_context_count() -> int:
    """返回当前有历史记录的用户数"""
    if chat_processor is None:
        return 0
    return sum(
        1 for uq in chat_processor.user_queues.values()
        if uq.history
    )


def clear_context(user_id: str | None = None) -> int:
    """清除上下文，返回清除的用户数。user_id=None 时清除所有"""
    if chat_processor is None:
        return 0
    if user_id is not None:
        uq = chat_processor.user_queues.get(user_id)
        if uq:
            uq.history.clear()
            return 1
        return 0
    count = sum(1 for uq in chat_processor.user_queues.values() if uq.history)
    for uq in chat_processor.user_queues.values():
        uq.history.clear()
    return count





# ---------- 消息处理入口 ----------
@chat.handle()
async def handle_chat(
    bot: BaseBot,
    event: Event,
    matcher: Matcher,
) -> None:
    """处理聊天消息（兼容 QQ 官方和 OneBot V11）"""
    bot_type = get_bot_type(bot)
    if bot_type == "unknown":
        logger.debug(f"Skipped: unknown bot type {type(bot)}")
        return

    if event.get_user_id() == bot.self_id:
        return

    user_id = get_user_id(bot, event, bot_type)
    message_text = get_plain_text(event, bot_type)

    if message_text.strip().startswith("/"):
        logger.debug(f"Ignored command: {message_text}")
        return

    if not is_mentioned(bot, event, bot_type, message_text):
        logger.debug(f"Skipped: not mentioned by user {user_id}")
        return

    actual_message = extract_actual_message(bot, event, bot_type, message_text) or "你好呀"
    logger.info(f"Processing from {user_id}: '{actual_message}' (original: '{message_text}')")

    if not plugin_config or not chat_processor:
        logger.info("Skipped: plugin not initialized")
        return

    if not plugin_config.api_key:
        logger.info("Skipped: no API key")
        return

    thinking_msg: object = None
    try:
        start_time = time.time()
        response = await chat_processor.process_message(actual_message, user_id, bot, event)
        logger.info(f"Chat processed in {time.time() - start_time:.2f}s for user {user_id}")

        if is_send_response(thinking_msg):
            _ = await delete_message(bot, thinking_msg["message_id"])

        if response and response.strip():
            await matcher.finish(response)  # pyright: ignore[reportUnknownMemberType]

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"Chat plugin error: {e}")
        try:
            await matcher.finish("喵…诺喵莉刚才走神了，能再说一遍吗？(>_<)")  # pyright: ignore[reportUnknownMemberType]
        except Exception:
            pass

__all__: list[str] = ["get_context_count", "clear_context"]
