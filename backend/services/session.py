"""CityFlow 分布式会话管理。

基于 Redis 的会话存储，支持：
- 会话创建 / 读取 / 更新 / 删除
- 自动 TTL 过期
- 用户维度会话查询
- 过期会话清理统计
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class SessionManager:
    """基于 Redis 的会话管理器。

    会话数据结构：
    {
        "session_id": "uuid",
        "user_id": "optional-user-id",
        "created_at": "ISO-8601",
        "last_active": "ISO-8601",
        "data": {}
    }
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        prefix: str = "session:",
        default_ttl: int = 3600,
    ) -> None:
        self._redis: aioredis.Redis | None = None
        self._redis_url = redis_url
        self._prefix = prefix
        self._default_ttl = default_ttl
        self._connected = False

    async def connect(self) -> None:
        """建立 Redis 连接。幂等，已连接时跳过。"""
        if self._connected and self._redis is not None:
            return
        try:
            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            await self._redis.ping()
            self._connected = True
            logger.info("Session Redis 连接成功: %s", self._redis_url)
        except Exception:
            self._connected = False
            logger.exception("Session Redis 连接失败: %s", self._redis_url)
            raise

    async def close(self) -> None:
        """关闭 Redis 连接。"""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
            self._connected = False

    def _key(self, session_id: str) -> str:
        """生成 Redis 键名。"""
        return f"{self._prefix}{session_id}"

    async def _ensure_connected(self) -> aioredis.Redis:
        """确保 Redis 已连接。"""
        if not self._connected or self._redis is None:
            await self.connect()
        assert self._redis is not None
        return self._redis

    async def create_session(self, user_id: str | None = None) -> str:
        """创建新会话，返回 session_id。"""
        r = await self._ensure_connected()
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": now,
            "last_active": now,
            "data": {},
        }
        await r.setex(
            self._key(session_id),
            self._default_ttl,
            json.dumps(session_data, ensure_ascii=False),
        )
        logger.debug("会话已创建: %s (user=%s)", session_id, user_id)
        return session_id

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """获取会话数据，不存在或已过期返回 None。"""
        r = await self._ensure_connected()
        data = await r.get(self._key(session_id))
        if data:
            return json.loads(data)
        return None

    async def update_session(self, session_id: str, data: dict[str, Any]) -> bool:
        """更新会话数据，返回是否成功。"""
        session = await self.get_session(session_id)
        if not session:
            return False

        session["data"].update(data)
        session["last_active"] = datetime.now().isoformat()

        r = await self._ensure_connected()
        await r.setex(
            self._key(session_id),
            self._default_ttl,
            json.dumps(session, ensure_ascii=False),
        )
        return True

    async def delete_session(self, session_id: str) -> bool:
        """删除会话，返回是否存在并被删除。"""
        r = await self._ensure_connected()
        result = await r.delete(self._key(session_id))
        return result > 0

    async def refresh_session(self, session_id: str) -> bool:
        """刷新会话过期时间（续期），返回是否成功。"""
        session = await self.get_session(session_id)
        if not session:
            return False

        session["last_active"] = datetime.now().isoformat()

        r = await self._ensure_connected()
        await r.setex(
            self._key(session_id),
            self._default_ttl,
            json.dumps(session, ensure_ascii=False),
        )
        return True

    async def get_user_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """获取指定用户的所有活跃会话。"""
        r = await self._ensure_connected()
        pattern = f"{self._prefix}*"
        sessions: list[dict[str, Any]] = []

        async for key in r.scan_iter(match=pattern, count=100):
            data = await r.get(key)
            if data:
                session = json.loads(data)
                if session.get("user_id") == user_id:
                    sessions.append(session)

        return sessions

    async def get_stats(self) -> dict[str, int]:
        """获取会话统计信息。"""
        r = await self._ensure_connected()
        pattern = f"{self._prefix}*"
        total = 0
        with_user = 0

        async for key in r.scan_iter(match=pattern, count=100):
            total += 1
            data = await r.get(key)
            if data:
                session = json.loads(data)
                if session.get("user_id"):
                    with_user += 1

        return {
            "total_sessions": total,
            "sessions_with_user": with_user,
            "anonymous_sessions": total - with_user,
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """获取全局会话管理器（懒初始化）。"""
    global _session_manager
    if _session_manager is None:
        from backend.config import settings

        rs = settings.redis
        redis_url = (
            f"redis://:{rs.password}@{rs.host}:{rs.port}/{rs.db}"
            if rs.password
            else f"redis://{rs.host}:{rs.port}/{rs.db}"
        )
        _session_manager = SessionManager(redis_url=redis_url)
    return _session_manager
