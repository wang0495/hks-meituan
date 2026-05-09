"""CityFlow 消息处理器。

注册各类业务消息的处理逻辑，供 MessageQueue 消费端调用。
处理器签名统一为 `async def handler(payload: dict) -> None`。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.services.message_queue import MessageHandler, get_message_queue

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 路线规划（异步长任务场景：前端提交后走队列，完成后回调）
# ---------------------------------------------------------------------------


async def handle_route_planning(payload: dict[str, Any]) -> None:
    """处理路线规划消息。

    payload 结构::

        {
            "session_id": "abc123",
            "user_input": "带女朋友逛商场",
            "callback_url": "https://xxx/callback"  # 可选
        }
    """
    user_input: str = payload.get("user_input", "")
    session_id: str = payload.get("session_id", "")
    callback_url: str | None = payload.get("callback_url")

    logger.info("处理路线规划: session=%s, input=%s", session_id, user_input)

    from backend.services.intent_parser import parse_intent
    from backend.services.notification import notify_personal
    from backend.services.solver import solve_route

    try:
        intent = await parse_intent(user_input)
        route = solve_route([], intent)

        # 通过 WebSocket 推送结果
        if session_id:
            await notify_personal(
                session_id,
                {"type": "route_result", "route": route},
            )

        # 可选：HTTP 回调通知
        if callback_url:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(callback_url, json=route)

        logger.info("路线规划完成: session=%s", session_id)
    except Exception:
        logger.exception("路线规划失败: session=%s", session_id)
        if session_id:
            from backend.services.notification import notify_error

            await notify_error(session_id, "路线规划失败，请稍后重试")
        raise


# ---------------------------------------------------------------------------
# 通知
# ---------------------------------------------------------------------------


async def handle_notification(payload: dict[str, Any]) -> None:
    """处理通知消息。

    payload 结构::

        {
            "session_id": "abc123",
            "content": "您的路线已更新",
            "msg_type": "info"  # info / warning / error
        }
    """
    session_id: str = payload.get("session_id", "")
    content: str = payload.get("content", "")
    msg_type: str = payload.get("msg_type", "info")

    logger.info("发送通知: session=%s, type=%s", session_id, msg_type)

    from backend.services.notification import notify_personal

    await notify_personal(
        session_id,
        {"type": "notification", "msg_type": msg_type, "content": content},
    )


# ---------------------------------------------------------------------------
# 数据分析（埋点事件落盘）
# ---------------------------------------------------------------------------


async def handle_analytics(payload: dict[str, Any]) -> None:
    """处理分析事件，记录用户行为。

    payload 结构::

        {
            "event_type": "route_planned",
            "user_id": "u_001",
            "data": {"city": "成都", "poi_count": 5}
        }
    """
    event_type: str = payload.get("event_type", "unknown")
    data: dict[str, Any] = payload.get("data", {})

    logger.info("记录分析事件: type=%s, data=%s", event_type, data)

    # TODO: 写入 ClickHouse / PostgreSQL analytics 表
    # 当前仅日志记录


# ---------------------------------------------------------------------------
# 处理器注册表
# ---------------------------------------------------------------------------

HANDLER_REGISTRY: dict[str, MessageHandler] = {
    "route_planning": handle_route_planning,
    "notification": handle_notification,
    "analytics": handle_analytics,
}


def get_handler(name: str) -> MessageHandler | None:
    """根据名称获取已注册的处理器。"""
    return HANDLER_REGISTRY.get(name)


async def start_default_consumers() -> None:
    """启动所有已注册处理器的默认消费者（用于应用启动时调用）。

    队列名与处理器名一一对应：
    - route_planning -> cityflow:mq:route_planning
    - notification   -> cityflow:mq:notification
    - analytics      -> cityflow:mq:analytics
    """
    mq = get_message_queue()
    for queue_name, handler in HANDLER_REGISTRY.items():
        mq.start_consumer(queue_name, handler)
        logger.info("默认消费者已启动: queue=%s", queue_name)
