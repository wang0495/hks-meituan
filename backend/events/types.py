"""CityFlow 预定义事件类型。

使用 :class:`enum.StrEnum` 统一管理事件类型字符串，避免拼写错误。
使用 :class:`dataclasses.dataclass` 定义带类型提示的事件子类。

所有事件子类继承自 :class:`~backend.services.event_bus.Event`，
可直接传入 :meth:`~backend.services.event_bus.EventBus.publish` 等方法。

使用示例::

    from backend.events.types import RoutePlannedEvent, EventType
    from backend.services.event_bus import get_event_bus

    event = RoutePlannedEvent(route_id="r-001", user_id="u-42", data={"steps": [...]})
    get_event_bus().publish(event)

    # 或使用枚举值发布通用事件
    bus.publish(Event(event_type=EventType.USER_FEEDBACK, data={...}))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from backend.services.event_bus import Event


class EventType(StrEnum):
    """事件类型常量。

    集中管理所有事件类型的字符串标识，防止硬编码散落各处。
    """

    # 路线相关
    ROUTE_PLANNED = "route.planned"
    ROUTE_ADJUSTED = "route.adjusted"
    ROUTE_COMPLETED = "route.completed"
    ROUTE_FAILED = "route.failed"

    # 用户交互
    USER_FEEDBACK = "user.feedback"
    USER_MESSAGE = "user.message"

    # 系统
    SYSTEM_ERROR = "system.error"
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"


@dataclass
class RoutePlannedEvent(Event):
    """路线规划完成事件。

    当路线求解器成功生成路线后发布，供通知、指标、缓存等
    下游处理器消费。
    """

    event_type: str = field(default=EventType.ROUTE_PLANNED, init=False)
    route_id: str = ""
    user_id: str = ""


@dataclass
class RouteAdjustedEvent(Event):
    """路线调整事件。

    当用户通过对话调整已有路线后发布。
    """

    event_type: str = field(default=EventType.ROUTE_ADJUSTED, init=False)
    route_id: str = ""
    adjustment_type: str = ""


@dataclass
class UserFeedbackEvent(Event):
    """用户反馈事件。

    当用户提交评价、纠错或其他反馈时发布。
    """

    event_type: str = field(default=EventType.USER_FEEDBACK, init=False)
    user_id: str = ""
    feedback_type: str = ""
    content: str = ""


@dataclass
class SystemErrorEvent(Event):
    """系统错误事件。

    当系统内部发生未预期错误时发布，供告警和日志处理器消费。
    """

    event_type: str = field(default=EventType.SYSTEM_ERROR, init=False)
    error_type: str = ""
    message: str = ""
    stack_trace: str = ""
