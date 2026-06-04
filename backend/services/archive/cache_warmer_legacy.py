"""CityFlow 缓存预热器。

提供三种预热策略：
- 启动时预热：应用启动时立即执行所有注册的预热任务
- 定时预热：后台周期性刷新缓存，防止数据过期
- 按需预热：通过 API 或手动调用触发单个/全部预热任务

使用方式::

    warmer = get_cache_warmer()
    warmer.register(my_warmup_task)

    # 启动时预热
    await warmer.warmup_all()

    # 定时预热（后台任务）
    task = asyncio.create_task(warmer.start_background_warmup(interval=3600))

    # 按需预热
    await warmer.warmup("poi")
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from backend.errors import CityFlowException, ErrorCode

logger = logging.getLogger(__name__)

# 预热任务类型：无参数异步可调用
WarmupTask = Callable[[], Coroutine[Any, Any, None]]


class CacheWarmerError(CityFlowException):
    """缓存预热异常。"""

    def __init__(
        self, message: str = "缓存预热失败", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            details=details,
        )


@dataclass
class WarmupResult:
    """单次预热执行结果。"""

    task_name: str
    success: bool
    duration_ms: float
    error: str | None = None


@dataclass
class WarmupReport:
    """预热汇总报告。"""

    results: list[WarmupResult] = field(default_factory=list)
    total_duration_ms: float = 0.0

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.success)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": len(self.results),
            "success": self.success_count,
            "failure": self.failure_count,
            "duration_ms": round(self.total_duration_ms, 1),
            "tasks": [
                {
                    "name": r.task_name,
                    "success": r.success,
                    "duration_ms": round(r.duration_ms, 1),
                    "error": r.error,
                }
                for r in self.results
            ],
        }


class CacheWarmer:
    """缓存预热器，管理所有预热任务的注册与执行。

    支持三种预热策略：
    1. 启动时预热 -- 调用 ``warmup_all()`` 执行全部任务
    2. 定时预热 -- 调用 ``start_background_warmup()`` 启动后台周期刷新
    3. 按需预热 -- 调用 ``warmup(name)`` 执行单个任务

    线程安全性：内部使用 asyncio.Lock 保证并发调用安全。
    """

    def __init__(self) -> None:
        self._tasks: dict[str, WarmupTask] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._background_task: asyncio.Task[None] | None = None
        self._last_report: WarmupReport | None = None

    def register(self, name: str, task: WarmupTask) -> None:
        """注册一个预热任务。

        Args:
            name: 任务名称，用于按需预热和日志标识
            task: 异步可调用对象，无参数

        Raises:
            ValueError: name 为空或已存在
        """
        if not name:
            raise ValueError("task name must not be empty")
        if name in self._tasks:
            raise ValueError(f"task '{name}' already registered")
        self._tasks[name] = task
        logger.debug("注册预热任务: %s", name)

    def unregister(self, name: str) -> None:
        """注销一个预热任务。不存在时静默忽略。"""
        self._tasks.pop(name, None)

    @property
    def task_names(self) -> list[str]:
        """返回所有已注册的任务名称。"""
        return list(self._tasks.keys())

    @property
    def last_report(self) -> WarmupReport | None:
        """最近一次预热报告。"""
        return self._last_report

    async def warmup(self, name: str) -> WarmupResult:
        """执行单个预热任务（按需预热）。

        Args:
            name: 已注册的任务名称

        Returns:
            WarmupResult 执行结果

        Raises:
            CacheWarmerError: 任务未注册
        """
        if name not in self._tasks:
            raise CacheWarmerError(
                message=f"预热任务 '{name}' 未注册",
                details={"available": self.task_names},
            )

        async with self._lock:
            return await self._run_task(name, self._tasks[name])

    async def warmup_all(self) -> WarmupReport:
        """执行全部预热任务（启动时预热 / 手动触发）。

        任务按注册顺序串行执行，单个任务失败不影响后续任务。

        Returns:
            WarmupReport 汇总报告
        """
        async with self._lock:
            start = time.monotonic()
            report = WarmupReport()

            logger.info("开始缓存预热 (%d 个任务)...", len(self._tasks))

            for name, task in self._tasks.items():
                result = await self._run_task(name, task)
                report.results.append(result)

            report.total_duration_ms = (time.monotonic() - start) * 1000
            self._last_report = report

            logger.info(
                "缓存预热完成: %d 成功, %d 失败, 耗时 %.0fms",
                report.success_count,
                report.failure_count,
                report.total_duration_ms,
            )

            return report

    async def start_background_warmup(self, interval: int = 3600) -> None:
        """启动后台定时预热循环。

        每隔 ``interval`` 秒执行一次全部预热任务。
        重复调用不会创建多个后台任务。

        Args:
            interval: 刷新间隔秒数，默认 3600（1 小时）
        """
        if self._running:
            logger.warning("后台预热已在运行，跳过重复启动")
            return

        self._running = True
        logger.info("启动后台缓存预热，间隔 %ds", interval)

        while self._running:
            try:
                await self.warmup_all()
            except Exception:
                logger.exception("后台缓存预热异常")

            if not self._running:
                break
            await asyncio.sleep(interval)

    def stop(self) -> None:
        """停止后台预热循环。"""
        if not self._running:
            return
        self._running = False
        if self._background_task is not None:
            self._background_task.cancel()
            self._background_task = None
        logger.info("后台缓存预热已停止")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _run_task(self, name: str, task: WarmupTask) -> WarmupResult:
        """执行单个任务并捕获异常。"""
        start = time.monotonic()
        try:
            await task()
            duration = (time.monotonic() - start) * 1000
            logger.info("预热 [%s] 成功 (%.0fms)", name, duration)
            return WarmupResult(task_name=name, success=True, duration_ms=duration)
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            logger.error("预热 [%s] 失败 (%.0fms): %s", name, duration, exc)
            return WarmupResult(
                task_name=name,
                success=False,
                duration_ms=duration,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_warmer: CacheWarmer | None = None


def get_cache_warmer() -> CacheWarmer:
    """获取全局缓存预热器单例。首次调用时自动注册默认任务。"""
    global _warmer
    if _warmer is None:
        _warmer = CacheWarmer()
        _register_default_tasks(_warmer)
    return _warmer


def reset_cache_warmer() -> None:
    """重置全局预热器（用于测试）。"""
    global _warmer
    if _warmer is not None:
        _warmer.stop()
    _warmer = None


# ---------------------------------------------------------------------------
# 默认预热任务
# ---------------------------------------------------------------------------


async def warmup_poi_cache() -> None:
    """预热 POI 数据到多级缓存。

    加载全量 POI 数据，按城市分桶缓存，同时提取城市列表和类别列表。
    """
    from backend.services.cache import get_multilevel_cache
    from backend.services.data_service import get_data

    cache = get_multilevel_cache()
    pois = get_data("city_poi_db")
    if not pois:
        logger.warning("无 POI 数据可预热")
        return

    # 全量 POI
    await cache.set("warmup:all_pois", pois, ttl=3600)

    # 按城市分桶
    city_buckets: dict[str, list[dict[str, Any]]] = {}
    for poi in pois:
        city = poi.get("city", "")
        city_buckets.setdefault(city, []).append(poi)

    for city, city_pois in city_buckets.items():
        await cache.set(f"warmup:city:{city}", city_pois, ttl=3600)

    # 城市列表
    cities = sorted(city_buckets.keys())
    await cache.set("warmup:cities", cities, ttl=3600)

    # 类别列表
    categories = sorted({p.get("category", "") for p in pois if p.get("category")})
    await cache.set("warmup:categories", categories, ttl=3600)

    logger.info(
        "POI 缓存预热: %d 条, %d 城市, %d 类别",
        len(pois),
        len(cities),
        len(categories),
    )


async def warmup_city_category_cache() -> None:
    """预热城市-类别交叉索引到多级缓存。

    构建 city:category -> [pois] 的映射，加速按城市+类别筛选。
    """
    from backend.services.cache import get_multilevel_cache
    from backend.services.data_service import get_data

    cache = get_multilevel_cache()
    pois = get_data("city_poi_db")
    if not pois:
        return

    # city:category -> [pois]
    index: dict[str, list[dict[str, Any]]] = {}
    for poi in pois:
        city = poi.get("city", "")
        category = poi.get("category", "")
        key = f"{city}:{category}"
        index.setdefault(key, []).append(poi)

    for key, items in index.items():
        await cache.set(f"warmup:idx:{key}", items, ttl=3600)

    logger.info("城市-类别索引预热: %d 个组合", len(index))


async def warmup_other_datasets() -> None:
    """预热非 POI 的其他数据集。"""
    from backend.services.cache import get_multilevel_cache
    from backend.services.data_service import get_data, get_datasets

    cache = get_multilevel_cache()
    dataset_names = get_datasets()

    count = 0
    for ds_name in dataset_names:
        if ds_name == "city_poi_db":
            continue  # POI 已单独预热
        data = get_data(ds_name)
        if data:
            await cache.set(f"warmup:dataset:{ds_name}", data, ttl=3600)
            count += 1

    logger.info("其他数据集预热: %d 个", count)


def _register_default_tasks(warmer: CacheWarmer) -> None:
    """注册默认预热任务（按依赖顺序）。"""
    warmer.register("poi", warmup_poi_cache)
    warmer.register("city_category_index", warmup_city_category_cache)
    warmer.register("other_datasets", warmup_other_datasets)
