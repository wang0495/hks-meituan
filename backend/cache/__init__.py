"""CityFlow 缓存模块。

提供多级缓存管理、缓存优化和缓存预热功能。

快速开始::

    from backend.cache import get_cache_manager, get_cache_warmup

    # 获取缓存管理器
    manager = get_cache_manager()
    await manager.get("key")
    await manager.set("key", value)

    # 获取预热器
    warmup = get_cache_warmup()
    await warmup.warmup_all()
"""

from backend.cache.manager import CacheManager, get_cache_manager, reset_cache_manager
from backend.cache.warmup import (
    CacheWarmup,
    WarmupReport,
    WarmupResult,
    get_cache_warmup,
    reset_cache_warmup,
    warmup_city_category_cache,
    warmup_other_datasets,
    warmup_poi_cache,
)

__all__ = [
    "CacheManager",
    "CacheWarmup",
    "WarmupReport",
    "WarmupResult",
    "get_cache_manager",
    "get_cache_warmup",
    "reset_cache_manager",
    "reset_cache_warmup",
    "warmup_city_category_cache",
    "warmup_other_datasets",
    "warmup_poi_cache",
]
