# tests/test_config.py
import pytest
from nonebot_plugin_ayasanko_chat.config import ChatConfig


def test_default_config():
    config = ChatConfig()
    assert config.model == "glm-4.5-air"
    assert config.nickname == ["猫猫"]
    assert config.max_tokens == 1000
    assert config.session_ttl == 1800
    assert config.max_sessions == 500
    assert config.group_session_mode == "individual"
    assert config.max_retries == 2
    assert config.whitelist_groups == []
    assert config.blacklist_groups == []


def test_nickname_parsing():
    # JSON list string
    config1 = ChatConfig(nickname='["bot", "alice"]')
    assert config1.nickname == ["bot", "alice"]

    # Comma separated string
    config2 = ChatConfig(nickname="bot, alice, bob")
    assert config2.nickname == ["bot", "alice", "bob"]

    # Single string
    config3 = ChatConfig(nickname="bot")
    assert config3.nickname == ["bot"]

    # Set
    config4 = ChatConfig(nickname={"bot1", "bot2"})
    assert set(config4.nickname) == {"bot1", "bot2"}


def test_whitelist_blacklist_parsing():
    config = ChatConfig(
        whitelist_groups='["123456", "789012"]',
        blacklist_groups="999999, 888888",
    )
    assert config.whitelist_groups == ["123456", "789012"]
    assert config.blacklist_groups == ["999999", "888888"]
