"""CityFlow 数据库连接池优化。

对 backend.database.base 的异步引擎进行池化参数调优，
并通过 Prometheus 指标暴露连接池状态。

关键优化：
  - pool_recycle: 定期回收空闲连接，避免 PostgreSQL 超时断开
  - pool_pre_ping: 每次取连接前执行 SELECT 1 探活
  - pool_timeout: 获取连接的最大等待时间
  - 连接池指标自动上报 Prometheus
  - ping: 轻量级健康检查
"""

from __future__ import annotations

import logging
from typing import Any

from prometheus_client import Gauge
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus 指标
# ---------------------------------------------------------------------------

DB_POOL_SIZE = Gauge(
    "cityflow_db_pool_size",
    "Database connection pool size",
)

DB_POOL_CHECKED_IN = Gauge(
    "cityflow_db_pool_checked_in",
    "Database connections checked in (idle)",
)

DB_POOL_CHECKED_OUT = Gauge(
    "cityflow_db_pool_checked_out",
    "Database connections checked out (in use)",
)

DB_POOL_OVERFLOW = Gauge(
    "cityflow_db_pool_overflow",
    "Database connections above pool_size",
)

DB_POOL_INVALIDATED = Gauge(
    "cityflow_db_pool_invalidated_total",
    "Total invalidated database connections",
)


class DatabasePool:
    """异步数据库连接池。

    封装 SQLAlchemy async engine 的创建和生命周期管理，
    提供连接池状态查询和 Prometheus 指标上报。

    Args:
        database_url: 异步数据库连接串 (postgresql+asyncpg://...)。
        pool_size: 常驻连接数，默认 10。
        max_overflow: 最大溢出连接数，默认 20。
        pool_recycle: 连接回收秒数，默认 3600。
        pool_timeout: 获取连接超时秒数，默认 30。
        echo: 是否打印 SQL，默认 False。
    """

    def __init__(
        self,
        database_url: str,
        *,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_recycle: int = 3600,
        pool_timeout: int = 30,
        echo: bool = False,
    ) -> None:
        self._engine: AsyncEngine = create_async_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            pool_recycle=pool_recycle,
            pool_timeout=pool_timeout,
            echo=echo,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info(
            "数据库连接池已创建: pool_size=%d, max_overflow=%d, recycle=%ds",
            pool_size,
            max_overflow,
            pool_recycle,
        )

    @property
    def engine(self) -> AsyncEngine:
        """底层异步引擎。"""
        return self._engine

    async def get_session(self) -> AsyncSession:
        """获取一个异步数据库会话。

        调用方负责关闭会话，推荐配合 async with 使用::

            async with db_pool.session_scope() as session:
                result = await session.execute(...)

        Returns:
            AsyncSession 实例。
        """
        return self._session_factory()

    def session_scope(self) -> _SessionContextManager:
        """返回一个上下文管理器，自动 commit/rollback 并关闭会话。"""
        return _SessionContextManager(self._session_factory)

    async def ping(self) -> bool:
        """执行轻量级查询验证连接可用性。

        Returns:
            True 表示连接正常，False 表示连接异常。
        """
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("数据库连接健康检查失败")
            return False

    def get_pool_stats(self) -> dict[str, int]:
        """获取连接池当前状态并上报 Prometheus。

        Returns:
            包含 pool_size, checkedin, checkedout, overflow 的字典。
        """
        pool = self._engine.pool
        stats = {
            "pool_size": pool.size(),
            "checkedin": pool.checkedin(),
            "checkedout": pool.checkedout(),
            "overflow": pool.overflow(),
        }

        # 上报 Prometheus
        DB_POOL_SIZE.set(stats["pool_size"])
        DB_POOL_CHECKED_IN.set(stats["checkedin"])
        DB_POOL_CHECKED_OUT.set(stats["checkedout"])
        DB_POOL_OVERFLOW.set(stats["overflow"])

        return stats

    async def close(self) -> None:
        """释放所有连接池资源。"""
        await self._engine.dispose()
        logger.info("数据库连接池已关闭")

    async def __aenter__(self) -> DatabasePool:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


class _SessionContextManager:
    """AsyncSession 上下文管理器，自动处理事务和关闭。"""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        self._session = self._factory()
        return self._session

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._session is None:
            return
        try:
            if exc_type is not None:
                await self._session.rollback()
            else:
                await self._session.commit()
        finally:
            await self._session.close()
