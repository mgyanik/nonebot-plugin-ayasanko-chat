# engine.py
from __future__ import annotations

import asyncio
import itertools
import json
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from nonebot.adapters import Bot, Event
from nonebot.log import logger

from .client import get_http_client
from .config import ChatConfig
from .limiter import RateLimiter
from .storage import get_storage_backend

_task_id_counter = itertools.count(1)


@dataclass
class ChatTask:
    """聊天任务模型（定制 __lt__ 避免 Future 比对异常）"""

    message: str
    session_id: str
    user_id: str
    images: list[str] = field(default_factory=list)
    priority: int = 0
    task_id: int = field(default_factory=lambda: next(_task_id_counter))
    start_time: float = field(default_factory=time.time)
    result: asyncio.Future[str] = field(default_factory=asyncio.Future)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ChatTask):
            return NotImplemented
        # 优先级数值越小越优先；相同时按生成先后顺序排列
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.task_id < other.task_id

    async def execute(self, engine: "ChatEngine") -> None:
        """在全局并发信号量限制下执行 API 调用"""
        async with engine.semaphore:
            try:
                history = engine.session_manager.get_history(self.session_id)
                api_response = await engine.call_api_with_retry(
                    self.message,
                    images=self.images,
                    history=history,
                )
                if not self.result.done():
                    self.result.set_result(api_response)
            except Exception as e:
                logger.error(f"Chat API execution failed for session {self.session_id}: {e}")
                if not self.result.done():
                    self.result.set_exception(e)


class UserQueue:
    """单会话串行任务队列"""

    def __init__(self, session_id: str, engine: "ChatEngine") -> None:
        self.session_id = session_id
        self.engine = engine
        self.queue: asyncio.PriorityQueue[ChatTask] = asyncio.PriorityQueue()
        self.processing = False
        self.current_task: ChatTask | None = None
        self.last_active = time.time()

    async def add_task(self, task: ChatTask) -> None:
        self.last_active = time.time()
        await self.queue.put(task)
        if not self.processing:
            _ = asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        self.processing = True
        try:
            while not self.queue.empty():
                task = await self.queue.get()
                self.current_task = task
                self.last_active = time.time()
                try:
                    await task.execute(self.engine)
                except Exception as e:
                    logger.error(f"Task execution error for session {self.session_id}: {e}")
                    if not task.result.done():
                        task.result.set_exception(e)
                finally:
                    self.current_task = None
        finally:
            self.processing = False


