"""CityFlow 连接池监控。

定期采集数据库和 HTTP 连接池的状态指标，
暴露 Prometheus Gauge 并提供 JSON 摘要。

与 backend.monitoring.prometheus 的指标命名体系保持一致。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from prometheus_client import Gauge

if TYPE_CHECKING:
    from backend.pool.database import DatabasePool
    from backend.pool.http import HTTPPool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus 指标
# ---------------------------------------------------------------------------

POOL_MONITOR_SCRAPE_INTERVAL = Gauge(
    "cityflow_pool_monitor_scrape_interval_seconds",
    "Pool monitor scrape interval in seconds",
)

POOL_MONITOR_LAST_SCRAPE = Gauge(
    "cityflow_pool_monitor_last_scrape_timestamp",
    "Timestamp of last pool stats scrape",
)

POOL_HEALTH_STATUS = Gauge(
    "cityflow_pool_health_status",
    "Pool health status (1=healthy, 0=unhealthy)",
    ["pool_type"],
)

POOL_ALERT_COUNT = Gauge(
    "cityflow_pool_alert_count",
    "Number of active pool alerts",
    ["severity"],
)


# ---------------------------------------------------------------------------
# 告警
# ---------------------------------------------------------------------------


class AlertSeverity(StrEnum):
    """告警级别。"""

    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class PoolAlert:
    """连接池告警条目。"""

    pool_type: str
    message: str
    severity: AlertSeverity
    metric_name: str
    metric_value: float
    threshold: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_type": self.pool_type,
            "message": self.message,
            "severity": self.severity.value,
            "metric_name": self.metric_name,
            "metric_value": round(self.metric_value, 3),
            "threshold": round(self.threshold, 3),
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True, slots=True)
class AlertThresholds:
    """告警阈值配置。"""

    db_utilization_warn: float = 0.7
    db_utilization_critical: float = 0.9
    http_active_warn: float = 0.8
    http_active_critical: float = 0.95


@dataclass(frozen=True, slots=True)
class PoolHealthReport:
    """连接池健康检查报告。"""

    healthy: bool
    issues: list[str]
    database: dict[str, Any]
    http: dict[str, Any]
    alerts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "issues": self.issues,
            "database": self.database,
            "http": self.http,
            "alerts": self.alerts,
        }


@dataclass(slots=True)
class HistoryEntry:
    """历史统计条目。"""

    timestamp: float
    db_checkedout: int
    db_pool_size: int
    db_utilization: float
    http_active: int
    http_max: int
    alert_count: int


# ---------------------------------------------------------------------------
# 监控器
# ---------------------------------------------------------------------------


class PoolMonitor:
    """连接池监控器。

    收集数据库和 HTTP 连接池的运行指标，提供：
    - Prometheus 指标上报
    - JSON 摘要输出
    - 阈值告警（warning / critical）
    - 历史统计采集
    - 健康检查

    Args:
        db_pool: 数据库连接池实例。
        http_pool: HTTP 连接池实例。
        scrape_interval: 采集间隔秒数，默认 15。
        thresholds: 告警阈值配置。
        history_max_size: 历史记录最大条数，默认 360（1 小时 @ 15s 间隔）。
    """

    def __init__(
        self,
        db_pool: DatabasePool | None = None,
        http_pool: HTTPPool | None = None,
        *,
        scrape_interval: float = 15.0,
        thresholds: AlertThresholds | None = None,
        history_max_size: int = 360,
    ) -> None:
        self._db_pool = db_pool
        self._http_pool = http_pool
        self._scrape_interval = scrape_interval
        self._thresholds = thresholds or AlertThresholds()
        self._history: list[HistoryEntry] = []
        self._history_max = history_max_size
        self._task: asyncio.Task[None] | None = None
        self._running = False

        POOL_MONITOR_SCRAPE_INTERVAL.set(scrape_interval)

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """获取所有连接池的当前状态快照。

        Returns:
            包含 database 和 http 两个子字典的统计信息。
        """
        result: dict[str, Any] = {}

        if self._db_pool is not None:
            try:
                db_stats = self._db_pool.get_pool_stats()
                result["database"] = db_stats

                # 健康判定: checkedout 不超过 pool_size + max_overflow
                pool_ok = db_stats["checkedout"] <= db_stats["pool_size"] + db_stats.get(
                    "overflow", 0
                )
                POOL_HEALTH_STATUS.labels(pool_type="database").set(1 if pool_ok else 0)
            except Exception:
                logger.exception("获取数据库连接池指标失败")
                POOL_HEALTH_STATUS.labels(pool_type="database").set(0)
                result["database"] = {"error": "获取失败"}

        if self._http_pool is not None:
            try:
                http_stats = self._http_pool.get_pool_stats()
                result["http"] = http_stats
                POOL_HEALTH_STATUS.labels(pool_type="http").set(1)
            except Exception:
                logger.exception("获取 HTTP 连接池指标失败")
                POOL_HEALTH_STATUS.labels(pool_type="http").set(0)
                result["http"] = {"error": "获取失败"}

        return result

    # ------------------------------------------------------------------
    # 告警
    # ------------------------------------------------------------------

    def check_alerts(self) -> list[PoolAlert]:
        """检查所有连接池是否有指标超过告警阈值。

        Returns:
            当前活跃的告警列表。
        """
        alerts: list[PoolAlert] = []

        # 数据库连接池告警
        if self._db_pool is not None:
            try:
                db_stats = self._db_pool.get_pool_stats()
                pool_size = db_stats["pool_size"]
                checked_out = db_stats["checkedout"]
                overflow = db_stats.get("overflow", 0)
                total = pool_size + overflow

                if total > 0:
                    utilization = checked_out / total
                    if utilization >= self._thresholds.db_utilization_critical:
                        alerts.append(
                            PoolAlert(
                                pool_type="database",
                                message=f"数据库连接池使用率严重过高: {utilization:.1%}",
                                severity=AlertSeverity.CRITICAL,
                                metric_name="utilization",
                                metric_value=utilization,
                                threshold=self._thresholds.db_utilization_critical,
                            )
                        )
                    elif utilization >= self._thresholds.db_utilization_warn:
                        alerts.append(
                            PoolAlert(
                                pool_type="database",
                                message=f"数据库连接池使用率偏高: {utilization:.1%}",
                                severity=AlertSeverity.WARNING,
                                metric_name="utilization",
                                metric_value=utilization,
                                threshold=self._thresholds.db_utilization_warn,
                            )
                        )
            except Exception:
                logger.exception("数据库告警检查失败")

        # HTTP 连接池告警
        if self._http_pool is not None:
            try:
                http_stats = self._http_pool.get_pool_stats()
                max_conn = http_stats.get("max_connections", 0)
                active = http_stats.get("active", 0)

                if max_conn > 0:
                    utilization = active / max_conn
                    if utilization >= self._thresholds.http_active_critical:
                        alerts.append(
                            PoolAlert(
                                pool_type="http",
                                message=f"HTTP 连接池使用率严重过高: {utilization:.1%}",
                                severity=AlertSeverity.CRITICAL,
                                metric_name="utilization",
                                metric_value=utilization,
                                threshold=self._thresholds.http_active_critical,
                            )
                        )
                    elif utilization >= self._thresholds.http_active_warn:
                        alerts.append(
                            PoolAlert(
                                pool_type="http",
                                message=f"HTTP 连接池使用率偏高: {utilization:.1%}",
                                severity=AlertSeverity.WARNING,
                                metric_name="utilization",
                                metric_value=utilization,
                                threshold=self._thresholds.http_active_warn,
                            )
                        )
            except Exception:
                logger.exception("HTTP 告警检查失败")

        # 上报 Prometheus
        warning_count = sum(1 for a in alerts if a.severity == AlertSeverity.WARNING)
        critical_count = sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL)
        POOL_ALERT_COUNT.labels(severity="warning").set(warning_count)
        POOL_ALERT_COUNT.labels(severity="critical").set(critical_count)

        # 记录日志
        for alert in alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                logger.error("[连接池告警] %s", alert.message)
            else:
                logger.warning("[连接池告警] %s", alert.message)

        return alerts

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    def check_health(self) -> PoolHealthReport:
        """执行全面健康检查，返回报告（纯内存操作，无网络调用）。

        Returns:
            PoolHealthReport 实例。
        """
        issues: list[str] = []
        db_stats_dict: dict[str, Any] = {}
        http_stats_dict: dict[str, Any] = {}

        # 数据库
        if self._db_pool is not None:
            try:
                raw = self._db_pool.get_pool_stats()
                pool_size = raw["pool_size"]
                checked_in = raw["checkedin"]
                checked_out = raw["checkedout"]
                overflow = raw.get("overflow", 0)
                total = pool_size + overflow
                utilization = checked_out / total if total > 0 else 0.0

                db_stats_dict = {
                    "pool_size": pool_size,
                    "checked_in": checked_in,
                    "checked_out": checked_out,
                    "overflow": overflow,
                    "utilization": round(utilization, 3),
                    "healthy": checked_out <= pool_size + overflow,
                }

                if not db_stats_dict["healthy"]:
                    issues.append("数据库连接池已耗尽")
            except Exception:
                logger.exception("数据库健康检查失败")
                db_stats_dict = {"error": "获取失败", "healthy": False}
                issues.append("数据库连接池指标获取失败")

        # HTTP
        if self._http_pool is not None:
            try:
                raw = self._http_pool.get_pool_stats()
                max_conn = raw.get("max_connections", 0)
                active = raw.get("active", 0)
                keepalive = raw.get("keepalive", 0)
                utilization = active / max_conn if max_conn > 0 else 0.0

                http_stats_dict = {
                    "max_connections": max_conn,
                    "active": active,
                    "keepalive": keepalive,
                    "utilization": round(utilization, 3),
                    "healthy": True,
                }
            except Exception:
                logger.exception("HTTP 健康检查失败")
                http_stats_dict = {"error": "获取失败", "healthy": False}
                issues.append("HTTP 连接池指标获取失败")

        # 告警
        alerts = self.check_alerts()
        for alert in alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                issues.append(alert.message)

        healthy = len(issues) == 0
        return PoolHealthReport(
            healthy=healthy,
            issues=issues,
            database=db_stats_dict,
            http=http_stats_dict,
            alerts=[a.to_dict() for a in alerts],
        )

    # ------------------------------------------------------------------
    # 仪表盘
    # ------------------------------------------------------------------

    def get_dashboard(self) -> dict[str, Any]:
        """生成连接池仪表盘数据，包含统计、告警、健康和历史。

        Returns:
            仪表盘完整数据。
        """
        stats = self.get_stats()
        alerts = self.check_alerts()
        health = self.check_health()

        return {
            "stats": stats,
            "alerts": [a.to_dict() for a in alerts],
            "health": health.to_dict(),
            "history": self.get_history(last_n=60),
            "thresholds": {
                "db_utilization_warn": self._thresholds.db_utilization_warn,
                "db_utilization_critical": self._thresholds.db_utilization_critical,
                "http_active_warn": self._thresholds.http_active_warn,
                "http_active_critical": self._thresholds.http_active_critical,
            },
        }

    # ------------------------------------------------------------------
    # 历史采集
    # ------------------------------------------------------------------

    def collect_history(self) -> None:
        """采集当前统计到历史记录（纯内存操作）。"""
        db_checkedout = 0
        db_pool_size = 0
        db_utilization = 0.0
        http_active = 0
        http_max = 0
        alert_count = 0

        if self._db_pool is not None:
            try:
                raw = self._db_pool.get_pool_stats()
                db_pool_size = raw["pool_size"]
                db_checkedout = raw["checkedout"]
                overflow = raw.get("overflow", 0)
                total = db_pool_size + overflow
                db_utilization = db_checkedout / total if total > 0 else 0.0
            except Exception:
                logger.debug("db pool stats collection failed", exc_info=True)

        if self._http_pool is not None:
            try:
                raw = self._http_pool.get_pool_stats()
                http_max = raw.get("max_connections", 0)
                http_active = raw.get("active", 0)
            except Exception:
                logger.debug("http pool stats collection failed", exc_info=True)

        try:
            alerts = self.check_alerts()
            alert_count = len(alerts)
        except Exception:
            logger.debug("alert count collection failed", exc_info=True)

        entry = HistoryEntry(
            timestamp=time.time(),
            db_checkedout=db_checkedout,
            db_pool_size=db_pool_size,
            db_utilization=db_utilization,
            http_active=http_active,
            http_max=http_max,
            alert_count=alert_count,
        )
        self._history.append(entry)
        if len(self._history) > self._history_max:
            self._history = self._history[-self._history_max :]

    def get_history(self, last_n: int = 60) -> list[dict[str, Any]]:
        """获取最近 N 条历史统计。

        Args:
            last_n: 返回条数，0 表示全部。

        Returns:
            历史统计列表。
        """
        entries = self._history[-last_n:] if last_n > 0 else self._history
        return [
            {
                "timestamp": e.timestamp,
                "db_checkedout": e.db_checkedout,
                "db_pool_size": e.db_pool_size,
                "db_utilization": round(e.db_utilization, 3),
                "http_active": e.http_active,
                "http_max": e.http_max,
                "alert_count": e.alert_count,
            }
            for e in entries
        ]

    # ------------------------------------------------------------------
    # 定时采集
    # ------------------------------------------------------------------

    async def start_periodic_scrape(self) -> None:
        """启动后台定时采集任务。"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._scrape_loop())
        logger.info("连接池监控已启动，采集间隔 %.1fs", self._scrape_interval)

    async def stop_periodic_scrape(self) -> None:
        """停止后台定时采集任务。"""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("连接池监控已停止")

    async def _scrape_loop(self) -> None:
        """定时采集循环。"""
        while self._running:
            try:
                self.get_stats()
                self.collect_history()
                POOL_MONITOR_LAST_SCRAPE.set(time.time())
            except Exception:
                logger.exception("连接池指标采集异常")
            await asyncio.sleep(self._scrape_interval)

    async def close(self) -> None:
        """停止监控。"""
        await self.stop_periodic_scrape()


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_pool_monitor: PoolMonitor | None = None


