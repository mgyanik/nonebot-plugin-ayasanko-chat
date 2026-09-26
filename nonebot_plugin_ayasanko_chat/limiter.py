# limiter.py
from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    """滑动窗口速率限制器（内存安全）"""

    def __init__(self, max_requests: int = 10, period: float = 60.0) -> None:
        self.max_requests = max_requests
        self.period = period
        self._records: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, key: str) -> tuple[bool, float]:
        """
        检查指定 key 是否允许访问
        返回: (是否放行, 若被限流则返回需等待的秒数)
        """
        if self.max_requests <= 0 or self.period <= 0:
            return True, 0.0

        now = time.time()
        record = self._records[key]

        # 移出时间窗口之外的历史请求时间戳
        while record and (now - record[0]) > self.period:
            record.popleft()

        if len(record) < self.max_requests:
            record.append(now)
            return True, 0.0

        # 已达上限，计算最早一条记录的释放剩余时间
        retry_after = max(0.0, self.period - (now - record[0]))
        return False, retry_after

    def cleanup(self) -> int:
        """清理已无活跃记录的空 key，释放内存"""
        now = time.time()
        expired_keys: list[str] = []
        for key, record in self._records.items():
            while record and (now - record[0]) > self.period:
                record.popleft()
            if not record:
                expired_keys.append(key)

        for key in expired_keys:
            del self._records[key]
        return len(expired_keys)
