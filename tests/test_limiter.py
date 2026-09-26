# tests/test_limiter.py
import time
from nonebot_plugin_ayasanko_chat.limiter import RateLimiter


def test_rate_limiter_allow():
    limiter = RateLimiter(max_requests=3, period=1.0)

    # 前 3 次允许
    assert limiter.is_allowed("user1")[0] is True
    assert limiter.is_allowed("user1")[0] is True
    assert limiter.is_allowed("user1")[0] is True

    # 第 4 次应被限制
    allowed, retry_after = limiter.is_allowed("user1")
    assert allowed is False
    assert retry_after > 0.0

    # 另一个独立 user2 不受影响
    assert limiter.is_allowed("user2")[0] is True

    # 等待窗口过去后恢复
    time.sleep(1.05)
    assert limiter.is_allowed("user1")[0] is True


def test_rate_limiter_cleanup():
    limiter = RateLimiter(max_requests=2, period=0.1)
    limiter.is_allowed("user_old")
    time.sleep(0.15)
    cleaned = limiter.cleanup()
    assert cleaned == 1
    assert "user_old" not in limiter._records
