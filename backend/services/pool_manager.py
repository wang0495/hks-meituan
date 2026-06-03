"""CityFlow 统一连接池管理器。

聚合数据库、HTTP、Redis 连接池的生命周期管理，提供：
- 统一启动 / 关闭接口
- 连接池健康检查与统计
- 与 FastAPI lifespan 集成的钩子

用法::

    from backend.services.pool_manager import get_pool_manager

    manager = get_pool_manager()
    await manager.start_all()

    # 获取各池
    db_pool = manager.db_pool
    http_pool = manager.http_pool

    # 关闭
    await manager.close_all()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.config.pool_config import PoolSettings, pool_settings
from backend.database.pool import DatabasePool, get_database_pool
from backend.services.http_pool import HTTPPool, get_http_pool

logger = logging.getLogger(__name__)

__all__ = [
    "PoolManager",
    "PoolManagerStats",
    "get_pool_manager",
]


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PoolManagerStats:
    """连接池管理器统计快照。"""

    db_pool_size: int
    db_checked_out: int
    db_utilization: float
    http_max_connections: int
    http_max_keepalive: int
    redis_max_connections: int
    all_healthy: bool


# ---------------------------------------------------------------------------
# 管理器
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PoolManager:
    """统一连接池管理器。

    Args:
        config: 连接池配置。
    """

    config: PoolSettings = field(default_factory=lambda: pool_settings)

    _db_pool: DatabasePool = field(init=False, repr=False)
    _http_pool: HTTPPool = field(init=False, repr=False)
    _started: bool = field(default=False, init=False, repr=False)

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def db_pool(self) -> DatabasePool:
        """数据库连接池。"""
        return self._db_pool

    @property
    def http_pool(self) -> HTTPPool:
        """HTTP 连接池。"""
        return self._http_pool

    @property
    def is_started(self) -> bool:
        """是否已启动。"""
        return self._started

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start_all(self) -> None:
        """启动所有连接池。幂等。"""
        if self._started:
            return

        # 数据库连接池
        self._db_pool = get_database_pool()
        # 用 pool_config 覆盖默认参数
        self._db_pool.pool_size = self.config.db_pool_size
        self._db_pool.max_overflow = self.config.db_max_overflow
        self._db_pool.pool_recycle = self.config.db_pool_recycle
        await self._db_pool.start()

        # HTTP 连接池
        self._http_pool = get_http_pool()
        self._http_pool.max_connections = self.config.http_max_connections
        self._http_pool.max_keepalive_connections = self.config.http_max_keepalive
        self._http_pool.timeout = self.config.http_timeout
        await self._http_pool.start()

        self._started = True
        logger.info(
            "连接池管理器已启动 | db_pool=%d+%d, http_conn=%d, keepalive=%d",
            self.config.db_pool_size,
            self.config.db_max_overflow,
            self.config.http_max_connections,
            self.config.http_max_keepalive,
        )

    async def close_all(self) -> None:
        """关闭所有连接池。幂等，按依赖逆序关闭。"""
        if not self._started:
            return

        errors: list[str] = []

        # HTTP 先关（不依赖 DB）
        try:
            await self._http_pool.close()
            logger.info("HTTP 连接池已关闭")
        except Exception as e:
            msg = f"HTTP 连接池关闭失败: {e}"
            logger.exception(msg)
            errors.append(msg)

        # DB 后关
        try:
            await self._db_pool.close()
            logger.info("数据库连接池已关闭")
        except Exception as e:
            msg = f"数据库连接池关闭失败: {e}"
            logger.exception(msg)
            errors.append(msg)

        self._started = False

        if errors:
            logger.warning("连接池关闭完成，但有 %d 个错误", len(errors))
        else:
            logger.info("所有连接池已关闭")

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    async def check_health(self) -> dict[str, Any]:
        """全面健康检查，返回各池状态。"""
        db_ok = await self._db_pool.ping()
        http_ok = not self._http_pool._client.is_closed

        warnings: list[str] = []
        if not db_ok:
            warnings.append("数据库连接 ping 失败")
        if not http_ok:
            warnings.append("HTTP 连接池已关闭")

        # 检查使用率
        db_stats = self._db_pool.get_stats()
        threshold = self.config.utilization_warn_threshold
        if db_stats.utilization >= threshold:
            warnings.append(
                f"数据库连接池使用率过高: {db_stats.utilization:.1%} " f"(阈值 {threshold:.0%})"
            )

        return {
            "all_healthy": db_ok and http_ok and len(warnings) == 0,
            "database": {"healthy": db_ok, **self._db_pool.get_stats_dict()},
            "http": {"healthy": http_ok, **self._http_pool.get_stats_dict()},
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> PoolManagerStats:
        """获取连接池统计快照。"""
        db_stats = self._db_pool.get_stats()
        return PoolManagerStats(
            db_pool_size=db_stats.pool_size,
            db_checked_out=db_stats.checked_out,
            db_utilization=db_stats.utilization,
            http_max_connections=self._http_pool.max_connections,
            http_max_keepalive=self._http_pool.max_keepalive_connections,
            redis_max_connections=self.config.redis_max_connections,
            all_healthy=True,
        )

    def get_stats_dict(self) -> dict[str, Any]:
        """以字典形式返回统计信息。"""
        return {
            "database": self._db_pool.get_stats_dict(),
            "http": self._http_pool.get_stats_dict(),
            "redis": {
                "max_connections": self.config.redis_max_connections,
            },
            "config": {
                "db_pool_size": self.config.db_pool_size,
                "db_max_overflow": self.config.db_max_overflow,
                "db_pool_recycle": self.config.db_pool_recycle,
                "http_max_connections": self.config.http_max_connections,
                "http_max_keepalive": self.config.http_max_keepalive,
                "http_timeout": self.config.http_timeout,
            },
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_pool_manager: PoolManager | None = None


def get_pool_manager() -> PoolManager:
    """获取全局连接池管理器单例。"""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = PoolManager()
    return _pool_manager


def reset_pool_manager() -> None:
    """重置全局单例（仅用于测试）。"""
    global _pool_manager
    _pool_manager = None
