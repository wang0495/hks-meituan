"""CityFlow 消息队列包。

提供 Redis 消息队列的核心组件：

- :mod:`backend.mq.queue`    -- 消息队列（生产者 / 消费者）
- :mod:`backend.mq.handlers` -- 消息处理器注册

快速开始::

    from backend.mq import setup_mq, publish, start_default_consumers

    # 在应用启动时初始化并启动消费者
    await setup_mq()

    # 在业务代码中发布消息
    await publish("route_planning", {"user_input": "逛商场"})
"""

from __future__ import annotations

import logging
from typing import Any

from backend.mq.handlers import (
    HANDLER_REGISTRY,
    get_handler,
    handle_analytics,
    handle_notification,
    handle_route_planning,
    start_default_consumers,
)
from backend.mq.queue import (
    Message,
    MessageHandler,
    MessageQueue,
    close_message_queue,
    get_message_queue,
)

logger = logging.getLogger(__name__)


async def setup_mq() -> None:
    """初始化消息队列并启动所有默认消费者。

    应在 FastAPI 应用启动时调用。内部会：

    1. 懒初始化全局 :class:`MessageQueue` 实例（连接 Redis）
    2. 为每个已注册处理器启动一个后台消费 task
    """
    await start_default_consumers()
    logger.info("消息队列初始化完成")


async def publish(queue: str, payload: dict[str, Any]) -> Message:
    """便捷发布函数。

    Args:
        queue: 队列名称。
        payload: 业务消息体。

    Returns:
        已发布的 Message 对象。
    """
    mq = get_message_queue()
    return await mq.publish(queue, payload)


async def shutdown_mq() -> None:
    """关闭消息队列（用于 FastAPI shutdown 事件）。"""
    await close_message_queue()
    logger.info("消息队列已关闭")


__all__ = [
    # 队列核心
    "Message",
    "MessageHandler",
    "MessageQueue",
    "get_message_queue",
    "close_message_queue",
    # 处理器
    "HANDLER_REGISTRY",
    "get_handler",
    "handle_route_planning",
    "handle_notification",
    "handle_analytics",
    "start_default_consumers",
    # 生命周期
    "setup_mq",
    "shutdown_mq",
    "publish",
]
