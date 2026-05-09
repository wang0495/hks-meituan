"""CityFlow 消息队列便捷导入。

本模块从 :mod:`backend.services.message_queue` 重导出核心符号，
允许从 ``backend.mq.queue`` 路径直接导入，保持 mq 模块的自包含性。

使用示例::

    from backend.mq.queue import MessageQueue, Message, get_message_queue

    mq = get_message_queue()
    await mq.publish("route_planning", {"user_input": "逛商场"})
    msg = await mq.publish("notification", {"session_id": "s1", "content": "ok"})
"""

from __future__ import annotations

from backend.services.message_queue import (
    Message,
    MessageHandler,
    MessageQueue,
    close_message_queue,
    get_message_queue,
)

__all__ = [
    "Message",
    "MessageHandler",
    "MessageQueue",
    "close_message_queue",
    "get_message_queue",
]
