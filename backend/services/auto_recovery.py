"""CityFlow 自动恢复模块。

当健康检查发现服务异常时，自动执行恢复动作：
- 指数退避重试
- 冷却期控制，避免短时间内反复恢复
- 恢复历史记录，用于故障分析
- 与 HealthChecker 联动，自动响应异常

用法：
    recovery = AutoRecovery()
    recovery.register("database", recover_database)
    recovery.register("redis", recover_redis)

    # 配合 HealthChecker 自动触发
    health_checker.set_on_unhealthy(recovery.handle_unhealthy)

    # 或手动触发
    success = await recovery.attempt("database")
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

__all__ = [
    "AutoRecovery",
    "RecoveryAttempt",
    "RecoveryResult",
    "RecoveryStatus",
    "recover_database",
    "recover_llm_service",
    "recover_redis",
]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 状态枚举与数据结构
# ---------------------------------------------------------------------------


class RecoveryStatus(StrEnum):
    """恢复尝试结果状态。"""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED_COOLDOWN = "skipped_cooldown"
    SKIPPED_MAX_RETRIES = "skipped_max_retries"
    NO_ACTION = "no_action"


class RecoveryAttempt:
    """单次恢复尝试的记录。"""

    __slots__ = ("attempt", "error", "latency_ms", "service", "status", "timestamp")

    def __init__(
        self,
        service: str,
        status: RecoveryStatus,
        attempt: int = 0,
        error: str | None = None,
        latency_ms: float = 0.0,
    ) -> None:
        self.service = service
        self.status = status
        self.attempt = attempt
        self.error = error
        self.latency_ms = latency_ms
        self.timestamp = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "service": self.service,
            "status": self.status.value,
            "attempt": self.attempt,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp.isoformat(),
        }
        if self.error:
            result["error"] = self.error
        return result


class RecoveryResult:
    """一组恢复尝试的汇总结果。"""

    __slots__ = ("all_succeeded", "attempts", "timestamp")

    def __init__(self, attempts: list[RecoveryAttempt]) -> None:
        self.attempts = attempts
        self.all_succeeded = all(a.status == RecoveryStatus.SUCCESS for a in attempts)
        self.timestamp = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_succeeded": self.all_succeeded,
            "timestamp": self.timestamp.isoformat(),
            "attempts": [a.to_dict() for a in self.attempts],
        }


# ---------------------------------------------------------------------------
# 恢复函数类型
# ---------------------------------------------------------------------------

RecoveryFunc = Callable[[], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# 自动恢复器核心
# ---------------------------------------------------------------------------


class AutoRecovery:
    """自动恢复器。

    Args:
        max_retries: 每个服务的最大连续重试次数，超过后停止尝试。
        base_delay: 重试基础延迟秒数，实际延迟 = base_delay * 2^attempt。
        max_delay: 重试延迟上限秒数。
        cooldown: 恢复成功后的冷却期秒数，期间不再重试。
        history_size: 保留最近多少条恢复记录。
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        cooldown: float = 30.0,
        history_size: int = 200,
    ) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._cooldown = cooldown

        self._actions: dict[str, RecoveryFunc] = {}
        self._retry_counts: dict[str, int] = {}
        self._last_recovery: dict[str, float] = {}  # service -> monotonic timestamp
        self._history: deque[RecoveryAttempt] = deque(maxlen=history_size)

    # -- 注册 / 注销 --

    def register(self, service: str, action: RecoveryFunc) -> None:
        """注册一个恢复动作。

        Args:
            service: 服务名称，需与 HealthChecker 中的检查名对应。
            action: 异步恢复函数，无参数，失败时抛异常。
        """
        self._actions[service] = action
        logger.debug("已注册恢复动作: %s", service)

    def unregister(self, service: str) -> None:
        """注销一个恢复动作。"""
        self._actions.pop(service, None)
        self._retry_counts.pop(service, None)
        self._last_recovery.pop(service, None)

    # -- 恢复执行 --

    async def attempt(self, service: str) -> RecoveryAttempt:
        """尝试恢复单个服务。

        按以下顺序检查：
        1. 是否有注册的恢复动作
        2. 是否在冷却期内
        3. 是否超过最大重试次数
        4. 执行恢复动作（带指数退避等待）

        Args:
            service: 服务名称。

        Returns:
            RecoveryAttempt 记录。
        """
        # 无注册动作
        if service not in self._actions:
            attempt = RecoveryAttempt(
                service=service,
                status=RecoveryStatus.NO_ACTION,
            )
            self._history.append(attempt)
            return attempt

        # 冷却期检查
        last = self._last_recovery.get(service, 0.0)
        elapsed = time.monotonic() - last
        if elapsed < self._cooldown:
            remaining = self._cooldown - elapsed
            attempt = RecoveryAttempt(
                service=service,
                status=RecoveryStatus.SKIPPED_COOLDOWN,
                error=f"冷却期剩余 {remaining:.1f}s",
            )
            self._history.append(attempt)
            logger.info(
                "服务 %s 在冷却期内，跳过恢复 (剩余 %.1fs)",
                service,
                remaining,
            )
            return attempt

        # 重试次数检查
        current_retry = self._retry_counts.get(service, 0)
        if current_retry >= self._max_retries:
            attempt = RecoveryAttempt(
                service=service,
                status=RecoveryStatus.SKIPPED_MAX_RETRIES,
                attempt=current_retry,
                error=f"已达最大重试次数 {self._max_retries}",
            )
            self._history.append(attempt)
            logger.warning(
                "服务 %s 已达最大重试次数 (%d)，跳过恢复",
                service,
                self._max_retries,
            )
            return attempt

        # 指数退避等待
        delay = min(
            self._base_delay * (2**current_retry),
            self._max_delay,
        )
        if current_retry > 0:
            logger.info(
                "服务 %s 等待 %.1fs 后执行第 %d 次恢复",
                service,
                delay,
                current_retry + 1,
            )
            await asyncio.sleep(delay)

        # 执行恢复
        start = time.monotonic()
        try:
            logger.info("开始恢复服务: %s (第%d次)", service, current_retry + 1)
            await self._actions[service]()
            latency = (time.monotonic() - start) * 1000

            # 恢复成功
            self._retry_counts[service] = 0
            self._last_recovery[service] = time.monotonic()

            attempt = RecoveryAttempt(
                service=service,
                status=RecoveryStatus.SUCCESS,
                attempt=current_retry + 1,
                latency_ms=latency,
            )
            self._history.append(attempt)
            logger.info("服务 %s 恢复成功 (%.1fms)", service, latency)
            return attempt

        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            self._retry_counts[service] = current_retry + 1

            attempt = RecoveryAttempt(
                service=service,
                status=RecoveryStatus.FAILED,
                attempt=current_retry + 1,
                error=f"{type(exc).__name__}: {exc}",
                latency_ms=latency,
            )
            self._history.append(attempt)
            logger.error(
                "服务 %s 恢复失败 (第%d次): %s",
                service,
                current_retry + 1,
                exc,
            )
            return attempt

    async def attempt_many(self, services: list[str]) -> RecoveryResult:
        """并行恢复多个服务。

        Args:
            services: 需要恢复的服务名称列表。

        Returns:
            RecoveryResult 汇总。
        """
        if not services:
            return RecoveryResult(attempts=[])

        tasks = {svc: asyncio.create_task(self.attempt(svc)) for svc in services}

        attempts: list[RecoveryAttempt] = []
        for svc, task in tasks.items():
            try:
                attempts.append(await task)
            except Exception:
                attempts.append(
                    RecoveryAttempt(
                        service=svc,
                        status=RecoveryStatus.FAILED,
                        error="恢复任务执行异常",
                    )
                )

        result = RecoveryResult(attempts=attempts)
        if result.all_succeeded:
            logger.info("所有服务恢复成功: %s", services)
        else:
            failed = [a.service for a in attempts if a.status != RecoveryStatus.SUCCESS]
            logger.warning("部分服务恢复失败: %s", failed)
        return result

    # -- 与 HealthChecker 联动 --

    async def handle_unhealthy(self, report: Any) -> RecoveryResult:
        """HealthChecker 的 on_unhealthy 回调入口。

        从健康报告中提取不健康的服务，自动触发恢复。

        Args:
            report: HealthReport 实例，需有 unhealthy_names 属性。

        Returns:
            RecoveryResult 汇总。
        """
        unhealthy = getattr(report, "unhealthy_names", [])
        if not unhealthy:
            return RecoveryResult(attempts=[])

        # 只恢复已注册恢复动作的服务
        to_recover = [s for s in unhealthy if s in self._actions]
        if not to_recover:
            logger.info("无恢复动作可执行，不健康服务: %s", unhealthy)
            return RecoveryResult(attempts=[])

        logger.warning("触发自动恢复: %s", to_recover)
        return await self.attempt_many(to_recover)

    # -- 状态查询 --

    def reset_retry_count(self, service: str) -> None:
        """手动重置某个服务的重试计数。"""
        self._retry_counts.pop(service, None)

    def reset_all(self) -> None:
        """重置所有服务的重试计数。"""
        self._retry_counts.clear()

    def get_retry_count(self, service: str) -> int:
        """获取某个服务当前的连续重试次数。"""
        return self._retry_counts.get(service, 0)

    @property
    def history(self) -> list[RecoveryAttempt]:
        return list(self._history)

    def get_service_history(self, service: str) -> list[RecoveryAttempt]:
        """获取某个服务的恢复历史。"""
        return [a for a in self._history if a.service == service]


