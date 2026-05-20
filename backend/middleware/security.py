"""安全响应头中间件。

为所有 HTTP 响应注入标准安全头，防止常见浏览器端攻击。
"""

from __future__ import annotations

import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """注入安全响应头。

    适用于 API + 前端静态文件的混合服务场景。
    如果仅提供纯 API 服务，可移除 X-Frame-Options 等与浏览器渲染相关的头。
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 防止 MIME 类型嗅探
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 防止页面被嵌入 iframe（点击劫持防护）
        response.headers["X-Frame-Options"] = "DENY"

        # XSS 过滤（现代浏览器已内置，但作为兼容层保留）
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 强制 HTTPS — 仅生产环境启用（避免开发环境localhost被锁死）
        env = os.getenv("ENVIRONMENT", "development")
        if env in ("production", "prod", "staging"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # 内容安全策略：限制资源加载来源
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )

        # 控制 Referer 头泄露的来源信息
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 禁用浏览器特性（按需调整）
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

        return response
