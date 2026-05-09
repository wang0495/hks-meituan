"""性能指标定义与阈值配置。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    """单次基准测试的聚合性能指标。"""

    # 响应时间（单位：毫秒）
    avg_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float

    # 吞吐量
    requests_per_second: float

    # 错误率（百分比 0-100）
    error_rate: float

    # 资源使用（百分比 0-100）
    cpu_usage: float = 0.0
    memory_usage: float = 0.0

    # 原始数据
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    total_duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典，便于序列化输出。"""
        return {
            "avg_response_time_ms": round(self.avg_response_time, 2),
            "p50_response_time_ms": round(self.p50_response_time, 2),
            "p95_response_time_ms": round(self.p95_response_time, 2),
            "p99_response_time_ms": round(self.p99_response_time, 2),
            "requests_per_second": round(self.requests_per_second, 2),
            "error_rate_percent": round(self.error_rate, 2),
            "cpu_usage_percent": round(self.cpu_usage, 2),
            "memory_usage_percent": round(self.memory_usage, 2),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "min_response_time_ms": round(self.min_response_time, 2),
            "max_response_time_ms": round(self.max_response_time, 2),
            "total_duration_seconds": round(self.total_duration_seconds, 2),
        }


# ---------------------------------------------------------------------------
# 性能阈值（基准线）
# ---------------------------------------------------------------------------

PERFORMANCE_THRESHOLDS: dict[str, float] = {
    # 响应时间（ms）
    "avg_response_time": 500,  # 平均响应时间 <= 500ms
    "p50_response_time": 300,  # P50 <= 300ms
    "p95_response_time": 1000,  # P95 <= 1s
    "p99_response_time": 2000,  # P99 <= 2s
    # 吞吐量
    "min_requests_per_second": 50,  # 至少 50 RPS
    # 错误率（%）
    "error_rate": 1.0,  # 错误率 <= 1%
    # 资源使用（%）
    "cpu_usage": 80,  # CPU <= 80%
    "memory_usage": 85,  # 内存 <= 85%
}


@dataclass(frozen=True, slots=True)
class ThresholdViolation:
    """单条阈值违规记录。"""

    metric: str
    actual: float
    threshold: float
    severity: str  # "warning" | "critical"

    def __str__(self) -> str:
        return (
            f"[{self.severity.upper()}] {self.metric}: "
            f"{self.actual:.2f} (阈值: {self.threshold:.2f})"
        )


def check_thresholds(
    metrics: PerformanceMetrics,
    thresholds: dict[str, float] | None = None,
) -> list[ThresholdViolation]:
    """检查指标是否超过阈值，返回违规列表。

    Args:
        metrics: 待检查的性能指标。
        thresholds: 自定义阈值，默认使用 PERFORMANCE_THRESHOLDS。

    Returns:
        违规记录列表。空列表表示全部通过。
    """
    limits = thresholds or PERFORMANCE_THRESHOLDS
    violations: list[ThresholdViolation] = []

    checks: list[tuple[str, float, float]] = [
        ("avg_response_time", metrics.avg_response_time, limits["avg_response_time"]),
        ("p50_response_time", metrics.p50_response_time, limits["p50_response_time"]),
        ("p95_response_time", metrics.p95_response_time, limits["p95_response_time"]),
        ("p99_response_time", metrics.p99_response_time, limits["p99_response_time"]),
        ("error_rate", metrics.error_rate, limits["error_rate"]),
        ("cpu_usage", metrics.cpu_usage, limits["cpu_usage"]),
        ("memory_usage", metrics.memory_usage, limits["memory_usage"]),
    ]

    for name, actual, threshold in checks:
        if actual > threshold:
            severity = "critical" if actual > threshold * 1.5 else "warning"
            violations.append(
                ThresholdViolation(
                    metric=name,
                    actual=actual,
                    threshold=threshold,
                    severity=severity,
                )
            )

    # RPS 是下限检查
    min_rps = limits.get("min_requests_per_second", 0)
    if metrics.requests_per_second < min_rps:
        severity = (
            "critical" if metrics.requests_per_second < min_rps * 0.5 else "warning"
        )
        violations.append(
            ThresholdViolation(
                metric="requests_per_second",
                actual=metrics.requests_per_second,
                threshold=min_rps,
                severity=severity,
            )
        )

    return violations
