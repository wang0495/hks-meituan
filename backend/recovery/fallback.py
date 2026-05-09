"""降级策略。

当主逻辑不可用时，执行预注册的降级动作返回兜底结果，
保证系统仍能给出合理响应而非直接报错。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

# 降级函数的类型签名：接受任意参数，返回 Any
FallbackAction = Callable[..., Awaitable[Any]]


class FallbackStrategy:
    """降级策略管理器。

    为每个服务注册一个降级函数；当主逻辑失败时，
    调用对应的降级函数返回兜底结果。
    """

    def __init__(self) -> None:
        self._fallbacks: dict[str, FallbackAction] = {}

    def register(self, service: str, fallback: FallbackAction) -> None:
        """注册降级策略。

        Args:
            service: 服务名称。
            fallback: 异步降级函数。
        """
        self._fallbacks[service] = fallback
        logger.info("已注册降级策略: %s", service)

    async def execute(
        self,
        service: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """执行降级策略。

        Args:
            service: 服务名称。
            *args: 传递给降级函数的位置参数。
            **kwargs: 传递给降级函数的关键字参数。

        Returns:
            降级函数的返回值。

        Raises:
            KeyError: 该服务未注册降级策略。
        """
        if service not in self._fallbacks:
            logger.error("无降级策略: %s", service)
            raise KeyError(f"无降级策略: {service}")

        logger.info("执行降级策略: %s", service)
        return await self._fallbacks[service](*args, **kwargs)

    def has_fallback(self, service: str) -> bool:
        """检查是否已注册降级策略。

        Args:
            service: 服务名称。

        Returns:
            True 表示已注册。
        """
        return service in self._fallbacks

    def unregister(self, service: str) -> None:
        """移除降级策略。

        Args:
            service: 服务名称。
        """
        self._fallbacks.pop(service, None)


# ---------------------------------------------------------------------------
# 预定义降级策略
# ---------------------------------------------------------------------------


async def fallback_route_planning(user_input: str) -> dict[str, Any]:
    """路线规划降级策略。

    当路线规划服务不可用时，返回空路线和友好提示。

    Args:
        user_input: 用户原始输入。

    Returns:
        包含空路线、降级提示的字典。
    """
    return {
        "route": [],
        "narrative": {"opening": "暂时无法规划路线，请稍后重试"},
        "fallback": True,
        "original_input": user_input,
    }


async def fallback_nearby_search(
    lat: float,
    lon: float,
    keyword: str = "",
) -> dict[str, Any]:
    """附近搜索降级策略。

    Args:
        lat: 纬度。
        lon: 经度。
        keyword: 搜索关键词。

    Returns:
        空结果列表和友好提示。
    """
    return {
        "results": [],
        "message": "附近搜索服务暂时不可用，请稍后重试",
        "fallback": True,
    }


async def fallback_llm_response(user_input: str) -> dict[str, Any]:
    """LLM 服务降级策略。

    当 LLM 不可用时返回固定话术。

    Args:
        user_input: 用户原始输入。

    Returns:
        固定回复内容。
    """
    return {
        "reply": "抱歉，智能助手暂时不可用，请稍后再试。",
        "fallback": True,
    }
