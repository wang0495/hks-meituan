"""缓存优化器 — 最小实现，满足 CacheManager 依赖。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheHealthReport:
    """缓存健康诊断报告。"""

    hit_rate: float = 0.0
    l1_size: int = 0
    l2_connected: bool = False
    recommendations: list[str] = field(default_factory=list)


class CacheOptimizer:
    """缓存优化器：分析命中率、推荐 TTL、提供统计。"""

    def __init__(self, cache: Any) -> None:
        self._cache = cache
        self._access_counts: dict[str, int] = {}

    # ── 分析 ──────────────────────────────────────────

    def analyze(self) -> CacheHealthReport:
        l1 = getattr(self._cache, "l1", None)
        l2 = getattr(self._cache, "l2", None)
        hit_rate = getattr(self._cache, "hit_rate", 0.0)
        l1_size = len(l1) if hasattr(l1, "__len__") else 0
        recs: list[str] = []
        if hit_rate < 0.3:
            recs.append("命中率偏低，考虑预热热点 key")
        return CacheHealthReport(
            hit_rate=hit_rate,
            l1_size=l1_size,
            l2_connected=l2 is not None,
            recommendations=recs,
        )

    def recommend_ttl(self, key: str) -> int:
        count = self._access_counts.get(key, 0)
        if count > 10:
            return 7200
        if count > 3:
            return 3600
        return 1800

    # ── 统计 ──────────────────────────────────────────

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "access_counts": dict(self._access_counts),
            "tracked_keys": len(self._access_counts),
        }

    def reset_stats(self) -> None:
        self._access_counts.clear()

    # ── 预热 ──────────────────────────────────────────

    async def warmup_keys(
        self,
        keys: list[str],
        compute_fn: Any,
        ttl: int = 3600,
        concurrency: int = 5,
    ) -> int:
        loaded = 0
        for key in keys:
            try:
                value = await compute_fn(key)
                if value is not None:
                    await self._cache.set(key, value, ttl)
                    loaded += 1
            except Exception:
                logger.debug("预热 key=%s 失败", key, exc_info=True)
        return loaded
