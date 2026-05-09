"""配置注入中间件。

将全局 Settings 实例挂载到 request.state.config，
方便路由/下游中间件直接读取配置，无需重复调用 get_settings()。
"""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import get_settings


class ConfigMiddleware(BaseHTTPMiddleware):
    """将配置注入到 request.state.config。"""

    async def dispatch(self, request: Request, call_next):
        request.state.config = get_settings()
        response = await call_next(request)
        return response
