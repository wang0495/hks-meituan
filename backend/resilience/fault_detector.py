"""CityFlow 故障检测器。

基于滑动窗口的故障频率检测，用于发现服务的间歇性故障模式。
与 CircuitBreaker（熔断器）互补：
- CircuitBreaker 关注"连续失败"，快速熔断
- FaultDetector 关注"窗口内失败频率"，捕捉间歇性故障

提供三种检测级别：
    - warning:  失败次数达到阈值的 50%
    - critical: 失败次数达到阈值
    - faulty:   失败次数超过阈值，服务判定为故障状态

用法：
    detector = FaultDetector()

    # 服务调用后记录结果
    try:
        result = await call_service()
        detector.record_success("llm")
    except Exception:
        is_faulty = detector.record_failure("llm")
        if is_faulty:
            # 触发自愈流程
            ...

    # 查询状态
    if detector.is_faulty("llm"):
        # 切换到降级模式
        ...
"""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Any

__all__ = [
    "FaultLevel",
    "FaultEvent",
    "FaultDetector",
    "get_fault_detector",
]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


class FaultLevel(str, Enum):
    """故障级别。"""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    FAULTY = "faulty"


class FaultEvent:
    """单次故障事件记录。"""

    __slots__ = ("service", "level", "failure_count", "threshold", "timestamp")

    def __init__(
        self,
        service: str,
        level: FaultLevel,
        failure_count: int,
        threshold: int,
    ) -> None:
        self.service = service
        self.level = level
        self.failure_count = failure_count
        self.threshold = threshold
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "level": self.level.value,
            "failure_count": self.failure_count,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# 故障检测器核心
# ---------------------------------------------------------------------------


