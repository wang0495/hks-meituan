"""CityFlow 数据库连接池管理。

复用 backend.database.base 的全局共享引擎，提供：
- 连接池监控（统计、健康检查）
- 会话管理（兼容接口）
- 连接池统计信息

注意：本模块不再创建独立的 AsyncEngine，避免重复连接池。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

# no longer creates its own engine — uses shared engine from base.py
from backend.config import settings
from backend.config.pool_config import pool_settings
from backend.database.base import async_session_factory as _shared_session_factory
from backend.database.base import engine as _shared_engine

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import Pool

logger = logging.getLogger(__name__)

__all__ = [
    "DatabasePool",
    "PoolStats",
    "get_database_pool",
]


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PoolStats:
    """连接池统计快照。"""

    pool_size: int
    checked_in: int
    checked_out: int
    overflow: int

    @property
    def utilization(self) -> float:
        """连接池使用率（0.0 ~ 1.0）。"""
        total = self.pool_size + self.overflow
        if total == 0:
            return 0.0
        return self.checked_out / total


@dataclass(slots=True)
class DatabasePool:
    """数据库连接池。

    Args:
        database_url: 异步数据库连接 URL。
        pool_size: 核心连接数。
        max_overflow: 超出 pool_size 后的最大临时连接数。
        pool_recycle: 连接回收周期（秒），避免数据库端超时断开。
    """

    database_url: str
    pool_size: int = pool_settings.db_pool_size
    max_overflow: int = pool_settings.db_max_overflow
    pool_recycle: int = pool_settings.db_pool_recycle

    engine: AsyncEngine = field(init=False, repr=False)
    session_factory: async_sessionmaker[AsyncSession] = field(init=False, repr=False)
    _started: bool = field(default=False, init=False, repr=False)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """关联共享引擎与会话工厂。幂等，重复调用无副作用。

        使用 backend.database.base 中已创建的全局引擎，
        避免创建重复连接池。
        """
        if self._started:
            return

        self.engine = _shared_engine
        self.session_factory = _shared_session_factory
        self._started = True
        logger.info(
            "数据库连接池已关联 | pool_size=%d, max_overflow=%d (shared engine)",
            self.pool_size,
            self.max_overflow,
        )

    async def close(self) -> None:
        """关闭连接池，释放所有连接。幂等。"""
        if not self._started:
            return

        await self.engine.dispose()
        self._started = False
        logger.info("数据库连接池已关闭")

    # ------------------------------------------------------------------
    # 会话
    # ------------------------------------------------------------------

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话（上下文管理器）。

        用法::

            async for session in pool.get_session():
                ...
        """
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """执行轻量级查询验证连接可用性。"""
        if not self._started:
            return False

        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("数据库连接健康检查失败")
            return False

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> PoolStats:
        """获取连接池统计快照。"""
        pool: Pool = self.engine.pool
        return PoolStats(
            pool_size=pool.size(),
            checked_in=pool.checkedin(),
            checked_out=pool.checkedout(),
            overflow=pool.overflow(),
        )

    def get_stats_dict(self) -> dict[str, Any]:
        """以字典形式返回统计信息。"""
        stats = self.get_stats()
        return {
            "pool_size": stats.pool_size,
            "checked_in": stats.checked_in,
            "checked_out": stats.checked_out,
            "overflow": stats.overflow,
            "utilization": round(stats.utilization, 3),
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_db_pool: DatabasePool | None = None


def get_database_pool() -> DatabasePool:
    """获取全局数据库连接池单例。"""
    global _db_pool
    if _db_pool is None:
        _db = settings.database
        url = (
            f"postgresql+asyncpg://{_db.user}:{_db.password}"
            f"@{_db.host}:{_db.port}/{_db.database}"
        )
        _db_pool = DatabasePool(database_url=url)
    return _db_pool
