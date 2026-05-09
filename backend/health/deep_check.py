"""CityFlow 深度健康检查。

在基础 /health 之上，提供三层检查：

1. 系统资源检查 -- CPU、内存、磁盘使用率
2. 依赖服务检查 -- 数据库、Redis、LLM 连通性
3. 健康状态聚合 -- 综合所有检查结果给出 overall 状态

与 backend.services.health_checker.HealthChecker 的关系：
HealthChecker 是底层引擎（注册、并行执行、历史记录），
DeepHealthCheck 在其上封装预定义检查项和聚合逻辑，
对外暴露简洁的 run() 接口供路由层调用。

用法：
    checker = DeepHealthCheck()
    report = await checker.run()
    # report["status"] == "healthy" | "degraded" | "unhealthy"
"""

from __future__ import annotations

import logging
import time
from collections.abc import Coroutine
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from backend.services.health_checker import (CheckResult, CheckStatus,
                                             HealthChecker, HealthReport,
                                             check_database, check_llm_service,
                                             check_redis)

__all__ = ["DeepHealthCheck", "AggregatedStatus"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 聚合状态
# ---------------------------------------------------------------------------


class AggregatedStatus(str, Enum):
    """深度检查的聚合状态。"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# ---------------------------------------------------------------------------
# 系统资源检查函数
# ---------------------------------------------------------------------------


async def check_disk_space() -> CheckResult:
    """检查磁盘使用率。超过 90% 视为 degraded，超过 95% 视为 unhealthy。"""
    try:
        import psutil

        start = time.monotonic()
        disk = psutil.disk_usage("/")
        latency = (time.monotonic() - start) * 1000
        percent = disk.percent

        if percent >= 95:
            status = CheckStatus.UNHEALTHY
        elif percent >= 90:
            status = CheckStatus.DEGRADED
        else:
            status = CheckStatus.HEALTHY

        return CheckResult(
            name="disk_space",
            status=status,
            latency_ms=latency,
            details={
                "percent": percent,
                "free_gb": round(disk.free / (1024**3), 2),
                "total_gb": round(disk.total / (1024**3), 2),
            },
        )
    except ImportError:
        return CheckResult(
            name="disk_space",
            status=CheckStatus.HEALTHY,
            details={"note": "psutil not installed, skipped"},
        )
    except Exception as exc:
        return CheckResult(
            name="disk_space",
            status=CheckStatus.ERROR,
            error=f"{type(exc).__name__}: {exc}",
        )


async def check_memory() -> CheckResult:
    """检查内存使用率。超过 85% 视为 degraded，超过 95% 视为 unhealthy。"""
    try:
        import psutil

        start = time.monotonic()
        mem = psutil.virtual_memory()
        latency = (time.monotonic() - start) * 1000
        percent = mem.percent

        if percent >= 95:
            status = CheckStatus.UNHEALTHY
        elif percent >= 85:
            status = CheckStatus.DEGRADED
        else:
            status = CheckStatus.HEALTHY

        return CheckResult(
            name="memory",
            status=status,
            latency_ms=latency,
            details={
                "percent": percent,
                "available_mb": round(mem.available / (1024**2), 1),
                "total_mb": round(mem.total / (1024**2), 1),
            },
        )
    except ImportError:
        return CheckResult(
            name="memory",
            status=CheckStatus.HEALTHY,
            details={"note": "psutil not installed, skipped"},
        )
    except Exception as exc:
        return CheckResult(
            name="memory",
            status=CheckStatus.ERROR,
            error=f"{type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# 深度健康检查器
# ---------------------------------------------------------------------------


# 检查项定义：(名称, 检查函数, 是否为关键依赖)
_DEFAULT_CHECKS: list[
    tuple[str, Callable[..., Coroutine[Any, Any, bool | CheckResult]], bool]
] = [
    ("database", check_database, True),
    ("redis", check_redis, True),
    ("llm_service", check_llm_service, False),
    ("disk_space", check_disk_space, False),
    ("memory", check_memory, False),
]


class DeepHealthCheck:
    """深度健康检查器。

    封装 HealthChecker，预注册系统资源和依赖服务检查，
    并提供聚合状态判定逻辑。

    Args:
        critical_only: 若为 True，只运行关键依赖检查（database、redis）。
    """

    def __init__(self, critical_only: bool = False) -> None:
        self._checker = HealthChecker()
        self._critical: dict[str, bool] = {}

        for name, func, is_critical in _DEFAULT_CHECKS:
            if critical_only and not is_critical:
                continue
            self._checker.register(name, func)
            self._critical[name] = is_critical

    def register(
        self,
        name: str,
        check_func: Callable[..., Coroutine[Any, Any, bool | CheckResult]],
        *,
        critical: bool = False,
    ) -> None:
        """注册额外的检查项。

        Args:
            name: 检查项名称。
            check_func: 异步检查函数。
            critical: 是否为关键依赖（关键依赖失败会导致整体 unhealthy）。
        """
        self._checker.register(name, check_func)
        self._critical[name] = critical

    async def run(self) -> dict[str, Any]:
        """执行所有检查并返回聚合报告。

        Returns:
            包含 status、checks、timestamp、duration_ms 的字典。
        """
        report: HealthReport = await self._checker.run_all()
        return self._aggregate(report)

    def _aggregate(self, report: HealthReport) -> dict[str, Any]:
        """将 HealthReport 转换为带聚合状态的字典。"""
        checks: dict[str, dict[str, Any]] = {}
        has_critical_failure = False
        has_degraded = False

        for result in report.results:
            entry = result.to_dict()
            is_critical = self._critical.get(result.name, False)
            entry["critical"] = is_critical
            checks[result.name] = entry

            if result.status in (CheckStatus.UNHEALTHY, CheckStatus.ERROR):
                if is_critical:
                    has_critical_failure = True
            elif result.status == CheckStatus.DEGRADED:
                has_degraded = True

        # 聚合状态判定：
        # - 关键依赖失败 -> unhealthy
        # - 非关键失败或有 degraded -> degraded
        # - 全部正常 -> healthy
        if has_critical_failure:
            status = AggregatedStatus.UNHEALTHY
        elif (
            report.overall_status in (CheckStatus.UNHEALTHY, CheckStatus.ERROR)
            or has_degraded
        ):
            status = AggregatedStatus.DEGRADED
        else:
            status = AggregatedStatus.HEALTHY

        return {
            "status": status.value,
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": round(report.duration_ms, 2),
            "total": len(report.results),
            "healthy": sum(
                1 for r in report.results if r.status == CheckStatus.HEALTHY
            ),
        }


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------


async def run_deep_check(*, critical_only: bool = False) -> dict[str, Any]:
    """运行深度健康检查的便捷入口。

    Args:
        critical_only: 若为 True，只检查关键依赖。

    Returns:
        聚合后的健康报告字典。
    """
    checker = DeepHealthCheck(critical_only=critical_only)
    return await checker.run()
