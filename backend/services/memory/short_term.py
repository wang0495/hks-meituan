"""L2: 短期行程记忆。

存储用户近期的行程历史 (sliding window of last 5 trips)。
Redis 不可用时自动回退到内存字典。
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

SHORT_TERM_KEY_PREFIX = "memory:st:"
SHORT_TERM_TTL = 86400  # 24 hours
SHORT_TERM_MAX_TRIPS = 5


class ShortTermMemory:
    """短期行程记忆。

    存储用户近期的行程历史 (sliding window of last 5 trips)。
    Redis List, key = f"memory:st:{user_id}"
    每个元素是行程摘要 dict (destination, date, pois_visited, emotion_summary)。
    列表长度上限 = 5 (自动裁剪)。
    TTL = 86400s (24h)。
    Redis 不可用时自动回退到内存字典。
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url
        self._redis: Any = None
        self._connected = False
        self._fallback = False
        self._memory: dict[str, list[dict[str, Any]]] = {}

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
            logger.info("[ShortTermMemory] Redis 连接成功")
            return self._redis
        except Exception:
            self._connected = False
            self._fallback = True
            logger.warning("[ShortTermMemory] Redis 不可达，切换到内存模式")
            return None

    async def add_trip(self, user_id: str, trip_summary: dict[str, Any]) -> None:
        """添加一次行程到短期记忆（最近的在最前面）。"""
        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{SHORT_TERM_KEY_PREFIX}{user_id}"
                await r.lpush(redis_key, json.dumps(trip_summary, ensure_ascii=False))
                await r.ltrim(redis_key, 0, SHORT_TERM_MAX_TRIPS - 1)
                await r.expire(redis_key, SHORT_TERM_TTL)
                return
            except Exception:
                self._fallback = True
                logger.warning("[ShortTermMemory] Redis lpush 失败，切换到内存模式")

        # Fallback: in-memory
        if user_id not in self._memory:
            self._memory[user_id] = []
        self._memory[user_id].insert(0, trip_summary)
        self._memory[user_id] = self._memory[user_id][:SHORT_TERM_MAX_TRIPS]

    async def get_recent_trips(self, user_id: str, n: int = 3) -> list[dict[str, Any]]:
        """获取最近的 n 次行程。"""
        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{SHORT_TERM_KEY_PREFIX}{user_id}"
                data = await r.lrange(redis_key, 0, n - 1)
                return [json.loads(item) for item in data]
            except Exception:
                self._fallback = True
                logger.warning("[ShortTermMemory] Redis lrange 失败，切换到内存模式")

        # Fallback: in-memory
        trips = self._memory.get(user_id, [])
        return trips[:n]

    async def get_last_trip(self, user_id: str) -> dict[str, Any] | None:
        """获取最近一次行程摘要。"""
        trips = await self.get_recent_trips(user_id, n=1)
        return trips[0] if trips else None

    @property
    def is_fallback(self) -> bool:
        return self._fallback
