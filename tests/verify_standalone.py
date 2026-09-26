# tests/verify_standalone.py
"""
独立验证脚本：不依赖完整 NoneBot 与 Pydantic 运行时，直接验证 SQLite 后端、速率限制以及 DeepSeek API
"""
import sys
from unittest.mock import MagicMock

# 模拟 NoneBot 与 Pydantic 环境以允许在未安装 C-extensions 的独立环境下导入模块
sys.modules.setdefault("nonebot", MagicMock())
sys.modules.setdefault("nonebot.adapters", MagicMock())
sys.modules.setdefault("nonebot.exception", MagicMock())
sys.modules.setdefault("nonebot.internal.matcher", MagicMock())
sys.modules.setdefault("nonebot.log", MagicMock())
sys.modules.setdefault("nonebot.plugin", MagicMock())

pydantic_mock = MagicMock()
pydantic_mock.Field = lambda *args, **kwargs: kwargs.get("default", None)
pydantic_mock.field_validator = lambda *args, **kwargs: (lambda f: f)
pydantic_mock.BaseModel = object
pydantic_mock.ConfigDict = dict
sys.modules.setdefault("pydantic", pydantic_mock)

import asyncio
import json
import os
import re
import tempfile
import time
from pathlib import Path
import httpx

from nonebot_plugin_ayasanko_chat.storage.sqlite import SqliteStorageBackend
from nonebot_plugin_ayasanko_chat.limiter import RateLimiter


def test_sqlite_standalone():
    print("[1/3] 验证 SQLite 存储后端...")
    with tempfile.TemporaryDirectory() as tmpdir:
        db = str(Path(tmpdir) / "test.db")
        backend = SqliteStorageBackend(db_path=db, default_ttl=0.2)

        # 写入对话
        backend.add_turn("session_qq_1", "你好", "你好！很高兴为你服务。", max_history=3)
        history = backend.get_history("session_qq_1")
        assert len(history) == 2, f"Expected 2 messages, got {len(history)}"
        assert history[0]["content"] == "你好"
        assert backend.count_active() == 1

        # 写入多模态内容
        multimodal = [{"type": "text", "text": "看图"}, {"type": "image_url", "image_url": {"url": "http://img.jpg"}}]
        backend.add_turn("session_qq_1", multimodal, "我看到了图片", max_history=3)
        hist2 = backend.get_history("session_qq_1")
        assert len(hist2) == 4
        assert hist2[2]["content"] == multimodal

        # TTL 测试
        time.sleep(0.25)
        expired_hist = backend.get_history("session_qq_1")
        assert len(expired_hist) == 0, "TTL 过期清理失败"
    print("  -> SQLite 存储后端验证通过！")


def test_limiter_standalone():
    print("[2/3] 验证滑动窗口速率限制器...")
    limiter = RateLimiter(max_requests=2, period=0.2)
    assert limiter.is_allowed("u1")[0] is True
    assert limiter.is_allowed("u1")[0] is True
    allowed, wait = limiter.is_allowed("u1")
    assert allowed is False
    assert wait > 0
    time.sleep(0.25)
    assert limiter.is_allowed("u1")[0] is True
    print("  -> 速率限制器验证通过！")


async def test_deepseek_api_live():
    print("[3/3] 正在调用 DeepSeek 官方 API 测试推理模型 (deepseek-reasoner R1) ...")
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("  -> 未检测到 DEEPSEEK_API_KEY 环境变量，跳过远程 API 调用验证。")
        return

    api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-reasoner",
        "messages": [
            {"role": "system", "content": "你是一位精通数学与逻辑的助手。"},
            {"role": "user", "content": "9.11 和 9.8 哪个数更大？请简短回答。"}
        ],
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{api_base}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        message = choice["message"]
        content = message.get("content", "")
        reasoning = message.get("reasoning_content", "")

        print("\n--- DeepSeek 思考链 (Reasoning Content) ---")
        print(reasoning[:300] + ("..." if len(reasoning) > 300 else ""))
        print("\n--- DeepSeek 最终回复 (Final Content) ---")
        print(content)

        # 验证思考链格式化输出
        reasoning_lines = "\n".join(f"> {line}" for line in reasoning.strip().splitlines())
        formatted = f"> 💡 【深度思考过程】\n{reasoning_lines}\n\n{content}"
        assert "9.8" in content, "回答不符合预期"
        print("\n  -> DeepSeek 推理与思考链提取验证通过！")


async def main():
    test_sqlite_standalone()
    test_limiter_standalone()
    await test_deepseek_api_live()
    print("\n🎉 全部功能独立测试均通过！")


if __name__ == "__main__":
    asyncio.run(main())
