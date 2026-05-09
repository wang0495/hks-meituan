"""CityFlow 事件处理器注册。

集中注册所有内置事件处理器。在应用启动时调用
:func:`setup_event_handlers` 一次即可。

新增处理器的步骤：
1. 在本模块编写 ``async def handle_xxx(event)`` 或同步函数
2. 在 :func:`setup_event_handlers` 中添加对应的订阅调用
"""

from __future__ import annotations

import logging

from backend.services.event_bus import Event, get_event_bus

logger = logging.getLogger(__name__)


def setup_event_handlers() -> None:
    """注册所有内置事件处理器。

    应在应用启动时调用一次。处理器分为两类：

    - **同步处理器**：用于轻量级操作（日志、指标记录）
    - **异步处理器**：用于 I/O 密集操作（通知推送、数据持久化）
    """
    bus = get_event_bus()

    # 同步处理器
    bus.subscribe("route.planned", handle_route_planned_metrics)
    bus.subscribe("system.error", handle_system_error_alert)

    # 异步处理器
    bus.subscribe_async("route.planned", handle_route_planned_notify)
    bus.subscribe_async("user.feedback", handle_user_feedback_record)

    registered = bus.event_types()
    logger.info("事件处理器注册完成，已注册事件类型: %s", registered)


# ---------------------------------------------------------------------------
# 路线规划事件
# ---------------------------------------------------------------------------


def handle_route_planned_metrics(event: Event) -> None:
    """路线规划完成 -> 记录指标（同步）。"""
    from backend.services.metrics import track_route_planning

    user_type = event.data.get("user_type", "unknown")
    track_route_planning(user_type)
    logger.debug("路线规划指标已记录: %s", event.data.get("route_id"))


async def handle_route_planned_notify(event: Event) -> None:
    """路线规划完成 -> 推送通知（异步）。"""
    from backend.services.notification import notify_route_complete

    route_id = event.data.get("route_id", "")
    route_data = event.data.get("route", {})
    await notify_route_complete(route_id, route_data)
    logger.info("路线规划通知已发送: %s", route_id)


# ---------------------------------------------------------------------------
# 用户反馈事件
# ---------------------------------------------------------------------------


async def handle_user_feedback_record(event: Event) -> None:
    """用户反馈 -> 持久化记录（异步）。"""
    user_id = event.data.get("user_id", "")
    feedback_type = event.data.get("feedback_type", "")
    content = event.data.get("content", "")
    logger.info(
        "用户反馈已记录: user=%s, type=%s, content=%s",
        user_id,
        feedback_type,
        content[:100] if content else "",
    )
    # TODO: 写入数据库或消息队列


# ---------------------------------------------------------------------------
# 系统错误事件
# ---------------------------------------------------------------------------


def handle_system_error_alert(event: Event) -> None:
    """系统错误 -> 发送告警（同步）。"""
    error_type = event.data.get("error_type", "unknown")
    message = event.data.get("message", "")
    logger.error("系统告警: [%s] %s", error_type, message)
    # TODO: 对接告警渠道（邮件 / 钉钉 / 飞书）
