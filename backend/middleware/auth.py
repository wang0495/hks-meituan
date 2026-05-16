"""API Key 认证中间件。

保护管理端点（/api/audit, /metrics, /pool, /mq, /tasks, /registry, /session），
公开端点（/api/plan, /api/health, /api/poi 等）无需认证。

配置：
  SECURITY_API_KEY=your-secret-key  # .env 中设置

请求头：
  X-API-Key: your-secret-key

未配置 API Key 时，中间件不生效（兼容开发模式）。
"""

from __future__ import annotations

import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# 不需要认证的路径前缀（公开端点）
_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/api/plan",
    "/api/route",
    "/api/dialogue",
    "/api/poi",
    "/api/health",
    "/api/cache/stats",
    "/health",
    "/system/health",
    "/data/",
    "/llm/",
    "/v1/",
    "/v2/",
    "/ws/",
    "/graphql",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/",
)

# 完全跳过中间件的路径
_SKIP_PATHS: frozenset[str] = frozenset({
    "/", "/docs", "/redoc", "/openapi.json",
    "/favicon.ico",
})


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """API Key 认证中间件。

    当 SECURITY_API_KEY 环境变量已设置时生效。
    管理端点要求 X-API-Key 请求头匹配配置的密钥。
    公开端点始终放行。
    """

    def __init__(self, app, api_key: str = ""):
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next):
        # 未配置 API Key → 全部放行（开发模式）
        if not self._api_key:
            return await call_next(request)

        # 静态文件和根路径放行
        path = request.url.path
        if path in _SKIP_PATHS:
            return await call_next(request)

        # 公开端点放行
        if any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
            return await call_next(request)

        # 静态文件放行
        if path.startswith("/static") or "." in path.split("/")[-1]:
            return await call_next(request)

        # 管理端点 → 要求 API Key
        provided = request.headers.get("X-API-Key", "")
        if provided == self._api_key:
            return await call_next(request)

        logger.warning(
            "认证失败: path=%s, ip=%s",
            path,
            request.client.host if request.client else "unknown",
        )
        return JSONResponse(
            status_code=401,
            content={"detail": "未授权。请在请求头中提供有效的 X-API-Key。"},
        )
