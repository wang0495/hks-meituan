"""CityFlow 停机感知中间件 -- 便捷导入路径。

实际实现位于 ``backend.middleware.shutdown``，此模块仅提供重导出。

使用方式::

    from backend.shutdown.middleware import ShutdownMiddleware

    app.add_middleware(ShutdownMiddleware)
"""

from backend.middleware.shutdown import ShutdownMiddleware

__all__ = ["ShutdownMiddleware"]
