"""CityFlow 事件总线。

提供同步/异步的事件发布-订阅机制，支持：
- 按事件类型注册/注销处理器
- 同步事件发布（阻塞式逐个调用）
- 异步事件发布（并发执行，异常隔离）
- 全局单例访问

使用示例::

    from backend.services.event_bus import get_event_bus, Event

    bus = get_event_bus()
    bus.subscribe("route.planned", my_handler)
    bus.publish(Event(event_type="route.planned", data={"route_id": "123"}))
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """事件基类。

    所有事件的通用载体，包含事件类型、负载数据、时间戳和来源。

    Attributes:
        event_type: 事件类型标识，如 ``"route.planned"``
        data: 事件负载数据
        timestamp: 事件发生时间（UTC），默认自动填充
        source: 事件来源标识，如模块名或服务名
    """

    event_type: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""


# 同步处理器类型
SyncHandler = Callable[[Event], None]
# 异步处理器类型
AsyncHandler = Callable[[Event], Any]  # 返回协程


class EventBus:
    """事件总线。

    维护同步和异步两套订阅者列表，发布时分别按同步阻塞 /
    异步并发方式调用所有已注册的处理器。单个处理器异常不会
    影响其他处理器的执行。
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[SyncHandler]] = {}
        self._async_subscribers: dict[str, list[AsyncHandler]] = {}

    # ------------------------------------------------------------------
    # 订阅
    # ------------------------------------------------------------------

    def subscribe(self, event_type: str, handler: SyncHandler) -> None:
        """注册同步事件处理器。

        Args:
            event_type: 要监听的事件类型
            handler: 同步回调 ``(event: Event) -> None``
        """
        self._subscribers.setdefault(event_type, []).append(handler)
        logger.info("订阅同步事件: %s -> %s", event_type, handler.__qualname__)

    def subscribe_async(self, event_type: str, handler: AsyncHandler) -> None:
        """注册异步事件处理器。

        Args:
            event_type: 要监听的事件类型
            handler: 异步回调 ``(event: Event) -> Coroutine``
        """
        self._async_subscribers.setdefault(event_type, []).append(handler)
        logger.info("订阅异步事件: %s -> %s", event_type, handler.__qualname__)

    # ------------------------------------------------------------------
    # 取消订阅
    # ------------------------------------------------------------------

    def unsubscribe(self, event_type: str, handler: Callable[..., Any]) -> None:
        """取消注册事件处理器。

        同时在同步和异步订阅者列表中查找并移除。如果 handler
        不在列表中，静默忽略。

        Args:
            event_type: 事件类型
            handler: 要移除的处理器
        """
        for registry in (self._subscribers, self._async_subscribers):
            handlers = registry.get(event_type)
            if handlers and handler in handlers:
                handlers.remove(handler)
                logger.info("取消订阅: %s -> %s", event_type, handler.__qualname__)

    # ------------------------------------------------------------------
    # 发布
    # ------------------------------------------------------------------

    def publish(self, event: Event) -> None:
        """同步发布事件。

        逐个调用所有已注册的同步处理器，单个处理器的异常会被
        捕获并记录，不影响后续处理器。

        Args:
            event: 要发布的事件
        """
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "同步事件处理异常: %s -> %s",
                    event.event_type,
                    handler.__qualname__,
                )

    async def publish_async(self, event: Event) -> None:
        """异步发布事件。

        并发执行所有已注册的异步处理器，使用 ``asyncio.gather``
        的 ``return_exceptions=True`` 保证单个处理器失败不影响
        其他处理器。处理完毕后逐条记录异常。

        注册到异步列表中的处理器如果实际是同步函数，会被自动
        包装为协程执行。

        Args:
            event: 要发布的事件
        """
        handlers = self._async_subscribers.get(event.event_type, [])
        if not handlers:
            return

        async def _invoke(handler: AsyncHandler) -> Any:
            """统一调用入口，兼容同步和异步处理器。"""
            result = handler(event)
            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                return await result
            return result

        results = await asyncio.gather(
            *(_invoke(h) for h in handlers),
            return_exceptions=True,
        )
        for handler, result in zip(handlers, results):
            if isinstance(result, Exception):
                logger.exception(
                    "异步事件处理异常: %s -> %s",
                    event.event_type,
                    handler.__qualname__,
                    exc_info=result,
                )

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_subscribers(self, event_type: str) -> list[Callable[..., Any]]:
        """获取指定事件类型的所有订阅者（同步 + 异步）。"""
        return self._subscribers.get(event_type, []) + self._async_subscribers.get(
            event_type, []
        )

    def event_types(self) -> list[str]:
        """返回所有已注册事件类型的列表（去重）。"""
        return list(set(self._subscribers.keys()) | set(self._async_subscribers.keys()))

    def clear(self) -> None:
        """清空所有订阅（主要用于测试）。"""
        self._subscribers.clear()
        self._async_subscribers.clear()
        logger.info("事件总线已清空所有订阅")


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线单例。"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """重置全局事件总线（仅用于测试）。"""
    global _event_bus
    _event_bus = None
