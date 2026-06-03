"""CityFlow 连接池监控。

聚合数据库、HTTP、Redis 连接池的统计信息，提供：
- 统一的统计查询接口
- 健康检查（数据库 ping + HTTP 连接状态 + Redis ping）
- 告警阈值检测（连接池使用率过高）
- 历史统计采集（用于 Prometheus 等监控系统）
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from backend.config.pool_config import pool_settings
from backend.database.pool import DatabasePool, PoolStats, get_database_pool
from backend.services.http_pool import HTTPPool, HTTPPoolStats, get_http_pool

logger = logging.getLogger(__name__)

__all__ = [
    "PoolHealthReport",
    "PoolMonitor",
    "get_pool_monitor",
]


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PoolHealthReport:
    """连接池健康报告。"""

    database_healthy: bool
    http_healthy: bool
    redis_healthy: bool
    database_stats: PoolStats
    http_stats: HTTPPoolStats
    warnings: list[str]

    @property
    def all_healthy(self) -> bool:
        return self.database_healthy and self.http_healthy and self.redis_healthy


@dataclass(slots=True)
class PoolHistoryEntry:
    """历史统计条目。"""

    timestamp: float
    db_checked_out: int
    db_pool_size: int
    db_utilization: float


# ---------------------------------------------------------------------------
# 监控器
# ---------------------------------------------------------------------------


class PoolMonitor:
    """连接池监控器。

    Args:
        db_pool: 数据库连接池实例。
        http_pool: HTTP 连接池实例。
        utilization_warn_threshold: 使用率告警阈值（0.0 ~ 1.0）。
        history_max_size: 历史记录最大条数。
    """

    def __init__(
        self,
        db_pool: DatabasePool,
        http_pool: HTTPPool,
        utilization_warn_threshold: float = pool_settings.utilization_warn_threshold,
        history_max_size: int = 360,
    ) -> None:
        self._db_pool = db_pool
        self._http_pool = http_pool
        self._threshold = utilization_warn_threshold
        self._history: list[PoolHistoryEntry] = []
        self._history_max = history_max_size

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    async def get_stats(self) -> dict[str, Any]:
        """获取全部连接池统计信息。"""
        db_stats = self._db_pool.get_stats_dict()
        http_stats = self._http_pool.get_stats_dict()
        return {
            "database": db_stats,
            "http": http_stats,
        }

    def collect_stats(self) -> None:
        """采集当前统计到历史记录（纯内存操作，无网络调用）。"""
        db_stats = self._db_pool.get_stats()
        entry = PoolHistoryEntry(
            timestamp=time.time(),
            db_checked_out=db_stats.checked_out,
            db_pool_size=db_stats.pool_size,
            db_utilization=db_stats.utilization,
        )
        self._history.append(entry)
        # 保持上限
        if len(self._history) > self._history_max:
            self._history = self._history[-self._history_max :]

    def get_history(self, last_n: int = 60) -> list[dict[str, Any]]:
        """获取最近 N 条历史统计。"""
        entries = self._history[-last_n:] if last_n > 0 else self._history
        return [
            {
                "timestamp": e.timestamp,
                "db_checked_out": e.db_checked_out,
                "db_pool_size": e.db_pool_size,
                "db_utilization": round(e.db_utilization, 3),
            }
            for e in entries
        ]

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    async def check_health(self) -> PoolHealthReport:
        """执行全面健康检查，返回报告。"""
        warnings: list[str] = []

        # 数据库
        db_healthy = await self._db_pool.ping()
        db_stats = self._db_pool.get_stats()
        if not db_healthy:
            warnings.append("数据库连接 ping 失败")
        elif db_stats.utilization >= self._threshold:
            warnings.append(
                f"数据库连接池使用率过高: {db_stats.utilization:.1%} "
                f"(阈值 {self._threshold:.0%})"
            )

        # HTTP
        http_stats = self._http_pool.get_stats()
        http_healthy = not self._http_pool._client.is_closed

        # Redis（可选，失败不阻塞）
        redis_healthy = await self._check_redis()

        return PoolHealthReport(
            database_healthy=db_healthy,
            http_healthy=http_healthy,
            redis_healthy=redis_healthy,
            database_stats=db_stats,
            http_stats=http_stats,
            warnings=warnings,
        )

    def report(self) -> dict[str, Any]:
        """生成快速报告（不做网络调用，纯内存读取）。"""
        db_stats = self._db_pool.get_stats()
        return {
            "database": self._db_pool.get_stats_dict(),
            "http": self._http_pool.get_stats_dict(),
            "warnings": self._collect_warnings(db_stats),
        }

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _collect_warnings(self, db_stats: PoolStats) -> list[str]:
        """检查是否有需要告警的指标。"""
        warnings: list[str] = []
        if db_stats.utilization >= self._threshold:
            warnings.append(
                f"数据库连接池使用率: {db_stats.utilization:.1%} " f"(阈值 {self._threshold:.0%})"
            )
        return warnings

    @staticmethod
    async def _check_redis() -> bool:
        """检查 Redis 连接可用性。"""
        try:
            import redis.asyncio as aioredis

            from backend.config import settings

            r = aioredis.from_url(
                f"redis://{settings.redis.host}:{settings.redis.port}/{settings.redis.db}",
                socket_connect_timeout=pool_settings.redis_socket_connect_timeout,
            )
            await r.ping()
            await r.aclose()
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_monitor: PoolMonitor | None = None


def get_pool_monitor() -> PoolMonitor:
    """获取全局连接池监控器单例。"""
    global _monitor
    if _monitor is None:
        _monitor = PoolMonitor(
            db_pool=get_database_pool(),
            http_pool=get_http_pool(),
        )
    return _monitor
