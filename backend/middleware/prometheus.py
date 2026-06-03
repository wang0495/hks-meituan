"""Prometheus 监控中间件。

自动为每个 HTTP 请求记录计数、延迟和请求/响应体大小，写入 Prometheus 指标。
监控端点和健康检查不计入统计，避免递归干扰和噪音。
"""

from __future__ import annotations

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.monitoring.metrics import REQUEST_COUNT, REQUEST_LATENCY
from backend.monitoring.prometheus import REQUEST_SIZE, RESPONSE_SIZE

# 不采集指标的路径前缀和精确路径
_EXCLUDED_PATHS: frozenset[str] = frozenset(
    {
        "/metrics",
        "/metrics/health",
        "/api/health",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """自动将每个 HTTP 请求的计数、延迟和体大小写入 Prometheus 指标。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # 跳过不需要采集的路径
        if path in _EXCLUDED_PATHS:
            return await call_next(request)

        method = request.method
        start = time.monotonic()

        # 估算请求体大小（Content-Length 头）
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                REQUEST_SIZE.labels(method=method, endpoint=path).observe(int(content_length))
            except (ValueError, TypeError):
                pass

        response = await call_next(request)

        duration = time.monotonic() - start
        status = str(response.status_code)

        REQUEST_COUNT.labels(method=method, endpoint=path, status=status).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=path).observe(duration)

        # 估算响应体大小（Content-Length 头）
        resp_length = response.headers.get("content-length")
        if resp_length is not None:
            try:
                RESPONSE_SIZE.labels(method=method, endpoint=path, status=status).observe(
                    int(resp_length)
                )
            except (ValueError, TypeError):
                pass

        return response
