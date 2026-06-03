"""CityFlow 自适应限流器。

根据系统负载动态调整限流阈值：
- 负载低时放宽限制（提升用户体验）
- 负载高时收紧限制（保护系统稳定性）
- 支持多种负载信号：CPU、内存、响应时间、错误率

设计思路：
    系统负载 = w1*cpu + w2*memory + w3*error_rate + w4*latency
    限流倍率 = 1.0 - (负载 - threshold) * sensitivity
    最终限制 = 基础限制 * 限流倍率

用法::

    adaptive = get_adaptive_limiter()
    multiplier = adaptive.get_multiplier()
    # 将 multiplier 传给 UserRateLimiter / IPRateLimiter
    result = await user_limiter.check("user_123", "/api/v1/plan_route", multiplier)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "AdaptiveRateLimiter",
    "LoadLevel",
    "SystemMetrics",
    "get_adaptive_limiter",
]


# ---------------------------------------------------------------------------
# 负载等级
# ---------------------------------------------------------------------------


class LoadLevel(str, Enum):
    """系统负载等级。"""

    LOW = "low"  # 负载 < 40%
    NORMAL = "normal"  # 40% - 70%
    HIGH = "high"  # 70% - 90%
    CRITICAL = "critical"  # > 90%


# 负载等级 -> 限流倍率
_LOAD_MULTIPLIERS: dict[LoadLevel, float] = {
    LoadLevel.LOW: 1.5,  # 放宽 50%
    LoadLevel.NORMAL: 1.0,  # 正常
    LoadLevel.HIGH: 0.5,  # 收紧 50%
    LoadLevel.CRITICAL: 0.2,  # 收紧 80%
}


# ---------------------------------------------------------------------------
# 系统指标
# ---------------------------------------------------------------------------


@dataclass
class SystemMetrics:
    """系统运行时指标快照。"""

    cpu_percent: float = 0.0  # CPU 使用率 (0-100)
    memory_percent: float = 0.0  # 内存使用率 (0-100)
    active_requests: int = 0  # 当前活跃请求数
    avg_response_ms: float = 0.0  # 平均响应时间 (ms)
    error_rate: float = 0.0  # 错误率 (0-1)
    timestamp: float = field(default_factory=time.time)

    @property
    def load_score(self) -> float:
        """计算综合负载分数 (0-100)。

        加权公式：
            score = 0.3*cpu + 0.2*memory + 0.3*error_rate*100 + 0.2*latency_factor
            latency_factor = min(avg_response_ms / 1000, 1) * 100
        """
        latency_factor = min(self.avg_response_ms / 1000.0, 1.0) * 100
        return (
            0.3 * self.cpu_percent
            + 0.2 * self.memory_percent
            + 0.3 * (self.error_rate * 100)
            + 0.2 * latency_factor
        )

    @property
    def level(self) -> LoadLevel:
        """根据负载分数判定等级。

        阈值说明（满载 100 分）：
        - LOW: < 30  （系统空闲）
        - NORMAL: 30 - 60  （正常负载）
        - HIGH: 60 - 85  （高负载，需收紧）
        - CRITICAL: >= 85  （过载，紧急收紧）
        """
        score = self.load_score
        if score < 30:
            return LoadLevel.LOW
        elif score < 60:
            return LoadLevel.NORMAL
        elif score < 85:
            return LoadLevel.HIGH
        else:
            return LoadLevel.CRITICAL


# ---------------------------------------------------------------------------
# 指标收集器
# ---------------------------------------------------------------------------


class MetricsCollector:
    """系统指标收集器。

    通过 psutil 收集系统指标，如果 psutil 不可用则使用估算值。
    """

    def __init__(self) -> None:
        self._psutil_available = False
        self._process = None
        try:
            import psutil  # type: ignore[import-untyped]

            self._psutil_available = True
            self._process = psutil.Process()
        except ImportError:
            logger.warning("psutil 未安装，系统指标将使用估算值")

        # 响应时间滑动窗口
        self._response_times: list[float] = []
        self._max_window = 1000

        # 错误计数
        self._total_requests = 0
        self._error_requests = 0
        self._last_reset = time.time()
        self._reset_interval = 60  # 每分钟重置错误率

    def record_response(self, duration_ms: float, is_error: bool = False) -> None:
        """记录一次请求的响应。"""
        self._response_times.append(duration_ms)
        if len(self._response_times) > self._max_window:
            self._response_times = self._response_times[-self._max_window :]

        self._total_requests += 1
        if is_error:
            self._error_requests += 1

        # 定期重置错误率计数
        now = time.time()
        if now - self._last_reset > self._reset_interval:
            self._error_requests = 0
            self._total_requests = 0
            self._last_reset = now

    def collect(self) -> SystemMetrics:
        """收集当前系统指标。"""
        cpu_percent = 0.0
        memory_percent = 0.0

        if self._psutil_available and self._process is not None:
            try:
                cpu_percent = self._process.cpu_percent(interval=0)
                memory_percent = self._process.memory_percent()
            except Exception:
                logger.debug("psutil cpu/memory read failed", exc_info=True)

        avg_response_ms = (
            sum(self._response_times[-100:]) / min(len(self._response_times), 100)
            if self._response_times
            else 0.0
        )

        error_rate = (
            self._error_requests / self._total_requests if self._total_requests > 0 else 0.0
        )

        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            avg_response_ms=avg_response_ms,
            error_rate=error_rate,
        )

    def reset(self) -> None:
        """重置所有指标。"""
        self._response_times.clear()
        self._total_requests = 0
        self._error_requests = 0
        self._last_reset = time.time()


# ---------------------------------------------------------------------------
# 自适应限流器
# ---------------------------------------------------------------------------


class AdaptiveRateLimiter:
    """自适应限流器。

    根据系统负载动态计算限流倍率，供 UserRateLimiter / IPRateLimiter 使用。
    支持手动覆盖和渐进式恢复。

    参数:
        high_threshold: 触发收紧的负载分数阈值（默认 70）。
        critical_threshold: 触发紧急收紧的负载分数阈值（默认 90）。
        low_threshold: 触发放宽的负载分数阈值（默认 40）。
        recovery_factor: 从高负载恢复时的渐进因子（0-1，默认 0.1）。
    """

    def __init__(
        self,
        high_threshold: float = 70.0,
        critical_threshold: float = 90.0,
        low_threshold: float = 40.0,
        recovery_factor: float = 0.1,
    ) -> None:
        self._high_threshold = high_threshold
        self._critical_threshold = critical_threshold
        self._low_threshold = low_threshold
        self._recovery_factor = recovery_factor

        self._collector = MetricsCollector()
        self._current_metrics = SystemMetrics()

        # 当前倍率（带渐进平滑）
        self._current_multiplier = 1.0

        # 手动覆盖（None 表示自动模式）
        self._manual_multiplier: float | None = None

        # 监控任务
        self._monitor_task: asyncio.Task[None] | None = None
        self._monitor_interval = 5  # 秒

    @property
    def metrics(self) -> SystemMetrics:
        """当前系统指标快照。"""
        return self._current_metrics

    @property
    def load_level(self) -> LoadLevel:
        """当前负载等级。"""
        return self._current_metrics.level

    def get_multiplier(self) -> float:
        """获取当前限流倍率。

        Returns:
            限流倍率。>1 表示放宽，<1 表示收紧，1.0 表示正常。
        """
        if self._manual_multiplier is not None:
            return self._manual_multiplier
        return self._current_multiplier

    def set_manual_multiplier(self, multiplier: float | None) -> None:
        """设置手动倍率覆盖。

        Args:
            multiplier: 倍率值，None 则恢复自动模式。
        """
        self._manual_multiplier = multiplier
        if multiplier is not None:
            logger.info("自适应限流切换到手动模式，倍率=%.2f", multiplier)
        else:
            logger.info("自适应限流切换到自动模式")

    def record_response(self, duration_ms: float, is_error: bool = False) -> None:
        """记录请求响应（供中间件调用）。"""
        self._collector.record_response(duration_ms, is_error)

    async def start_monitoring(self) -> None:
        """启动后台指标监控。"""
        if self._monitor_task is not None:
            return
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("自适应限流监控已启动（间隔 %d 秒）", self._monitor_interval)

    async def stop_monitoring(self) -> None:
        """停止后台指标监控。"""
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("自适应限流监控已停止")

    def force_update(self) -> SystemMetrics:
        """立即更新指标并重新计算倍率。"""
        self._current_metrics = self._collector.collect()
        self._update_multiplier()
        return self._current_metrics

    def get_status(self) -> dict[str, Any]:
        """获取自适应限流器状态。"""
        return {
            "load_level": self.load_level.value,
            "load_score": round(self._current_metrics.load_score, 2),
            "multiplier": round(self.get_multiplier(), 3),
            "mode": "manual" if self._manual_multiplier is not None else "auto",
            "metrics": {
                "cpu_percent": round(self._current_metrics.cpu_percent, 1),
                "memory_percent": round(self._current_metrics.memory_percent, 1),
                "avg_response_ms": round(self._current_metrics.avg_response_ms, 1),
                "error_rate": round(self._current_metrics.error_rate, 4),
            },
            "thresholds": {
                "low": self._low_threshold,
                "high": self._high_threshold,
                "critical": self._critical_threshold,
            },
        }

    # -- 内部方法 --

    def _update_multiplier(self) -> None:
        """根据当前负载更新倍率（带渐进平滑）。"""
        level = self._current_metrics.level
        target = _LOAD_MULTIPLIERS[level]

        # 渐进式调整：不直接跳到目标值，而是逐步逼近
        if target > self._current_multiplier:
            # 放宽：缓慢恢复
            self._current_multiplier += (target - self._current_multiplier) * self._recovery_factor
        else:
            # 收紧：快速响应
            self._current_multiplier = target

        # 限制范围 [0.1, 3.0]
        self._current_multiplier = max(0.1, min(3.0, self._current_multiplier))

    async def _monitor_loop(self) -> None:
        """后台监控循环。"""
        while True:
            try:
                await asyncio.sleep(self._monitor_interval)
                self.force_update()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("自适应限流监控异常")


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_adaptive: AdaptiveRateLimiter | None = None


def get_adaptive_limiter() -> AdaptiveRateLimiter:
    """获取全局自适应限流器单例。"""
    global _adaptive
    if _adaptive is None:
        _adaptive = AdaptiveRateLimiter()
    return _adaptive
