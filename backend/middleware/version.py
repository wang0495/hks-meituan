"""API 版本控制中间件。"""

from __future__ import annotations

import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIVersionMiddleware(BaseHTTPMiddleware):
    """API版本中间件。

    支持两种版本控制方式：
    1. URL路径版本控制（/api/v1/...、/api/v2/...）
    2. 请求头版本控制（X-API-Version: v1）

    优先级：URL路径 > 请求头 > 默认版本
    """

    SUPPORTED_VERSIONS = ["v1", "v2"]
    DEFAULT_VERSION = "v1"

    async def dispatch(self, request: Request, call_next):
        # 优先从 URL 路径提取版本
        path_version = self._extract_version_from_path(request.url.path)

        if path_version:
            # URL 中已包含版本号，直接使用
            request.state.api_version = path_version
        else:
            # 从请求头获取版本
            header_version = request.headers.get("X-API-Version", self.DEFAULT_VERSION)

            # 验证版本
            if header_version not in self.SUPPORTED_VERSIONS:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": f"不支持的API版本: {header_version}",
                        "supported_versions": self.SUPPORTED_VERSIONS,
                    },
                )

            request.state.api_version = header_version

        # 处理请求
        response = await call_next(request)

        # 添加版本信息到响应头
        response.headers["X-API-Version"] = request.state.api_version

        return response

    @staticmethod
    def _extract_version_from_path(path: str) -> str | None:
        """从URL路径中提取版本号。

        Args:
            path: 请求路径，如 /api/v1/plan

        Returns:
            版本号（如 "v1"），如果不是版本化路径则返回 None
        """
        parts = path.strip("/").split("/")
        # 匹配 /api/v{n}/... 格式
        if len(parts) >= 2 and parts[0] == "api" and parts[1].startswith("v"):
            version = parts[1]
            if version in APIVersionMiddleware.SUPPORTED_VERSIONS:
                return version
        return None
