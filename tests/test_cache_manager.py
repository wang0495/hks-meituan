"""CacheManager 统一缓存管理器测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.cache.manager import CacheManager, get_cache_manager, reset_cache_manager
from backend.services.cache import MemoryCache, MultiLevelCache, RedisCache

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ml_cache() -> MultiLevelCache:
    """带 Mock Redis 的多级缓存。"""
    l1 = MemoryCache(max_size=10, ttl_seconds=60)
    l2 = RedisCache()
    l2._connected = True
    l2._redis = AsyncMock()
    return MultiLevelCache(l1=l1, l2=l2)


@pytest.fixture
def manager(ml_cache: MultiLevelCache) -> CacheManager:
    """基于 Mock 缓存的管理器。"""
    return CacheManager(cache=ml_cache)


# ---------------------------------------------------------------------------
# 基础操作
# ---------------------------------------------------------------------------


class TestCacheManagerBasic:
    """基础缓存操作测试。"""

    @pytest.mark.asyncio
    async def test_get_set(self, manager: CacheManager) -> None:
        await manager.set("key", "value")
        result = await manager.get("key")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_get_miss(self, manager: CacheManager) -> None:
        result = await manager.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, manager: CacheManager) -> None:
        await manager.set("key", "value")
        await manager.delete("key")
        assert await manager.get("key") is None

    @pytest.mark.asyncio
    async def test_invalidate(self, manager: CacheManager) -> None:
        await manager.set("dist:a", 1)
        await manager.set("dist:b", 2)
        await manager.set("other:c", 3)

        # Mock L2 scan_iter
        async def mock_scan_iter(match="", count=100):
            yield "cityflow:dist:a"
            yield "cityflow:dist:b"

        manager.cache.l2._redis.scan_iter = mock_scan_iter
        manager.cache.l2._redis.delete = AsyncMock()

        result = await manager.invalidate("dist:")
        assert result["l1_deleted"] == 2


# ---------------------------------------------------------------------------
# 高级操作
# ---------------------------------------------------------------------------


class TestCacheManagerAdvanced:
    """高级缓存操作测试。"""

    @pytest.mark.asyncio
    async def test_get_or_compute(self, manager: CacheManager) -> None:
        call_count = 0

        async def compute() -> str:
            nonlocal call_count
            call_count += 1
            return "computed"

        # 第一次：执行计算
        result = await manager.get_or_compute("key", compute)
        assert result == "computed"
        assert call_count == 1

        # 第二次：命中缓存
        result = await manager.get_or_compute("key", compute)
        assert result == "computed"
        assert call_count == 1  # 不应再次调用

    @pytest.mark.asyncio
    async def test_multi_get(self, manager: CacheManager) -> None:
        await manager.set("k1", "v1")
        await manager.set("k2", "v2")

        results = await manager.multi_get(["k1", "k2", "k3"])
        assert results == {"k1": "v1", "k2": "v2"}

    @pytest.mark.asyncio
    async def test_multi_set(self, manager: CacheManager) -> None:
        await manager.multi_set({"k1": "v1", "k2": "v2"})

        assert await manager.get("k1") == "v1"
        assert await manager.get("k2") == "v2"


# ---------------------------------------------------------------------------
# 分析与诊断
# ---------------------------------------------------------------------------


class TestCacheManagerAnalysis:
    """缓存分析与诊断测试。"""

    def test_analyze(self, manager: CacheManager) -> None:
        report = manager.analyze()
        assert hasattr(report, "l1_hit_rate")
        assert hasattr(report, "recommendations")

    def test_stats(self, manager: CacheManager) -> None:
        stats = manager.stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats

    def test_reset_stats(self, manager: CacheManager) -> None:
        # 触发一些访问
        manager.analyze()
        manager.reset_stats()
        stats = manager.stats
        assert stats["hits"] == 0
        assert stats["misses"] == 0


# ---------------------------------------------------------------------------
# 生命周期
# ---------------------------------------------------------------------------


class TestCacheManagerLifecycle:
    """生命周期测试。"""

    @pytest.mark.asyncio
    async def test_init_connects_l2(self, ml_cache: MultiLevelCache) -> None:
        manager = CacheManager(cache=ml_cache)
        # Mock connect
        ml_cache.l2._redis.ping = AsyncMock()
        await manager.init()
        # 不应抛出异常

    @pytest.mark.asyncio
    async def test_close_disconnects_l2(self, ml_cache: MultiLevelCache) -> None:
        manager = CacheManager(cache=ml_cache)
        mock_redis = ml_cache.l2._redis
        await manager.close()
        mock_redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_l2_graceful(self) -> None:
        """没有 L2 时 init/close 不应抛出异常。"""
        cache = MultiLevelCache(l1=MemoryCache(ttl_seconds=60))
        manager = CacheManager(cache=cache)
        await manager.init()
        await manager.close()


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------


class TestGlobalCacheManager:
    """全局单例测试。"""

    def setup_method(self) -> None:
        reset_cache_manager()

    def teardown_method(self) -> None:
        reset_cache_manager()

    def test_singleton(self) -> None:
        m1 = get_cache_manager()
        m2 = get_cache_manager()
        assert m1 is m2

    def test_reset(self) -> None:
        m1 = get_cache_manager()
        reset_cache_manager()
        m2 = get_cache_manager()
        assert m1 is not m2
