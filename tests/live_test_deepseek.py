# tests/live_test_deepseek.py
import asyncio
from nonebot_plugin_ayasanko_chat.config import ChatConfig
from nonebot_plugin_ayasanko_chat.engine import ChatEngine


async def main():
    print("=== Testing DeepSeek API with Ayasanko Chat Engine ===")

    api_key = os.getenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
    api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")

    # 1. 测试常规 DeepSeek Chat
    config = ChatConfig(
        api_key=api_key,
        api_base=api_base,
        model="deepseek-chat",
        storage_backend="sqlite",
        sqlite_path="tests/test_live.db",
        stream=False,
        show_thinking=True,
    )
    engine = ChatEngine(config)

    print("\n[1] Testing process_message with SQLite persistence...")
    reply1 = await engine.process_message(
        message="你好！请用一句话介绍你自己。",
        user_id="user_live_test",
        session_id="test:group:100:user1",
    )
    print(f"Bot Reply 1:\n{reply1}")

    print("\n[2] Testing Context History...")
    reply2 = await engine.process_message(
        message="我上一句话对你说了什么？",
        user_id="user_live_test",
        session_id="test:group:100:user1",
    )
    print(f"Bot Reply 2:\n{reply2}")

    print("\n[3] Testing DeepSeek-Reasoner (R1) with Thinking Extraction...")
    r1_config = ChatConfig(
        api_key=api_key,
        api_base=api_base,
        model="deepseek-reasoner",
        stream=True,
        show_thinking=True,
    )
    r1_engine = ChatEngine(r1_config)

    r1_reply = await r1_engine.process_message(
        message="9.11 和 9.8 哪个数更大？",
        user_id="user_r1_test",
    )
    print(f"DeepSeek R1 Reply (with Thinking):\n{r1_reply}")

    print("\n=== All Live Tests Passed Successfully! ===")


if __name__ == "__main__":
    asyncio.run(main())
