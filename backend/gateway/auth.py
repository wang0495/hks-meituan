"""JWT 认证中间件。

拦截请求，验证 Bearer token，将解析出的用户信息注入 ``request.state``。
白名单路径跳过认证，开发环境可配置为可选认证。
"""

from __future__ import annotations

import logging
import time
from typing import Any

import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# 默认白名单路径（无需认证）
_DEFAULT_WHITELIST: set[str] = {
    "/health",
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT 认证中间件。

    Args:
        app: ASGI 应用。
        secret_key: JWT 签名密钥。
        algorithm: JWT 算法，默认 HS256。
        whitelist: 白名单路径集合，这些路径不校验 token。
        optional: 为 ``True`` 时缺少 token 不报错（开发模式）。
    """

    def __init__(
        self,
        app,
        secret_key: str = "change-me-in-production",
        algorithm: str = "HS256",
        whitelist: set[str] | None = None,
        optional: bool = False,
    ):
        super().__init__(app)
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.whitelist = whitelist or _DEFAULT_WHITELIST
        self.optional = optional

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 白名单放行
        if self._is_whitelisted(path):
            return await call_next(request)

        # 提取 token
        token = self._extract_token(request)

        if not token:
            if self.optional:
                # 开发模式：无 token 也放行，user_id 为空
                request.state.user_id = None
                request.state.user_payload = {}
                return await call_next(request)
            return JSONResponse(
                status_code=401,
                content={"error": {"code": 2001, "message": "缺少认证令牌"}},
            )

        # 验证 token
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError:
            logger.warning("token 已过期: path=%s", path)
            return JSONResponse(
                status_code=401,
                content={"error": {"code": 2003, "message": "认证令牌已过期"}},
            )
        except jwt.InvalidTokenError as exc:
            logger.warning("无效 token: path=%s, err=%s", path, exc)
            return JSONResponse(
                status_code=401,
                content={"error": {"code": 2001, "message": "无效的认证令牌"}},
            )

        # 注入用户信息到 request.state
        request.state.user_id = payload.get("sub") or payload.get("user_id")
        request.state.user_payload = payload

        logger.debug("认证通过: user=%s, path=%s", request.state.user_id, path)
        return await call_next(request)

    # ------------------------------------------------------------------

    def _is_whitelisted(self, path: str) -> bool:
        """判断路径是否在白名单中。

        支持精确匹配和前缀匹配（以 ``*`` 结尾的白名单项）。
        """
        if path in self.whitelist:
            return True
        # 支持 /api/public/* 之类的通配
        for pattern in self.whitelist:
            if pattern.endswith("*") and path.startswith(pattern[:-1]):
                return True
        return False

    @staticmethod
    def _extract_token(request: Request) -> str | None:
        """从 Authorization 头提取 Bearer token。"""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        # 也支持 query 参数（仅用于 SSE 等不方便设 header 的场景）
        return request.query_params.get("token")


def create_token(
    payload: dict[str, Any],
    secret_key: str,
    expires_in: int = 3600,
    algorithm: str = "HS256",
) -> str:
    """生成 JWT token（辅助函数）。

    Args:
        payload: token 载荷，需包含 ``sub`` 或 ``user_id``。
        secret_key: 签名密钥。
        expires_in: 过期时间（秒），默认 1 小时。
        algorithm: 算法。

    Returns:
        编码后的 JWT 字符串。
    """
    now = int(time.time())
    token_payload = {
        **payload,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(token_payload, secret_key, algorithm=algorithm)
