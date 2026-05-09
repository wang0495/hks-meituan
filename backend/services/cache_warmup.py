"""CityFlow 缓存预热模块。

在应用启动时将热点数据加载到缓存中，减少冷启动时的延迟抖动。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.services.cache import get_multilevel_cache
from backend.services.data_service import get_data

logger = logging.getLogger(__name__)


async def warmup_multilevel_cache() -> None:
    """将热点数据预热到多级缓存（L1 + L2）。"""
    cache = get_multilevel_cache()

    logger.info("开始缓存预热...")

    # 1. 预热 POI 全量数据
    pois = get_data("city_poi_db")
    if pois:
        await cache.set("warmup:all_pois", pois, ttl=3600)
        logger.info("预热 POI 数据: %d 条", len(pois))

        # 2. 预热城市列表
        cities = sorted({p.get("city", "") for p in pois if p.get("city")})
        await cache.set("warmup:cities", cities, ttl=3600)
        logger.info("预热城市列表: %s", cities)

        # 3. 预热类别列表
        categories = sorted({p.get("category", "") for p in pois if p.get("category")})
        await cache.set("warmup:categories", categories, ttl=3600)
        logger.info("预热类别列表: %s", categories)

    # 4. 预热其他数据集
    from backend.services.data_service import get_datasets

    dataset_names = get_datasets()
    for ds_name in dataset_names:
        if ds_name == "city_poi_db":
            continue
        data = get_data(ds_name)
        if data:
            await cache.set(f"warmup:dataset:{ds_name}", data, ttl=3600)
            logger.info(
                "预热数据集 %s: %d 条",
                ds_name,
                len(data) if isinstance(data, list) else 1,
            )

    logger.info("缓存预热完成")


def warmup_memory_caches(pois: list[dict[str, Any]] | None = None) -> None:
    """将热点数据预热到全局 MemoryCache 实例（同步）。

    在 startup 中 ``load_data()`` 之后调用。
    """
    from backend.services.cache import general_cache, poi_cache

    if pois is None:
        pois = get_data("city_poi_db")
    if not pois:
        return

    # 按城市分桶缓存
    city_buckets: dict[str, list[dict]] = {}
    for poi in pois:
        city = poi.get("city", "")
        city_buckets.setdefault(city, []).append(poi)

    for city, city_pois in city_buckets.items():
        poi_cache.set(f"city:{city}", city_pois)

    # 缓存类别列表
    categories = sorted({p.get("category", "") for p in pois if p.get("category")})
    general_cache.set("categories", categories)

    logger.info(
        "MemoryCache 预热完成: %d 城市, %d 类别",
        len(city_buckets),
        len(categories),
    )


async def schedule_cache_refresh(interval_seconds: int = 3600) -> None:
    """定时刷新多级缓存中的预热数据。

    在后台任务中运行，每 ``interval_seconds`` 秒刷新一次。
    """
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await warmup_multilevel_cache()
            logger.info("定时缓存刷新完成")
        except Exception:
            logger.exception("定时缓存刷新失败")
