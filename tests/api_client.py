"""CityFlow API 测试客户端。

封装 httpx.AsyncClient，统一请求/响应格式，方便在测试用例生成器和
测试运行器中复用。

用法:
    async with APITestClient("http://localhost:8000") as client:
        result = await client.get("/api/health")
        assert result["status_code"] == 200
"""

from __future__ import annotations

from typing import Any, Optional

import httpx


class APITestClient:
    """异步 API 测试客户端。

    所有请求方法返回统一的 dict::

        {
            "status_code": int,
            "headers": dict,
            "data": dict | list | None,   # JSON body（非 2xx 时可能为 None）
            "error": str | None,           # 原始文本（非 2xx 时）
            "elapsed_ms": float,           # 请求耗时（毫秒）
        }
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._default_headers = headers or {}
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers=self._default_headers,
        )

    # ------------------------------------------------------------------
    # 上下文管理器
    # ------------------------------------------------------------------

    async def __aenter__(self) -> APITestClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # 核心请求方法
    # ------------------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[Any] = None,
        content: Optional[bytes] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """发送 HTTP 请求并返回统一格式的响应。"""
        response = await self._client.request(
            method,
            path,
            params=params,
            json=json,
            content=content,
            headers=headers,
        )
        return self._build_result(response)

    async def get(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """GET 请求。"""
        return await self.request("GET", path, params=params, headers=headers)

    async def post(
        self,
        path: str,
        json: Optional[Any] = None,
        content: Optional[bytes] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """POST 请求。"""
        return await self.request(
            "POST", path, json=json, content=content, headers=headers
        )

    async def put(
        self,
        path: str,
        json: Optional[Any] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """PUT 请求。"""
        return await self.request("PUT", path, json=json, headers=headers)

    async def delete(
        self,
        path: str,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """DELETE 请求。"""
        return await self.request("DELETE", path, headers=headers)

    async def head(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """HEAD 请求（常用于健康检查 / 探活）。"""
        return await self.request("HEAD", path, params=params, headers=headers)

    # ------------------------------------------------------------------
    # SSE 流式请求（用于 /api/plan 等 SSE 端点）
    # ------------------------------------------------------------------

    async def stream_sse(
        self,
        path: str,
        json: Optional[Any] = None,
    ) -> list[dict[str, str]]:
        """发送请求并解析 SSE 事件流，返回事件列表。

        每个事件::

            {"event": "phase", "data": "{...}"}
        """
        events: list[dict[str, str]] = []
        async with self._client.stream("POST", path, json=json) as response:
            current_event = ""
            current_data = ""
            async for line in response.aiter_lines():
                line = line.strip()
                if line.startswith("event:"):
                    current_event = line[len("event:") :].strip()
                elif line.startswith("data:"):
                    current_data = line[len("data:") :].strip()
                elif line == "":
                    if current_event or current_data:
                        events.append({"event": current_event, "data": current_data})
                        current_event = ""
                        current_data = ""
            # 流末尾可能没有空行
            if current_event or current_data:
                events.append({"event": current_event, "data": current_data})
        return events

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """关闭底层 httpx 客户端。"""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _build_result(response: httpx.Response) -> dict[str, Any]:
        """将 httpx.Response 转换为统一 dict。"""
        status = response.status_code
        elapsed_ms = response.elapsed.total_seconds() * 1000

        data: Any = None
        error: str | None = None

        try:
            body = response.json()
            if status < 400:
                data = body
            else:
                # CityFlow 错误格式: {"error": "...", "code": 400}
                error = (
                    body.get("error", str(body))
                    if isinstance(body, dict)
                    else str(body)
                )
                data = body
        except Exception:
            if status >= 400:
                error = response.text

        return {
            "status_code": status,
            "headers": dict(response.headers),
            "data": data,
            "error": error,
            "elapsed_ms": round(elapsed_ms, 2),
        }
