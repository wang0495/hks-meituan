"""CityFlow 健康检查模块。

提供可扩展的健康检查框架，支持：
- 注册自定义检查函数（数据库、Redis、LLM 等）
- 周期性后台监控，自动检测服务异常
- 检查结果历史记录，用于趋势分析
- 与 auto_recovery 联动，异常时自动触发恢复

用法：
    checker = HealthChecker()
    checker.register("database", check_database)
    checker.register("redis", check_redis)

    # 后台启动
    await checker.start(interval=30)

    # 或手动触发
    results = await checker.run_all()
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from enum import Enum
from typing import Any

__all__ = [
    "CheckStatus",
    "CheckResult",
    "HealthReport",
    "HealthChecker",
    "check_database",
    "check_redis",
    "check_llm_service",
]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 状态枚举与数据结构
# ---------------------------------------------------------------------------


class CheckStatus(str, Enum):
    """单次检查结果状态。"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    ERROR = "error"


class CheckResult:
    """单个检查项的结果。"""

    __slots__ = ("name", "status", "latency_ms", "error", "details", "timestamp")

    def __init__(
        self,
        name: str,
        status: CheckStatus,
        latency_ms: float = 0.0,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.status = status
        self.latency_ms = latency_ms
        self.error = error
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp.isoformat(),
        }
        if self.error:
            result["error"] = self.error
        if self.details:
            result["details"] = self.details
        return result


class HealthReport:
    """一次完整健康检查的汇总报告。"""

    __slots__ = ("results", "overall_status", "timestamp", "duration_ms")

    def __init__(
        self,
        results: list[CheckResult],
        duration_ms: float = 0.0,
    ) -> None:
        self.results = results
        self.timestamp = datetime.now(timezone.utc)
        self.duration_ms = duration_ms
        self.overall_status = self._compute_overall()

    def _compute_overall(self) -> CheckStatus:
        if not self.results:
            return CheckStatus.HEALTHY

        statuses = {r.status for r in self.results}

        if CheckStatus.ERROR in statuses or CheckStatus.UNHEALTHY in statuses:
            # 只要有一个核心服务 error/unhealthy，整体 unhealthy
            return CheckStatus.UNHEALTHY
        if CheckStatus.DEGRADED in statuses:
            return CheckStatus.DEGRADED
        return CheckStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": round(self.duration_ms, 2),
            "checks": [r.to_dict() for r in self.results],
        }

    @property
    def unhealthy_names(self) -> list[str]:
        return [
            r.name
            for r in self.results
            if r.status in (CheckStatus.UNHEALTHY, CheckStatus.ERROR)
        ]


# ---------------------------------------------------------------------------
# 检查函数类型
# ---------------------------------------------------------------------------

# 检查函数签名：async def check() -> bool | CheckResult
# 返回 bool: True=healthy, False=unhealthy
# 返回 CheckResult: 自定义结果
HealthCheckFunc = Callable[[], Coroutine[Any, Any, bool | CheckResult]]


# ---------------------------------------------------------------------------
# 健康检查器核心
# ---------------------------------------------------------------------------


class HealthChecker:
    """可扩展的健康检查器。

    Args:
        history_size: 保留最近多少次检查报告。
    """

    def __init__(self, history_size: int = 100) -> None:
        self._checks: dict[str, HealthCheckFunc] = {}
        self._history: deque[HealthReport] = deque(maxlen=history_size)
        self._running = False
        self._task: asyncio.Task[None] | None = None
        # 可选回调：检测到异常时调用
        self._on_unhealthy: (
            Callable[[HealthReport], Coroutine[Any, Any, None]] | None
        ) = None

    # -- 注册 / 注销 --

    def register(self, name: str, check_func: HealthCheckFunc) -> None:
        """注册一个健康检查函数。

        Args:
            name: 检查项名称，如 "database"、"redis"。
            check_func: 异步检查函数，返回 bool 或 CheckResult。
        """
        self._checks[name] = check_func
        logger.debug("已注册健康检查: %s", name)

    def unregister(self, name: str) -> None:
        """注销一个健康检查。"""
        self._checks.pop(name, None)

    def set_on_unhealthy(
        self, callback: Callable[[HealthReport], Coroutine[Any, Any, None]]
    ) -> None:
        """设置异常回调，每次检测到 unhealthy 时触发。

        典型用途：触发 auto_recovery。
        """
        self._on_unhealthy = callback

    # -- 执行检查 --

    async def run_check(self, name: str) -> CheckResult:
        """运行单个检查。"""
        func = self._checks.get(name)
        if func is None:
            return CheckResult(
                name=name,
                status=CheckStatus.ERROR,
                error=f"未注册的检查项: {name}",
            )

        start = time.monotonic()
        try:
            result = await func()
            latency = (time.monotonic() - start) * 1000

            if isinstance(result, CheckResult):
                result.latency_ms = latency
                return result

            return CheckResult(
                name=name,
                status=CheckStatus.HEALTHY if result else CheckStatus.UNHEALTHY,
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            logger.exception("健康检查 [%s] 执行异常", name)
            return CheckResult(
                name=name,
                status=CheckStatus.ERROR,
                latency_ms=latency,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def run_all(self) -> HealthReport:
        """并行运行所有已注册的检查，返回汇总报告。"""
        start = time.monotonic()

        if not self._checks:
            return HealthReport(results=[], duration_ms=0.0)

        tasks = {
            name: asyncio.create_task(self.run_check(name)) for name in self._checks
        }

        results: list[CheckResult] = []
        for name, task in tasks.items():
            try:
                results.append(await task)
            except Exception:
                results.append(
                    CheckResult(
                        name=name,
                        status=CheckStatus.ERROR,
                        error="任务执行异常",
                    )
                )

        duration = (time.monotonic() - start) * 1000
        report = HealthReport(results=results, duration_ms=duration)
        self._history.append(report)

        # 日志输出
        if report.overall_status == CheckStatus.HEALTHY:
            logger.info(
                "健康检查通过 (%.1fms, %d项)",
                duration,
                len(results),
            )
        else:
            logger.warning(
                "健康检查异常: overall=%s, unhealthy=%s",
                report.overall_status.value,
                report.unhealthy_names,
            )

        # 触发异常回调
        if self._on_unhealthy and report.overall_status in (
            CheckStatus.UNHEALTHY,
            CheckStatus.ERROR,
        ):
            try:
                await self._on_unhealthy(report)
            except Exception:
                logger.exception("on_unhealthy 回调异常")

        return report

    # -- 后台监控 --

    async def start(self, interval: int = 30) -> None:
        """启动后台周期性健康检查。

        Args:
            interval: 检查间隔秒数，默认 30 秒。
        """
        if self._running:
            logger.warning("健康检查已在运行中")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop(interval))
        logger.info("健康检查后台监控已启动 (间隔=%ds)", interval)

    async def _monitor_loop(self, interval: int) -> None:
        while self._running:
            await self.run_all()
            await asyncio.sleep(interval)

    def stop(self) -> None:
        """停止后台监控。"""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("健康检查后台监控已停止")

    # -- 历史与查询 --

    @property
    def latest(self) -> HealthReport | None:
        """最近一次检查报告。"""
        return self._history[-1] if self._history else None

    @property
    def history(self) -> list[HealthReport]:
        return list(self._history)

    def get_check_names(self) -> list[str]:
        """返回所有已注册的检查名称。"""
        return list(self._checks.keys())


# ---------------------------------------------------------------------------
# 预定义检查函数
# ---------------------------------------------------------------------------


async def check_database() -> CheckResult:
    """检查数据库连接。"""
    try:
        from sqlalchemy import text

        from backend.database.base import async_session_factory

        start = time.monotonic()
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        latency = (time.monotonic() - start) * 1000

        return CheckResult(
            name="database",
            status=CheckStatus.HEALTHY,
            latency_ms=latency,
        )
    except Exception as exc:
        return CheckResult(
            name="database",
            status=CheckStatus.UNHEALTHY,
            error=f"{type(exc).__name__}: {exc}",
        )


async def check_redis() -> CheckResult:
    """检查 Redis 连接。"""
    try:
        import redis.asyncio as aioredis

        from backend.config import settings

        start = time.monotonic()
        r = aioredis.from_url(
            f"redis://{settings.redis.host}:{settings.redis.port}/{settings.redis.db}",
            socket_connect_timeout=2,
        )
        await r.ping()
        latency = (time.monotonic() - start) * 1000
        await r.aclose()

        return CheckResult(
            name="redis",
            status=CheckStatus.HEALTHY,
            latency_ms=latency,
        )
    except Exception as exc:
        return CheckResult(
            name="redis",
            status=CheckStatus.UNHEALTHY,
            error=f"{type(exc).__name__}: {exc}",
        )


async def check_llm_service() -> CheckResult:
    """检查 LLM 服务可用性（轻量级，只验证连通性）。"""
    try:
        from backend.services.llm_service import get_client

        start = time.monotonic()
        client = get_client()
        # 发一个最小请求验证 API Key 和网络
        await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            timeout=5,
        )
        latency = (time.monotonic() - start) * 1000

        return CheckResult(
            name="llm_service",
            status=CheckStatus.HEALTHY,
            latency_ms=latency,
            details={"model": "gpt-4o-mini"},
        )
    except Exception as exc:
        return CheckResult(
            name="llm_service",
            status=CheckStatus.UNHEALTHY,
            error=f"{type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_health_checker: HealthChecker | None = None


def get_health_checker() -> HealthChecker:
    """获取全局 HealthChecker 单例。"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker
