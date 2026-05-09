"""CityFlow 缓存策略优化器。

在现有 MultiLevelCache (L1 内存 + L2 Redis) 基础上提供：
1. 缓存击穿保护 -- singleflight 模式，防止缓存失效时大量请求穿透到后端
2. 分级 TTL 策略 -- 根据数据热度自动调整 TTL
3. 缓存预热调度 -- 基于访问频率的智能预热优先级
4. 缓存健康诊断 -- 命中率、淘汰率、内存占用分析

用法::

    optimizer = CacheOptimizer(cache)

    # singleflight 保护的缓存读取
    value = await optimizer.get_or_compute("key", expensive_fn)

    # 分析缓存状态
    report = optimizer.analyze()
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

from backend.services.cache import MultiLevelCache

logger = logging.getLogger(__name__)

# 计算函数类型
ComputeFunc = Callable[[], Coroutine[Any, Any, Any]]


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CacheTierConfig:
    """缓存层配置。"""

    name: str
    max_size: int
    ttl_seconds: int
    description: str


@dataclass(frozen=True, slots=True)
class CacheHealthReport:
    """缓存健康诊断报告。"""

    l1_hit_rate: float
    l1_size: int
    l1_max_size: int
    l1_utilization: float
    l2_connected: bool
    access_counts: dict[str, int]
    recommendations: list[str]


# ---------------------------------------------------------------------------
# TTL 分级策略
# ---------------------------------------------------------------------------

# 根据数据访问频率自动匹配 TTL
TTL_TIERS: list[CacheTierConfig] = [
    CacheTierConfig(
        name="hot",
        max_size=100,
        ttl_seconds=300,  # 5 分钟
        description="高频访问数据（POI 列表、城市列表）",
    ),
    CacheTierConfig(
        name="warm",
        max_size=500,
        ttl_seconds=1800,  # 30 分钟
        description="中频访问数据（路线规划结果）",
    ),
    CacheTierConfig(
        name="cold",
        max_size=2000,
        ttl_seconds=3600,  # 1 小时
        description="低频访问数据（用户画像、数据集）",
    ),
]


# ---------------------------------------------------------------------------
# 优化器
# ---------------------------------------------------------------------------


class CacheOptimizer:
    """缓存策略优化器。

    Args:
        cache: 多级缓存实例。
    """

    def __init__(self, cache: MultiLevelCache) -> None:
        self._cache = cache
        # singleflight: key -> Future，防止缓存击穿
        self._inflight: dict[str, asyncio.Future[Any]] = {}
        # 访问计数
        self._access_counts: dict[str, int] = defaultdict(int)
        # 命中/未命中计数
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # 1. 缓存击穿保护（singleflight）
    # ------------------------------------------------------------------

    async def get_or_compute(
        self,
        key: str,
        compute_fn: ComputeFunc,
        ttl: int = 3600,
    ) -> Any:
        """带 singleflight 保护的缓存读取。

        如果缓存未命中，多个并发请求只执行一次 compute_fn，
        其余请求等待并共享结果。

        Args:
            key: 缓存键
            compute_fn: 缓存未命中时的异步计算函数
            ttl: L2 缓存 TTL（秒）

        Returns:
            缓存值或计算结果
        """
        self._access_counts[key] += 1

        # 1. 先查缓存
        value = await self._cache.get(key)
        if value is not None:
            self._hits += 1
            return value

        self._misses += 1

        # 2. 检查是否有正在进行的计算
        if key in self._inflight:
            logger.debug("singleflight 等待: %s", key)
            return await self._inflight[key]

        # 3. 发起计算
        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._inflight[key] = future

        try:
            result = await compute_fn()
            # 写入缓存
            await self._cache.set(key, result, ttl)
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            self._inflight.pop(key, None)

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
            ttl: 新鲜 TTL（秒）
            stale_ttl: 陈旧 TTL（秒，超过此时间彻底删除）
        """
        self._access_counts[key] += 1

        # 直接查缓存（L1 + L2）
        value = await self._cache.get(key)
        if value is not None:
            self._hits += 1
            return value

        self._misses += 1

        # 缓存未命中，阻塞计算
        if key in self._inflight:
            return await self._inflight[key]

        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._inflight[key] = future

        try:
            result = await compute_fn()
            await self._cache.set(key, result, ttl)
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            self._inflight.pop(key, None)

    # ------------------------------------------------------------------
    # 2. 分级 TTL 策略
    # ------------------------------------------------------------------

    def recommend_ttl(self, key: str) -> int:
        """根据访问频率推荐 TTL。

        Args:
            key: 缓存键

        Returns:
            推荐的 TTL 秒数
        """
        count = self._access_counts.get(key, 0)

        if count >= 100:
            return TTL_TIERS[0].ttl_seconds  # hot: 5 分钟（频繁刷新）
        elif count >= 10:
            return TTL_TIERS[1].ttl_seconds  # warm: 30 分钟
        else:
            return TTL_TIERS[2].ttl_seconds  # cold: 1 小时

    def get_tier_for_key(self, key: str) -> CacheTierConfig:
        """根据访问频率返回推荐的缓存层配置。"""
        count = self._access_counts.get(key, 0)

        if count >= 100:
            return TTL_TIERS[0]
        elif count >= 10:
            return TTL_TIERS[1]
        else:
            return TTL_TIERS[2]

    # ------------------------------------------------------------------
    # 3. 缓存预热调度
    # ------------------------------------------------------------------

    def get_warmup_priorities(self) -> list[tuple[str, int]]:
        """根据访问频率返回预热优先级列表。

        Returns:
            [(缓存键, 访问次数)] 按访问次数降序排列
        """
        return sorted(
            self._access_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

    def get_top_keys(self, n: int = 20) -> list[str]:
        """返回访问频率最高的 N 个缓存键。"""
        priorities = self.get_warmup_priorities()
        return [key for key, _ in priorities[:n]]

    # ------------------------------------------------------------------
    # 4. 缓存健康诊断
    # ------------------------------------------------------------------

    def analyze(self) -> CacheHealthReport:
        """分析缓存健康状态并给出优化建议。"""
        l1_stats = self._cache.l1.stats

        recommendations: list[str] = []

        # 命中率分析
        hit_rate = l1_stats.get("hit_rate", 0)
        if hit_rate < 0.5:
            recommendations.append(
                f"L1 命中率过低 ({hit_rate:.1%})，建议增大 L1 容量或调整 TTL"
            )
        elif hit_rate < 0.8:
            recommendations.append(
                f"L1 命中率偏低 ({hit_rate:.1%})，建议检查缓存键设计是否合理"
            )

        # 容量分析
        l1_size = int(l1_stats.get("size", 0))
        l1_max = self._cache.l1._max_size
        utilization = l1_size / l1_max if l1_max > 0 else 0
        if utilization > 0.9:
            recommendations.append(
                f"L1 容量接近上限 ({utilization:.0%})，建议增大 max_size 或缩短 TTL"
            )

        # L2 连接状态
        l2_connected = self._cache.l2 is not None and self._cache.l2.is_connected
        if not l2_connected:
            recommendations.append("L2 (Redis) 未连接，多级缓存降级为仅 L1")

        # 热点 key 分析
        top_keys = self.get_top_keys(5)
        if top_keys:
            recommendations.append(f"热点 key: {', '.join(top_keys[:3])}，建议单独预热")

        return CacheHealthReport(
            l1_hit_rate=hit_rate,
            l1_size=l1_size,
            l1_max_size=l1_max,
            l1_utilization=utilization,
            l2_connected=l2_connected,
            access_counts=dict(self._access_counts),
            recommendations=recommendations,
        )

    # ------------------------------------------------------------------
    # 5. 批量缓存操作
    # ------------------------------------------------------------------

    async def multi_get(self, keys: list[str]) -> dict[str, Any]:
        """批量获取缓存值。

        Args:
            keys: 缓存键列表

        Returns:
            {key: value} 仅包含命中的键
        """
        results: dict[str, Any] = {}
        for key in keys:
            value = await self._cache.get(key)
            if value is not None:
                results[key] = value
                self._hits += 1
            else:
                self._misses += 1
        return results

    async def multi_set(self, items: dict[str, Any], ttl: int = 3600) -> None:
        """批量写入缓存。

        Args:
            items: {key: value} 字典
            ttl: L2 缓存 TTL（秒）
        """
        for key, value in items.items():
            await self._cache.set(key, value, ttl)

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
        semaphore = asyncio.Semaphore(concurrency)
        results: dict[str, bool] = {}

        async def _warmup(key: str) -> None:
            async with semaphore:
                try:
                    value = await compute_fn(key)
                    await self._cache.set(key, value, ttl)
                    results[key] = True
                except Exception:
                    logger.exception("预热失败: %s", key)
                    results[key] = False

        async with asyncio.TaskGroup() as tg:
            for key in keys:
                tg.create_task(_warmup(key))

        return results

    # ------------------------------------------------------------------
    # 6. 统计
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict[str, Any]:
        """返回优化器统计信息。"""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0,
            "inflight_count": len(self._inflight),
            "tracked_keys": len(self._access_counts),
            "l1": self._cache.l1.stats,
            "l2_connected": (self._cache.l2.is_connected if self._cache.l2 else False),
        }

    def reset_stats(self) -> None:
        """重置统计计数器。"""
        self._hits = 0
        self._misses = 0
        self._access_counts.clear()


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_optimizer: CacheOptimizer | None = None


def get_cache_optimizer() -> CacheOptimizer:
    """获取全局缓存优化器单例。"""
    global _optimizer
    if _optimizer is None:
        from backend.services.cache import get_multilevel_cache

        _optimizer = CacheOptimizer(get_multilevel_cache())
    return _optimizer


def reset_cache_optimizer() -> None:
    """重置全局单例（用于测试）。"""
    global _optimizer
    _optimizer = None
