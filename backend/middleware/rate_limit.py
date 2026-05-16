"""速率限制中间件。

基于客户端 IP 的滑动窗口速率限制。使用内存存储，适合单实例部署。
如需多实例共享，应替换为 Redis 等外部存储。
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """滑动窗口速率限制。

    Args:
        app: ASGI 应用。
        requests_per_minute: 每个 IP 每分钟允许的最大请求数。
        cleanup_interval: 清理过期记录的间隔（秒）。
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        cleanup_interval: int = 300,
        trusted_proxies: list[str] | None = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.cleanup_interval = cleanup_interval
        self._trusted_proxies: frozenset[str] = frozenset(trusted_proxies or [])
        # {ip: [timestamp, ...]}
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.monotonic()

    # ------------------------------------------------------------------

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        now = time.time()

        # 定期清理长时间无请求的 IP，防止内存泄漏
        self._maybe_cleanup(now)

        # 滑动窗口：移除 60 秒前的记录
        window = self._requests[client_ip]
        cutoff = now - 60
        self._requests[client_ip] = [t for t in window if t > cutoff]
        window = self._requests[client_ip]

        # 检查是否超限
        if len(window) >= self.requests_per_minute:
            retry_after = int(window[0] + 60 - now) + 1
            logger.warning("IP %s 触发速率限制 (%d 请求/分钟)", client_ip, len(window))
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now) + retry_after),
                },
            )

        # 记录本次请求
        window.append(now)

        # 处理请求
        response = await call_next(request)

        # 注入速率限制响应头
        remaining = self.requests_per_minute - len(window)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        response.headers["X-RateLimit-Reset"] = str(int(now) + 60)

        return response

    # ------------------------------------------------------------------

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP，仅在可信代理链中读取转发头。"""
        direct_ip = request.client.host if request.client else "unknown"

        # 仅当直连 IP 是可信代理时，才读取 X-Forwarded-For
        if self._trusted_proxies and direct_ip in self._trusted_proxies:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                # 取最右边的非可信条目（最接近客户端的真实 IP）
                parts = [p.strip() for p in forwarded.split(",")]
                for ip in reversed(parts):
                    if ip not in self._trusted_proxies:
                        return ip
                return parts[-1]  # 全部都是代理，取最后一个
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip.strip()

        return direct_ip

    def _maybe_cleanup(self, now: float) -> None:
        """定期清理超过 2 分钟无请求的 IP 条目。"""
        mono_now = time.monotonic()
        if mono_now - self._last_cleanup < self.cleanup_interval:
            return
        self._last_cleanup = mono_now

        stale_threshold = now - 120
        stale_ips = [
            ip
            for ip, timestamps in self._requests.items()
            if not timestamps or timestamps[-1] < stale_threshold
        ]
        for ip in stale_ips:
            del self._requests[ip]
        if stale_ips:
            logger.debug("速率限制：清理了 %d 个过期 IP 条目", len(stale_ips))
