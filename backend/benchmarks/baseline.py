"""基准测试核心运行器。

提供同步和异步两种模式的基准测试能力，
支持并发负载模拟和详细指标采集。
"""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from backend.benchmarks.metrics import PerformanceMetrics


@dataclass(slots=True)
class BenchmarkResult:
    """单次基准测试的原始结果。"""

    durations_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    total_duration_seconds: float = 0.0

    @property
    def success_count(self) -> int:
        return len(self.durations_ms)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def total_count(self) -> int:
        return self.success_count + self.error_count


class BaselineBenchmark:
    """基准测试运行器。

    支持：
    - 单请求顺序执行（baseline 模式）
    - 并发负载模拟（concurrent 模式）

    用法::

        benchmark = BaselineBenchmark()
        result = await benchmark.run(
            func=some_async_func,
            iterations=100,
        )
        metrics = benchmark.calculate_metrics(result)
    """

    async def run(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        iterations: int = 100,
        *,
        concurrency: int = 1,
        warmup: int = 5,
    ) -> BenchmarkResult:
        """运行基准测试。

        Args:
            func: 被测异步函数，每次调用无参数。
            iterations: 正式测试轮次。
            concurrency: 并发数（1 = 顺序执行）。
            warmup: 预热轮次，不计入结果。

        Returns:
            BenchmarkResult 原始结果。
        """
        result = BenchmarkResult()

        # 预热
        for _ in range(warmup):
            try:
                await func()
            except Exception:
                pass

        overall_start = time.perf_counter()

        if concurrency <= 1:
            await self._run_sequential(func, iterations, result)
        else:
            await self._run_concurrent(func, iterations, concurrency, result)

        result.total_duration_seconds = time.perf_counter() - overall_start

        return result

    async def _run_sequential(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        iterations: int,
        result: BenchmarkResult,
    ) -> None:
        """顺序执行。"""
        for _ in range(iterations):
            start = time.perf_counter()
            try:
                await func()
                duration_ms = (time.perf_counter() - start) * 1000
                result.durations_ms.append(duration_ms)
            except Exception as exc:
                duration_ms = (time.perf_counter() - start) * 1000
                result.durations_ms.append(duration_ms)
                result.errors.append(str(exc))

    async def _run_concurrent(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        iterations: int,
        concurrency: int,
        result: BenchmarkResult,
    ) -> None:
        """并发执行。"""
        semaphore = asyncio.Semaphore(concurrency)

        async def _single_run() -> None:
            async with semaphore:
                start = time.perf_counter()
                try:
                    await func()
                    duration_ms = (time.perf_counter() - start) * 1000
                    result.durations_ms.append(duration_ms)
                except Exception as exc:
                    duration_ms = (time.perf_counter() - start) * 1000
                    result.durations_ms.append(duration_ms)
                    result.errors.append(str(exc))

        async with asyncio.TaskGroup() as tg:
            for _ in range(iterations):
                tg.create_task(_single_run())

    def calculate_metrics(self, result: BenchmarkResult) -> PerformanceMetrics:
        """将原始结果转换为聚合性能指标。

        Args:
            result: 原始基准测试结果。

        Returns:
            PerformanceMetrics 聚合指标。
        """
        durations = sorted(result.durations_ms)
        n = len(durations)

        if n == 0:
            return PerformanceMetrics(
                avg_response_time=0.0,
                p50_response_time=0.0,
                p95_response_time=0.0,
                p99_response_time=0.0,
                requests_per_second=0.0,
                error_rate=100.0,
                total_requests=result.total_count,
                successful_requests=0,
                failed_requests=result.error_count,
            )

        total_time = result.total_duration_seconds
        rps = result.total_count / total_time if total_time > 0 else 0.0
        error_rate = (
            (result.error_count / result.total_count * 100)
            if result.total_count > 0
            else 0.0
        )

        return PerformanceMetrics(
            avg_response_time=statistics.mean(durations),
            p50_response_time=durations[n // 2],
            p95_response_time=durations[int(n * 0.95)] if n >= 20 else durations[-1],
            p99_response_time=durations[int(n * 0.99)] if n >= 100 else durations[-1],
            requests_per_second=rps,
            error_rate=error_rate,
            total_requests=result.total_count,
            successful_requests=result.success_count,
            failed_requests=result.error_count,
            min_response_time=durations[0],
            max_response_time=durations[-1],
            total_duration_seconds=total_time,
        )

    async def run_full(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        iterations: int = 100,
        *,
        concurrency: int = 1,
        warmup: int = 5,
    ) -> PerformanceMetrics:
        """运行基准测试并直接返回聚合指标（便捷方法）。

        Args:
            func: 被测异步函数。
            iterations: 正式测试轮次。
            concurrency: 并发数。
            warmup: 预热轮次。

        Returns:
            PerformanceMetrics 聚合指标。
        """
        result = await self.run(
            func, iterations, concurrency=concurrency, warmup=warmup
        )
        return self.calculate_metrics(result)
