"""
聊天处理器 - 异步化改造
支持并发控制、任务队列、重试机制和性能监控
"""

# processor.py
# fmt: off
import asyncio
import time
from dataclasses import dataclass, field
from asyncio import Future, PriorityQueue
from typing import cast

from nonebot.log import logger
from nonebot.adapters import Bot, Event

from .config import ChatConfig


@dataclass(order=True)
class ChatTask:
    """聊天任务"""

    priority: int = 0
    message: str = ""
    user_id: str = ""
    start_time: float = 0.0
    result: Future[str] = field(default_factory=Future)

    def __post_init__(self) -> None:
        if self.start_time == 0.0:
            self.start_time = time.time()

    async def execute(self, processor: "ChatProcessor") -> None:
        """执行任务"""
        async with processor.semaphore:
            try:
                history = processor.get_history(self.user_id)
                api_response = await processor.call_bigmodel_api(
                    self.message, history=history
                )
                if not self.result.done():
                    self.result.set_result(api_response)
                else:
                    logger.warning("Task already completed, skipping result set")
            except Exception as e:
                logger.error(f"API call failed: {e}")
                if not self.result.done():
                    self.result.set_exception(e)


class UserTaskQueue:
    """用户独立任务队列"""

    user_id: str
    processor: "ChatProcessor"
    queue: PriorityQueue[ChatTask]
    processing: bool
    current_task: ChatTask | None
    history: list[dict[str, str]]

    def __init__(self, user_id: str, processor: "ChatProcessor") -> None:
        self.user_id = user_id
        self.processor = processor
        self.queue = PriorityQueue[ChatTask]()
        self.processing = False
        self.current_task = None
        self.history = []

    async def add_task(self, task: ChatTask) -> None:
        """添加任务到队列"""
        await self.queue.put(task)
        if not self.processing:
            _ = asyncio.create_task(self._process_queue())  # type: ignore[unused-awaitable]

    async def _process_queue(self) -> None:
        """处理队列中的任务"""
        self.processing = True
        try:
            while not self.queue.empty():
                task = await self.queue.get()
                self.current_task = task
                try:
                    await task.execute(self.processor)
                except Exception as e:
                    logger.error(f"Task execution failed for user {self.user_id}: {e}")
                    if not task.result.done():
                        task.result.set_exception(e)
                finally:
                    self.current_task = None
        finally:
            self.processing = False


class ChatProcessor:
    """聊天处理器 - 异步化改造"""

    config: ChatConfig
    user_queues: dict[str, UserTaskQueue]
    semaphore: asyncio.Semaphore
    metrics: dict[str, object]

    def __init__(self, config: ChatConfig) -> None:
        self.config = config
        self.user_queues = {}
        self.system_prompt: str = config.system_prompt
        self.semaphore = asyncio.Semaphore(config.max_concurrent or 5)
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "current_queue_length": 0,
        }

    def get_history(self, user_id: str) -> list[dict[str, str]]:
        if user_id in self.user_queues:
            return self.user_queues[user_id].history
        return []

    async def process_message(
        self,
        message: str,
        user_id: str,
        _bot: Bot,
        event: Event,  # pyright: ignore[reportUnusedParameter]
    ) -> str:
        """处理消息"""
        if user_id not in self.user_queues:
            self.user_queues[user_id] = UserTaskQueue(user_id, self)

        task = ChatTask(
            message=message,
            user_id=user_id,
            start_time=time.time(),
            result=asyncio.Future(),
        )

        await self.user_queues[user_id].add_task(task)

        try:
            result = await task.result
            self.user_queues[user_id].history.append(
                {"role": "user", "content": message}
            )
            self.user_queues[user_id].history.append(
                {"role": "assistant", "content": result}
            )
            max_history = self.config.max_history * 2
            if len(self.user_queues[user_id].history) > max_history:
                self.user_queues[user_id].history = (
                    self.user_queues[user_id].history[-max_history:]
                )
            return result
        except Exception as e:
            logger.error(f"Task failed for user {user_id}: {e}")
            raise

    async def call_bigmodel_api(
        self, message: str, history: list[dict[str, str]] | None = None
    ) -> str:
        """调用 BigModel API（带重试机制）"""
        import httpx

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        messages: list[dict[str, str]] = [
            {"role": "system", "content": self.system_prompt}
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})

        payload: dict[str, object] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            try:
                response = await client.post(
                    f"{self.config.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                _ = response.raise_for_status()
            except httpx.TimeoutException as e:
                logger.error(f"API request timeout: {e}")
                raise
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error {e.response.status_code}: {e.response.text[:200]}"
                )
                raise
            except Exception as e:
                logger.error(f"Unexpected request error: {type(e).__name__}: {e}")
                raise

            raw_data = cast(object, response.json())
            if not isinstance(raw_data, dict):
                raise ValueError("API返回格式错误：响应不是字典类型")
            data = cast(dict[str, object], raw_data)

            choices_raw = data.get("choices")
            if not isinstance(choices_raw, list) or not choices_raw:
                raise ValueError("API返回格式错误：choices 字段缺失或为空")

            choices_list = cast(list[object], choices_raw)
            first_raw: object = choices_list[0]
            if not isinstance(first_raw, dict):
                raise ValueError("API返回格式错误：choices[0] 不是字典")
            first_d = cast(dict[str, object], first_raw)

            message_raw = first_d.get("message")
            if not isinstance(message_raw, dict):
                raise ValueError("API返回格式错误：message 结构异常")
            message_d = cast(dict[str, object], message_raw)

            content_raw = message_d.get("content")
            if not isinstance(content_raw, str):
                raise ValueError("API返回格式错误：content 不是字符串类型")

            logger.info(f"API response received: {content_raw[:50]}...")
            return content_raw

    async def get_queue_length(self, user_id: str) -> int:
        """获取用户队列长度"""
        if user_id not in self.user_queues:
            return 0
        return self.user_queues[user_id].queue.qsize()

    def get_metrics(self) -> dict[str, object]:
        """获取性能指标"""
        return self.metrics.copy()

    def cleanup_expired_queues(self) -> None:
        """清理空闲队列"""
        expired_users: list[str] = [
            user_id
            for user_id, uq in self.user_queues.items()
            if uq.queue.empty() and uq.current_task is None
        ]
        for user_id in expired_users:
            del self.user_queues[user_id]
            logger.info(f"Cleaned up expired queue for user {user_id}")