class FaultDetector:
    """基于滑动窗口的故障检测器。

    在指定时间窗口内，统计每个服务的失败次数。
    达到不同阈值时触发不同级别的告警和事件。

    Args:
        threshold: 判定服务为故障状态的失败次数阈值。
        window_sec: 滑动窗口时长（秒），超过窗口的旧记录自动过期。
        history_size: 保留最近多少条故障事件记录。
    """

    def __init__(
        self,
        threshold: int = 5,
        window_sec: float = 300.0,
        history_size: int = 500,
    ) -> None:
        self._threshold = threshold
        self._window_sec = window_sec

        # 每个服务的失败时间戳列表（单调时钟）
        self._failure_times: dict[str, deque[float]] = {}
        # 事件历史
        self._events: deque[FaultEvent] = deque(maxlen=history_size)
        # 上次通知级别，避免重复告警
        self._last_notified_level: dict[str, FaultLevel] = {}

    # -- 记录结果 --

    def record_failure(self, service: str) -> FaultLevel:
        """记录一次失败，返回当前故障级别。

        窗口外的旧记录会被自动清理。

        Args:
            service: 服务名称。

        Returns:
            当前故障级别。
        """
        now = time.monotonic()

        if service not in self._failure_times:
            self._failure_times[service] = deque()

        failures = self._failure_times[service]
        failures.append(now)

        # 清理窗口外的旧记录
        cutoff = now - self._window_sec
        while failures and failures[0] < cutoff:
            failures.popleft()

        count = len(failures)
        level = self._compute_level(count)

        # 只在级别变化时记录事件和日志
        last_level = self._last_notified_level.get(service, FaultLevel.HEALTHY)
        if level != last_level:
            self._last_notified_level[service] = level
            event = FaultEvent(
                service=service,
                level=level,
                failure_count=count,
                threshold=self._threshold,
            )
            self._events.append(event)
            self._log_level_change(service, level, count)

        return level

    def record_success(self, service: str) -> None:
        """记录一次成功，清除该服务的失败记录。"""
        if service in self._failure_times:
            self._failure_times[service].clear()
        if service in self._last_notified_level:
            prev = self._last_notified_level.pop(service)
            if prev != FaultLevel.HEALTHY:
                logger.info("[故障检测] 服务 %s 恢复正常", service)

    # -- 状态查询 --

    def get_failure_count(self, service: str) -> int:
        """获取当前窗口内的失败次数。"""
        failures = self._failure_times.get(service)
        if not failures:
            return 0

        # 清理过期记录后返回
        now = time.monotonic()
        cutoff = now - self._window_sec
        while failures and failures[0] < cutoff:
            failures.popleft()
        return len(failures)

    def get_level(self, service: str) -> FaultLevel:
        """获取服务当前故障级别。"""
        return self._compute_level(self.get_failure_count(service))

    def is_faulty(self, service: str) -> bool:
        """服务是否处于故障状态（失败次数超过阈值）。"""
        return self.get_level(service) == FaultLevel.FAULTY

    def is_warning(self, service: str) -> bool:
        """服务是否处于警告状态。"""
        return self.get_level(service) == FaultLevel.WARNING

    def is_critical(self, service: str) -> bool:
        """服务是否处于严重状态。"""
        return self.get_level(service) == FaultLevel.CRITICAL

    def get_all_statuses(self) -> dict[str, dict[str, Any]]:
        """获取所有被监控服务的状态概览。"""
        statuses: dict[str, dict[str, Any]] = {}
        for service in set(
            list(self._failure_times.keys()) + list(self._last_notified_level.keys())
        ):
            count = self.get_failure_count(service)
            level = self._compute_level(count)
            statuses[service] = {
                "level": level.value,
                "failure_count": count,
                "threshold": self._threshold,
                "window_sec": self._window_sec,
            }
        return statuses

    @property
    def events(self) -> list[FaultEvent]:
        """获取事件历史。"""
        return list(self._events)

    def get_service_events(self, service: str) -> list[FaultEvent]:
        """获取指定服务的事件历史。"""
        return [e for e in self._events if e.service == service]

    # -- 配置 --

    @property
    def threshold(self) -> int:
        return self._threshold

    @threshold.setter
    def threshold(self, value: int) -> None:
        if value < 1:
            raise ValueError("threshold 必须 >= 1")
        self._threshold = value

    @property
    def window_sec(self) -> float:
        return self._window_sec

    @window_sec.setter
    def window_sec(self, value: float) -> None:
        if value <= 0:
            raise ValueError("window_sec 必须 > 0")
        self._window_sec = value

    # -- 重置 --

    def reset(self, service: str | None = None) -> None:
        """重置指定服务（或全部服务）的故障计数。"""
        if service:
            self._failure_times.pop(service, None)
            self._last_notified_level.pop(service, None)
        else:
            self._failure_times.clear()
            self._last_notified_level.clear()

    # -- 内部方法 --

    def _compute_level(self, count: int) -> FaultLevel:
        """根据失败次数计算故障级别。"""
        if count >= self._threshold:
            return FaultLevel.FAULTY
        if count >= self._threshold * 0.8:
            return FaultLevel.CRITICAL
        if count >= self._threshold * 0.5:
            return FaultLevel.WARNING
        return FaultLevel.HEALTHY

    def _log_level_change(self, service: str, level: FaultLevel, count: int) -> None:
        """记录级别变化日志。"""
        match level:
            case FaultLevel.WARNING:
                logger.warning(
                    "[故障检测] 服务 %s 进入警告状态 (失败 %d/%d)",
                    service,
                    count,
                    self._threshold,
                )
            case FaultLevel.CRITICAL:
                logger.error(
                    "[故障检测] 服务 %s 进入严重状态 (失败 %d/%d)",
                    service,
                    count,
                    self._threshold,
                )
            case FaultLevel.FAULTY:
                logger.error(
                    "[故障检测] 服务 %s 判定为故障 (失败 %d/%d, 超过阈值)",
                    service,
                    count,
                    self._threshold,
                )
            case FaultLevel.HEALTHY:
                pass  # 已在 record_success 中处理


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_fault_detector: FaultDetector | None = None


def get_fault_detector() -> FaultDetector:
    """获取全局 FaultDetector 单例。"""
    global _fault_detector
    if _fault_detector is None:
        _fault_detector = FaultDetector()
    return _fault_detector
