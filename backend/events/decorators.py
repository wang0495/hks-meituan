"""CityFlow 事件发射装饰器。

提供声明式的事件发布能力，将事件发射逻辑从业务代码中解耦。

使用示例::

    from backend.events.decorators import emit_event
    from backend.events.types import EventType

    @emit_event(EventType.ROUTE_PLANNED)
    async def plan_route(user_input: str) -> dict:
        # ... 业务逻辑 ...
        return {"route_id": "r-001", "steps": [...]}

    # 调用 plan_route 后会自动发布 route.planned 事件，
    # 事件 data 中包含 {"result": {...}, "args": [...], "kwargs": {...}}
"""

from __future__ import annotations

import inspect
import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from backend.services.event_bus import Event, get_event_bus

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def emit_event(
    event_type: str,
    *,
    data_fn: Callable[..., dict[str, Any]] | None = None,
) -> Callable[[F], F]:
    """事件发射装饰器。

    被装饰的函数执行完毕后，自动向全局事件总线发布一条事件。
    支持同步和异步函数。

    Args:
        event_type: 要发布的事件类型字符串
        data_fn: 可选的自定义数据提取函数，签名
            ``(result, *args, **kwargs) -> dict``。
            如果不提供，使用默认的 ``{"result": result}``
            作为事件数据。

    Returns:
        装饰后的函数，签名和行为与原函数一致。

    Example::

        @emit_event(EventType.ROUTE_PLANNED)
        async def plan_route(user_input: str) -> dict:
            return {"route_id": "r-001"}

        # 自定义数据提取
        def extract_route_data(result, *args, **kwargs):
            return {"route_id": result["route_id"], "user_input": args[0]}

        @emit_event(EventType.ROUTE_PLANNED, data_fn=extract_route_data)
        async def plan_route_v2(user_input: str) -> dict:
            return {"route_id": "r-001"}
    """

    def _build_event(
        result: Any, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> Event:
        if data_fn is not None:
            data = data_fn(result, *args, **kwargs)
        else:
            data = {"result": result}
        return Event(event_type=event_type, data=data)

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                result = await func(*args, **kwargs)
                event = _build_event(result, args, kwargs)
                bus = get_event_bus()
                await bus.publish_async(event)
                return result

            return async_wrapper  # type: ignore[return-value]

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            event = _build_event(result, args, kwargs)
            bus = get_event_bus()
            bus.publish(event)
            return result

        return sync_wrapper  # type: ignore[return-value]

    return decorator
