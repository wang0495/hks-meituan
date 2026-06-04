"""CityFlow HTTP 连接池。

基于 httpx.AsyncClient 的连接池，提供：
- 可配置的最大连接数与 keep-alive 连接数
- 全生命周期管理（启动 / 关闭）
- GET / POST / PUT / PATCH / DELETE 等便捷方法
- 连接池统计信息

替代项目中散落的 ``async with httpx.AsyncClient(...) as client`` 临时连接，
复用底层 TCP 连接以降低延迟。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from backend.config.pool_config import pool_settings

logger = logging.getLogger(__name__)

__all__ = [
    "HTTPPool",
    "HTTPPoolStats",
    "get_http_pool",
]


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HTTPPoolStats:
    """HTTP 连接池统计快照。"""

    max_connections: int
    max_keepalive_connections: int


# ---------------------------------------------------------------------------
# 连接池
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class HTTPPool:
    """HTTP 连接池。

    Args:
        max_connections: 最大并发连接数。
        max_keepalive_connections: 最大 keep-alive 连接数。
        timeout: 默认请求超时（秒）。
    """

    max_connections: int = pool_settings.http_max_connections
    max_keepalive_connections: int = pool_settings.http_max_keepalive
    timeout: float = pool_settings.http_timeout

    _client: httpx.AsyncClient = field(init=False, repr=False)
    _started: bool = field(default=False, init=False, repr=False)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """初始化 HTTP 客户端。幂等。"""
        if self._started:
            return

        self._client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=self.max_connections,
                max_keepalive_connections=self.max_keepalive_connections,
            ),
            timeout=httpx.Timeout(self.timeout),
        )
        self._started = True
        logger.info(
            "HTTP 连接池已启动 | max_conn=%d, keepalive=%d",
            self.max_connections,
            self.max_keepalive_connections,
        )

    async def close(self) -> None:
        """关闭连接池。幂等。"""
        if not self._started:
            return

        await self._client.aclose()
        self._started = False
        logger.info("HTTP 连接池已关闭")

    # ------------------------------------------------------------------
    # 请求方法
    # ------------------------------------------------------------------

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """发送 HTTP 请求。

        Args:
            method: HTTP 方法（GET / POST / ...）。
            url: 目标 URL。
            **kwargs: 传递给 httpx.AsyncClient.request 的其余参数。
        """
        return await self._client.request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """GET 请求。"""
        return await self._client.get(url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """POST 请求。"""
        return await self._client.post(url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        """PUT 请求。"""
        return await self._client.put(url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        """PATCH 请求。"""
        return await self._client.patch(url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """DELETE 请求。"""
        return await self._client.delete(url, **kwargs)

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> HTTPPoolStats:
        """获取连接池配置快照。"""
        return HTTPPoolStats(
            max_connections=self.max_connections,
            max_keepalive_connections=self.max_keepalive_connections,
        )

    def get_stats_dict(self) -> dict[str, Any]:
        """以字典形式返回统计信息。"""
        stats = self.get_stats()
        return {
            "max_connections": stats.max_connections,
            "max_keepalive_connections": stats.max_keepalive_connections,
            "is_closed": self._client.is_closed if self._started else True,
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_http_pool: HTTPPool | None = None


def get_http_pool() -> HTTPPool:
    """获取全局 HTTP 连接池单例。"""
    global _http_pool
    if _http_pool is None:
        _http_pool = HTTPPool()
    return _http_pool
