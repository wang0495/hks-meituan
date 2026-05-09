"""CityFlow 性能监控中间件。

为每个请求注入唯一 ID 和耗时信息，自动记录慢请求日志。
响应头中携带 ``X-Request-ID`` 和 ``X-Response-Time``，方便前端 / 网关追踪。
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# 慢请求阈值（秒）
_DEFAULT_SLOW_THRESHOLD = 1.0


class PerformanceMiddleware(BaseHTTPMiddleware):
    """请求性能监控中间件。

    功能：
    1. 为每个请求生成唯一 ``X-Request-ID``（写入 request.state 和响应头）
    2. 精确测量请求处理耗时（使用 ``time.perf_counter``）
    3. 超过阈值的慢请求自动记录 WARNING 日志
    4. 在响应头中注入性能指标，方便前端监控

    Args:
        app: ASGI 应用。
        slow_threshold: 慢请求判定阈值（秒），默认 1.0。
        request_id_header: 自定义请求 ID 响应头名称，默认 ``X-Request-ID``。
    """

    def __init__(
        self,
        app,
        slow_threshold: float = _DEFAULT_SLOW_THRESHOLD,
        request_id_header: str = "X-Request-ID",
    ) -> None:
        super().__init__(app)
        self.slow_threshold = slow_threshold
        self.request_id_header = request_id_header

    async def dispatch(self, request: Request, call_next) -> Response:
        """拦截请求，注入性能信息。"""
        # 生成请求 ID（8 位 hex，碰撞概率极低）
        request_id = uuid.uuid4().hex[:8]
        request.state.request_id = request_id

        # 高精度计时
        start = time.perf_counter()

        # 执行下游处理
        response = await call_next(request)

        # 计算耗时
        duration = time.perf_counter() - start

        # 注入性能响应头
        response.headers[self.request_id_header] = request_id
        response.headers["X-Response-Time"] = f"{duration:.3f}s"

        # 记录慢请求
        if duration > self.slow_threshold:
            logger.warning(
                "慢请求: %s %s - %.3fs (阈值 %.1fs)",
                request.method,
                request.url.path,
                duration,
                self.slow_threshold,
            )

        return response
