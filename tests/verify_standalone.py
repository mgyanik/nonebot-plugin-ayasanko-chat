# tests/verify_standalone.py
"""
Ayasanko Chat Engine - 独立交互式终端模拟器 (CLI)
不依赖 NoneBot 运行时，支持可持续对话、多模态图片识别测试、SQLite 会话持久化与思考链实时展示。
"""
import sys
from unittest.mock import MagicMock

# 模拟 NoneBot 与 Pydantic 环境以允许独立直接运行
if "nonebot" not in sys.modules:
    mock_nonebot = MagicMock()
    mock_matcher = MagicMock()
    mock_matcher.handle.return_value = lambda f: f
    mock_nonebot.on_message.return_value = mock_matcher
    sys.modules["nonebot"] = mock_nonebot
    sys.modules["nonebot.adapters"] = MagicMock()
    sys.modules["nonebot.exception"] = MagicMock()
    sys.modules["nonebot.internal.matcher"] = MagicMock()
    sys.modules["nonebot.log"] = MagicMock()
    sys.modules["nonebot.plugin"] = MagicMock()

if "pydantic" not in sys.modules:
    class MockBaseModel:
        def __init__(self, **kwargs):
            for k in dir(self.__class__):
                if not k.startswith("_"):
                    val = getattr(self.__class__, k)
                    if not callable(val):
                        setattr(self, k, val)
            for k, v in kwargs.items():
                setattr(self, k, v)

    mock_pydantic = MagicMock()
    mock_pydantic.Field = lambda *args, default=None, default_factory=None, **kwargs: default_factory() if default_factory else default
    mock_pydantic.field_validator = lambda *args, **kwargs: (lambda f: f)
    mock_pydantic.BaseModel = MockBaseModel
    mock_pydantic.ConfigDict = dict
    sys.modules["pydantic"] = mock_pydantic

import asyncio
import os
import re
import shlex
import time
from pathlib import Path

from nonebot_plugin_ayasanko_chat.config import ChatConfig
from nonebot_plugin_ayasanko_chat.engine import ChatEngine


def load_env_file(filepath: str = ".env") -> None:
    """加载当前目录下的 .env 环境变量"""
    p = Path(filepath)
    if not p.is_file():
        return
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k not in os.environ:
                os.environ[k] = v


