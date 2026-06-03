"""CityFlow 中间件管道。

提供可编程的中间件链式执行引擎，支持：
- 动态添加/移除中间件
- 条件中间件（按请求特征决定是否执行）
- 每个中间件的性能统计（请求数、耗时、错误率、分位数）
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import Request, Response

logger = logging.getLogger(__name__)

# 分位数计算保留最近 N 条采样，避免内存无限增长
_MAX_LATENCY_SAMPLES = 1000


class MiddlewareHandler(Protocol):
    """中间件处理函数签名。"""

    async def __call__(self, request: Request, call_next: Callable[..., Any]) -> Response: ...


@dataclass
class MiddlewareStats:
    """单个中间件的运行统计。"""

    count: int = 0
    total_time: float = 0.0
    errors: int = 0
    latency_samples: deque[float] = field(
        default_factory=lambda: deque(maxlen=_MAX_LATENCY_SAMPLES)
    )

    @property
    def avg_time(self) -> float:
        """平均耗时（秒）。"""
        return self.total_time / self.count if self.count else 0.0

    @property
    def error_rate(self) -> float:
        """错误率。"""
        return self.errors / self.count if self.count else 0.0

    def percentile(self, p: float) -> float:
        """计算第 p 分位数（p 取 0~100）。"""
        if not self.latency_samples:
            return 0.0
        sorted_vals = sorted(self.latency_samples)
        idx = int(len(sorted_vals) * p / 100)
        idx = min(idx, len(sorted_vals) - 1)
        return sorted_vals[idx]

    def to_dict(self) -> dict[str, Any]:
        """导出为字典。"""
        return {
            "count": self.count,
            "total_time": round(self.total_time, 4),
            "avg_time": round(self.avg_time, 4),
            "errors": self.errors,
            "error_rate": round(self.error_rate, 4),
            "p50": round(self.percentile(50), 4),
            "p95": round(self.percentile(95), 4),
            "p99": round(self.percentile(99), 4),
        }


@dataclass
class _MiddlewareEntry:
    """管道中的一个中间件条目。"""

    name: str
    handler: MiddlewareHandler


class MiddlewarePipeline:
    """可编程中间件管道。

    中间件按添加顺序从外到内执行（即先添加的先执行）。
    执行模型与 Starlette 的 ``add_middleware`` 一致：后添加的中间件
    包裹先添加的中间件，形成洋葱模型。

    用法::

        pipeline = MiddlewarePipeline()
        pipeline.add(my_auth_middleware, name="auth")
        pipeline.add(my_logging_middleware, name="logging")

        # 在 FastAPI 中使用
        @app.middleware("http")
        async def pipeline_dispatch(request: Request, call_next):
            return await pipeline.execute(request, call_next)
    """

    def __init__(self) -> None:
        self._middlewares: list[_MiddlewareEntry] = []
        self._stats: dict[str, MiddlewareStats] = {}

    # ------------------------------------------------------------------
    # 管道管理
    # ------------------------------------------------------------------

    def add(
        self,
        middleware: MiddlewareHandler,
        name: str | None = None,
    ) -> MiddlewarePipeline:
        """添加中间件到管道末尾。

        Args:
            middleware: 中间件处理函数，签名为 ``(request, call_next) -> Response``。
            name: 中间件名称（用于统计展示），默认使用函数名。

        Returns:
            self，支持链式调用。
        """
        entry = _MiddlewareEntry(
            name=name or getattr(middleware, "__name__", "anonymous"),
            handler=middleware,
        )
        self._middlewares.append(entry)
        self._stats[entry.name] = MiddlewareStats()
        return self

    def remove(self, name: str) -> bool:
        """按名称移除中间件。

        Args:
            name: 要移除的中间件名称。

        Returns:
            是否成功移除。
        """
        for i, entry in enumerate(self._middlewares):
            if entry.name == name:
                self._middlewares.pop(i)
                self._stats.pop(name, None)
                return True
        return False

    @property
    def names(self) -> list[str]:
        """当前管道中所有中间件的名称（按执行顺序）。"""
        return [entry.name for entry in self._middlewares]

    # ------------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------------

    async def execute(
        self,
        request: Request,
        call_next: Callable[..., Any],
    ) -> Response:
        """执行中间件管道。

        中间件从后向前组装，从前往后执行，形成洋葱模型。
        每个中间件的签名必须为 ``(request, call_next) -> Response``。

        Args:
            request: 当前 HTTP 请求。
            call_next: 最终处理函数（通常是路由处理器）。

        Returns:
            HTTP 响应。
        """

        async def terminal(request: Request) -> Response:
            return await call_next(request)

        handler: Callable[..., Any] = terminal

        # 从后向前包裹，使得第一个添加的中间件最先执行
        for entry in reversed(self._middlewares):
            # 使用默认参数捕获当前循环变量，避免闭包晚绑定问题
            current_handler = handler
            current_entry = entry

            async def wrapped(
                request: Request,
                _handler: Callable[..., Any] = current_handler,
                _entry: _MiddlewareEntry = current_entry,
            ) -> Response:
                start = time.perf_counter()
                try:
                    response = await _entry.handler(request, _handler)
                    duration = time.perf_counter() - start
                    self._record_stats(_entry.name, duration, success=True)
                    return response
                except Exception as e:
                    duration = time.perf_counter() - start
                    self._record_stats(_entry.name, duration, success=False)
                    logger.error("middleware pipeline error: %s", e)
                    raise

            handler = wrapped

        return await handler(request)

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def _record_stats(self, name: str, duration: float, success: bool) -> None:
        """记录中间件执行统计。"""
        stats = self._stats[name]
        stats.count += 1
        stats.total_time += duration
        stats.latency_samples.append(duration)
        if not success:
            stats.errors += 1

    def get_stats(self, name: str) -> dict[str, Any] | None:
        """获取单个中间件的统计信息。"""
        stats = self._stats.get(name)
        return stats.to_dict() if stats else None

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """获取所有中间件的统计信息。"""
        return {name: stats.to_dict() for name, stats in self._stats.items()}

    def reset_stats(self) -> None:
        """重置所有统计信息。"""
        for stats in self._stats.values():
            stats.count = 0
            stats.total_time = 0.0
            stats.errors = 0
            stats.latency_samples.clear()

    # ------------------------------------------------------------------
    # 便捷方法
    # ------------------------------------------------------------------

    def get_stats_summary(self) -> dict[str, Any]:
        """获取管道整体统计摘要。

        Returns:
            包含管道总请求数、总错误数、最慢中间件等信息的字典。
        """
        all_stats = self.get_all_stats()
        total_requests = sum(s["count"] for s in all_stats.values())
        total_errors = sum(s["errors"] for s in all_stats.values())

        slowest_name = ""
        slowest_p95 = 0.0
        for name, s in all_stats.items():
            if s["p95"] > slowest_p95:
                slowest_p95 = s["p95"]
                slowest_name = name

        return {
            "pipeline_length": len(self._middlewares),
            "middleware_order": self.names,
            "total_requests": total_requests,
            "total_errors": total_errors,
            "overall_error_rate": (
                round(total_errors / total_requests, 4) if total_requests else 0.0
            ),
            "slowest_middleware": {
                "name": slowest_name,
                "p95": slowest_p95,
            },
            "per_middleware": all_stats,
        }


class ConditionalMiddleware:
    """条件中间件包装器。

    根据请求特征决定是否执行内部中间件。
    条件函数返回 True 时执行中间件，否则直接跳过。

    用法::

        # 仅对 API 路径执行认证中间件
        auth_guard = ConditionalMiddleware(
            condition=lambda req: req.url.path.startswith("/api/"),
            middleware=auth_middleware,
        )
        pipeline.add(auth_guard, name="auth")

        # 按 HTTP 方法条件执行
        cache_mw = ConditionalMiddleware(
            condition=lambda req: req.method == "GET",
            middleware=cache_middleware,
        )
        pipeline.add(cache_mw, name="cache")
    """

    def __init__(
        self,
        condition: Callable[[Request], bool],
        middleware: MiddlewareHandler,
    ) -> None:
        self._condition = condition
        self._middleware = middleware

    async def __call__(
        self,
        request: Request,
        call_next: Callable[..., Any],
    ) -> Response:
        """根据条件决定是否执行中间件。

        Args:
            request: 当前 HTTP 请求。
            call_next: 下一个处理函数。

        Returns:
            HTTP 响应。
        """
        if self._condition(request):
            return await self._middleware(request, call_next)
        return await call_next(request)
