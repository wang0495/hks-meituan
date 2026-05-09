"""CityFlow 系统资源监控器。

提供系统级资源指标采集与告警规则引擎，包括：
- CPU / 内存 / 磁盘 / 网络指标采集
- 可配置的告警规则（阈值比较）
- 告警回调通知（异步）
- 告警冷却期（防止同一规则短时间内重复触发）

使用示例::

    from backend.services.resource_monitor import get_resource_monitor

    monitor = get_resource_monitor()
    monitor.add_rule("high_cpu", "cpu_percent", threshold=80.0)
    await monitor.start_monitoring(interval=30)

停机时调用 ``await monitor.stop_monitoring()`` 或依赖
``GracefulShutdown`` 注册的清理回调自动停止。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Coroutine

import psutil

logger = logging.getLogger(__name__)

__all__ = [
    "AlertRule",
    "AlertSeverity",
    "ResourceMetrics",
    "ResourceMonitor",
    "get_resource_monitor",
    "reset_resource_monitor",
]

# ---------------------------------------------------------------------------
# 告警冷却期（秒）：同一规则在此时间内不会重复触发
# ---------------------------------------------------------------------------
_DEFAULT_COOLDOWN_SECONDS: float = 300.0


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


class AlertSeverity(StrEnum):
    """告警严重程度。"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ComparisonOperator(StrEnum):
    """阈值比较运算符。"""

    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    EQ = "=="
    NE = "!="


@dataclass(frozen=True, slots=True)
class ResourceMetrics:
    """系统资源快照。"""

    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    net_bytes_sent: int
    net_bytes_recv: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_used_mb": round(self.memory_used_mb, 1),
            "memory_total_mb": round(self.memory_total_mb, 1),
            "disk_percent": self.disk_percent,
            "disk_used_gb": round(self.disk_used_gb, 2),
            "disk_total_gb": round(self.disk_total_gb, 2),
            "net_bytes_sent": self.net_bytes_sent,
            "net_bytes_recv": self.net_bytes_recv,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AlertRule:
    """告警规则。

    Attributes:
        name: 规则唯一名称，如 ``"high_cpu"``
        metric: 对应 ``ResourceMetrics`` 的字段名
        threshold: 阈值
        operator: 比较运算符，默认 ``>``（当前值大于阈值时触发）
        severity: 告警严重程度
        cooldown_seconds: 冷却期（秒），同一规则在此时间内不重复触发
    """

    name: str
    metric: str
    threshold: float
    operator: str = ComparisonOperator.GT
    severity: AlertSeverity = AlertSeverity.WARNING
    cooldown_seconds: float = _DEFAULT_COOLDOWN_SECONDS


@dataclass
class AlertEvent:
    """告警事件。

    Attributes:
        rule_name: 触发的规则名称
        metric: 指标字段名
        current_value: 当前指标值
        threshold: 阈值
        severity: 严重程度
        message: 告警消息
        timestamp: 触发时间
    """

    rule_name: str
    metric: str
    current_value: float
    threshold: float
    severity: AlertSeverity
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "rule_name": self.rule_name,
            "metric": self.metric,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


