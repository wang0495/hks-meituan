"""CityFlow 会话中间件。

自动为请求创建 / 注入会话，支持：
- Cookie 读取 session_id
- Header (X-Session-ID) 读取
- 无会话时自动创建
- 响应时设置 Cookie 和 Header
"""

from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.services.session import get_session_manager


class SessionMiddleware(BaseHTTPMiddleware):
    """会话中间件：为每个请求注入 session_id。

    优先级：Cookie > Header > 自动创建。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        session_manager = get_session_manager()

        # 从 cookie 或 header 获取 session_id
        session_id = request.cookies.get("session_id") or request.headers.get(
            "X-Session-ID"
        )

        # 没有 session 则创建新的
        if not session_id:
            session_id = await session_manager.create_session()

        # 注入到请求状态，后续路由可通过 request.state.session_id 获取
        request.state.session_id = session_id

        # 处理请求
        response = await call_next(request)

        # 设置 session cookie（HttpOnly 防 XSS，SameSite=Lax 防 CSRF）
        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=3600,
            httponly=True,
            samesite="lax",
        )

        # 同时在 Header 中暴露（方便前端 SPA / 移动端读取）
        response.headers["X-Session-ID"] = session_id

        return response
