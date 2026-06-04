"""CityFlow 消息队列 API。

提供消息发布、消费者管理、队列状态查询等接口。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.message_handlers import HANDLER_REGISTRY, get_handler
from backend.services.message_queue import get_message_queue

router = APIRouter(prefix="/api/mq", tags=["消息队列"])


# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------


class PublishRequest(BaseModel):
    """发布消息请求体。"""

    payload: dict[str, Any] = Field(..., description="业务消息体")


class PublishBatchRequest(BaseModel):
    """批量发布请求体。"""

    payloads: list[dict[str, Any]] = Field(
        ..., min_length=1, max_length=100, description="消息列表"
    )


class StartConsumerRequest(BaseModel):
    """启动消费者请求体。"""

    handler_name: str = Field(..., description="处理器名称")


# ---------------------------------------------------------------------------
# 发布消息
# ---------------------------------------------------------------------------


@router.post("/publish/{queue}", summary="发布单条消息")
async def publish_message(queue: str, body: PublishRequest) -> dict[str, Any]:
    """发布一条消息到指定队列。"""
    mq = get_message_queue()
    msg = await mq.publish(queue, body.payload)
    return {
        "message": "消息已发布",
        "message_id": msg.message_id,
        "queue": queue,
    }


@router.post("/publish/{queue}/batch", summary="批量发布消息")
async def publish_batch(queue: str, body: PublishBatchRequest) -> dict[str, Any]:
    """批量发布消息到指定队列。"""
    mq = get_message_queue()
    messages = await mq.publish_many(queue, body.payloads)
    return {
        "message": f"已发布 {len(messages)} 条消息",
        "queue": queue,
        "message_ids": [m.message_id for m in messages],
    }


# ---------------------------------------------------------------------------
# 消费者管理
# ---------------------------------------------------------------------------


@router.post("/consume/{queue}", summary="启动消费者")
async def start_consumer(queue: str, body: StartConsumerRequest) -> dict[str, str]:
    """为指定队列启动一个后台消费者。"""
    handler = get_handler(body.handler_name)
    if handler is None:
        raise HTTPException(
            status_code=400,
            detail=f"处理器不存在: {body.handler_name}，可用: {list(HANDLER_REGISTRY.keys())}",
        )
    mq = get_message_queue()
    mq.start_consumer(queue, handler)
    return {"message": f"消费者已启动: queue={queue}, handler={body.handler_name}"}


# ---------------------------------------------------------------------------
# 队列状态
# ---------------------------------------------------------------------------


@router.get("/status/{queue}", summary="查询队列状态")
async def queue_status(queue: str) -> dict[str, Any]:
    """查询指定队列的长度。"""
    mq = get_message_queue()
    length = await mq.queue_length(queue)
    return {"queue": queue, "length": length}


@router.delete("/{queue}", summary="清空队列")
async def clear_queue(queue: str) -> dict[str, Any]:
    """清空指定队列中的所有消息。"""
    mq = get_message_queue()
    deleted = await mq.clear_queue(queue)
    return {"queue": queue, "deleted": deleted}


@router.get("/handlers", summary="列出已注册处理器")
async def list_handlers() -> dict[str, list[str]]:
    """列出所有已注册的消息处理器名称。"""
    return {"handlers": list(HANDLER_REGISTRY.keys())}
