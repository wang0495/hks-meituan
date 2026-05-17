"""CityFlow WebSocket 实时通信端点。

提供 WebSocket 连接入口，支持路线订阅、心跳检测等实时交互。
"""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.websocket import get_websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# WebSocket security limits
_WS_MAX_MESSAGE_SIZE = 64 * 1024  # 64 KB per message
_WS_RATE_LIMIT = 30  # max messages per minute per connection


# ---------------------------------------------------------------------------
# WebSocket 端点
# ---------------------------------------------------------------------------


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """WebSocket 实时通信端点。

    客户端通过 `ws://host/ws/{session_id}` 建立连接后，
    可发送 JSON 消息进行交互。

    支持的消息类型：

    | type | 说明 | 额外字段 |
    |------|------|----------|
    | subscribe | 订阅路线更新 | route_id |
    | unsubscribe | 取消订阅 | route_id |
    | ping | 心跳检测 | - |

    服务端推送的消息类型：

    | type | 说明 |
    |------|------|
    | subscribed | 订阅成功确认 |
    | unsubscribed | 取消订阅确认 |
    | pong | 心跳响应 |
    | route_update | 路线更新通知 |
    | error | 错误通知 |
    """
    manager = get_websocket_manager()
    await manager.connect(websocket, session_id)

    # Per-connection rate limiting state
    msg_timestamps: list[float] = []

    try:
        while True:
            data = await websocket.receive_text()

            # Message size limit
            if len(data) > _WS_MAX_MESSAGE_SIZE:
                await manager.send_personal_message(
                    session_id,
                    {"type": "error", "message": "消息过大"},
                )
                continue

            # Rate limiting
            now = time.monotonic()
            msg_timestamps = [t for t in msg_timestamps if now - t < 60]
            if len(msg_timestamps) >= _WS_RATE_LIMIT:
                await manager.send_personal_message(
                    session_id,
                    {"type": "error", "message": "消息过于频繁"},
                )
                continue
            msg_timestamps.append(now)

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await manager.send_personal_message(
                    session_id,
                    {
                        "type": "error",
                        "message": "无效的 JSON 格式",
                    },
                )
                continue

            await _handle_message(session_id, message)

    except WebSocketDisconnect:
        await manager.disconnect(session_id)
    except Exception as e:
        logger.error("WebSocket 异常: %s (%s)", session_id, e)
        await manager.disconnect(session_id)


# ---------------------------------------------------------------------------
# 消息处理
# ---------------------------------------------------------------------------


async def _handle_message(session_id: str, message: dict) -> None:
    """根据消息类型分发处理。"""
    manager = get_websocket_manager()
    msg_type = message.get("type")

    if msg_type == "subscribe":
        route_id = message.get("route_id")
        if not route_id:
            await manager.send_personal_message(
                session_id,
                {
                    "type": "error",
                    "message": "缺少 route_id 字段",
                },
            )
            return
        await manager.subscribe(session_id, route_id)
        await manager.send_personal_message(
            session_id,
            {
                "type": "subscribed",
                "route_id": route_id,
            },
        )

    elif msg_type == "unsubscribe":
        route_id = message.get("route_id")
        if not route_id:
            await manager.send_personal_message(
                session_id,
                {
                    "type": "error",
                    "message": "缺少 route_id 字段",
                },
            )
            return
        await manager.unsubscribe(session_id, route_id)
        await manager.send_personal_message(
            session_id,
            {
                "type": "unsubscribed",
                "route_id": route_id,
            },
        )

    elif msg_type == "ping":
        await manager.send_personal_message(session_id, {"type": "pong"})

    else:
        await manager.send_personal_message(
            session_id,
            {
                "type": "error",
                "message": f"未知消息类型: {msg_type}",
            },
        )
