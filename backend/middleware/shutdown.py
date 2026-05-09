"""CityFlow 停机感知中间件。

将每个 HTTP 请求的生命周期与 GracefulShutdown 管理器绑定：
- 请求进入时注册为活跃请求
- 请求结束时（无论成功/失败）注销
- 停机期间拒绝新请求，返回 503 Service Unavailable

使用方式::

    from backend.middleware.shutdown import ShutdownMiddleware

    app.add_middleware(ShutdownMiddleware)
"""

from __future__ import annotations

import logging
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.services.graceful_shutdown import get_shutdown_manager

logger = logging.getLogger(__name__)

# 停机期间跳过注册的路径（健康检查需存活以便负载均衡器探活）
_EXEMPT_PATHS: frozenset[str] = frozenset({"/api/health"})


class ShutdownMiddleware(BaseHTTPMiddleware):
    """停机感知中间件。

    功能：
    1. 为每个请求生成短 ID 并注册到停机管理器
    2. 停机期间对新请求返回 503
    3. 请求完成（成功或异常）后自动注销

    在中间件链中的位置建议：靠近最外层，早于业务中间件，
    以便尽早拒绝停机期间的请求。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        manager = get_shutdown_manager()

        # 停机期间跳过健康检查路径（负载均衡器需要探活）
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # 停机中：拒绝新请求
        if manager.is_shutting_down:
            logger.debug("停机中，拒绝请求: %s %s", request.method, request.url.path)
            return Response(
                content='{"detail":"Service is shutting down"}',
                status_code=503,
                media_type="application/json",
                headers={"Retry-After": "5"},
            )

        # 正常请求：注册 -> 执行 -> 注销
        request_id = uuid.uuid4().hex[:8]
        manager.request_started(request_id)

        try:
            response = await call_next(request)
            return response
        finally:
            manager.request_finished(request_id)
