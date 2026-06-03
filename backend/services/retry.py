"""CityFlow 重试机制模块。

提供指数退避重试装饰器，支持：
- 可配置最大重试次数、初始延迟、退避倍数
- 可配置触发重试的异常类型
- 可配置最大延迟上限（防止退避时间过长）
- 同步/异步函数通用
- 每次重试前可执行自定义回调

用法：
    @retry(max_retries=3, delay=1.0, backoff=2.0)
    async def call_api(url: str) -> dict:
        ...

    # 只对特定异常重试
    @retry(max_retries=2, exceptions=(TimeoutError, ConnectionError))
    async def call_external_service():
        ...
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

__all__ = ["RetryExhaustedError", "retry"]

F = TypeVar("F", bound=Callable[..., Any])


class RetryExhaustedError(Exception):
    """所有重试用尽后抛出，保留最后一次异常。"""

    def __init__(
        self,
        message: str,
        last_exception: BaseException | None = None,
        attempts: int = 0,
    ) -> None:
        self.last_exception = last_exception
        self.attempts = attempts
        super().__init__(message)


def retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: type[BaseException] | tuple[type[BaseException], ...] = Exception,
    on_retry: Callable[[int, BaseException], None] | None = None,
) -> Callable[[F], F]:
    """指数退避重试装饰器。

    Args:
        max_retries: 最大重试次数（不含首次调用）。0 表示不重试。
        delay: 首次重试前的等待秒数。
        backoff: 每次重试的延迟倍数。
        max_delay: 延迟上限秒数，防止退避过长。
        jitter: 是否添加随机抖动（防止雪崩）。
        exceptions: 触发重试的异常类型。
        on_retry: 重试前的回调函数，接收 (attempt_number, exception)。

    Returns:
        装饰器。

    Example::

        @retry(max_retries=2, delay=0.5, exceptions=(TimeoutError,))
        async def fetch_data(url: str) -> bytes:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    return await resp.read()
    """

    def _calc_delay(attempt: int) -> float:
        """计算第 attempt 次重试的等待时间。"""
        d = delay * (backoff**attempt)
        d = min(d, max_delay)
        if jitter:
            d = d * (0.5 + random.random())
        return d

    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)  # type: ignore[misc]
                except exceptions as e:
                    last_exc = e

                    if attempt < max_retries:
                        wait = _calc_delay(attempt)
                        logger.warning(
                            "[重试] %s 第%d次失败，%.1fs后第%d次重试: %s: %s",
                            func.__name__,
                            attempt + 1,
                            wait,
                            attempt + 2,
                            type(e).__name__,
                            e,
                        )
                        if on_retry:
                            try:
                                on_retry(attempt + 1, e)
                            except Exception:
                                logger.debug("on_retry回调异常", exc_info=True)
                        await asyncio.sleep(wait)
                    else:
                        logger.error(
                            "[重试] %s 重试%d次后仍然失败: %s: %s",
                            func.__name__,
                            max_retries,
                            type(e).__name__,
                            e,
                        )

            raise RetryExhaustedError(
                message=f"{func.__name__} 在{max_retries + 1}次尝试后仍然失败",
                last_exception=last_exc,
                attempts=max_retries + 1,
            )

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            import time as _time

            last_exc: BaseException | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e

                    if attempt < max_retries:
                        wait = _calc_delay(attempt)
                        logger.warning(
                            "[重试] %s 第%d次失败，%.1fs后第%d次重试: %s: %s",
                            func.__name__,
                            attempt + 1,
                            wait,
                            attempt + 2,
                            type(e).__name__,
                            e,
                        )
                        if on_retry:
                            try:
                                on_retry(attempt + 1, e)
                            except Exception:
                                logger.debug("on_retry回调异常", exc_info=True)
                        _time.sleep(wait)
                    else:
                        logger.error(
                            "[重试] %s 重试%d次后仍然失败: %s: %s",
                            func.__name__,
                            max_retries,
                            type(e).__name__,
                            e,
                        )

            raise RetryExhaustedError(
                message=f"{func.__name__} 在{max_retries + 1}次尝试后仍然失败",
                last_exception=last_exc,
                attempts=max_retries + 1,
            )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator
