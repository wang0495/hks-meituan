"""CityFlow 优雅停机管理器 -- 便捷导入路径。

实际实现位于 ``backend.services.graceful_shutdown``，此模块仅提供重导出。

使用方式::

    from backend.shutdown.graceful import get_shutdown_manager

    manager = get_shutdown_manager()
    manager.register_signal_handlers()

    # 在中间件中注册请求
    manager.request_started(request_id)
    try:
        response = await handle(request)
    finally:
        manager.request_finished(request_id)

    # 注册清理回调
    manager.register_cleanup("db", close_db_pool)
    manager.register_cleanup("redis", close_redis)
"""

from backend.services.graceful_shutdown import (
    CleanupCallback,
    GracefulShutdown,
    ShutdownStats,
    get_shutdown_manager,
    reset_shutdown_manager,
)

__all__ = [
    "CleanupCallback",
    "GracefulShutdown",
    "ShutdownStats",
    "get_shutdown_manager",
    "reset_shutdown_manager",
]
