"""CityFlow 多级缓存模块。

提供三级缓存架构：
- L1: 内存缓存（MemoryCache）-- 同步，进程内，毫秒级
- L2: Redis 缓存（RedisCache）-- 异步，跨进程，亚毫秒级
- 组合层: MultiLevelCache -- L1 + L2 联合读写

同时保留原有全局缓存实例和装饰器，向后兼容。
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import threading
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote_plus

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MemoryCache: TTL + LRU 混合淘汰（L1 层）
# ---------------------------------------------------------------------------


class MemoryCache:
    """线程安全的内存缓存，支持 TTL 过期和容量上限。

    淘汰策略：TTL 过期优先，满时按 LRU 淘汰（最近最少访问）。
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300) -> None:
        self._cache: dict[str, tuple[Any, float, float]] = {}
        # 每条记录: (value, write_ts, last_access_ts)
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        """获取缓存值，过期则删除并返回 None。命中时更新访问时间（LRU）。"""
        with self._lock:
            if key in self._cache:
                value, write_ts, _ = self._cache[key]
                if time.monotonic() - write_ts < self._ttl:
                    self._hits += 1
                    # 更新最后访问时间，实现 LRU
                    self._cache[key] = (value, write_ts, time.monotonic())
                    return value
                # 过期，删除
                del self._cache[key]
            self._misses += 1
            return None

    def set(self, key: str, value: Any) -> None:
        """写入缓存，满时按 LRU 淘汰。"""
        with self._lock:
            now = time.monotonic()
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict_one()
            self._cache[key] = (value, now, now)

    def delete(self, key: str) -> None:
        """删除指定缓存条目。"""
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """清空全部缓存。"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def _evict_one(self) -> None:
        """淘汰最近最少访问的条目（LRU）。"""
        if not self._cache:
            return
        lru_key = min(self._cache, key=lambda k: self._cache[k][2])
        del self._cache[lru_key]

    @property
    def size(self) -> int:
        """当前缓存条目数。"""
        return len(self._cache)

    @property
    def stats(self) -> dict[str, int | float]:
        """返回命中率统计。"""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0,
            "size": self.size,
        }


# ---------------------------------------------------------------------------
# RedisCache: 异步 Redis 缓存（L2 层）
# ---------------------------------------------------------------------------


class RedisCache:
    """基于 Redis 的异步缓存，支持 TTL 和按前缀批量清除。

    所有键自动添加 ``cityflow:`` 前缀以避免命名冲突。
    """

    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self._redis: aioredis.Redis | None = None
        self._redis_url = redis_url
        self._prefix = "cityflow:"
        self._connected = False

    async def connect(self) -> None:
        """建立 Redis 连接。幂等，已连接时跳过。"""
        if self._connected and self._redis is not None:
            return
        try:
            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            # 验证连接
            await self._redis.ping()
            self._connected = True
            logger.info("Redis 连接成功: %s", self._redis_url)
        except Exception:
            self._connected = False
            self._redis = None
            logger.warning("Redis 连接失败，L2 缓存不可用: %s", self._redis_url)

    async def get(self, key: str) -> Any | None:
        """从 Redis 获取缓存值。未连接时直接返回 None。"""
        if not self._connected or self._redis is None:
            return None
        try:
            data = await self._redis.get(self._prefix + key)
            if data is not None:
                return json.loads(data)
        except Exception:
            logger.debug("Redis GET 失败: %s", key, exc_info=True)
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """写入 Redis 缓存，默认 1 小时过期。"""
        if not self._connected or self._redis is None:
            return
        try:
            await self._redis.setex(
                self._prefix + key,
                ttl,
                json.dumps(value, ensure_ascii=False, default=str),
            )
        except Exception:
            logger.debug("Redis SET 失败: %s", key, exc_info=True)

    async def delete(self, key: str) -> None:
        """删除指定键。"""
        if not self._connected or self._redis is None:
            return
        try:
            await self._redis.delete(self._prefix + key)
        except Exception:
            logger.debug("Redis DEL 失败: %s", key, exc_info=True)

    async def clear_pattern(self, pattern: str) -> int:
        """按通配符批量删除，返回删除数量。"""
        if not self._connected or self._redis is None:
            return 0
        try:
            full_pattern = self._prefix + pattern
            deleted = 0
            async for key in self._redis.scan_iter(match=full_pattern, count=100):
                await self._redis.delete(key)
                deleted += 1
            return deleted
        except Exception:
            logger.debug("Redis CLEAR_PATTERN 失败: %s", pattern, exc_info=True)
            return 0

    async def close(self) -> None:
        """关闭 Redis 连接。"""
        if self._redis is not None:
            await self._redis.close()
            self._connected = False
            self._redis = None

    @property
    def is_connected(self) -> bool:
        return self._connected


# ---------------------------------------------------------------------------
# MultiLevelCache: L1 + L2 联合缓存
# ---------------------------------------------------------------------------


class MultiLevelCache:
    """多级缓存：L1（内存） + L2（Redis）。

    读取策略：L1 命中直接返回 -> L2 命中回填 L1 -> 都未命中返回 None
    写入策略：同时写入 L1 和 L2
    删除策略：同时删除 L1 和 L2
    """

    def __init__(
        self,
        l1: MemoryCache | None = None,
        l2: RedisCache | None = None,
    ) -> None:
        self.l1 = l1 or MemoryCache(max_size=500, ttl_seconds=60)
        self.l2 = l2

    async def get(self, key: str) -> Any | None:
        """获取缓存值（L1 -> L2 -> None）。"""
        # L1 命中
        value = self.l1.get(key)
        if value is not None:
            return value

        # L2 命中 -> 回填 L1
        if self.l2 is not None:
            value = await self.l2.get(key)
            if value is not None:
                self.l1.set(key, value)
                return value

        return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """同时写入 L1 和 L2。L2 使用指定 TTL（默认 1 小时）。"""
        self.l1.set(key, value)
        if self.l2 is not None:
            await self.l2.set(key, value, ttl)

    async def delete(self, key: str) -> None:
        """同时删除 L1 和 L2。"""
        self.l1.delete(key)
        if self.l2 is not None:
            await self.l2.delete(key)

    async def clear_l2_pattern(self, pattern: str) -> int:
        """清除 L2 中匹配模式的键。返回删除数量。"""
        if self.l2 is not None:
            return await self.l2.clear_pattern(pattern)
        return 0

    async def invalidate(self, prefix: str) -> dict[str, int]:
        """按前缀同时清除 L1 和 L2 中的缓存条目。

        Returns:
            {"l1_deleted": int, "l2_deleted": int}
        """
        l1_deleted = invalidate(self.l1, prefix)
        l2_deleted = await self.clear_l2_pattern(f"{prefix}*")
        logger.debug(
            "invalidate prefix=%s: L1 删除 %d 条, L2 删除 %d 条",
            prefix,
            l1_deleted,
            l2_deleted,
        )
        return {"l1_deleted": l1_deleted, "l2_deleted": l2_deleted}

    @property
    def stats(self) -> dict[str, Any]:
        """返回 L1 统计 + L2 连接状态。"""
        result: dict[str, Any] = {"l1": self.l1.stats}
        if self.l2 is not None:
            result["l2_connected"] = self.l2.is_connected
        else:
            result["l2_connected"] = False
        return result


# ---------------------------------------------------------------------------
# 全局缓存实例（向后兼容，同步 L1）
# ---------------------------------------------------------------------------

# POI 数据缓存：100 条，10 分钟过期
poi_cache = MemoryCache(max_size=100, ttl_seconds=600)

# 距离矩阵缓存：10000 条，1 小时过期
distance_cache = MemoryCache(max_size=10000, ttl_seconds=3600)

# 路线结果缓存：50 条，30 分钟过期
route_cache = MemoryCache(max_size=50, ttl_seconds=1800)

# 用户画像匹配缓存：500 条，15 分钟过期
profile_cache = MemoryCache(max_size=500, ttl_seconds=900)

# 通用缓存：200 条，5 分钟过期
general_cache = MemoryCache(max_size=200, ttl_seconds=300)


# ---------------------------------------------------------------------------
# 全局多级缓存实例（异步，带 Redis L2）
# ---------------------------------------------------------------------------

_multilevel_cache: MultiLevelCache | None = None


def get_multilevel_cache() -> MultiLevelCache:
    """获取全局多级缓存单例。首次调用时根据配置创建。"""
    global _multilevel_cache
    if _multilevel_cache is None:
        from backend.config import settings

        l2: RedisCache | None = None
        redis_cfg = settings.redis
        if redis_cfg.host:
            url = f"redis://{redis_cfg.host}:{redis_cfg.port}/{redis_cfg.db}"
            if redis_cfg.password:
                url = f"redis://:{quote_plus(redis_cfg.password)}@{redis_cfg.host}:{redis_cfg.port}/{redis_cfg.db}"
            l2 = RedisCache(redis_url=url)
        _multilevel_cache = MultiLevelCache(
            l1=MemoryCache(max_size=500, ttl_seconds=60),
            l2=l2,
        )
    return _multilevel_cache


async def init_multilevel_cache() -> None:
    """初始化多级缓存的 L2（Redis）连接。应用启动时调用。"""
    cache = get_multilevel_cache()
    if cache.l2 is not None:
        await cache.l2.connect()


async def close_multilevel_cache() -> None:
    """关闭多级缓存的 L2 连接。应用关闭时调用。"""
    global _multilevel_cache
    if _multilevel_cache is not None and _multilevel_cache.l2 is not None:
        await _multilevel_cache.l2.close()


# ---------------------------------------------------------------------------
# 缓存键生成
# ---------------------------------------------------------------------------


def cache_key(*args: Any, **kwargs: Any) -> str:
    """根据参数生成稳定的 MD5 缓存键。"""
    data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(data.encode()).hexdigest()


# ---------------------------------------------------------------------------
# 缓存装饰器（同步 + 异步，支持 MemoryCache 和 MultiLevelCache）
# ---------------------------------------------------------------------------


def cached(
    cache: MemoryCache | MultiLevelCache,
    prefix: str = "",
    key_builder: Callable[..., str] | None = None,
    ttl: int = 3600,
) -> Callable:
    """通用缓存装饰器，同时支持同步和异步函数。

    Args:
        cache: MemoryCache（同步）或 MultiLevelCache（异步）实例
        prefix: 缓存键前缀
        key_builder: 自定义键生成函数，默认使用 cache_key
        ttl: MultiLevelCache 的 L2 TTL 秒数，默认 3600

    Returns:
        装饰后的函数
    """

    def decorator(func: Callable) -> Callable:
        _key_fn = key_builder or cache_key
        _is_multilevel = isinstance(cache, MultiLevelCache)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            key = f"{prefix}:{_key_fn(*args, **kwargs)}"
            if _is_multilevel:
                result = await cache.get(key)
            else:
                result = cache.get(key)
            if result is not None:
                logger.debug("缓存命中: %s", key[:16])
                return result
            result = await func(*args, **kwargs)
            if _is_multilevel:
                await cache.set(key, result, ttl)
            else:
                cache.set(key, result)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            key = f"{prefix}:{_key_fn(*args, **kwargs)}"
            result = cache.get(key)
            if result is not None:
                logger.debug("缓存命中: %s", key[:16])
                return result
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def invalidate(cache: MemoryCache, prefix: str = "") -> int:
    """清除指定前缀的所有缓存条目，返回删除数量。"""
    keys_to_delete = [k for k in cache._cache if k.startswith(prefix)]
    for k in keys_to_delete:
        cache.delete(k)
    return len(keys_to_delete)
