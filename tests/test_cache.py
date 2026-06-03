"""缓存模块测试。"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.cache import (
    MemoryCache,
    MultiLevelCache,
    RedisCache,
    cache_key,
    cached,
    distance_cache,
    invalidate,
    poi_cache,
    profile_cache,
    route_cache,
)

# ---------------------------------------------------------------------------
# MemoryCache 基础测试
# ---------------------------------------------------------------------------


class TestMemoryCache:
    """MemoryCache 核心功能测试。"""

    def test_set_and_get(self) -> None:
        cache = MemoryCache(max_size=10, ttl_seconds=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key_returns_none(self) -> None:
        cache = MemoryCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self) -> None:
        cache = MemoryCache(max_size=10, ttl_seconds=0)
        cache.set("key1", "value1")
        # TTL=0，立即过期
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_max_size_eviction(self) -> None:
        cache = MemoryCache(max_size=3, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # 应该淘汰 "a"（最早写入且未被访问）
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_lru_eviction_protects_accessed_keys(self) -> None:
        """LRU: 访问过的 key 不应被淘汰，应淘汰最久未访问的。"""
        cache = MemoryCache(max_size=3, ttl_seconds=60)
        cache.set("a", 1)
        time.sleep(0.01)
        cache.set("b", 2)
        time.sleep(0.01)
        cache.set("c", 3)
        time.sleep(0.01)
        # 访问 "a"，使其成为最近使用的
        cache.get("a")
        time.sleep(0.01)
        # 写入 "d"，此时 "b" 是最久未访问的（应被淘汰）
        cache.set("d", 4)
        assert cache.get("a") == 1  # a 被访问过，保留
        assert cache.get("b") is None  # b 最久未访问，被淘汰
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_overwrite_existing_key(self) -> None:
        cache = MemoryCache(max_size=2, ttl_seconds=60)
        cache.set("key", "old")
        cache.set("key", "new")
        assert cache.get("key") == "new"
        assert cache.size == 1

    def test_delete(self) -> None:
        cache = MemoryCache()
        cache.set("key", "value")
        cache.delete("key")
        assert cache.get("key") is None

    def test_clear(self) -> None:
        cache = MemoryCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.size == 0
        assert cache.get("a") is None

    def test_size_property(self) -> None:
        cache = MemoryCache()
        assert cache.size == 0
        cache.set("a", 1)
        assert cache.size == 1
        cache.set("b", 2)
        assert cache.size == 2

    def test_stats(self) -> None:
        cache = MemoryCache(ttl_seconds=60)
        cache.set("a", 1)
        cache.get("a")  # hit
        cache.get("b")  # miss
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["total"] == 2
        assert stats["hit_rate"] == 0.5
        assert stats["size"] == 1


# ---------------------------------------------------------------------------
# cache_key 测试
# ---------------------------------------------------------------------------


class TestCacheKey:
    """cache_key 生成测试。"""

    def test_same_args_same_key(self) -> None:
        k1 = cache_key("a", "b", x=1)
        k2 = cache_key("a", "b", x=1)
        assert k1 == k2

    def test_different_args_different_key(self) -> None:
        k1 = cache_key("a")
        k2 = cache_key("b")
        assert k1 != k2

    def test_kwargs_order_independent(self) -> None:
        k1 = cache_key(a=1, b=2)
        k2 = cache_key(b=2, a=1)
        assert k1 == k2

    def test_returns_hex_string(self) -> None:
        k = cache_key("test")
        assert len(k) == 32  # MD5 hex length
        assert all(c in "0123456789abcdef" for c in k)


# ---------------------------------------------------------------------------
# cached 装饰器测试
# ---------------------------------------------------------------------------


class TestCachedDecorator:
    """cached 装饰器测试。"""

    def test_sync_function_caching(self) -> None:
        call_count = 0
        cache = MemoryCache(ttl_seconds=60)

        @cached(cache, prefix="test")
        def add(a: int, b: int) -> int:
            nonlocal call_count
            call_count += 1
            return a + b

        result1 = add(1, 2)
        result2 = add(1, 2)
        assert result1 == 3
        assert result2 == 3
        assert call_count == 1  # 第二次命中缓存

    @pytest.mark.asyncio
    async def test_async_function_caching(self) -> None:
        call_count = 0
        cache = MemoryCache(ttl_seconds=60)

        @cached(cache, prefix="async_test")
        async def fetch(url: str) -> str:
            nonlocal call_count
            call_count += 1
            return f"result:{url}"

        r1 = await fetch("http://example.com")
        r2 = await fetch("http://example.com")
        assert r1 == "result:http://example.com"
        assert r2 == "result:http://example.com"
        assert call_count == 1


# ---------------------------------------------------------------------------
# invalidate 测试
# ---------------------------------------------------------------------------


class TestInvalidate:
    """缓存失效测试。"""

    def test_invalidate_by_prefix(self) -> None:
        cache = MemoryCache()
        cache.set("dist:a:b", 100)
        cache.set("dist:c:d", 200)
        cache.set("other:key", 300)

        deleted = invalidate(cache, prefix="dist:")
        assert deleted == 2
        assert cache.get("dist:a:b") is None
        assert cache.get("other:key") == 300

    def test_invalidate_no_match(self) -> None:
        cache = MemoryCache()
        cache.set("key", "value")
        deleted = invalidate(cache, prefix="nonexistent:")
        assert deleted == 0
        assert cache.get("key") == "value"


# ---------------------------------------------------------------------------
# RedisCache 测试
# ---------------------------------------------------------------------------


class TestRedisCache:
    """RedisCache 测试（Mock Redis）。"""

    @pytest.fixture
    def redis_cache(self) -> RedisCache:
        cache = RedisCache(redis_url="redis://localhost:6379")
        # 模拟已连接状态
        cache._connected = True
        mock_redis = AsyncMock()
        cache._redis = mock_redis
        return cache

    @pytest.mark.asyncio
    async def test_get_hit(self, redis_cache: RedisCache) -> None:
        redis_cache._redis.get.return_value = '{"data": "value"}'
        result = await redis_cache.get("test_key")
        assert result == {"data": "value"}
        redis_cache._redis.get.assert_called_once_with("cityflow:test_key")

    @pytest.mark.asyncio
    async def test_get_miss(self, redis_cache: RedisCache) -> None:
        redis_cache._redis.get.return_value = None
        result = await redis_cache.get("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_not_connected(self) -> None:
        cache = RedisCache()
        cache._connected = False
        result = await cache.get("key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set(self, redis_cache: RedisCache) -> None:
        await redis_cache.set("key", {"a": 1}, ttl=600)
        redis_cache._redis.setex.assert_called_once()
        args = redis_cache._redis.setex.call_args
        assert args[0][0] == "cityflow:key"
        assert args[0][1] == 600

    @pytest.mark.asyncio
    async def test_delete(self, redis_cache: RedisCache) -> None:
        await redis_cache.delete("key")
        redis_cache._redis.delete.assert_called_once_with("cityflow:key")

    @pytest.mark.asyncio
    async def test_clear_pattern(self, redis_cache: RedisCache) -> None:
        # 模拟 scan_iter 返回
        async def mock_scan_iter(match="", count=100):
            yield "cityflow:warmup:a"
            yield "cityflow:warmup:b"

        redis_cache._redis.scan_iter = mock_scan_iter
        redis_cache._redis.delete = AsyncMock()
        deleted = await redis_cache.clear_pattern("warmup:*")
        assert deleted == 2

    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        cache = RedisCache()
        with patch("backend.services.cache.aioredis.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_from_url.return_value = mock_client
            await cache.connect()
            assert cache.is_connected is True
            mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self) -> None:
        cache = RedisCache()
        with patch("backend.services.cache.aioredis.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping.side_effect = ConnectionError("refused")
            mock_from_url.return_value = mock_client
            await cache.connect()
            assert cache.is_connected is False

    @pytest.mark.asyncio
    async def test_close(self, redis_cache: RedisCache) -> None:
        mock_redis = redis_cache._redis
        await redis_cache.close()
        assert redis_cache.is_connected is False
        mock_redis.close.assert_called_once()


# ---------------------------------------------------------------------------
# MultiLevelCache 测试
# ---------------------------------------------------------------------------


class TestMultiLevelCache:
    """MultiLevelCache 测试。"""

    @pytest.fixture
    def ml_cache(self) -> MultiLevelCache:
        l1 = MemoryCache(max_size=10, ttl_seconds=60)
        l2 = RedisCache()
        l2._connected = True
        l2._redis = AsyncMock()
        return MultiLevelCache(l1=l1, l2=l2)

    @pytest.mark.asyncio
    async def test_l1_hit_no_l2_call(self, ml_cache: MultiLevelCache) -> None:
        """L1 命中时不查 L2。"""
        ml_cache.l1.set("k", "v")
        result = await ml_cache.get("k")
        assert result == "v"
        # L2 不应被调用
        ml_cache.l2._redis.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_l2_hit_backfills_l1(self, ml_cache: MultiLevelCache) -> None:
        """L2 命中后回填 L1。"""
        ml_cache.l2._redis.get.return_value = '"from_l2"'
        result = await ml_cache.get("k")
        assert result == "from_l2"
        # L1 应该被回填
        assert ml_cache.l1.get("k") == "from_l2"

    @pytest.mark.asyncio
    async def test_miss_returns_none(self, ml_cache: MultiLevelCache) -> None:
        """L1 和 L2 都未命中时返回 None。"""
        ml_cache.l2._redis.get.return_value = None
        result = await ml_cache.get("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_writes_both(self, ml_cache: MultiLevelCache) -> None:
        """set 同时写入 L1 和 L2。"""
        await ml_cache.set("k", "v", ttl=600)
        assert ml_cache.l1.get("k") == "v"
        ml_cache.l2._redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_removes_both(self, ml_cache: MultiLevelCache) -> None:
        """delete 同时删除 L1 和 L2。"""
        ml_cache.l1.set("k", "v")
        await ml_cache.delete("k")
        assert ml_cache.l1.get("k") is None
        ml_cache.l2._redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_l2_graceful(self) -> None:
        """没有 L2 时也能正常工作。"""
        cache = MultiLevelCache(l1=MemoryCache(ttl_seconds=60))
        await cache.set("k", "v")
        result = await cache.get("k")
        assert result == "v"
        await cache.delete("k")
        assert await cache.get("k") is None

    def test_stats(self, ml_cache: MultiLevelCache) -> None:
        stats = ml_cache.stats
        assert "l1" in stats
        assert "l2_connected" in stats
        assert stats["l2_connected"] is True

    @pytest.mark.asyncio
    async def test_invalidate_by_prefix(self, ml_cache: MultiLevelCache) -> None:
        """invalidate 按前缀同时清除 L1 和 L2。"""
        ml_cache.l1.set("dist:a:b", 100)
        ml_cache.l1.set("dist:c:d", 200)
        ml_cache.l1.set("other:key", 300)

        # Mock L2 scan_iter
        async def mock_scan_iter(match="", count=100):
            yield "cityflow:dist:a:b"
            yield "cityflow:dist:c:d"

        ml_cache.l2._redis.scan_iter = mock_scan_iter
        ml_cache.l2._redis.delete = AsyncMock()

        result = await ml_cache.invalidate("dist:")
        assert result["l1_deleted"] == 2
        assert result["l2_deleted"] == 2
        assert ml_cache.l1.get("dist:a:b") is None
        assert ml_cache.l1.get("other:key") == 300

    @pytest.mark.asyncio
    async def test_invalidate_no_l2(self) -> None:
        """没有 L2 时 invalidate 只清除 L1。"""
        cache = MultiLevelCache(l1=MemoryCache(ttl_seconds=60))
        cache.l1.set("prefix:key1", 1)
        cache.l1.set("prefix:key2", 2)
        cache.l1.set("other:key", 3)

        result = await cache.invalidate("prefix:")
        assert result["l1_deleted"] == 2
        assert result["l2_deleted"] == 0
        assert cache.l1.get("other:key") == 3


# ---------------------------------------------------------------------------
# MultiLevelCache cached 装饰器测试
# ---------------------------------------------------------------------------


class TestCachedWithMultiLevel:
    """cached 装饰器配合 MultiLevelCache 测试。"""

    @pytest.mark.asyncio
    async def test_async_decorator_with_multilevel(self) -> None:
        call_count = 0
        l1 = MemoryCache(max_size=10, ttl_seconds=60)
        l2 = RedisCache()
        l2._connected = True
        l2._redis = AsyncMock()
        ml = MultiLevelCache(l1=l1, l2=l2)

        @cached(ml, prefix="ml_test", ttl=600)
        async def compute(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        r1 = await compute(5)
        r2 = await compute(5)
        assert r1 == 10
        assert r2 == 10
        assert call_count == 1


# ---------------------------------------------------------------------------
# 全局缓存实例测试
# ---------------------------------------------------------------------------


class TestGlobalCaches:
    """全局缓存实例基本测试。"""

    def test_poi_cache_writable(self) -> None:
        poi_cache.set("test_poi", {"id": "test"})
        assert poi_cache.get("test_poi") == {"id": "test"}
        poi_cache.delete("test_poi")

    def test_distance_cache_writable(self) -> None:
        distance_cache.set("dist:test", 123.4)
        assert distance_cache.get("dist:test") == 123.4
        distance_cache.delete("dist:test")

    def test_route_cache_writable(self) -> None:
        route_cache.set("route_123", {"route": []})
        assert route_cache.get("route_123") == {"route": []}
        route_cache.delete("route_123")

    def test_profile_cache_writable(self) -> None:
        profile_cache.set("profile:test", "P1")
        assert profile_cache.get("profile:test") == "P1"
        profile_cache.delete("profile:test")