async def run_interactive_cli():
    load_env_file(".env")

    api_key = os.getenv("CHAT__API_KEY") or os.getenv("DEEPSEEK_API_KEY") or ""
    api_base = os.getenv("CHAT__API_BASE") or os.getenv("DEEPSEEK_API_BASE") or "https://api.deepseek.com"
    model = os.getenv("CHAT__MODEL") or "deepseek-chat"
    db_path = os.getenv("CHAT__SQLITE_PATH") or "data/chat.db"
    show_thinking = os.getenv("CHAT__SHOW_THINKING", "true").lower() in ("true", "1", "yes")

    if not api_key:
        print("\n⚠️ 未检测到 API Key，请输入您的 API Key（如 DeepSeek key）：")
        try:
            api_key = input("🔑 API_KEY > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n已退出。")
            return
        if not api_key:
            print("❌ 错误：未提供 API Key，无法进行测试。")
            return

    config = ChatConfig(
        api_key=api_key,
        api_base=api_base,
        model=model,
        max_tokens=4000,
        storage_backend="sqlite",
        sqlite_path=db_path,
        stream=False,
        show_thinking=show_thinking,
        session_ttl=3600,
        max_history=15,
    )
    engine = ChatEngine(config)
    session_id = "cli_standalone_user"

    print("\n" + "=" * 68)
    print("🤖 Ayasanko Chat Engine - 独立终端实机模拟器 (v0.3.0)")
    print("=" * 68)
    print(f"• 接入地址: {config.api_base}")
    print(f"• 当前模型: {config.model}")
    print(f"• 持久化后端: SQLite ({config.sqlite_path})")
    print(f"• 思考链展示: {'开启' if config.show_thinking else '关闭'}")
    print("• 操作指令:")
    print("  - 直接输入内容回车：进行多轮对话")
    print("  - 发送多模态图片识别：/img <图片本地路径或URL> [提问文本]")
    print("  - 查看会话历史：/history")
    print("  - 清空当前记忆：/clear")
    print("  - 切换模型：/model <模型名称>")
    print("  - 开关思考过程：/thinking")
    print("  - 退出：/exit 或 Ctrl+C")
    print("=" * 68 + "\n")

    while True:
        try:
            user_input = input("\n👤 [你] > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 模拟器已退出。")
            break

        if not user_input:
            continue

        # 指令处理
        if user_input in ("/exit", "/quit", "exit", "quit"):
            print("👋 再见！")
            break

        if user_input == "/clear":
            count = engine.session_manager.clear(session_id)
            print(f"✨ 已清空当前会话记忆（清理轮次记录数: {count}）。")
            continue

        if user_input == "/history":
            hist = engine.session_manager.get_history(session_id)
            if not hist:
                print("📜 当前会话暂无历史记录。")
            else:
                print(f"📜 当前会话历史 (共 {len(hist)} 条记录):")
                for idx, msg in enumerate(hist, 1):
                    role_name = "👤 用户" if msg["role"] == "user" else "🤖 助手"
                    c = msg["content"]
                    if isinstance(c, list):
                        c_str = f"[多模态消息: {len(c)} 个段落]"
                    else:
                        c_str = str(c)
                        if len(c_str) > 80:
                            c_str = c_str[:80] + "..."
                    print(f"  {idx}. {role_name}: {c_str}")
            continue

        if user_input.startswith("/model"):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                new_model = parts[1].strip()
                engine.config.model = new_model
                print(f"🔄 模型已切换为: {new_model}")
            else:
                print(f"当前模型: {engine.config.model} (可使用 /model <新模型名> 进行切换)")
            continue

        if user_input == "/thinking":
            engine.config.show_thinking = not engine.config.show_thinking
            status_text = "开启" if engine.config.show_thinking else "关闭"
            print(f"💡 思考过程展示已设为: {status_text}")
            continue

        if user_input == "/help":
            print("可用指令: /img <url/path> [msg], /clear, /history, /model <name>, /thinking, /exit")
            continue

        # 解析是否为图片多模态提问: /img <url_or_path> [prompt]
        images: list[str] = []
        actual_message = user_input

        if user_input.startswith(("/img", "/image")):
            parts = user_input.split(maxsplit=2)
            if len(parts) >= 2:
                img_target = parts[1].strip()
                images.append(img_target)
                actual_message = parts[2].strip() if len(parts) >= 3 else "请识别并描述这张图片的内容"
                print(f"🖼️ [检测到图片输入]: {img_target}")
            else:
                print("❌ 格式错误：请使用 /img <图片路径或URL> [提问问题]")
                continue

        print("🤖 [猫猫] 正在思考中...")
        start_time = time.time()
        try:
            reply = await engine.process_message(
                message=actual_message,
                user_id="cli_user",
                session_id=session_id,
                images=images,
            )
            cost = time.time() - start_time
            print(f"\n🤖 [猫猫] (耗时: {cost:.2f}s):\n{reply}")
        except Exception as e:
            print(f"\n❌ 请求出错: {e}")


def run_unit_tests():
    """自动化测试模式（非交互）"""
    print("=== 执行独立单元验证 ===")
    from nonebot_plugin_ayasanko_chat.storage.sqlite import SqliteStorageBackend
    from nonebot_plugin_ayasanko_chat.limiter import RateLimiter
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db = str(Path(tmpdir) / "test.db")
        backend = SqliteStorageBackend(db_path=db, default_ttl=0.2)
        backend.add_turn("s1", "你好", "你好！", max_history=3)
        assert len(backend.get_history("s1")) == 2
        print("✓ SQLite 存储验证通过")

    limiter = RateLimiter(max_requests=2, period=0.2)
    assert limiter.is_allowed("u1")[0] is True
    assert limiter.is_allowed("u1")[0] is True
    assert limiter.is_allowed("u1")[0] is False
    print("✓ 滑动窗口限流验证通过")
    print("全部独立检查通过！")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_unit_tests()
    else:
        asyncio.run(run_interactive_cli())