def get_pool_monitor() -> PoolMonitor:
    """获取全局连接池监控器单例。"""
    global _pool_monitor
    if _pool_monitor is None:
        _pool_monitor = PoolMonitor()
    return _pool_monitor


def reset_pool_monitor() -> None:
    """重置全局单例（仅用于测试）。"""
    global _pool_monitor
    _pool_monitor = None


# ---------------------------------------------------------------------------
# PoolManager（生命周期管理器，保持向后兼容）
# ---------------------------------------------------------------------------


class PoolManager:
    """连接池统一生命周期管理器。

    以 async context manager 方式管理数据库连接池、HTTP 连接池和监控器
    的创建与销毁，确保资源正确释放。

    Usage:
        async with PoolManager(db_pool, http_pool) as manager:
            stats = manager.monitor.get_stats()
            session = await manager.db_pool.get_session()

    Args:
        db_pool: 数据库连接池。
        http_pool: HTTP 连接池。
        enable_monitor: 是否启用自动监控，默认 True。
        scrape_interval: 监控采集间隔秒数，默认 15。
    """

    def __init__(
        self,
        db_pool: DatabasePool | None = None,
        http_pool: HTTPPool | None = None,
        *,
        enable_monitor: bool = True,
        scrape_interval: float = 15.0,
    ) -> None:
        self.db_pool = db_pool
        self.http_pool = http_pool
        self.monitor: PoolMonitor | None = None

        if enable_monitor:
            self.monitor = PoolMonitor(
                db_pool=db_pool,
                http_pool=http_pool,
                scrape_interval=scrape_interval,
            )

    async def __aenter__(self) -> PoolManager:
        if self.monitor is not None:
            await self.monitor.start_periodic_scrape()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self.monitor is not None:
            await self.monitor.close()
        if self.http_pool is not None:
            await self.http_pool.close()
        if self.db_pool is not None:
            await self.db_pool.close()
