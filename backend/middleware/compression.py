"""CityFlow HTTP 响应压缩中间件。

根据客户端 Accept-Encoding 头自动压缩响应体。
支持 gzip 和 deflate 两种压缩方式。
"""

from __future__ import annotations

import gzip
import zlib
from typing import TYPE_CHECKING

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from collections.abc import Callable

# 不压缩的最小字节数（小于此值压缩反而增大体积）
_MIN_COMPRESS_SIZE = 500

# 不压缩的 Content-Type（已压缩的格式）
_SKIP_CONTENT_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "application/zip",
        "application/gzip",
        "application/pdf",
        "video/",
        "audio/",
    }
)


class CompressionMiddleware(BaseHTTPMiddleware):
    """HTTP 响应 gzip/deflate 压缩中间件。

    仅在满足以下条件时压缩：
    - 客户端声明支持对应编码
    - 响应状态码为 2xx
    - 响应体大于最小阈值
    - Content-Type 不是已压缩格式
    """

    def __init__(
        self,
        app: Callable,
        minimum_size: int = _MIN_COMPRESS_SIZE,
        compresslevel: int = 6,
    ) -> None:
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compresslevel = compresslevel

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """拦截响应，按需压缩。"""
        response = await call_next(request)

        # 只压缩成功响应
        if response.status_code < 200 or response.status_code >= 300:
            return response

        # 检查 Content-Type 是否已压缩
        content_type = response.headers.get("content-type", "")
        if any(ct in content_type for ct in _SKIP_CONTENT_TYPES):
            return response

        # 读取完整响应体
        body = await self._read_body(response)

        # 小体积不压缩
        if len(body) < self.minimum_size:
            return self._make_response(body, response)

        # 根据客户端支持选择压缩方式
        accept_encoding = request.headers.get("accept-encoding", "")

        if "gzip" in accept_encoding:
            compressed = gzip.compress(body, compresslevel=self.compresslevel)
            return self._make_response(compressed, response, content_encoding="gzip")

        if "deflate" in accept_encoding:
            compressed = zlib.compress(body, self.compresslevel)
            return self._make_response(compressed, response, content_encoding="deflate")

        return self._make_response(body, response)

    @staticmethod
    async def _read_body(response: Response) -> bytes:
        """从响应中读取完整 body。"""
        if hasattr(response, "body"):
            return response.body  # type: ignore[return-value]

        # StreamingResponse 需要迭代读取
        chunks: list[bytes] = []
        async for chunk in response.body_iterator:  # type: ignore[union-attr]
            if isinstance(chunk, str):
                chunks.append(chunk.encode("utf-8"))
            else:
                chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _make_response(
        body: bytes,
        original: Response,
        content_encoding: str | None = None,
    ) -> Response:
        """构造最终响应。"""
        headers = dict(original.headers)
        headers["content-length"] = str(len(body))

        if content_encoding:
            headers["content-encoding"] = content_encoding
            headers["vary"] = "Accept-Encoding"

        return Response(
            content=body,
            status_code=original.status_code,
            headers=headers,
            media_type=original.media_type,
        )
