"""CityFlow WebSocket 连接管理器。

提供 WebSocket 连接生命周期管理、路线订阅机制和消息广播能力。
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器。

    职责：
    - 管理活跃 WebSocket 连接的生命周期
    - 维护路线订阅关系（一个连接可订阅多条路线）
    - 提供点对点、路线组播和全局广播三种消息推送方式
    """

    def __init__(self) -> None:
        # 活跃连接: {session_id: WebSocket}
        self._connections: Dict[str, WebSocket] = {}
        # 订阅关系: {route_id: Set[session_id]}
        self._subscriptions: Dict[str, Set[str]] = {}

    # ------------------------------------------------------------------
    # 连接生命周期
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """接受 WebSocket 连接并注册。"""
        await websocket.accept()
        self._connections[session_id] = websocket
        logger.info(
            "WebSocket 连接建立: %s (当前 %d 个)", session_id, len(self._connections)
        )

    async def disconnect(self, session_id: str) -> None:
        """断开连接并清理所有订阅关系。"""
        if session_id in self._connections:
            del self._connections[session_id]

        # 清理该 session 的所有订阅
        for subscribers in self._subscriptions.values():
            subscribers.discard(session_id)
        # 移除空的订阅条目
        empty_routes = [rid for rid, subs in self._subscriptions.items() if not subs]
        for rid in empty_routes:
            del self._subscriptions[rid]

        logger.info(
            "WebSocket 连接断开: %s (剩余 %d 个)", session_id, len(self._connections)
        )

    # ------------------------------------------------------------------
    # 订阅管理
    # ------------------------------------------------------------------

    async def subscribe(self, session_id: str, route_id: str) -> None:
        """订阅路线更新。"""
        if route_id not in self._subscriptions:
            self._subscriptions[route_id] = set()
        self._subscriptions[route_id].add(session_id)
        logger.info("订阅: %s -> %s", session_id, route_id)

    async def unsubscribe(self, session_id: str, route_id: str) -> None:
        """取消订阅路线更新。"""
        if route_id in self._subscriptions:
            self._subscriptions[route_id].discard(session_id)
            if not self._subscriptions[route_id]:
                del self._subscriptions[route_id]

    # ------------------------------------------------------------------
    # 消息推送
    # ------------------------------------------------------------------

    async def send_personal_message(self, session_id: str, message: dict) -> None:
        """向单个连接发送 JSON 消息。发送失败时自动断开。"""
        websocket = self._connections.get(session_id)
        if websocket is None:
            return
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error("发送消息失败: %s (%s)", session_id, e)
            await self.disconnect(session_id)

    async def broadcast_to_route(self, route_id: str, message: dict) -> None:
        """向订阅了指定路线的所有连接广播消息。"""
        subscribers = self._subscriptions.get(route_id, set())
        for session_id in subscribers.copy():
            await self.send_personal_message(session_id, message)

    async def broadcast_all(self, message: dict) -> None:
        """向所有活跃连接广播消息。"""
        for session_id in list(self._connections.keys()):
            await self.send_personal_message(session_id, message)

    # ------------------------------------------------------------------
    # 状态查询
    # ------------------------------------------------------------------

    def get_connection_count(self) -> int:
        """获取当前活跃连接数。"""
        return len(self._connections)

    def get_subscription_count(self) -> int:
        """获取当前订阅的路线数。"""
        return len(self._subscriptions)

    def get_subscribers(self, route_id: str) -> Set[str]:
        """获取某条路线的所有订阅者。"""
        return self._subscriptions.get(route_id, set()).copy()

    def is_connected(self, session_id: str) -> bool:
        """检查指定 session 是否在线。"""
        return session_id in self._connections


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

_manager: Optional[ConnectionManager] = None


def get_websocket_manager() -> ConnectionManager:
    """获取全局 WebSocket 连接管理器单例。"""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
