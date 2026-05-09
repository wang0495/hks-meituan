"""CityFlow 性能分析器。

提供函数耗时统计功能，包括装饰器和手动记录两种方式。
支持全局统计与慢函数告警。
"""

from __future__ import annotations

import functools
import logging
import time
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ProfilerStats:
    """单个函数的统计数据。"""

    __slots__ = ("count", "total", "min", "max")

    def __init__(self) -> None:
        self.count: int = 0
        self.total: float = 0.0
        self.min: float = float("inf")
        self.max: float = 0.0

    def record(self, duration: float) -> None:
        self.count += 1
        self.total += duration
        if duration < self.min:
            self.min = duration
        if duration > self.max:
            self.max = duration

    @property
    def avg(self) -> float:
        return self.total / self.count if self.count > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "total": round(self.total, 6),
            "avg": round(self.avg, 6),
            "min": round(self.min, 6),
            "max": round(self.max, 6),
        }


class Profiler:
    """性能分析器。

    用法::

        profiler = get_profiler()

        # 方式 1: 装饰器
        @profile("my_func")
        async def my_func():
            ...

        # 方式 2: 手动记录
        start = time.time()
        ...
        profiler.record("my_func", time.time() - start)

        # 查看统计
        print(profiler.get_stats())
    """

    def __init__(self, slow_threshold: float = 1.0) -> None:
        self._stats: dict[str, ProfilerStats] = defaultdict(ProfilerStats)
        self._enabled: bool = True
        self._slow_threshold: float = slow_threshold

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def set_slow_threshold(self, seconds: float) -> None:
        """设置慢函数告警阈值（秒）。"""
        self._slow_threshold = seconds

    def record(self, name: str, duration: float) -> None:
        """记录一次函数耗时。"""
        if self._enabled:
            self._stats[name].record(duration)

    def get_stats(self) -> dict[str, dict[str, Any]]:
        """获取所有函数的统计数据。"""
        return {name: stats.to_dict() for name, stats in self._stats.items()}

    def get_slow_functions(self) -> list[dict[str, Any]]:
        """获取超过慢阈值的函数列表。"""
        result: list[dict[str, Any]] = []
        for name, stats in self._stats.items():
            if stats.max > self._slow_threshold:
                d = stats.to_dict()
                d["name"] = name
                result.append(d)
        result.sort(key=lambda x: x["max"], reverse=True)
        return result

    def reset(self) -> None:
        """重置所有统计数据。"""
        self._stats.clear()

    def log_summary(self) -> None:
        """以日志形式输出统计摘要。"""
        if not self._stats:
            logger.info("Profiler: 无统计数据")
            return

        sorted_stats = sorted(
            self._stats.items(),
            key=lambda x: x[1].total,
            reverse=True,
        )
        lines = [
            "Profiler Summary:",
            f"{'Function':<40} {'Count':>6} {'Total':>10} {'Avg':>10} {'Max':>10}",
        ]
        lines.append("-" * 82)
        for name, stats in sorted_stats:
            lines.append(
                f"{name:<40} {stats.count:>6} {stats.total:>10.4f}s {stats.avg:>10.4f}s {stats.max:>10.4f}s"
            )
        logger.info("\n".join(lines))


# ---------------------------------------------------------------------------
# 全局实例
# ---------------------------------------------------------------------------

_profiler = Profiler()


def get_profiler() -> Profiler:
    """获取全局性能分析器实例。"""
    return _profiler


def profile(
    name: str | None = None, *, slow_threshold: float | None = None
) -> Callable:
    """性能分析装饰器（异步函数）。

    用法::

        @profile()
        async def my_func():
            ...

        @profile("custom_name")
        async def my_func():
            ...

    Args:
        name: 自定义统计名称，默认使用函数名。
        slow_threshold: 覆盖全局慢函数阈值（秒），仅对本次调用生效。
    """

    def decorator(func: Callable) -> Callable:
        func_name = name or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                _profiler.record(func_name, duration)

                threshold = (
                    slow_threshold
                    if slow_threshold is not None
                    else _profiler._slow_threshold
                )
                if duration > threshold:
                    logger.warning("慢函数: %s - %.3fs", func_name, duration)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                _profiler.record(func_name, duration)

                threshold = (
                    slow_threshold
                    if slow_threshold is not None
                    else _profiler._slow_threshold
                )
                if duration > threshold:
                    logger.warning("慢函数: %s - %.3fs", func_name, duration)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
