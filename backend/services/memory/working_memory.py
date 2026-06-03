"""L1: 即时工作记忆。

存储当前 session 的对话上下文，包括 last_intent、last_route_summary、
current_emotion 状态等。Redis 不可用时自动回退到内存字典。
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

WORKING_MEMORY_KEY_PREFIX = "memory:w:"
WORKING_MEMORY_TTL = 600  # 10 minutes


class WorkingMemory:
    """当前 session 的即时工作记忆。

    Redis Hash, key = f"memory:w:{session_id}"
    TTL = 600s (10 min)，自动过期。
    Redis 不可用时自动回退到内存字典。
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url
        self._redis: Any = None
        self._connected = False
        self._fallback = False
        self._memory: dict[str, dict[str, Any]] = {}

    async def _get_redis(self) -> Any:
        """获取 Redis 连接（延迟连接）。"""
        if self._connected and self._redis is not None:
            return self._redis
        if self._fallback or not self._redis_url:
            return None
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            await self._redis.ping()
            self._connected = True
            self._fallback = False
            logger.info("[WorkingMemory] Redis 连接成功")
            return self._redis
        except Exception:
            self._connected = False
            self._fallback = True
            logger.warning("[WorkingMemory] Redis 不可达，切换到内存模式")
            return None

    async def set(self, session_id: str, key: str, value: Any) -> None:
        """设置工作记忆中的某个字段。"""
        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{WORKING_MEMORY_KEY_PREFIX}{session_id}"
                await r.hset(redis_key, key, json.dumps(value, ensure_ascii=False))
                await r.expire(redis_key, WORKING_MEMORY_TTL)
                return
            except Exception:
                self._fallback = True
                logger.warning("[WorkingMemory] Redis hset 失败，切换到内存模式")

        # Fallback: in-memory
        if session_id not in self._memory:
            self._memory[session_id] = {}
        self._memory[session_id][key] = value

    async def get(self, session_id: str, key: str) -> Any | None:
        """获取工作记忆中的某个字段。"""
        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{WORKING_MEMORY_KEY_PREFIX}{session_id}"
                data = await r.hget(redis_key, key)
                if data is not None:
                    return json.loads(data)
                return None
            except Exception:
                self._fallback = True
                logger.warning("[WorkingMemory] Redis hget 失败，切换到内存模式")

        # Fallback: in-memory
        return self._memory.get(session_id, {}).get(key)

    async def get_all(self, session_id: str) -> dict[str, Any]:
        """获取工作记忆中的所有字段。"""
        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{WORKING_MEMORY_KEY_PREFIX}{session_id}"
                data = await r.hgetall(redis_key)
                if data:
                    return {k: json.loads(v) for k, v in data.items()}
                return {}
            except Exception:
                self._fallback = True
                logger.warning("[WorkingMemory] Redis hgetall 失败，切换到内存模式")

        # Fallback: in-memory
        return dict(self._memory.get(session_id, {}))

    async def clear(self, session_id: str) -> None:
        """清除当前 session 的所有工作记忆。"""
        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{WORKING_MEMORY_KEY_PREFIX}{session_id}"
                await r.delete(redis_key)
                return
            except Exception:
                self._fallback = True
                logger.warning("[WorkingMemory] Redis delete 失败，切换到内存模式")

        # Fallback: in-memory
        self._memory.pop(session_id, None)

    @property
    def is_fallback(self) -> bool:
        return self._fallback
