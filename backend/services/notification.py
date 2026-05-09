"""CityFlow 消息推送服务。

提供路线更新、步骤变更、错误通知等实时推送能力，
供其他业务模块调用，将变更实时推送给已订阅的客户端。
"""

from __future__ import annotations

import logging
from typing import Any

from backend.services.websocket import get_websocket_manager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 路线更新通知
# ---------------------------------------------------------------------------


async def notify_route_update(
    route_id: str,
    update_type: str,
    data: dict[str, Any],
) -> None:
    """通知路线订阅者：路线发生了变更。

    Args:
        route_id: 路线 ID
        update_type: 变更类型（new_step / complete / adjusted / removed）
        data: 变更的具体数据
    """
    manager = get_websocket_manager()
    message = {
        "type": "route_update",
        "route_id": route_id,
        "update_type": update_type,
        "data": data,
    }
    await manager.broadcast_to_route(route_id, message)
    logger.info("路线更新通知: %s [%s]", route_id, update_type)


async def notify_new_step(route_id: str, step: dict[str, Any]) -> None:
    """通知路线新增了一个步骤（用于 SSE 流式规划过程中的实时推送）。"""
    await notify_route_update(route_id, "new_step", step)


async def notify_route_complete(route_id: str, route: dict[str, Any]) -> None:
    """通知路线规划完成。"""
    await notify_route_update(route_id, "complete", route)


async def notify_route_adjusted(route_id: str, changes: list[dict[str, Any]]) -> None:
    """通知路线已被对话调整。"""
    await notify_route_update(route_id, "adjusted", {"changes": changes})


# ---------------------------------------------------------------------------
# 个人通知
# ---------------------------------------------------------------------------


async def notify_error(session_id: str, error: str) -> None:
    """向单个客户端发送错误通知。"""
    manager = get_websocket_manager()
    await manager.send_personal_message(
        session_id,
        {
            "type": "error",
            "message": error,
        },
    )


async def notify_personal(session_id: str, message: dict[str, Any]) -> None:
    """向单个客户端发送自定义消息。"""
    manager = get_websocket_manager()
    await manager.send_personal_message(session_id, message)


# ---------------------------------------------------------------------------
# 全局广播
# ---------------------------------------------------------------------------


async def broadcast_system_message(text: str) -> None:
    """向所有在线客户端广播系统消息（维护通知、公告等）。"""
    manager = get_websocket_manager()
    await manager.broadcast_all(
        {
            "type": "system",
            "message": text,
        }
    )
