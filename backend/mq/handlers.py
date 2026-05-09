"""CityFlow 消息处理器便捷导入。

本模块从 :mod:`backend.services.message_handlers` 重导出核心符号，
允许从 ``backend.mq.handlers`` 路径直接导入。

使用示例::

    from backend.mq.handlers import (
        handle_route_planning,
        handle_notification,
        start_default_consumers,
    )

    # 注册自定义处理器
    from backend.mq.queue import get_message_queue
    mq = get_message_queue()
    mq.start_consumer("my_queue", my_handler)

    # 或启动所有默认消费者
    await start_default_consumers()
"""

from __future__ import annotations

from backend.services.message_handlers import (
    HANDLER_REGISTRY,
    get_handler,
    handle_analytics,
    handle_notification,
    handle_route_planning,
    start_default_consumers,
)

__all__ = [
    "HANDLER_REGISTRY",
    "get_handler",
    "handle_analytics",
    "handle_notification",
    "handle_route_planning",
    "start_default_consumers",
]
