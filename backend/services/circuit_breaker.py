"""CityFlow 熔断器模块。

实现三态熔断器（CLOSED / OPEN / HALF_OPEN），用于保护外部服务调用。
提供同步/异步装饰器和手动控制两种使用方式。

状态机：
    CLOSED  --(失败次数 >= 阈值)--> OPEN
    OPEN    --(恢复超时)----------> HALF_OPEN
    HALF_OPEN --(调用成功)--------> CLOSED
    HALF_OPEN --(调用失败)--------> OPEN
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

from backend.errors import CityFlowException, ErrorCode

logger = logging.getLogger(__name__)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerMetrics",
    "CircuitBreakerOpenError",
    "CircuitState",
]

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# 熔断器打开异常（继承项目异常体系）
# ---------------------------------------------------------------------------


class CircuitBreakerOpenError(CityFlowException):
    """熔断器处于打开状态时抛出。"""

    def __init__(
        self,
        message: str = "服务暂时不可用（熔断器已打开）",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.EXTERNAL_API_ERROR,
            message=message,
            details=details,
        )


# ---------------------------------------------------------------------------
# 熔断器状态枚举
# ---------------------------------------------------------------------------


class CircuitState(str, Enum):
    """熔断器三态。"""

    CLOSED = "closed"  # 正常放行
    OPEN = "open"  # 熔断，拒绝请求
    HALF_OPEN = "half_open"  # 半开，试探性放行


# ---------------------------------------------------------------------------
# 指标收集（可选 Prometheus 集成）
# ---------------------------------------------------------------------------


class CircuitBreakerMetrics:
    """熔断器指标收集器。

    默认使用简单的内存计数器。如果 prometheus_client 可用，
    会自动注册 Prometheus 指标，可在 /metrics 端点暴露。
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.success_count: int = 0
        self.failure_count: int = 0
        self.rejected_count: int = 0
        self.state_changes: int = 0
        self._prom_counter: Any = None

        # 尝试注册 Prometheus 指标（使用独立 registry 避免测试中的命名冲突）
        try:
            from prometheus_client import CollectorRegistry, Counter

            self._prom_registry = CollectorRegistry()
            self._prom_counter = Counter(
                f"cityflow_circuit_breaker_{name}",
                f"Circuit breaker '{name}' events",
                ["event"],
                registry=self._prom_registry,
            )
        except ImportError:
            pass

    def record_success(self) -> None:
        self.success_count += 1
        if self._prom_counter:
            self._prom_counter.labels(event="success").inc()

    def record_failure(self) -> None:
        self.failure_count += 1
        if self._prom_counter:
            self._prom_counter.labels(event="failure").inc()

    def record_rejected(self) -> None:
        self.rejected_count += 1
        if self._prom_counter:
            self._prom_counter.labels(event="rejected").inc()

    def record_state_change(self) -> None:
        self.state_changes += 1
        if self._prom_counter:
            self._prom_counter.labels(event="state_change").inc()

    def as_dict(self) -> dict[str, int]:
        return {
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "rejected_count": self.rejected_count,
            "state_changes": self.state_changes,
        }


# ---------------------------------------------------------------------------
# 熔断器核心
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """三态熔断器。

    Args:
        failure_threshold: 连续失败次数阈值，达到后进入 OPEN 状态。
        recovery_timeout: OPEN 状态持续多少秒后进入 HALF_OPEN。
        expected_exception: 哪些异常算"失败"，默认所有 Exception。
        name: 熔断器名称，用于日志和指标。
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exception: type[BaseException] | tuple[type[BaseException], ...] = Exception,
        name: str = "default",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._metrics = CircuitBreakerMetrics(name)

    # -- 属性 --

    @property
    def state(self) -> CircuitState:
        """获取当前状态，OPEN 超时后自动转 HALF_OPEN。"""
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._transition(CircuitState.HALF_OPEN)
        return self._state

    @property
    def metrics(self) -> CircuitBreakerMetrics:
        return self._metrics

    @property
    def failure_count(self) -> int:
        return self._failure_count

    # -- 状态转换 --

    def _transition(self, new_state: CircuitState) -> None:
        old = self._state
        if old != new_state:
            self._state = new_state
            self._metrics.record_state_change()
            logger.info(
                "[%s] 熔断器状态: %s -> %s (失败次数=%d)",
                self.name,
                old.value,
                new_state.value,
                self._failure_count,
            )

    # -- 记录结果 --

    def record_success(self) -> None:
        """记录一次成功调用，重置失败计数并关闭熔断器。"""
        self._failure_count = 0
        self._metrics.record_success()
        if self._state != CircuitState.CLOSED:
            self._transition(CircuitState.CLOSED)

    def record_failure(self) -> None:
        """记录一次失败调用，达到阈值时打开熔断器。"""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        self._metrics.record_failure()

        if self._failure_count >= self.failure_threshold:
            if self._state != CircuitState.OPEN:
                self._transition(CircuitState.OPEN)
                logger.warning(
                    "[%s] 熔断器打开，连续失败 %d 次",
                    self.name,
                    self._failure_count,
                )

    def reject_if_open(self) -> None:
        """如果熔断器已打开，直接抛出异常。"""
        if self.state == CircuitState.OPEN:
            self._metrics.record_rejected()
            raise CircuitBreakerOpenError(
                message=f"熔断器已打开: {self.name}",
                details={
                    "circuit_breaker": self.name,
                    "failure_count": self._failure_count,
                    "recovery_timeout": self.recovery_timeout,
                },
            )

    # -- 手动控制 --

    def reset(self) -> None:
        """手动重置熔断器到 CLOSED 状态。"""
        self._failure_count = 0
        self._transition(CircuitState.CLOSED)

    def trip(self) -> None:
        """手动触发熔断器到 OPEN 状态。"""
        self._last_failure_time = time.monotonic()
        self._transition(CircuitState.OPEN)

    # -- 装饰器 --

    def __call__(self, func: F) -> F:
        """作为装饰器使用，包装异步函数。"""

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            state = self.state

            if state == CircuitState.OPEN:
                self._metrics.record_rejected()
                raise CircuitBreakerOpenError(
                    message=f"熔断器已打开: {self.name} -> {func.__name__}",
                    details={"circuit_breaker": self.name},
                )

            try:
                result = await func(*args, **kwargs)  # type: ignore[misc]
                self.record_success()
                return result
            except self.expected_exception:
                self.record_failure()
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            state = self.state

            if state == CircuitState.OPEN:
                self._metrics.record_rejected()
                raise CircuitBreakerOpenError(
                    message=f"熔断器已打开: {self.name} -> {func.__name__}",
                    details={"circuit_breaker": self.name},
                )

            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except self.expected_exception:
                self.record_failure()
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self.name!r}, state={self._state.value}, "
            f"failures={self._failure_count}/{self.failure_threshold})"
        )
