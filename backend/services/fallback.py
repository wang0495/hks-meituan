"""CityFlow 降级策略模块。

当主函数执行失败时，自动切换到预定义的降级函数返回兜底结果。
保证用户始终能拿到一个有效响应，而不是看到错误页。

用法：
    @fallback(fallback_route_planning)
    async def plan_route(...):
        ...

    # 配合熔断器和重试使用
    @retry(max_retries=2)
    @fallback(fallback_route_planning, exceptions=(CircuitBreakerOpenError,))
    @llm_circuit_breaker
    async def plan_route(...):
        ...
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

__all__ = [
    "FallbackError",
    "fallback",
    "fallback_emotion_analysis",
    "fallback_llm_chat",
    "fallback_narrative_generation",
    "fallback_poi_search",
    "fallback_route_planning",
]

F = TypeVar("F", bound=Callable[..., Any])


class FallbackError(Exception):
    """降级函数本身也失败时抛出。"""

    pass


def fallback(
    fallback_func: Callable[..., Any],
    exceptions: type[BaseException] | tuple[type[BaseException], ...] = Exception,
) -> Callable[[F], F]:
    """降级装饰器。

    当被装饰的函数抛出指定异常时，调用 fallback_func 代替。

    Args:
        fallback_func: 降级函数，签名应与被装饰函数兼容。
        exceptions: 触发降级的异常类型，默认所有 Exception。

    Returns:
        装饰器。

    Example::

        @fallback(my_fallback, exceptions=(TimeoutError, ConnectionError))
        async def call_external_api(url: str) -> dict:
            ...
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)  # type: ignore[misc]
            except exceptions as e:
                logger.warning(
                    "[降级] %s 失败 (%s: %s)，执行降级函数 %s",
                    func.__name__,
                    type(e).__name__,
                    e,
                    fallback_func.__name__,
                )
                try:
                    return await fallback_func(*args, **kwargs)
                except Exception as fallback_exc:
                    logger.error(
                        "[降级] 降级函数 %s 也失败: %s",
                        fallback_func.__name__,
                        fallback_exc,
                    )
                    raise fallback_exc from e

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                logger.warning(
                    "[降级] %s 失败 (%s: %s)，执行降级函数 %s",
                    func.__name__,
                    type(e).__name__,
                    e,
                    fallback_func.__name__,
                )
                try:
                    return fallback_func(*args, **kwargs)
                except Exception as fallback_exc:
                    logger.error(
                        "[降级] 降级函数 %s 也失败: %s",
                        fallback_func.__name__,
                        fallback_exc,
                    )
                    raise fallback_exc from e

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


# ===========================================================================
# CityFlow 预定义降级函数
# ===========================================================================


async def fallback_route_planning(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """路线规划降级：返回空路线，提示稍后重试。"""
    return {
        "route": [],
        "emotion_curve": [],
        "total_cost": {"time_min": 0, "budget_used": 0, "step_estimate": 0},
        "unused_candidates": [],
        "breathing_spots": [],
        "narrative": {
            "opening": "暂时无法规划路线，请稍后重试。",
            "steps": [],
            "closing": "期待为你规划更好的旅程！",
        },
        "fallback": True,
    }


async def fallback_poi_search(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """POI 搜索降级：返回空列表。"""
    return {
        "pois": [],
        "total": 0,
        "fallback": True,
    }


async def fallback_narrative_generation(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """文案生成降级：返回简洁模板文案。"""
    return {
        "opening": "行程规划中，精彩即将呈现。",
        "steps": ["下一站就在前方，跟着感觉走。"],
        "closing": "祝你旅途愉快！",
        "emotion_highlights": [],
        "fallback": True,
    }


async def fallback_llm_chat(*args: Any, **kwargs: Any) -> str:
    """LLM 对话降级：返回固定提示。"""
    return "抱歉，AI 助手暂时无法回应，请稍后再试。"


async def fallback_emotion_analysis(*args: Any, **kwargs: Any) -> dict[str, float]:
    """情绪分析降级：返回中性情绪值。"""
    return {
        "excitement": 0.5,
        "tranquility": 0.5,
        "sociability": 0.5,
        "culture_depth": 0.5,
        "surprise": 0.5,
        "physical_demand": 0.5,
    }
