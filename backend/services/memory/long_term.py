"""L3: 长期用户画像。

存储用户的长期偏好数据，包括累计偏好统计、访问次数最多的category、
平均消费水平、历史情绪曲线。长期保留 (无 TTL)。
Redis 不可用时自动回退到内存字典。
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

LONG_TERM_KEY_PREFIX = "memory:lt:"


class LongTermMemory:
    """长期用户画像。

    存储用户的长期偏好数据。
    Redis Hash, key = f"memory:lt:{user_id}"
    字段: preferences, category_visits, visit_count, total_spent, emotion_history。
    TTL = 无 (长期保留)。
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
            logger.info("[LongTermMemory] Redis 连接成功")
            return self._redis
        except Exception:
            self._connected = False
            self._fallback = True
            logger.warning("[LongTermMemory] Redis 不可达，切换到内存模式")
            return None

    async def _ensure_profile_exists(self, user_id: str) -> None:
        """确保用户画像在 Redis 或内存中存在。"""
        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{LONG_TERM_KEY_PREFIX}{user_id}"
                exists = await r.exists(redis_key)
                if not exists:
                    default = self._default_profile()
                    await r.hset(
                        redis_key,
                        mapping={
                            "preferences": json.dumps(
                                default["preferences"], ensure_ascii=False
                            ),
                            "category_visits": json.dumps(
                                default["category_visits"], ensure_ascii=False
                            ),
                            "visit_count": json.dumps(default["visit_count"]),
                            "total_spent": json.dumps(default["total_spent"]),
                            "emotion_history": json.dumps(
                                default["emotion_history"], ensure_ascii=False
                            ),
                        },
                    )
                return
            except Exception:
                self._fallback = True

        # Fallback
        if user_id not in self._memory:
            self._memory[user_id] = self._default_profile()

    @staticmethod
    def _default_profile() -> dict[str, Any]:
        """返回默认用户画像。"""
        return {
            "preferences": {},
            "category_visits": {},
            "visit_count": 0,
            "total_spent": 0,
            "emotion_history": [],
        }

    async def get_profile(self, user_id: str) -> dict[str, Any]:
        """获取用户画像（含默认值）。"""
        await self._ensure_profile_exists(user_id)
        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{LONG_TERM_KEY_PREFIX}{user_id}"
                data = await r.hgetall(redis_key)
                if data:
                    return {
                        "preferences": json.loads(data.get("preferences", "{}")),
                        "category_visits": json.loads(
                            data.get("category_visits", "{}")
                        ),
                        "visit_count": json.loads(data.get("visit_count", "0")),
                        "total_spent": json.loads(data.get("total_spent", "0")),
                        "emotion_history": json.loads(
                            data.get("emotion_history", "[]")
                        ),
                    }
                return self._default_profile()
            except Exception:
                self._fallback = True

        # Fallback: in-memory
        return dict(self._memory.get(user_id, self._default_profile()))

    async def update_preference(
        self, user_id: str, category: str, value: float
    ) -> None:
        """更新或添加用户偏好。"""
        profile = await self.get_profile(user_id)
        profile["preferences"][category] = value

        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{LONG_TERM_KEY_PREFIX}{user_id}"
                await r.hset(
                    redis_key,
                    "preferences",
                    json.dumps(profile["preferences"], ensure_ascii=False),
                )
                return
            except Exception:
                self._fallback = True

        # Fallback: in-memory
        self._memory[user_id] = profile

    async def record_visit(
        self, user_id: str, poi_category: str, price: float, emotion: str
    ) -> None:
        """记录一次 POI 访问，更新类别计数和统计数据。"""
        profile = await self.get_profile(user_id)

        profile["category_visits"][poi_category] = (
            profile["category_visits"].get(poi_category, 0) + 1
        )
        profile["visit_count"] += 1
        profile["total_spent"] += price

        profile["emotion_history"].append(
            {"category": poi_category, "emotion": emotion, "price": price}
        )
        if len(profile["emotion_history"]) > 50:
            profile["emotion_history"] = profile["emotion_history"][-50:]

        r = await self._get_redis()
        if r is not None:
            try:
                redis_key = f"{LONG_TERM_KEY_PREFIX}{user_id}"
                await r.hset(
                    redis_key,
                    mapping={
                        "category_visits": json.dumps(
                            profile["category_visits"], ensure_ascii=False
                        ),
                        "visit_count": json.dumps(profile["visit_count"]),
                        "total_spent": json.dumps(profile["total_spent"]),
                        "emotion_history": json.dumps(
                            profile["emotion_history"], ensure_ascii=False
                        ),
                    },
                )
                return
            except Exception:
                self._fallback = True

        # Fallback: in-memory
        self._memory[user_id] = profile

    async def get_statistics(self, user_id: str) -> dict[str, Any]:
        """获取用户统计信息。"""
        profile = await self.get_profile(user_id)

        category_visits = profile.get("category_visits", {})
        most_visited_category = (
            max(category_visits, key=category_visits.get)
            if category_visits
            else None
        )

        visit_count = profile.get("visit_count", 0)
        total_spent = profile.get("total_spent", 0)

        return {
            "visit_count": visit_count,
            "category_visits": category_visits,
            "most_visited_category": most_visited_category,
            "average_spending": (
                round(total_spent / visit_count, 2) if visit_count > 0 else 0.0
            ),
            "total_spent": total_spent,
            "emotion_history_count": len(profile.get("emotion_history", [])),
        }

    @property
    def is_fallback(self) -> bool:
        return self._fallback
