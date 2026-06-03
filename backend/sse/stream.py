"""SSE 流式传输核心实现。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi.responses import StreamingResponse


class SSEStream:
    """SSE 流，基于 asyncio.Queue 实现事件缓冲与异步生成。"""

    def __init__(self) -> None:
        self._events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def send(self, event_type: str, data: dict[str, Any]) -> None:
        """发送一个 SSE 事件到队列。"""
        await self._events.put({"event": event_type, "data": data})

    async def stream(self) -> AsyncGenerator[str, None]:
        """生成 SSE 文本流。超时 30s 发送心跳保活。"""
        while True:
            try:
                event = await asyncio.wait_for(self._events.get(), timeout=30)

                event_type = event["event"]
                data = json.dumps(event["data"], ensure_ascii=False)

                yield f"event: {event_type}\ndata: {data}\n\n"
            except TimeoutError:
                # 心跳保活
                yield ": heartbeat\n\n"
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                break


def create_sse_response(stream: SSEStream) -> StreamingResponse:
    """创建标准 SSE StreamingResponse。"""
    return StreamingResponse(
        stream.stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
