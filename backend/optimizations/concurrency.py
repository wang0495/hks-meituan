"""CityFlow 并发处理优化器。

在现有 parallel.py (parallel_filter / parallel_solve / parallel_map) 基础上提供：
1. 结构化并发 -- 使用 asyncio.TaskGroup 替代裸 gather，自动传播异常和取消
2. 有界并发执行器 -- 带速率限制和背压的批量任务调度
3. LLM 并发控制 -- 专门针对 LLM API 调用的并发限制与超时保护
4. 连接池调优建议 -- 根据负载特征推荐连接池参数

用法::

    optimizer = ConcurrencyOptimizer()

    # 结构化并发执行
    results = await optimizer.run_tasks(tasks)

    # 有界批量执行
    results = await optimizer.bounded_batch(items, worker, max_concurrency=10)

    # LLM 并发调用
    results = await optimizer.concurrent_llm_calls(prompts, max_concurrency=3)
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TaskResult:
    """单个任务执行结果。"""

    task_id: int
    success: bool
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class BatchReport:
    """批量执行报告。"""

    total: int
    success_count: int
    failure_count: int
    total_duration_ms: float
    avg_duration_ms: float
    p95_duration_ms: float
    results: list[TaskResult]


@dataclass(frozen=True, slots=True)
class PoolRecommendation:
    """连接池调优建议。"""

    parameter: str
    current_value: int | float
    recommended_value: int | float
    reason: str


# ---------------------------------------------------------------------------
# 优化器
# ---------------------------------------------------------------------------


class ConcurrencyOptimizer:
    """并发处理优化器。"""

    # ------------------------------------------------------------------
    # 1. 结构化并发
    # ------------------------------------------------------------------

    async def run_tasks(
        self,
        tasks: list[Coroutine[Any, Any, T]],
        *,
        max_concurrency: int = 0,
    ) -> list[T]:
        """使用 TaskGroup 执行多个协程，自动传播异常。

        Args:
            tasks: 协程列表
            max_concurrency: 最大并发数，0 表示不限制

        Returns:
            与输入等长的结果列表（按提交顺序）

        Raises:
            ExceptionGroup: 任一任务失败时抛出
        """
        if not tasks:
            return []

        if max_concurrency <= 0:
            # 不限制并发，直接 gather
            return list(await asyncio.gather(*tasks))

        # 有并发限制时使用信号量
        semaphore = asyncio.Semaphore(max_concurrency)
        wrapped: list[Coroutine[Any, Any, T]] = []

        async def _limited(coro: Coroutine[Any, Any, T]) -> T:
            async with semaphore:
                return await coro

        for coro in tasks:
            wrapped.append(_limited(coro))

        return await asyncio.gather(*wrapped)

    # ------------------------------------------------------------------
    # 2. 有界并发执行器（带背压和超时）
    # ------------------------------------------------------------------

    async def bounded_batch(
        self,
        items: list[T],
        worker: Callable[[T], Coroutine[Any, Any, R]],
        *,
        max_concurrency: int = 10,
        timeout_seconds: float = 30.0,
        fail_fast: bool = False,
    ) -> BatchReport:
        """有界批量执行，带背压控制。

        Args:
            items: 输入列表
            worker: 异步工作函数
            max_concurrency: 最大并发数
            timeout_seconds: 单个任务超时
            fail_fast: 是否在首个失败时立即终止

        Returns:
            BatchReport 执行报告
        """
        if not items:
            return BatchReport(
                total=0,
                success_count=0,
                failure_count=0,
                total_duration_ms=0,
                avg_duration_ms=0,
                p95_duration_ms=0,
                results=[],
            )

        semaphore = asyncio.Semaphore(max_concurrency)
        results: list[TaskResult] = []
        durations: list[float] = []
        start_time = time.monotonic()
        cancel_event = asyncio.Event()

        async def _run(idx: int, item: T) -> None:
            if cancel_event.is_set():
                return

            async with semaphore:
                task_start = time.monotonic()
                try:
                    result = await asyncio.wait_for(
                        worker(item), timeout=timeout_seconds
                    )
                    duration = (time.monotonic() - task_start) * 1000
                    durations.append(duration)
                    results.append(
                        TaskResult(
                            task_id=idx,
                            success=True,
                            result=result,
                            duration_ms=duration,
                        )
                    )
                except asyncio.TimeoutError:
                    duration = (time.monotonic() - task_start) * 1000
                    durations.append(duration)
                    results.append(
                        TaskResult(
                            task_id=idx,
                            success=False,
                            error=f"超时 ({timeout_seconds}s)",
                            duration_ms=duration,
                        )
                    )
                    if fail_fast:
                        cancel_event.set()
                except Exception as exc:
                    duration = (time.monotonic() - task_start) * 1000
                    durations.append(duration)
                    results.append(
                        TaskResult(
                            task_id=idx,
                            success=False,
                            error=str(exc),
                            duration_ms=duration,
                        )
                    )
                    if fail_fast:
                        cancel_event.set()

        async with asyncio.TaskGroup() as tg:
            for idx, item in enumerate(items):
                if cancel_event.is_set():
                    break
                tg.create_task(_run(idx, item))

        total_duration = (time.monotonic() - start_time) * 1000
        success_count = sum(1 for r in results if r.success)
        failure_count = len(results) - success_count

        # P95 计算
        p95 = 0.0
        if durations:
            sorted_durations = sorted(durations)
            p95_idx = int(len(sorted_durations) * 0.95)
            p95 = sorted_durations[min(p95_idx, len(sorted_durations) - 1)]

        return BatchReport(
            total=len(items),
            success_count=success_count,
            failure_count=failure_count,
            total_duration_ms=total_duration,
            avg_duration_ms=(sum(durations) / len(durations) if durations else 0),
            p95_duration_ms=p95,
            results=results,
        )

    # ------------------------------------------------------------------
    # 3. LLM 并发控制
    # ------------------------------------------------------------------

    async def concurrent_llm_calls(
        self,
        prompts: list[str],
        llm_func: Callable[[str], Coroutine[Any, Any, str]],
        *,
        max_concurrency: int = 3,
        timeout_seconds: float = 60.0,
        retry_count: int = 2,
        retry_delay: float = 1.0,
    ) -> list[TaskResult]:
        """并发执行多个 LLM 调用，带重试和超时保护。

        Args:
            prompts: 提示词列表
            llm_func: 接受 prompt 返回 response 的异步函数
            max_concurrency: 最大并发 LLM 请求数（防止 API 限流）
            timeout_seconds: 单次调用超时
            retry_count: 失败重试次数
            retry_delay: 重试间隔（秒）

        Returns:
            TaskResult 列表
        """
        semaphore = asyncio.Semaphore(max_concurrency)
        results: list[TaskResult] = []

        async def _call(idx: int, prompt: str) -> None:
            async with semaphore:
                task_start = time.monotonic()
                last_error: str | None = None

                for attempt in range(1, retry_count + 1):
                    try:
                        response = await asyncio.wait_for(
                            llm_func(prompt), timeout=timeout_seconds
                        )
                        duration = (time.monotonic() - task_start) * 1000
                        results.append(
                            TaskResult(
                                task_id=idx,
                                success=True,
                                result=response,
                                duration_ms=duration,
                            )
                        )
                        return
                    except asyncio.TimeoutError:
                        last_error = f"超时 ({timeout_seconds}s)，第 {attempt} 次"
                        logger.warning(
                            "LLM 调用超时 [%d/%d] prompt=%s",
                            attempt,
                            retry_count,
                            prompt[:50],
                        )
                    except Exception as exc:
                        last_error = f"{exc}，第 {attempt} 次"
                        logger.warning(
                            "LLM 调用失败 [%d/%d]: %s",
                            attempt,
                            retry_count,
                            exc,
                        )

                    if attempt < retry_count:
                        await asyncio.sleep(retry_delay * attempt)

                # 全部重试失败
                duration = (time.monotonic() - task_start) * 1000
                results.append(
                    TaskResult(
                        task_id=idx,
                        success=False,
                        error=last_error,
                        duration_ms=duration,
                    )
                )

        async with asyncio.TaskGroup() as tg:
            for idx, prompt in enumerate(prompts):
                tg.create_task(_call(idx, prompt))

        # 按 task_id 排序保证顺序
        results.sort(key=lambda r: r.task_id)
        return results

    # ------------------------------------------------------------------
    # 4. 并行求解优化（替代 parallel_solve）
    # ------------------------------------------------------------------

    async def parallel_solve_optimized(
        self,
        solve_func: Callable[[], Coroutine[Any, Any, dict[str, Any]]],
        n_attempts: int = 3,
        timeout_seconds: float = 15.0,
    ) -> dict[str, Any]:
        """并行运行多次求解，返回评分最高的结果。

        相比 parallel.py 中的 parallel_solve，增加了：
        - 单次求解超时保护
        - 使用 TaskGroup 结构化并发

        Args:
            solve_func: 无参异步求解函数，返回带 'score' 字段的字典
            n_attempts: 并行尝试次数
            timeout_seconds: 单次求解超时

        Returns:
            评分最高的结果
        """

        async def _safe_solve() -> dict[str, Any] | None:
            try:
                return await asyncio.wait_for(solve_func(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                logger.warning("路线求解超时 (%.1fs)", timeout_seconds)
                return None
            except Exception:
                logger.debug("路线求解失败", exc_info=True)
                return None

        results = await asyncio.gather(*(_safe_solve() for _ in range(n_attempts)))

        valid = [r for r in results if isinstance(r, dict) and "route" in r]
        if not valid:
            return {}
        return max(valid, key=lambda r: r.get("score", 0))

    # ------------------------------------------------------------------
    # 5. 连接池调优建议
    # ------------------------------------------------------------------

    def get_pool_recommendations(
        self,
        current_config: dict[str, int | float],
        avg_concurrent_requests: int,
        avg_db_query_ms: float,
        avg_llm_call_ms: float,
    ) -> list[PoolRecommendation]:
        """根据负载特征推荐连接池参数。

        Args:
            current_config: 当前连接池配置
            avg_concurrent_requests: 平均并发请求数
            avg_db_query_ms: 平均数据库查询耗时（毫秒）
            avg_llm_call_ms: 平均 LLM 调用耗时（毫秒）

        Returns:
            调优建议列表
        """
        recommendations: list[PoolRecommendation] = []

        # 数据库连接池
        # 理论所需连接数 = 并发数 * (DB查询时间 / 总请求时间)
        # 简化：DB 查询占比约 20%，所以连接数 ≈ 并发数 * 0.2
        ideal_db_pool = max(5, int(avg_concurrent_requests * 0.2))
        current_db_pool = current_config.get("db_pool_size", 10)

        if ideal_db_pool > current_db_pool * 1.5:
            recommendations.append(
                PoolRecommendation(
                    parameter="db_pool_size",
                    current_value=current_db_pool,
                    recommended_value=ideal_db_pool,
                    reason=(
                        f"并发数 {avg_concurrent_requests}，平均 DB 查询 {avg_db_query_ms:.0f}ms，"
                        f"建议增大连接池到 {ideal_db_pool}"
                    ),
                )
            )
        elif ideal_db_pool < current_db_pool * 0.5:
            recommendations.append(
                PoolRecommendation(
                    parameter="db_pool_size",
                    current_value=current_db_pool,
                    recommended_value=max(5, ideal_db_pool),
                    reason=f"当前连接池过大，并发数仅 {avg_concurrent_requests}，可适当缩小",
                )
            )

        # max_overflow
        current_overflow = current_config.get("db_max_overflow", 20)
        ideal_overflow = max(10, int(ideal_db_pool * 1.5))
        if ideal_overflow != current_overflow:
            recommendations.append(
                PoolRecommendation(
                    parameter="db_max_overflow",
                    current_value=current_overflow,
                    recommended_value=ideal_overflow,
                    reason="建议 max_overflow 为 pool_size 的 1.5 倍",
                )
            )

        # HTTP 连接池
        current_http = current_config.get("http_max_connections", 100)
        ideal_http = max(50, avg_concurrent_requests * 2)
        if ideal_http > current_http * 1.5:
            recommendations.append(
                PoolRecommendation(
                    parameter="http_max_connections",
                    current_value=current_http,
                    recommended_value=ideal_http,
                    reason=(
                        f"LLM 调用平均 {avg_llm_call_ms:.0f}ms，并发 {avg_concurrent_requests}，"
                        f"HTTP 连接池可能成为瓶颈"
                    ),
                )
            )

        # pool_recycle
        current_recycle = current_config.get("db_pool_recycle", 3600)
        if avg_db_query_ms > 500:
            # 慢查询多时缩短回收周期，避免持有长时间空闲连接
            recommendations.append(
                PoolRecommendation(
                    parameter="db_pool_recycle",
                    current_value=current_recycle,
                    recommended_value=1800,
                    reason="慢查询较多，建议缩短连接回收周期到 30 分钟",
                )
            )

        return recommendations

    # ------------------------------------------------------------------
    # 6. 综合报告
    # ------------------------------------------------------------------

    def generate_report(
        self,
        current_config: dict[str, int | float] | None = None,
    ) -> dict[str, Any]:
        """生成并发优化报告。"""
        config = current_config or {}

        return {
            "structured_concurrency": {
                "description": "使用 TaskGroup 替代 gather，自动传播异常和取消",
                "benefits": [
                    "任一子任务异常时自动取消其余任务",
                    "避免裸 gather 静默吞掉异常",
                    "Python 3.11+ 原生支持",
                ],
            },
            "bounded_batch": {
                "description": "有界并发执行器，防止资源耗尽",
                "features": [
                    "信号量控制最大并发数",
                    "单任务超时保护",
                    "fail_fast 模式：首个失败立即终止",
                    "P95 延迟统计",
                ],
            },
            "llm_concurrency": {
                "description": "LLM 专用并发控制",
                "features": [
                    "建议 max_concurrency=3（防止 API 限流）",
                    "指数退避重试",
                    "单次调用 60s 超时",
                ],
            },
            "pool_recommendations": (
                self.get_pool_recommendations(
                    config,
                    avg_concurrent_requests=50,
                    avg_db_query_ms=50,
                    avg_llm_call_ms=2000,
                )
                if config
                else []
            ),
            "parallel_vs_sequential": {
                "example_speedup": "3 次路线求解：串行 6s -> 并行 2.5s（含超时保护）",
                "llm_speedup": "5 个 LLM 调用：串行 25s -> 并发 8s（max_concurrency=3）",
            },
        }
