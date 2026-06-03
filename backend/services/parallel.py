"""CityFlow 异步并行处理模块。

提供并行过滤、并行求解等并发工具。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# 并行过滤
# ---------------------------------------------------------------------------


async def parallel_filter[T](
    items: list[T],
    filter_func: Callable[[T], Coroutine[Any, Any, bool]],
    max_workers: int = 4,
) -> list[T]:
    """并行过滤列表。

    Args:
        items: 待过滤列表
        filter_func: 异步过滤函数，返回 True 保留
        max_workers: 最大并发数

    Returns:
        过滤后的列表（保持原顺序）
    """
    semaphore = asyncio.Semaphore(max_workers)

    async def _check(item: T) -> T | None:
        async with semaphore:
            try:
                if await filter_func(item):
                    return item
            except Exception:
                logger.debug("并行过滤中某个元素检查失败", exc_info=True)
            return None

    tasks = [_check(item) for item in items]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


# ---------------------------------------------------------------------------
# 并行求解多条路线
# ---------------------------------------------------------------------------


async def parallel_solve(
    solve_func: Callable[[], Coroutine[Any, Any, dict[str, Any]]],
    n_attempts: int = 3,
) -> dict[str, Any]:
    """并行运行多次求解，返回评分最高的结果。

    Args:
        solve_func: 无参异步求解函数，返回带 'score' 字段的字典
        n_attempts: 并行尝试次数

    Returns:
        评分最高的结果
    """
    tasks = [solve_func() for _ in range(n_attempts)]
    routes = await asyncio.gather(*tasks, return_exceptions=True)

    valid = [r for r in routes if isinstance(r, dict) and "route" in r]
    if not valid:
        return {}
    return max(valid, key=lambda r: r.get("score", 0))


# ---------------------------------------------------------------------------
# 并行批量执行
# ---------------------------------------------------------------------------


async def parallel_map[T](
    items: list[T],
    func: Callable[[T], Coroutine[Any, Any, Any]],
    max_workers: int = 4,
) -> list[Any]:
    """并行映射函数到列表，保持顺序。

    Args:
        items: 输入列表
        func: 异步映射函数
        max_workers: 最大并发数

    Returns:
        与输入等长的结果列表
    """
    semaphore = asyncio.Semaphore(max_workers)

    async def _run(item: T) -> Any:
        async with semaphore:
            return await func(item)

    return list(await asyncio.gather(*(_run(item) for item in items)))


# ---------------------------------------------------------------------------
# 超时包装
# ---------------------------------------------------------------------------


async def with_timeout[T](
    coro: Coroutine[Any, Any, T],
    timeout_seconds: float = 10.0,
    fallback: T | None = None,
) -> T | None:
    """给协程加超时保护。

    Args:
        coro: 待执行协程
        timeout_seconds: 超时秒数
        fallback: 超时时返回的默认值

    Returns:
        协程结果或 fallback
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except TimeoutError:
        logger.warning("操作超时 (%.1fs)，返回兜底值", timeout_seconds)
        return fallback
