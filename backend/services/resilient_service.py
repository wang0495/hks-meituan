"""CityFlow 弹性服务集成模块。

将熔断器、重试、降级策略应用到 CityFlow 的核心服务调用上。
这是实际对接业务的地方，不是示例。

设计原则：
    - 外部依赖（LLM、高德API）必须有容错
    - 内部计算（solver、narrator）不需要熔断，但可以加重试
    - 降级结果必须标记 fallback=True，前端据此提示用户
"""

from __future__ import annotations

import logging
from typing import Any

from backend.services.circuit_breaker import (CircuitBreaker,
                                              CircuitBreakerOpenError)
from backend.services.fallback import (fallback, fallback_llm_chat,
                                       fallback_narrative_generation,
                                       fallback_route_planning)
from backend.services.retry import retry

logger = logging.getLogger(__name__)

__all__ = [
    "llm_circuit_breaker",
    "plan_route_with_resilience",
    "generate_narrative_with_resilience",
    "chat_with_resilience",
    "get_all_circuit_breakers",
]

# ---------------------------------------------------------------------------
# 熔断器实例（全局单例，每个外部服务一个）
# ---------------------------------------------------------------------------

llm_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=60.0,
    expected_exception=(TimeoutError, ConnectionError, OSError),
    name="llm",
)

# ---------------------------------------------------------------------------
# 带容错的 LLM 对话
# ---------------------------------------------------------------------------


@retry(max_retries=2, delay=1.0, backoff=2.0, exceptions=(TimeoutError, OSError))
@fallback(fallback_llm_chat, exceptions=(CircuitBreakerOpenError,))
@llm_circuit_breaker
async def chat_with_resilience(
    message: str,
    model: str = "gpt-4o-mini",
) -> str:
    """带容错的 LLM 对话。

    调用链：retry -> fallback -> circuit_breaker -> 实际调用
    1. circuit_breaker: 检查熔断状态，失败计数
    2. fallback: 熔断器打开时返回降级文案
    3. retry: 超时/连接错误时自动重试

    Args:
        message: 用户消息。
        model: 模型名称。

    Returns:
        LLM 回复文本，熔断时返回降级文案。
    """
    from backend.services.llm_service import chat

    return await chat(message, model=model)


# ---------------------------------------------------------------------------
# 带容错的路线规划
# ---------------------------------------------------------------------------


@retry(
    max_retries=1,
    delay=2.0,
    exceptions=(TimeoutError, OSError),
)
@fallback(fallback_route_planning, exceptions=(CircuitBreakerOpenError,))
@llm_circuit_breaker
async def plan_route_with_resilience(
    candidates: list[dict[str, Any]],
    user_intent: dict[str, Any],
    start_time: str = "09:00",
) -> dict[str, Any]:
    """带容错的路线规划。

    solver 本身是 CPU 计算，不会超时。但如果上游调用链
    中有任何网络调用失败（如距离矩阵 API），这里兜底。

    Args:
        candidates: 候选 POI 列表。
        user_intent: 用户意图。
        start_time: 出发时间。

    Returns:
        路线规划结果，降级时返回空路线 + fallback=True。
    """
    from backend.services.solver import solve_route

    return solve_route(candidates, user_intent, start_time)


# ---------------------------------------------------------------------------
# 带容错的文案生成
# ---------------------------------------------------------------------------


@retry(max_retries=1, delay=1.0, exceptions=(TimeoutError, OSError))
@fallback(fallback_narrative_generation, exceptions=(CircuitBreakerOpenError,))
@llm_circuit_breaker
async def generate_narrative_with_resilience(
    route_result: dict[str, Any],
    user_intent: dict[str, Any],
    *,
    enable_llm_polish: bool = False,
) -> dict[str, Any]:
    """带容错的文案生成。

    文案生成中 LLM 润色部分可能超时，降级为纯模板文案。

    Args:
        route_result: solver 输出。
        user_intent: 用户意图。
        enable_llm_polish: 是否启用 LLM 润色。

    Returns:
        文案字典，降级时返回简洁模板 + fallback=True。
    """
    from backend.services.narrator import generate_narrative

    return await generate_narrative(
        route_result,
        user_intent,
        enable_llm_polish=enable_llm_polish,
    )


# ---------------------------------------------------------------------------
# 监控接口
# ---------------------------------------------------------------------------


def get_all_circuit_breakers() -> dict[str, dict[str, Any]]:
    """获取所有熔断器的状态和指标，供监控端点使用。

    Returns:
        {name: {state, failure_count, metrics}} 的字典。
    """
    breakers = {
        "llm": llm_circuit_breaker,
    }
    return {
        name: {
            "state": cb.state.value,
            "failure_count": cb.failure_count,
            "failure_threshold": cb.failure_threshold,
            "recovery_timeout": cb.recovery_timeout,
            "metrics": cb.metrics.as_dict(),
        }
        for name, cb in breakers.items()
    }
