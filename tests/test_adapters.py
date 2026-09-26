# tests/test_adapters.py
from nonebot_plugin_ayasanko_chat.adapters import FallbackHandler
from nonebot_plugin_ayasanko_chat.adapters.discord import DiscordHandler
from nonebot_plugin_ayasanko_chat.engine import split_response


class MockBot:
    def __init__(self, self_id: str = "123456"):
        self.self_id = self_id


class MockEvent:
    def __init__(self, user_id: str = "u100", group_id: str | None = None, text: str = ""):
        self._user_id = user_id
        self.group_id = group_id
        self._text = text

    def get_user_id(self) -> str:
        return self._user_id

    def get_plaintext(self) -> str:
        return self._text


def test_session_id_generation():
    handler = FallbackHandler()
    bot = MockBot("bot_001")

    # 私聊
    private_event = MockEvent(user_id="u123", group_id=None)
    sid_private = handler.get_session_id(bot, private_event, mode="individual")
    assert sid_private == "unknown:private:u123"

    # 群聊 - 独立模式
    group_event = MockEvent(user_id="u123", group_id="g888")
    sid_ind = handler.get_session_id(bot, group_event, mode="individual")
    assert sid_ind == "unknown:group:g888:u123"

    # 群聊 - 共享模式
    sid_shared = handler.get_session_id(bot, group_event, mode="shared")
    assert sid_shared == "unknown:group:g888:shared"


def test_discord_message_cleaning():
    discord_handler = DiscordHandler()
    bot = MockBot("999999")
    event = MockEvent(user_id="d100", text="<@999999> 猫猫 今天天气怎么样？")

    # 提及检测
    assert discord_handler.is_mentioned(bot, event, event.get_plaintext(), ["猫猫"]) is True

    # 提取净化后的消息（移除 <@999999> 与首个出现的昵称）
    extracted = discord_handler.extract_actual_message(bot, event, event.get_plaintext(), ["猫猫"])
    assert extracted == "今天天气怎么样？"


def test_split_response():
    short_text = "这是一个很短的文本"
    assert split_response(short_text, max_length=100) == [short_text]

    long_text = "\n".join([f"第{i}行内容详细叙述" for i in range(50)])
    chunks = split_response(long_text, max_length=100)
    assert len(chunks) > 1
    assert all(len(c) <= 120 for c in chunks)
