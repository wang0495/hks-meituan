"""CityFlow 启动时缓存预热脚本。

在应用启动时执行缓存预热，减少冷启动时的延迟抖动。

使用方式::

    from backend.startup.warmup import startup_warmup

    # 在 FastAPI startup 事件中调用
    await startup_warmup()
"""

from __future__ import annotations

import asyncio
import logging

from backend.cache.warmup import CacheWarmup, get_cache_warmup

logger = logging.getLogger(__name__)


async def startup_warmup() -> CacheWarmup:
    """启动时预热：执行所有注册的预热任务。

    创建 CacheWarmup 实例，注册默认预热任务，执行全量预热。

    Returns:
        CacheWarmup 实例，可用于后续按需预热或启动定时预热
    """
    warmup = get_cache_warmup()

    logger.info("启动缓存预热...")
    report = await warmup.warmup_all()

    if report.failure_count > 0:
        logger.warning(
            "缓存预热部分失败: %d/%d 任务失败",
            report.failure_count,
            len(report.results),
        )
    else:
        logger.info(
            "缓存预热全部成功: %d 个任务, 耗时 %.0fms",
            report.success_count,
            report.total_duration_ms,
        )

    return warmup


async def startup_warmup_with_background(
    interval: int = 3600,
) -> tuple[CacheWarmup, asyncio.Task[None]]:
    """启动时预热 + 启动定时预热后台任务。

    先执行一次全量预热，然后启动后台定时刷新循环。

    Args:
        interval: 定时刷新间隔秒数，默认 3600（1 小时）

    Returns:
        (CacheWarmup 实例, 后台定时任务)
    """
    warmup = await startup_warmup()

    # 启动后台定时预热
    background_task = asyncio.create_task(warmup.start_background_warmup(interval=interval))

    logger.info("定时缓存预热已启动，间隔 %ds", interval)

    return warmup, background_task
