"""CityFlow 事件系统。

提供事件驱动架构的核心组件：

- :mod:`backend.events.types`    -- 预定义事件类型
- :mod:`backend.events.handlers` -- 事件处理器注册
- :mod:`backend.events.decorators` -- 事件发射装饰器

快速开始::

    from backend.events import setup_events, EventType
    from backend.services.event_bus import get_event_bus, Event

    # 在应用启动时初始化
    setup_events()

    # 在业务代码中发布事件
    bus = get_event_bus()
    bus.publish(Event(event_type=EventType.ROUTE_PLANNED, data={"route_id": "xxx"}))
"""

from __future__ import annotations

from backend.events.handlers import setup_event_handlers
from backend.events.types import (EventType, RouteAdjustedEvent,
                                  RoutePlannedEvent, SystemErrorEvent,
                                  UserFeedbackEvent)


def setup_events() -> None:
    """初始化事件系统：注册所有内置事件处理器。

    应在 FastAPI 应用启动时调用一次。
    """
    setup_event_handlers()


__all__ = [
    "EventType",
    "RoutePlannedEvent",
    "RouteAdjustedEvent",
    "UserFeedbackEvent",
    "SystemErrorEvent",
    "setup_events",
]
