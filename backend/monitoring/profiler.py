"""性能分析装饰器，自动将端点耗时记录到 Prometheus Histogram。"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from backend.monitoring.metrics import REQUEST_LATENCY

logger = logging.getLogger(__name__)


def profile_endpoint(
    endpoint: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """性能分析装饰器 —— 自动记录被装饰异步端点的执行耗时。

    用法::

        @profile_endpoint("/api/plan")
        async def plan_route(request):
            ...

    Args:
        endpoint: 端点路径标签，写入 Prometheus label。

    Returns:
        装饰后的异步函数。
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.monotonic() - start
                REQUEST_LATENCY.labels(method="POST", endpoint=endpoint).observe(
                    duration,
                )
                if duration > 5.0:
                    logger.warning(
                        "Slow endpoint: %s took %.2fs",
                        endpoint,
                        duration,
                    )

        return wrapper

    return decorator