class ChatEngine:
    """聊天调度引擎核心：支持多模态、持久化、思考链、流式与重试退避"""

    def __init__(self, config: ChatConfig) -> None:
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrent or 5)
        # 获取存储后端（支持 memory 或 sqlite 持久化）
        self.session_manager = get_storage_backend(config)
        self.rate_limiter = RateLimiter(
            max_requests=config.rate_limit_requests,
            period=float(config.rate_limit_period),
        )
        self.user_queues: dict[str, UserQueue] = {}
        self.metrics: dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "retried_requests": 0,
            "rate_limited_requests": 0,
            "total_latency": 0.0,
        }
        self._cleanup_task: asyncio.Task[None] | None = None

    def start_background_tasks(self) -> None:
        """启动后台定时清理任务"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """定时清理空闲队列、过期会话与限流记录"""
        while True:
            try:
                await asyncio.sleep(300)
                self.cleanup_idle_queues()
                self.session_manager.cleanup_expired(float(self.config.session_ttl))
                self.rate_limiter.cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Background cleanup exception: {e}")

    def cleanup_idle_queues(self) -> int:
        """清理无正在执行任务且已空闲的队列"""
        now = time.time()
        idle_timeout = max(float(self.config.session_ttl), 300.0)
        idle_keys = [
            sid for sid, uq in self.user_queues.items()
            if uq.queue.empty() and uq.current_task is None and (now - uq.last_active) > idle_timeout
        ]
        for sid in idle_keys:
            del self.user_queues[sid]
        return len(idle_keys)

    async def _prepare_image_urls(self, client: httpx.AsyncClient, images: list[str]) -> list[str]:
        """将图片路径或 URL 规范化为 Base64 Data URL，确保大模型无论是否具备公网爬图权限均能识别"""
        if not images:
            return []
        import base64
        import mimetypes
        import os

        prepared: list[str] = []
        for img in images:
            if img.startswith("data:image/"):
                prepared.append(img)
                continue
            if os.path.isfile(img):
                mime, _ = mimetypes.guess_type(img)
                mime = mime or "image/png"
                raw_bytes: bytes | None = None
                try:
                    with open(img, "rb") as f:
                        raw_bytes = f.read()
                except PermissionError:
                    # 在 Android/Termux 下若被其他应用 (如 QQ 0770) 限制读取，尝试通过 su 读取
                    try:
                        import subprocess
                        proc = subprocess.run(["su", "-c", f"cat '{img}'"], capture_output=True, timeout=5)
                        if proc.returncode == 0 and proc.stdout:
                            raw_bytes = proc.stdout
                    except Exception:
                        pass
                except Exception as e:
                    logger.warning(f"Failed to read local image {img}: {e}")

                if raw_bytes is not None:
                    b64 = base64.b64encode(raw_bytes).decode("utf-8")
                    prepared.append(f"data:{mime};base64,{b64}")
                    continue
                else:
                    raise PermissionError(f"无法读取本地图片文件 '{img}'：权限不足。在 Android 上若为 QQ/微信等外部应用私有目录图片，请检查文件读取权限。")
            if img.startswith("http://") or img.startswith("https://"):
                try:
                    resp = await client.get(img, timeout=15.0)
                    if resp.status_code == 200:
                        content_type = resp.headers.get("content-type", "").split(";")[0].strip()
                        if not content_type.startswith("image/"):
                            content_type = "image/png"
                        b64 = base64.b64encode(resp.content).decode("utf-8")
                        prepared.append(f"data:{content_type};base64,{b64}")
                        continue
                except Exception as e:
                    logger.warning(f"Failed to download image {img} for base64: {e}")
            prepared.append(img)
        return prepared

    def _format_user_content(self, message: str, images: list[str]) -> Any:
        """构造 OpenAI 兼容的多模态内容结构"""
        if not images:
            return message
        content_items: list[dict[str, Any]] = [{"type": "text", "text": message}]
        for img_url in images:
            content_items.append({"type": "image_url", "image_url": {"url": img_url}})
        return content_items

    async def call_api_with_retry(
        self,
        message: str,
        images: list[str] | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> str:
        """带指数退避与抖动 (Exponential Backoff with Jitter) 的 API 调用"""
        max_retries = max(0, self.config.max_retries)
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                if self.config.stream:
                    return await self._call_api_stream(message, images=images or [], history=history)
                return await self._call_api_once(message, images=images or [], history=history)
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_error = e
                logger.warning(f"Network error on attempt {attempt + 1}/{max_retries + 1}: {e}")
            except httpx.HTTPStatusError as e:
                last_error = e
                # 仅对限流(429)与服务端错误(500, 502, 503, 504)实施重试
                if e.response.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        f"Retryable HTTP error {e.response.status_code} on attempt {attempt + 1}/{max_retries + 1}"
                    )
                else:
                    # 客户端鉴权或格式错误(400, 401, 403)，不予重试
                    raise

            if attempt < max_retries:
                self.metrics["retried_requests"] = int(self.metrics["retried_requests"]) + 1
                backoff = min(
                    self.config.retry_delay * (2 ** attempt) + random.uniform(0.1, 0.6),
                    15.0,
                )
                logger.info(f"Backing off for {backoff:.2f}s before retry...")
                await asyncio.sleep(backoff)

        if last_error is not None:
            raise last_error
        raise RuntimeError("API 调用未知错误")

    def _assemble_final_text(self, content: str, reasoning: str | None = None) -> str:
        """处理思考链与最终回复合成"""
        final_content = content
        final_reasoning = reasoning or ""

        # 检查正文中是否含有嵌入的 <think>...</think> 标签（如 DeepSeek-R1 本地模型）
        think_match = re.search(r"<think>(.*?)</think>", final_content, flags=re.DOTALL)
        if think_match:
            embedded_reasoning = think_match.group(1).strip()
            final_content = re.sub(r"<think>.*?</think>", "", final_content, flags=re.DOTALL).strip()
            if not final_reasoning and embedded_reasoning:
                final_reasoning = embedded_reasoning

        if final_reasoning and self.config.show_thinking:
            # 格式化思考链
            reasoning_lines = "\n".join(f"> {line}" for line in final_reasoning.strip().splitlines())
            return f"> 💡 【深度思考过程】\n{reasoning_lines}\n\n{final_content}"

        return final_content

    async def _call_api_once(
        self,
        message: str,
        images: list[str],
        history: list[dict[str, Any]] | None = None,
    ) -> str:
        """非流式调用大模型 HTTP 接口（支持 DeepSeek reasoning_content 与视觉输入）"""
        client = get_http_client(timeout=float(self.config.timeout))
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        prepared_images = await self._prepare_image_urls(client, images)
        user_content = self._format_user_content(message, prepared_images)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.config.system_prompt}
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_content})

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": False,
        }

        start_time = time.time()
        self.metrics["total_requests"] = int(self.metrics["total_requests"]) + 1

        try:
            response = await client.post(
                f"{self.config.api_base.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        except Exception:
            self.metrics["failed_requests"] = int(self.metrics["failed_requests"]) + 1
            raise

        duration = time.time() - start_time
        self.metrics["successful_requests"] = int(self.metrics["successful_requests"]) + 1
        self.metrics["total_latency"] = float(self.metrics["total_latency"]) + duration

        raw_json = response.json()
        if not isinstance(raw_json, dict):
            raise ValueError("API 响应非法：非字典格式")

        choices = raw_json.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("API 响应缺少有效 choices 字段")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("API choices[0] 格式异常")

        msg_obj = first_choice.get("message")
        if not isinstance(msg_obj, dict):
            raise ValueError("API message 字段结构异常")

        content = msg_obj.get("content") or ""
        if not isinstance(content, str):
            raise ValueError("API 返回内容非文本格式")

        # 提取 DeepSeek 专属 reasoning_content
        reasoning_content = msg_obj.get("reasoning_content")
        if not isinstance(reasoning_content, str):
            reasoning_content = None

        return self._assemble_final_text(content, reasoning_content)

    async def _call_api_stream(
        self,
        message: str,
        images: list[str],
        history: list[dict[str, Any]] | None = None,
    ) -> str:
        """流式 SSE 调用大模型 HTTP 接口并聚合思考链"""
        client = get_http_client(timeout=float(self.config.timeout))
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        prepared_images = await self._prepare_image_urls(client, images)
        user_content = self._format_user_content(message, prepared_images)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.config.system_prompt}
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_content})

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": True,
        }

        start_time = time.time()
        self.metrics["total_requests"] = int(self.metrics["total_requests"]) + 1

        content_chunks: list[str] = []
        reasoning_chunks: list[str] = []

        try:
            async with client.stream(
                "POST",
                f"{self.config.api_base.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(data_str)
                            choices = chunk_data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                c_delta = delta.get("content")
                                if c_delta:
                                    content_chunks.append(c_delta)
                                r_delta = delta.get("reasoning_content")
                                if r_delta:
                                    reasoning_chunks.append(r_delta)
                        except json.JSONDecodeError:
                            continue

        except Exception:
            self.metrics["failed_requests"] = int(self.metrics["failed_requests"]) + 1
            raise

        duration = time.time() - start_time
        self.metrics["successful_requests"] = int(self.metrics["successful_requests"]) + 1
        self.metrics["total_latency"] = float(self.metrics["total_latency"]) + duration

        full_content = "".join(content_chunks)
        full_reasoning = "".join(reasoning_chunks) if reasoning_chunks else None

        return self._assemble_final_text(full_content, full_reasoning)

    async def call_api(
        self,
        message: str,
        images: list[str] | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> str:
        """对外部调用的公开接口（带重试机制）"""
        return await self.call_api_with_retry(message, images=images, history=history)

    async def process_message(
        self,
        message: str,
        user_id: str,
        _bot: Bot | None = None,
        _event: Event | None = None,
        session_id: str | None = None,
        images: list[str] | None = None,
    ) -> str:
        """主入口：排队并发执行提问并更新上下文会话"""
        self.start_background_tasks()
        actual_session_id = session_id or user_id
        actual_images = images or []

        # 速率限制判定
        allowed, retry_after = self.rate_limiter.is_allowed(actual_session_id)
        if not allowed:
            self.metrics["rate_limited_requests"] = int(self.metrics["rate_limited_requests"]) + 1
            logger.warning(f"Rate limit exceeded for {actual_session_id}, wait {retry_after:.1f}s")
            return f"喵…提问太快啦，请歇息 {retry_after:.0f} 秒再找我哦~ (•ω•)"

        if actual_session_id not in self.user_queues:
            self.user_queues[actual_session_id] = UserQueue(actual_session_id, self)

        task = ChatTask(
            message=message,
            session_id=actual_session_id,
            user_id=user_id,
            images=actual_images,
        )
        await self.user_queues[actual_session_id].add_task(task)

        try:
            result = await task.result
            # 存储对话轮次（若含图片则存储多模态结构）
            stored_user_msg = self._format_user_content(message, actual_images)
            self.session_manager.add_turn(
                session_id=actual_session_id,
                user_msg=stored_user_msg,
                assistant_msg=result,
                max_history=self.config.max_history,
            )
            return result
        except Exception as e:
            logger.error(f"Process message failed for session {actual_session_id}: {e}")
            raise

    def get_metrics(self) -> dict[str, Any]:
        """获取性能与监控指标"""
        total = int(self.metrics["total_requests"])
        success = int(self.metrics["successful_requests"])
        total_lat = float(self.metrics["total_latency"])
        avg_lat = (total_lat / success) if success > 0 else 0.0

        return {
            **self.metrics,
            "avg_latency": round(avg_lat, 3),
            "active_sessions": self.session_manager.count_active(),
            "active_user_queues": len(self.user_queues),
        }


def split_response(text: str, max_length: int = 1200) -> list[str]:
    """将长回复安全切分为多段，防止平台因单条消息过长吞字或风控"""
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    lines = text.split("\n")
    current_chunk: list[str] = []
    current_length = 0

    for line in lines:
        line_len = len(line) + 1
        if current_length + line_len > max_length:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            if line_len > max_length:
                # 极端情况：单行超过限制，强行切片
                for i in range(0, len(line), max_length):
                    chunks.append(line[i : i + max_length])
                continue

        current_chunk.append(line)
        current_length += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks
