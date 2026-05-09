"""CityFlow 优雅停机模块。

提供统一的导入路径::

    from backend.shutdown import GracefulShutdown, get_shutdown_manager
    from backend.shutdown import ShutdownMiddleware

实际实现位于 ``backend.services.graceful_shutdown`` 和
``backend.middleware.shutdown``，此包仅为便捷入口。
"""

from backend.middleware.shutdown import ShutdownMiddleware
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
    "ShutdownMiddleware",
    "ShutdownStats",
    "get_shutdown_manager",
    "reset_shutdown_manager",
]
