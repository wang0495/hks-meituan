"""网关级速率限制中间件。

基于客户端 IP 的滑动窗口限流，支持 X-Forwarded-For 等反向代理头。
与 ``backend.middleware.rate_limit.RateLimitMiddleware`` 功能类似，
但专为网关场景设计，响应头格式对齐网关惯例。
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class GatewayRateLimitMiddleware(BaseHTTPMiddleware):
    """网关速率限制中间件。

    Args:
        app: ASGI 应用。
        requests_per_minute: 每个客户端 IP 每分钟最大请求数。
        whitelist_paths: 不限流的路径前缀列表。
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        whitelist_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.whitelist_paths = whitelist_paths or ["/health", "/api/health"]
        # {ip: [timestamp, ...]}
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.monotonic()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 白名单路径不限流
        if any(path.startswith(p) for p in self.whitelist_paths):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.time()

        # 定期清理
        self._maybe_cleanup(now)

        # 滑动窗口：移除 60 秒前的记录
        window = self._requests[client_ip]
        cutoff = now - 60
        self._requests[client_ip] = [t for t in window if t > cutoff]
        window = self._requests[client_ip]

        # 检查是否超限
        if len(window) >= self.requests_per_minute:
            retry_after = int(window[0] + 60 - now) + 1
            logger.warning(
                "网关限流: ip=%s, requests=%d, path=%s",
                client_ip,
                len(window),
                path,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": 1005,
                        "message": "请求过于频繁，请稍后再试",
                    }
                },
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

        # 注入限流响应头
        remaining = self.requests_per_minute - len(window)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        response.headers["X-RateLimit-Reset"] = str(int(now) + 60)

        return response

    # ------------------------------------------------------------------

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """获取客户端真实 IP。

        优先读取反向代理注入的头部，回退到 ``request.client.host``。
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _maybe_cleanup(self, now: float) -> None:
        """定期清理超过 2 分钟无请求的 IP 条目，防止内存泄漏。"""
        mono_now = time.monotonic()
        if mono_now - self._last_cleanup < 300:  # 5 分钟清理一次
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
            logger.debug("网关限流: 清理了 %d 个过期 IP 条目", len(stale_ips))
