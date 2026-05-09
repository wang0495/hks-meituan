"""CityFlow 统一缓存管理器。

整合多级缓存 (L1 内存 + L2 Redis) 和缓存优化器 (singleflight、分级 TTL、健康诊断)，
提供面向业务层的统一 API。

使用方式::

    from backend.cache.manager import get_cache_manager

    manager = get_cache_manager()

    # 基础缓存操作
    await manager.get("key")
    await manager.set("key", value, ttl=300)
    await manager.delete("key")

    # 带 singleflight 保护的缓存读取（防止缓存击穿）
    value = await manager.get_or_compute("key", expensive_fn)

    # 批量操作
    values = await manager.multi_get(["k1", "k2"])
    await manager.multi_set({"k1": v1, "k2": v2})

    # 缓存健康分析
    report = manager.analyze()
    print(report.recommendations)
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

from backend.optimizations.cache import CacheHealthReport, CacheOptimizer
from backend.services.cache import MultiLevelCache, get_multilevel_cache

logger = logging.getLogger(__name__)

# 计算函数类型
ComputeFunc = Callable[[], Coroutine[Any, Any, Any]]


class CacheManager:
    """CityFlow 统一缓存管理器。

    整合多级缓存和缓存优化器，提供面向业务层的统一 API。

    Args:
        cache: 多级缓存实例，默认使用全局单例
    """

    def __init__(self, cache: MultiLevelCache | None = None) -> None:
        self._cache = cache or get_multilevel_cache()
        self._optimizer = CacheOptimizer(self._cache)

    # ------------------------------------------------------------------
    # 基础缓存操作
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Any | None:
        """获取缓存值（L1 -> L2 -> None）。

        Args:
            key: 缓存键

        Returns:
            缓存值，未命中返回 None
        """
        return await self._cache.get(key)

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """写入缓存（同时写入 L1 和 L2）。

        Args:
            key: 缓存键
            value: 缓存值
            ttl: L2 缓存 TTL 秒数，默认 3600
        """
        await self._cache.set(key, value, ttl)

    async def delete(self, key: str) -> None:
        """删除缓存（同时删除 L1 和 L2）。

        Args:
            key: 缓存键
        """
        await self._cache.delete(key)

    async def invalidate(self, prefix: str) -> dict[str, int]:
        """按前缀清除缓存。

        Args:
            prefix: 缓存键前缀

        Returns:
            {"l1_deleted": int, "l2_deleted": int}
        """
        return await self._cache.invalidate(prefix)

    # ------------------------------------------------------------------
    # 高级缓存操作（带优化器保护）
    # ------------------------------------------------------------------

    async def get_or_compute(
        self,
        key: str,
        compute_fn: ComputeFunc,
        ttl: int = 3600,
    ) -> Any:
        """带 singleflight 保护的缓存读取。

        缓存未命中时，多个并发请求只执行一次 compute_fn，
        其余请求等待并共享结果，防止缓存击穿。

        Args:
            key: 缓存键
            compute_fn: 缓存未命中时的异步计算函数
            ttl: L2 缓存 TTL 秒数

        Returns:
            缓存值或计算结果
        """
        return await self._optimizer.get_or_compute(key, compute_fn, ttl)

    async def get_or_compute_with_stale(
        self,
        key: str,
        compute_fn: ComputeFunc,
        ttl: int = 3600,
        stale_ttl: int = 7200,
    ) -> Any:
        """Stale-While-Revalidate 模式。

        缓存命中但已过期时，返回旧值并在后台刷新；
        缓存完全不存在时，阻塞等待计算结果。

        Args:
            key: 缓存键
            compute_fn: 异步计算函数
            ttl: 新鲜 TTL 秒数
            stale_ttl: 陈旧 TTL 秒数
        """
        return await self._optimizer.get_or_compute_with_stale(
            key, compute_fn, ttl, stale_ttl
        )

    async def multi_get(self, keys: list[str]) -> dict[str, Any]:
        """批量获取缓存值。

        Args:
            keys: 缓存键列表

        Returns:
            {key: value} 仅包含命中的键
        """
        return await self._optimizer.multi_get(keys)

    async def multi_set(self, items: dict[str, Any], ttl: int = 3600) -> None:
        """批量写入缓存。

        Args:
            items: {key: value} 字典
            ttl: L2 缓存 TTL 秒数
        """
        await self._optimizer.multi_set(items, ttl)

    async def warmup_keys(
        self,
        keys: list[str],
        compute_fn: Callable[[str], Coroutine[Any, Any, Any]],
        ttl: int = 3600,
        concurrency: int = 4,
    ) -> dict[str, bool]:
        """并发预热指定的缓存键。

        Args:
            keys: 待预热的缓存键列表
            compute_fn: 接受 key 返回 value 的异步函数
            ttl: 缓存 TTL
            concurrency: 最大并发数

        Returns:
            {key: success} 预热结果
        """
        return await self._optimizer.warmup_keys(keys, compute_fn, ttl, concurrency)

    # ------------------------------------------------------------------
    # 分析与诊断
    # ------------------------------------------------------------------

    def analyze(self) -> CacheHealthReport:
        """分析缓存健康状态并给出优化建议。

        Returns:
            CacheHealthReport 诊断报告
        """
        return self._optimizer.analyze()

    def recommend_ttl(self, key: str) -> int:
        """根据访问频率推荐 TTL。

        Args:
            key: 缓存键

        Returns:
            推荐的 TTL 秒数
        """
        return self._optimizer.recommend_ttl(key)

    @property
    def stats(self) -> dict[str, Any]:
        """返回缓存统计信息。"""
        return self._optimizer.stats

    def reset_stats(self) -> None:
        """重置统计计数器。"""
        self._optimizer.reset_stats()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def init(self) -> None:
        """初始化缓存（连接 Redis L2）。应用启动时调用。"""
        if self._cache.l2 is not None:
            await self._cache.l2.connect()
        logger.info("CacheManager 初始化完成")

    async def close(self) -> None:
        """关闭缓存（断开 Redis L2）。应用关闭时调用。"""
        if self._cache.l2 is not None:
            await self._cache.l2.close()
        logger.info("CacheManager 已关闭")

    @property
    def cache(self) -> MultiLevelCache:
        """返回底层多级缓存实例。"""
        return self._cache

    @property
    def optimizer(self) -> CacheOptimizer:
        """返回缓存优化器实例。"""
        return self._optimizer


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器单例。"""
    global _manager
    if _manager is None:
        _manager = CacheManager()
    return _manager


def reset_cache_manager() -> None:
    """重置全局缓存管理器（用于测试）。"""
    global _manager
    _manager = None
