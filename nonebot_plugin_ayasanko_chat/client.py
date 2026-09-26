# client.py
from __future__ import annotations

import httpx
from nonebot import get_driver
from nonebot.log import logger

_http_client: httpx.AsyncClient | None = None


def get_http_client(timeout: float = 30.0) -> httpx.AsyncClient:
    """获取或初始化全局共享的 HTTP 连接池客户端"""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=50,
            keepalive_expiry=60.0,
        )
        _http_client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            trust_env=True,
        )
        logger.debug("Chat global HTTP client pool initialized")
    return _http_client


async def close_http_client() -> None:
    """关闭全局 HTTP 客户端连接池"""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None
        logger.debug("Chat global HTTP client pool closed")


# 绑定 NoneBot 驱动生命周期
try:
    driver = get_driver()

    @driver.on_shutdown
    async def _on_shutdown() -> None:
        await close_http_client()

except Exception:
    # 允许在无 driver 的独立单测或脚本环境中导入
    pass
