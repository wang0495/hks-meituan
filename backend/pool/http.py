"""CityFlow HTTP 连接池优化。

基于 httpx.AsyncClient 提供可复用的 HTTP 连接池，
支持自动重试、超时配置和 Prometheus 指标上报。

关键优化：
  - 连接池大小根据业务负载调优
  - Keep-Alive 连接复用减少 TCP 握手开销
  - 指数退避重试应对瞬时网络故障
  - 请求/响应指标自动采集
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus 指标
# ---------------------------------------------------------------------------

HTTP_POOL_CONNECTIONS = Gauge(
    "cityflow_http_pool_connections",
    "HTTP connection pool total connections",
)

HTTP_POOL_KEEPALIVE = Gauge(
    "cityflow_http_pool_keepalive",
    "HTTP connection pool keep-alive connections",
)

HTTP_REQUEST_COUNT = Counter(
    "cityflow_http_client_requests_total",
    "Total outgoing HTTP requests",
    ["method", "host", "status"],
)

HTTP_REQUEST_LATENCY = Histogram(
    "cityflow_http_client_duration_seconds",
    "Outgoing HTTP request latency",
    ["method", "host"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_RETRY_COUNT = Counter(
    "cityflow_http_client_retries_total",
    "Total HTTP request retries",
)


class HTTPPool:
    """HTTP 连接池。

    封装 httpx.AsyncClient，提供连接复用和重试能力。
    支持 async context manager 自动管理生命周期。

    Args:
        max_connections: 最大连接数，默认 100。
        max_keepalive: 最大 Keep-Alive 连接数，默认 20。
        timeout: 请求超时秒数，默认 30.0。
        max_retries: 最大重试次数，默认 3。
        retry_backoff: 重试退避基数秒数，默认 0.5。
    """

    def __init__(
        self,
        *,
        max_connections: int = 100,
        max_keepalive: int = 20,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
    ) -> None:
        self._max_connections = max_connections
        self._max_keepalive = max_keepalive
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._client: httpx.AsyncClient | None = None
        logger.info(
            "HTTP 连接池配置: max_conn=%d, keepalive=%d, timeout=%.1fs, retries=%d",
            max_connections,
            max_keepalive,
            timeout,
            max_retries,
        )

    def _ensure_client(self) -> httpx.AsyncClient:
        """延迟初始化客户端。"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                limits=httpx.Limits(
                    max_connections=self._max_connections,
                    max_keepalive_connections=self._max_keepalive,
                ),
                timeout=httpx.Timeout(self._timeout),
                follow_redirects=True,
            )
        return self._client

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """发送 HTTP 请求，自动重试。

        Args:
            method: HTTP 方法 (GET, POST, ...)。
            url: 请求地址。
            **kwargs: 透传给 httpx 的参数。

        Returns:
            httpx.Response 实例。

        Raises:
            httpx.HTTPStatusError: 4xx/5xx 响应（重试用尽后）。
            httpx.RequestError: 网络层错误（重试用尽后）。
        """
        client = self._ensure_client()
        host = _extract_host(url)
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)
                HTTP_REQUEST_COUNT.labels(
                    method=method, host=host, status=str(response.status_code)
                ).inc()
                response.raise_for_status()
                return response
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    wait = self._retry_backoff * (2**attempt)
                    HTTP_RETRY_COUNT.inc()
                    logger.warning(
                        "HTTP %s %s 失败 (尝试 %d/%d): %s, %.1fs 后重试",
                        method,
                        url,
                        attempt + 1,
                        self._max_retries,
                        exc,
                        wait,
                    )
                    await asyncio.sleep(wait)

        raise last_exc  # type: ignore[misc]

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """发送 GET 请求。"""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """发送 POST 请求。"""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        """发送 PUT 请求。"""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """发送 DELETE 请求。"""
        return await self.request("DELETE", url, **kwargs)

    async def ping(self, url: str = "https://httpbin.org/get") -> bool:
        """执行轻量级 HTTP 请求验证连接可用性。

        Args:
            url: 用于探测的目标 URL，默认 httpbin.org。

        Returns:
            True 表示连接正常，False 表示连接异常。
        """
        try:
            client = self._ensure_client()
            resp = await client.head(url, timeout=5.0)
            return resp.status_code < 500
        except Exception:
            logger.exception("HTTP 连接健康检查失败")
            return False

    def get_pool_stats(self) -> dict[str, int]:
        """获取连接池统计并上报 Prometheus。

        注意: httpx/httpcore 未暴露连接池的公开 API，这里通过内部属性读取。
        如果 httpx 版本升级导致内部结构变化，此方法需要适配。

        Returns:
            包含连接池状态的字典。客户端未初始化时返回全零。
        """
        if self._client is None or self._client.is_closed:
            stats: dict[str, int] = {
                "max_connections": self._max_connections,
                "active": 0,
                "keepalive": 0,
            }
        else:
            # httpcore.AsyncConnectionPool 内部结构:
            #   _transport._pool._connections -> list[AsyncHTTPConnection]
            # 每个连接有 is_idle() / is_closed() / is_available() 方法
            transport = self._client._transport
            pool = getattr(transport, "_pool", None)
            if pool is not None:
                connections = pool._connections
                total = len(connections)
                idle = sum(1 for c in connections if c.is_idle())
                stats = {
                    "max_connections": self._max_connections,
                    "active": total - idle,
                    "keepalive": idle,
                }
            else:
                stats = {
                    "max_connections": self._max_connections,
                    "active": 0,
                    "keepalive": 0,
                }

        HTTP_POOL_CONNECTIONS.set(stats["active"])
        HTTP_POOL_KEEPALIVE.set(stats["keepalive"])
        return stats

    async def close(self) -> None:
        """关闭 HTTP 连接池。"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
            logger.info("HTTP 连接池已关闭")

    async def __aenter__(self) -> HTTPPool:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


def _extract_host(url: str) -> str:
    """从 URL 中提取 host，用于 Prometheus label。"""
    try:
        return url.split("://", 1)[1].split("/", 1)[0].split(":")[0]
    except (IndexError, AttributeError):
        return "unknown"
