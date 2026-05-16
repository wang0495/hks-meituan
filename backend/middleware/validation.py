"""输入验证中间件。

在请求到达路由处理函数之前，对查询参数和请求体进行基本的安全检查。
这不是输入验证的唯一防线——路由层的 Pydantic 模型校验同样重要。
"""

from __future__ import annotations

import logging
import re

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class InputValidationMiddleware(BaseHTTPMiddleware):
    """基本的注入 / XSS 检测中间件。

    对查询参数和 JSON 请求体进行正则匹配，拦截明显的攻击模式。
    不替代参数化查询或 Pydantic 校验，而是作为纵深防御的一层。

    Args:
        app: ASGI 应用。
        max_body_size: 请求体最大字节数（默认 10 MB）。
    """

    # 需要拦截的危险模式（不区分大小写）
    DANGEROUS_PATTERNS: list[re.Pattern] = [
        re.compile(r"<script[^>]*>", re.IGNORECASE),
        re.compile(r"javascript\s*:", re.IGNORECASE),
        re.compile(r"on\w+\s*=\s*[\"']", re.IGNORECASE),
        re.compile(r"union\s+(all\s+)?select", re.IGNORECASE),
        re.compile(r";\s*drop\s+table", re.IGNORECASE),
        re.compile(r";\s*delete\s+from", re.IGNORECASE),
        re.compile(r"\.\./\.\./", re.IGNORECASE),
    ]

    # LLM prompt injection 模式（警告但不禁断 — 业务需要处理）
    LLM_INJECTION_PATTERNS: list[re.Pattern] = [
        re.compile(r"ignore\s+(previous|above|all)\s+(instructions?|rules?|prompts?)", re.IGNORECASE),
        re.compile(r"system\s*prompt", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(admin|root|superuser|debug)", re.IGNORECASE),
        re.compile(r"output\s+(all\s+)?(system|your)\s+instructions", re.IGNORECASE),
        re.compile(r"\[ignore\s+previous\]", re.IGNORECASE),
    ]

    # 不需要检查的路径（静态文件、健康检查等）
    SKIP_PATHS: set[str] = {"/api/health", "/docs", "/redoc", "/openapi.json"}

    # 不需要检查 body 的 Content-Type
    SKIP_CONTENT_TYPES: set[str] = {
        "multipart/form-data",
        "application/octet-stream",
    }

    def __init__(self, app, max_body_size: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_body_size = max_body_size

    # ------------------------------------------------------------------

    async def dispatch(self, request: Request, call_next):
        # 跳过不需要检查的路径
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # 检查请求体大小
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_size:
            logger.warning(
                "请求体过大: %s bytes from %s",
                content_length,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=413,
                content={"detail": "请求体过大"},
            )

        # 检查查询参数
        for key, value in request.query_params.items():
            if self._contains_dangerous(value):
                logger.warning(
                    "查询参数包含危险内容: key=%s, ip=%s",
                    key,
                    request.client.host if request.client else "unknown",
                )
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"无效的查询参数: {key}"},
                )

        # 检查请求体（仅对 JSON 类型）
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if not any(ct in content_type for ct in self.SKIP_CONTENT_TYPES):
                try:
                    body = await request.body()
                    if len(body) > self.max_body_size:
                        return JSONResponse(
                            status_code=413,
                            content={"detail": "请求体过大"},
                        )
                    if body:
                        body_str = body.decode("utf-8", errors="ignore")
                        if self._contains_dangerous(body_str):
                            logger.warning(
                                "请求体包含危险内容, ip=%s, path=%s",
                                request.client.host if request.client else "unknown",
                                request.url.path,
                            )
                            return JSONResponse(
                                status_code=400,
                                content={"detail": "请求体包含无效内容"},
                            )
                except Exception:
                    # 解析失败不阻断请求，交给路由层处理
                    pass

        return await call_next(request)

    # ------------------------------------------------------------------

    def _contains_dangerous(self, text: str) -> bool:
        """检查文本是否匹配任何危险模式。"""
        return any(pattern.search(text) for pattern in self.DANGEROUS_PATTERNS)
