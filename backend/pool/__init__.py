"""CityFlow 连接池优化模块。

提供数据库连接池、HTTP 连接池的优化配置和统一监控。
与 backend.database.base 的异步引擎和 backend.monitoring.prometheus
的指标体系集成。

Usage:
    from backend.pool import DatabasePool, HTTPPool, PoolMonitor

    db_pool = DatabasePool(database_url)
    http_pool = HTTPPool()
    monitor = PoolMonitor(db_pool, http_pool)

    # 或使用 PoolManager 统一管理生命周期
    async with PoolManager(db_pool, http_pool) as manager:
        session = await db_pool.get_session()
        ...
"""

from __future__ import annotations

from backend.pool.database import DatabasePool
from backend.pool.http import HTTPPool
from backend.pool.monitor import (
    AlertSeverity,
    AlertThresholds,
    PoolAlert,
    PoolHealthReport,
    PoolManager,
    PoolMonitor,
    get_pool_monitor,
)

__all__ = [
    "AlertSeverity",
    "AlertThresholds",
    "DatabasePool",
    "HTTPPool",
    "PoolAlert",
    "PoolHealthReport",
    "PoolManager",
    "PoolMonitor",
    "get_pool_monitor",
]