# ---------------------------------------------------------------------------
# 预定义恢复动作
# ---------------------------------------------------------------------------


async def recover_database() -> None:
    """恢复数据库连接池。

    策略：关闭旧引擎，创建新引擎。
    """
    from backend.database.base import engine

    logger.info("开始恢复数据库连接池")
    await engine.dispose()
    # dispose 之后，下次请求会自动创建新连接
    # 验证连接可用
    from sqlalchemy import text

    from backend.database.base import async_session_factory

    async with async_session_factory() as session:
        await session.execute(text("SELECT 1"))
    logger.info("数据库连接池恢复完成")


async def recover_redis() -> None:
    """恢复 Redis 连接。

    策略：关闭旧连接，重新 ping 验证。
    """
    import redis.asyncio as aioredis

    from backend.config import settings

    logger.info("开始恢复 Redis 连接")
    r = aioredis.from_url(
        f"redis://{settings.redis.host}:{settings.redis.port}/{settings.redis.db}",
        socket_connect_timeout=5,
    )
    await r.ping()
    await r.aclose()
    logger.info("Redis 连接恢复完成")


async def recover_llm_service() -> None:
    """恢复 LLM 服务客户端。

    策略：重置全局客户端实例，强制下次调用重新创建。
    """
    import backend.services.llm_service as llm_mod

    logger.info("开始恢复 LLM 服务客户端")
    llm_mod._openai_client = None
    # 触发重新创建并验证
    client = llm_mod.get_client()
    await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=1,
        timeout=5,
    )
    logger.info("LLM 服务客户端恢复完成")


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_auto_recovery: AutoRecovery | None = None


def get_auto_recovery() -> AutoRecovery:
    """获取全局 AutoRecovery 单例。"""
    global _auto_recovery
    if _auto_recovery is None:
        _auto_recovery = AutoRecovery()
    return _auto_recovery