# 告警回调类型：接收 AlertEvent 对象
AlertCallback = Callable[[AlertEvent], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# 比较运算符映射
# ---------------------------------------------------------------------------

_COMPARISON_TABLE: dict[str, Callable[[float, float], bool]] = {
    ComparisonOperator.GT: lambda a, b: a > b,
    ComparisonOperator.GE: lambda a, b: a >= b,
    ComparisonOperator.LT: lambda a, b: a < b,
    ComparisonOperator.LE: lambda a, b: a <= b,
    ComparisonOperator.EQ: lambda a, b: a == b,
    ComparisonOperator.NE: lambda a, b: a != b,
}


# ---------------------------------------------------------------------------
# 指标采集
# ---------------------------------------------------------------------------


def collect_metrics(disk_path: str = "/") -> ResourceMetrics:
    """采集当前系统资源指标。

    Args:
        disk_path: 磁盘挂载路径（Windows 下无效，使用所有磁盘）。

    Returns:
        系统资源快照。
    """
    mem = psutil.virtual_memory()
    # Windows 上 psutil.disk_usage("/") 实际返回 C: 盘
    disk = psutil.disk_usage(disk_path)
    net = psutil.net_io_counters()

    return ResourceMetrics(
        cpu_percent=psutil.cpu_percent(interval=0.5),
        memory_percent=mem.percent,
        memory_used_mb=mem.used / (1024 * 1024),
        memory_total_mb=mem.total / (1024 * 1024),
        disk_percent=disk.percent,
        disk_used_gb=disk.used / (1024**3),
        disk_total_gb=disk.total / (1024**3),
        net_bytes_sent=net.bytes_sent,
        net_bytes_recv=net.bytes_recv,
    )


# ---------------------------------------------------------------------------
# 监控器
# ---------------------------------------------------------------------------


class ResourceMonitor:
    """系统资源监控器。

    职责：
    - 定期采集系统资源指标
    - 按配置的告警规则评估指标
    - 触发告警回调（日志 + 自定义通知）

    Args:
        disk_path: 磁盘采集路径。
    """

    def __init__(self, disk_path: str = "/") -> None:
        self._disk_path = disk_path
        self._rules: dict[str, AlertRule] = {}
        self._callbacks: list[AlertCallback] = []
        self._cooldown_tracker: dict[str, datetime] = {}
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._latest_metrics: ResourceMetrics | None = None

    # ------------------------------------------------------------------
    # 规则管理
    # ------------------------------------------------------------------

    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则。

        如果已存在同名规则，会被覆盖。

        Args:
            rule: 告警规则实例。
        """
        self._rules[rule.name] = rule
        logger.info(
            "添加告警规则: %s (%s %s %.1f)",
            rule.name,
            rule.metric,
            rule.operator,
            rule.threshold,
        )

    def remove_rule(self, name: str) -> bool:
        """移除告警规则。

        Args:
            name: 规则名称。

        Returns:
            是否成功移除（规则不存在返回 False）。
        """
        if name in self._rules:
            del self._rules[name]
            self._cooldown_tracker.pop(name, None)
            logger.info("移除告警规则: %s", name)
            return True
        return False

    def get_rules(self) -> list[AlertRule]:
        """获取所有告警规则列表。"""
        return list(self._rules.values())

    # ------------------------------------------------------------------
    # 回调管理
    # ------------------------------------------------------------------

    def add_callback(self, callback: AlertCallback) -> None:
        """注册告警回调。

        回调将在告警触发时被异步调用，单个回调异常不影响其他回调。

        Args:
            callback: 异步回调 ``(event: AlertEvent) -> None``
        """
        self._callbacks.append(callback)
        logger.debug("注册告警回调: %s", callback.__qualname__)

    # ------------------------------------------------------------------
    # 监控生命周期
    # ------------------------------------------------------------------

    async def start_monitoring(self, interval: int = 60) -> None:
        """启动后台监控循环。

        以 ``asyncio.create_task`` 方式启动，不阻塞调用方。
        重复调用不会创建多个任务。

        Args:
            interval: 采集间隔（秒），默认 60。
        """
        if self._running:
            logger.warning("资源监控已在运行，忽略重复启动")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop(interval))
        logger.info("资源监控已启动，采集间隔 %ds", interval)

    async def stop_monitoring(self) -> None:
        """停止后台监控循环。"""
        if not self._running:
            return

        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("资源监控已停止")

    @property
    def is_running(self) -> bool:
        """监控是否正在运行。"""
        return self._running

    # ------------------------------------------------------------------
    # 指标查询
    # ------------------------------------------------------------------

    @property
    def latest_metrics(self) -> ResourceMetrics | None:
        """最近一次采集的指标快照。"""
        return self._latest_metrics

    def get_current_metrics(self) -> ResourceMetrics:
        """立即采集一次指标并返回。"""
        return collect_metrics(self._disk_path)

    # ------------------------------------------------------------------
    # 内部循环
    # ------------------------------------------------------------------

    async def _monitor_loop(self, interval: int) -> None:
        """后台监控主循环。"""
        while self._running:
            try:
                metrics = collect_metrics(self._disk_path)
                self._latest_metrics = metrics
                await self._evaluate_rules(metrics)
            except Exception:
                logger.exception("资源采集或告警评估异常")
            await asyncio.sleep(interval)

    async def _evaluate_rules(self, metrics: ResourceMetrics) -> None:
        """评估所有告警规则。"""
        metrics_dict = metrics.to_dict()
        now = datetime.now(timezone.utc)

        for rule in self._rules.values():
            value = metrics_dict.get(rule.metric)
            if value is None or not isinstance(value, (int, float)):
                continue

            compare = _COMPARISON_TABLE.get(rule.operator)
            if compare is None:
                logger.warning("未知比较运算符: %s", rule.operator)
                continue

            if not compare(float(value), rule.threshold):
                continue

            # 检查冷却期
            last_fired = self._cooldown_tracker.get(rule.name)
            if last_fired is not None:
                elapsed = (now - last_fired).total_seconds()
                if elapsed < rule.cooldown_seconds:
                    logger.debug(
                        "告警 %s 在冷却期内（%.0fs / %.0fs），跳过",
                        rule.name,
                        elapsed,
                        rule.cooldown_seconds,
                    )
                    continue

            # 触发告警
            self._cooldown_tracker[rule.name] = now
            await self._fire_alert(rule, float(value))

    async def _fire_alert(self, rule: AlertRule, current_value: float) -> None:
        """触发告警并通知所有回调。"""
        event = AlertEvent(
            rule_name=rule.name,
            metric=rule.metric,
            current_value=current_value,
            threshold=rule.threshold,
            severity=rule.severity,
            message=(
                f"[{rule.severity.upper()}] 告警: {rule.name} - "
                f"{rule.metric} 当前值 {current_value:.1f}，"
                f"阈值 {rule.operator} {rule.threshold:.1f}"
            ),
        )

        logger.warning(
            "告警触发: %s | %s=%s %s %s",
            rule.name,
            rule.metric,
            current_value,
            rule.operator,
            rule.threshold,
        )

        for callback in self._callbacks:
            try:
                await callback(event)
            except Exception:
                logger.exception("告警回调异常: %s", callback.__qualname__)

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """返回监控器当前状态。"""
        return {
            "running": self._running,
            "rules_count": len(self._rules),
            "callbacks_count": len(self._callbacks),
            "latest_metrics": (
                self._latest_metrics.to_dict()
                if self._latest_metrics is not None
                else None
            ),
        }


# ---------------------------------------------------------------------------
# 预定义告警规则
# ---------------------------------------------------------------------------

DEFAULT_RULES: list[AlertRule] = [
    AlertRule(
        name="high_cpu",
        metric="cpu_percent",
        threshold=80.0,
        operator=ComparisonOperator.GT,
        severity=AlertSeverity.WARNING,
    ),
    AlertRule(
        name="critical_cpu",
        metric="cpu_percent",
        threshold=95.0,
        operator=ComparisonOperator.GT,
        severity=AlertSeverity.CRITICAL,
    ),
    AlertRule(
        name="high_memory",
        metric="memory_percent",
        threshold=85.0,
        operator=ComparisonOperator.GT,
        severity=AlertSeverity.WARNING,
    ),
    AlertRule(
        name="critical_memory",
        metric="memory_percent",
        threshold=95.0,
        operator=ComparisonOperator.GT,
        severity=AlertSeverity.CRITICAL,
    ),
    AlertRule(
        name="high_disk",
        metric="disk_percent",
        threshold=90.0,
        operator=ComparisonOperator.GT,
        severity=AlertSeverity.WARNING,
    ),
    AlertRule(
        name="critical_disk",
        metric="disk_percent",
        threshold=95.0,
        operator=ComparisonOperator.GT,
        severity=AlertSeverity.CRITICAL,
    ),
]


def _load_default_rules(monitor: ResourceMonitor) -> None:
    """将预定义规则加载到监控器。"""
    for rule in DEFAULT_RULES:
        monitor.add_rule(rule)


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_monitor: ResourceMonitor | None = None


def get_resource_monitor() -> ResourceMonitor:
    """获取全局资源监控器单例。

    首次调用时自动加载预定义告警规则。
    """
    global _monitor
    if _monitor is None:
        _monitor = ResourceMonitor()
        _load_default_rules(_monitor)
    return _monitor


def reset_resource_monitor() -> None:
    """重置全局资源监控器（仅用于测试）。"""
    global _monitor
    _monitor = None
