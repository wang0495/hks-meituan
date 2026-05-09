"""CityFlow Redis 消息队列。

基于 Redis List 实现的生产者/消费者模型，支持：
- 多队列隔离（queue 前缀分组）
- 多消费者并发
- 优雅启停
- 全局单例访问
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional

import redis.asyncio as aioredis

from backend.config import settings

logger = logging.getLogger(__name__)

# 消息处理器类型：接收 dict 消息体，返回协程
MessageHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class Message:
    """消息信封，封装元数据 + 业务载荷。"""

    def __init__(
        self,
        queue: str,
        payload: dict[str, Any],
        *,
        message_id: str | None = None,
        retry_count: int = 0,
    ) -> None:
        self.message_id = message_id or uuid.uuid4().hex[:12]
        self.queue = queue
        self.payload = payload
        self.retry_count = retry_count
        self.created_at = datetime.now().isoformat()

    def to_json(self) -> str:
        """序列化为 JSON 字符串，用于写入 Redis。"""
        return json.dumps(
            {
                "message_id": self.message_id,
                "queue": self.queue,
                "payload": self.payload,
                "retry_count": self.retry_count,
                "created_at": self.created_at,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> Message:
        """从 Redis 读取的 JSON 反序列化。"""
        obj = json.loads(data)
        return cls(
            queue=obj["queue"],
            payload=obj["payload"],
            message_id=obj.get("message_id"),
            retry_count=obj.get("retry_count", 0),
        )


class MessageQueue:
    """基于 Redis List 的消息队列。

    Args:
        redis_url: Redis 连接 URL，默认从配置读取。
        prefix: 所有队列键的前缀，避免 key 冲突。
        max_retries: 单条消息最大重试次数。
    """

    def __init__(
        self,
        redis_url: str | None = None,
        prefix: str = "cityflow:mq:",
        max_retries: int = 3,
    ) -> None:
        if redis_url is None:
            redis_url = self._build_redis_url()
        self._redis: aioredis.Redis = aioredis.from_url(  # type: ignore[union-attr]
            redis_url,
            decode_responses=True,
        )
        self._prefix = prefix
        self._max_retries = max_retries
        self._consumers: dict[str, asyncio.Task] = {}
        self._running = False

    @staticmethod
    def _build_redis_url() -> str:
        """根据 settings.redis 配置拼接 Redis URL。"""
        rs = settings.redis
        auth = f":{rs.password}@" if rs.password else ""
        return f"redis://{auth}{rs.host}:{rs.port}/{rs.db}"

    def _key(self, queue: str) -> str:
        """生成 Redis key。"""
        return f"{self._prefix}{queue}"

    # ------------------------------------------------------------------
    # 生产者
    # ------------------------------------------------------------------

    async def publish(self, queue: str, payload: dict[str, Any]) -> Message:
        """发布一条消息到指定队列。

        Args:
            queue: 队列名称。
            payload: 业务消息体。

        Returns:
            已发布的 Message 对象（含 message_id）。
        """
        msg = Message(queue=queue, payload=payload)
        await self._redis.rpush(self._key(queue), msg.to_json())
        logger.info("消息已发布: queue=%s, id=%s", queue, msg.message_id)
        return msg

    async def publish_many(
        self, queue: str, payloads: list[dict[str, Any]]
    ) -> list[Message]:
        """批量发布消息，使用 pipeline 减少 RTT。"""
        messages = [Message(queue=queue, payload=p) for p in payloads]
        pipe = self._redis.pipeline()
        key = self._key(queue)
        for msg in messages:
            pipe.rpush(key, msg.to_json())
        await pipe.execute()
        logger.info("批量发布 %d 条消息: queue=%s", len(messages), queue)
        return messages

    # ------------------------------------------------------------------
    # 消费者
    # ------------------------------------------------------------------

    async def consume(
        self,
        queue: str,
        handler: MessageHandler,
        *,
        timeout: int = 1,
    ) -> None:
        """阻塞消费循环（应作为后台 task 运行）。

        Args:
            queue: 队列名称。
            handler: 异步消息处理函数。
            timeout: BLPOP 超时秒数，到时自动重试。
        """
        key = self._key(queue)
        logger.info("消费者启动: queue=%s", queue)

        while self._running:
            try:
                result = await self._redis.blpop(key, timeout=timeout)
                if result is None:
                    continue
                # blpop with decode_responses returns (key, value)
                _key, raw = result
                msg = Message.from_json(raw)
                try:
                    await handler(msg.payload)
                    logger.info("消息消费成功: queue=%s, id=%s", queue, msg.message_id)
                except Exception as handler_err:
                    msg.retry_count += 1
                    if msg.retry_count <= self._max_retries:
                        # 放回队列尾部重试
                        await self._redis.rpush(key, msg.to_json())
                        logger.warning(
                            "消息处理失败，重新入队: queue=%s, id=%s, retry=%d, err=%s",
                            queue,
                            msg.message_id,
                            msg.retry_count,
                            handler_err,
                        )
                    else:
                        # 超过重试次数，写入死信队列
                        dlq_key = f"{self._prefix}dlq:{queue}"
                        await self._redis.rpush(dlq_key, msg.to_json())
                        logger.error(
                            "消息消费最终失败，移入死信队列: queue=%s, id=%s",
                            queue,
                            msg.message_id,
                        )
            except asyncio.CancelledError:
                logger.info("消费者被取消: queue=%s", queue)
                break
            except Exception as exc:
                logger.error("消费者异常: queue=%s, err=%s", queue, exc)
                await asyncio.sleep(1)

        logger.info("消费者已停止: queue=%s", queue)

    def start_consumer(self, queue: str, handler: MessageHandler) -> asyncio.Task:
        """启动一个后台消费者 task。

        Args:
            queue: 队列名称。
            handler: 异步消息处理函数。

        Returns:
            消费者 asyncio.Task。
        """
        self._running = True
        task = asyncio.create_task(
            self.consume(queue, handler), name=f"mq-consumer-{queue}"
        )
        self._consumers[queue] = task
        logger.info("消费者 task 已创建: queue=%s", queue)
        return task

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def stop(self) -> None:
        """停止所有消费者并关闭 Redis 连接。"""
        self._running = False
        for queue_name, task in self._consumers.items():
            task.cancel()
            logger.info("消费者 task 已取消: queue=%s", queue_name)
        if self._consumers:
            await asyncio.gather(*self._consumers.values(), return_exceptions=True)
        self._consumers.clear()
        await self._redis.aclose()
        logger.info("消息队列已停止，Redis 连接已关闭")

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    async def queue_length(self, queue: str) -> int:
        """查询队列长度。"""
        return await self._redis.llen(self._key(queue))

    async def clear_queue(self, queue: str) -> int:
        """清空指定队列，返回删除的消息数。"""
        key = self._key(queue)
        length = await self._redis.llen(key)
        if length > 0:
            await self._redis.delete(key)
        logger.info("队列已清空: queue=%s, 删除 %d 条", queue, length)
        return length


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_mq: Optional[MessageQueue] = None


def get_message_queue() -> MessageQueue:
    """获取全局消息队列实例（懒初始化）。"""
    global _mq
    if _mq is None:
        _mq = MessageQueue()
    return _mq


async def close_message_queue() -> None:
    """关闭全局消息队列（用于 FastAPI shutdown 事件）。"""
    global _mq
    if _mq is not None:
        await _mq.stop()
        _mq = None
