"""CityFlow 事件总线便捷导入。

本模块从 :mod:`backend.services.event_bus` 重导出核心符号，
允许从 ``backend.events.bus`` 路径直接导入，保持事件模块
的自包含性。

使用示例::

    from backend.events.bus import EventBus, Event, get_event_bus

    bus = get_event_bus()
    bus.subscribe("route.planned", my_handler)
    bus.publish(Event(event_type="route.planned", data={"route_id": "123"}))
"""

from __future__ import annotations

from backend.services.event_bus import (
    Event,
    EventBus,
    get_event_bus,
    reset_event_bus,
)

__all__ = [
    "Event",
    "EventBus",
    "get_event_bus",
    "reset_event_bus",
]
