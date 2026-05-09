"""CityFlow 自愈管理器。

整合故障检测、自动恢复和降级策略，提供统一的自愈流程：
    1. FaultDetector 检测到故障
    2. SelfHealing 协调恢复动作
    3. 恢复失败时切换到降级模式
    4. 降级模式下定期探测，服务恢复后自动切回

与现有模块的关系：
    - FaultDetector (本包): 滑动窗口故障频率检测
    - AutoRecovery (services): 单服务恢复执行（带冷却期和指数退避）
    - CircuitBreaker (services): 连续失败快速熔断
    - fallback (services): 函数级降级装饰器

SelfHealing 是最上层的编排者，把上述模块串联成完整自愈流程。

用法：
    healing = SelfHealing()
    healing.register_service(
        service="database",
        recovery=recover_database,
        degradation=degrade_database,
    )

    # 配合 FaultDetector 自动触发
    # 或手动触发
    result = await healing.heal("database")
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

from backend.resilience.fault_detector import (FaultDetector, FaultLevel,
                                               get_fault_detector)

__all__ = [
    "HealingStatus",
    "DegradationLevel",
    "HealingAttempt",
    "SelfHealing",
    "get_self_healing",
    "degrade_database",
    "degrade_redis",
    "degrade_llm_service",
]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 状态枚举
# ---------------------------------------------------------------------------


class HealingStatus(str, Enum):
    """自愈尝试结果。"""

    RECOVERED = "recovered"
    DEGRADED = "degraded"
    ALREADY_DEGRADED = "already_degraded"
    SKIPPED_COOLDOWN = "skipped_cooldown"
    NO_ACTION = "no_action"


class DegradationLevel(str, Enum):
    """降级程度。"""

    NONE = "none"
    LIGHT = "light"  # 部分功能降级，核心可用
    HEAVY = "heavy"  # 大部分功能降级，仅保留基本响应
    FULL = "full"  # 完全降级，返回静态兜底


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


class HealingAttempt:
    """单次自愈尝试记录。"""

    __slots__ = (
        "service",
        "status",
        "recovery_succeeded",
        "degradation_level",
        "latency_ms",
        "error",
        "timestamp",
    )

    def __init__(
        self,
        service: str,
        status: HealingStatus,
        recovery_succeeded: bool = False,
        degradation_level: DegradationLevel = DegradationLevel.NONE,
        latency_ms: float = 0.0,
        error: str | None = None,
    ) -> None:
        self.service = service
        self.status = status
        self.recovery_succeeded = recovery_succeeded
        self.degradation_level = degradation_level
        self.latency_ms = latency_ms
        self.error = error
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "service": self.service,
            "status": self.status.value,
            "recovery_succeeded": self.recovery_succeeded,
            "degradation_level": self.degradation_level.value,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp.isoformat(),
        }
        if self.error:
            result["error"] = self.error
        return result


# ---------------------------------------------------------------------------
# 函数类型
# ---------------------------------------------------------------------------

# 恢复函数：无参数异步函数，失败时抛异常
RecoveryFunc = Callable[[], Coroutine[Any, Any, None]]

# 降级函数：返回降级结果，接收当前降级级别
DegradationFunc = Callable[[DegradationLevel], Coroutine[Any, Any, Any]]


# ---------------------------------------------------------------------------
# 服务配置
# ---------------------------------------------------------------------------


class ServiceConfig:
    """单个服务的自愈配置。"""

    __slots__ = (
        "service",
        "recovery",
        "degradation",
        "probe",
        "cooldown_sec",
        "probe_interval_sec",
    )

    def __init__(
        self,
        service: str,
        recovery: RecoveryFunc | None = None,
        degradation: DegradationFunc | None = None,
        probe: Callable[[], Coroutine[Any, Any, bool]] | None = None,
        cooldown_sec: float = 60.0,
        probe_interval_sec: float = 30.0,
    ) -> None:
        self.service = service
        self.recovery = recovery
        self.degradation = degradation
        self.probe = probe
        self.cooldown_sec = cooldown_sec
        self.probe_interval_sec = probe_interval_sec


# ---------------------------------------------------------------------------
# 自愈管理器核心
# ---------------------------------------------------------------------------


class SelfHealing:
    """自愈管理器。

    编排故障检测 -> 自动恢复 -> 降级策略的完整流程。

    Args:
        fault_detector: 故障检测器实例，默认使用全局单例。
        history_size: 保留最近多少条自愈记录。
    """

    def __init__(
        self,
        fault_detector: FaultDetector | None = None,
        history_size: int = 500,
    ) -> None:
        self._detector = fault_detector or get_fault_detector()
        self._configs: dict[str, ServiceConfig] = {}
        self._degraded_services: dict[str, DegradationLevel] = {}
        self._last_heal_time: dict[str, float] = {}
        self._history: deque[HealingAttempt] = deque(maxlen=history_size)
        self._background_task: asyncio.Task[None] | None = None
        self._running = False

    # -- 注册服务 --

    def register_service(
        self,
        service: str,
        recovery: RecoveryFunc | None = None,
        degradation: DegradationFunc | None = None,
        probe: Callable[[], Coroutine[Any, Any, bool]] | None = None,
        cooldown_sec: float = 60.0,
        probe_interval_sec: float = 30.0,
    ) -> None:
        """注册一个服务的自愈配置。

        Args:
            service: 服务名称。
            recovery: 恢复函数，失败时抛异常。
            degradation: 降级函数，接收 DegradationLevel，返回降级结果。
            probe: 探测函数，返回 True 表示服务已恢复。
            cooldown_sec: 自愈冷却期（秒）。
            probe_interval_sec: 降级模式下的探测间隔（秒）。
        """
        self._configs[service] = ServiceConfig(
            service=service,
            recovery=recovery,
            degradation=degradation,
            probe=probe,
            cooldown_sec=cooldown_sec,
            probe_interval_sec=probe_interval_sec,
        )
        logger.info("[自愈] 已注册服务: %s", service)

    def unregister_service(self, service: str) -> None:
        """注销一个服务。"""
        self._configs.pop(service, None)
        self._degraded_services.pop(service, None)
        self._last_heal_time.pop(service, None)

    # -- 记录调用结果（对接 FaultDetector）--

    def record_failure(self, service: str) -> None:
        """记录服务调用失败，委托给 FaultDetector。"""
        self._detector.record_failure(service)

    def record_success(self, service: str) -> None:
        """记录服务调用成功，委托给 FaultDetector。"""
        self._detector.record_success(service)
        # 如果之前降级了，成功后自动恢复
        if service in self._degraded_services:
            self._degraded_services.pop(service)
            logger.info("[自愈] 服务 %s 调用成功，退出降级模式", service)

    # -- 自愈流程 --

    async def heal(self, service: str) -> HealingAttempt:
        """对单个服务执行自愈流程。

        流程：
        1. 检查是否在冷却期
        2. 尝试恢复
        3. 恢复失败则切换到降级模式

        Args:
            service: 服务名称。

        Returns:
            HealingAttempt 记录。
        """
        config = self._configs.get(service)
        if config is None:
            attempt = HealingAttempt(
                service=service,
                status=HealingStatus.NO_ACTION,
            )
            self._history.append(attempt)
            return attempt

        # 已经降级的服务，不重复降级
        if service in self._degraded_services:
            attempt = HealingAttempt(
                service=service,
                status=HealingStatus.ALREADY_DEGRADED,
                degradation_level=self._degraded_services[service],
            )
            self._history.append(attempt)
            return attempt

        # 冷却期检查
        last = self._last_heal_time.get(service, 0.0)
        elapsed = time.monotonic() - last
        if elapsed < config.cooldown_sec:
            remaining = config.cooldown_sec - elapsed
            attempt = HealingAttempt(
                service=service,
                status=HealingStatus.SKIPPED_COOLDOWN,
                error=f"冷却期剩余 {remaining:.1f}s",
            )
            self._history.append(attempt)
            return attempt

        start = time.monotonic()

        # 步骤 1: 尝试恢复
        recovery_ok = False
        if config.recovery:
            try:
                logger.info("[自愈] 尝试恢复服务: %s", service)
                await config.recovery()
                recovery_ok = True
                latency = (time.monotonic() - start) * 1000
                logger.info("[自愈] 服务 %s 恢复成功 (%.1fms)", service, latency)
            except Exception as exc:
                latency = (time.monotonic() - start) * 1000
                logger.warning(
                    "[自愈] 服务 %s 恢复失败: %s",
                    service,
                    exc,
                )

        if recovery_ok:
            self._last_heal_time[service] = time.monotonic()
            self._detector.record_success(service)
            attempt = HealingAttempt(
                service=service,
                status=HealingStatus.RECOVERED,
                recovery_succeeded=True,
                latency_ms=latency,
            )
            self._history.append(attempt)
            return attempt

        # 步骤 2: 恢复失败，切换到降级模式
        degradation_level = self._determine_degradation_level(service)
        self._degraded_services[service] = degradation_level
        self._last_heal_time[service] = time.monotonic()

        if config.degradation:
            try:
                await config.degradation(degradation_level)
                logger.info(
                    "[自愈] 服务 %s 已切换到降级模式 (%s)",
                    service,
                    degradation_level.value,
                )
            except Exception as exc:
                logger.error(
                    "[自愈] 服务 %s 降级函数执行失败: %s",
                    service,
                    exc,
                )

        attempt = HealingAttempt(
            service=service,
            status=HealingStatus.DEGRADED,
            recovery_succeeded=False,
            degradation_level=degradation_level,
            latency_ms=(time.monotonic() - start) * 1000,
        )
        self._history.append(attempt)
        return attempt

    async def heal_many(self, services: list[str]) -> list[HealingAttempt]:
        """并行对多个服务执行自愈。"""
        if not services:
            return []

        tasks = {svc: asyncio.create_task(self.heal(svc)) for svc in services}

        results: list[HealingAttempt] = []
        for svc, task in tasks.items():
            try:
                results.append(await task)
            except Exception:
                results.append(
                    HealingAttempt(
                        service=svc,
                        status=HealingStatus.NO_ACTION,
                        error="自愈任务执行异常",
                    )
                )
        return results

    async def heal_all_faulty(self) -> list[HealingAttempt]:
        """自动对所有处于故障状态的服务执行自愈。"""
        faulty = [
            svc
            for svc in self._configs
            if self._detector.is_faulty(svc) or self._detector.is_critical(svc)
        ]
        if not faulty:
            return []
        logger.warning("[自愈] 检测到故障服务: %s，开始自愈", faulty)
        return await self.heal_many(faulty)

    # -- 降级查询 --

    def is_degraded(self, service: str) -> bool:
        """服务是否处于降级模式。"""
        return service in self._degraded_services

    def get_degradation_level(self, service: str) -> DegradationLevel:
        """获取服务当前降级级别。"""
        return self._degraded_services.get(service, DegradationLevel.NONE)

    def get_degraded_services(self) -> dict[str, DegradationLevel]:
        """获取所有降级中的服务。"""
        return dict(self._degraded_services)

    # -- 探测恢复 --

    async def probe_service(self, service: str) -> bool:
        """探测降级中的服务是否已恢复。

        调用注册的 probe 函数，如果返回 True，退出降级模式。

        Args:
            service: 服务名称。

        Returns:
            True 表示服务已恢复。
        """
        config = self._configs.get(service)
        if config is None or config.probe is None:
            return False

        if service not in self._degraded_services:
            return True  # 没有降级，不需要探测

        try:
            ok = await config.probe()
            if ok:
                self._degraded_services.pop(service, None)
                self._detector.record_success(service)
                logger.info("[自愈] 服务 %s 探测成功，退出降级模式", service)
                return True
        except Exception as exc:
            logger.debug("[自愈] 服务 %s 探测失败: %s", service, exc)

        return False

    async def probe_all_degraded(self) -> dict[str, bool]:
        """探测所有降级中的服务。"""
        results: dict[str, bool] = {}
        for service in list(self._degraded_services.keys()):
            results[service] = await self.probe_service(service)
        return results

    # -- 后台监控 --

    async def start(self, check_interval: float = 30.0) -> None:
        """启动后台自愈监控。

        定期执行：
        1. 检测故障服务并触发自愈
        2. 探测降级中的服务是否已恢复

        Args:
            check_interval: 检查间隔（秒）。
        """
        if self._running:
            return

        self._running = True
        self._background_task = asyncio.create_task(self._monitor_loop(check_interval))
        logger.info("[自愈] 后台监控已启动 (间隔=%.0fs)", check_interval)

    async def _monitor_loop(self, interval: float) -> None:
        while self._running:
            try:
                # 自愈故障服务
                await self.heal_all_faulty()
                # 探测降级服务
                await self.probe_all_degraded()
            except Exception:
                logger.exception("[自愈] 后台监控异常")
            await asyncio.sleep(interval)

    def stop(self) -> None:
        """停止后台监控。"""
        self._running = False
        if self._background_task and not self._background_task.done():
            self._background_task.cancel()
            logger.info("[自愈] 后台监控已停止")

    # -- 历史与状态 --

    @property
    def history(self) -> list[HealingAttempt]:
        return list(self._history)

    def get_service_history(self, service: str) -> list[HealingAttempt]:
        return [a for a in self._history if a.service == service]

    def get_status(self) -> dict[str, Any]:
        """获取自愈管理器整体状态。"""
        return {
            "registered_services": list(self._configs.keys()),
            "degraded_services": {
                svc: lvl.value for svc, lvl in self._degraded_services.items()
            },
            "fault_detector": self._detector.get_all_statuses(),
            "running": self._running,
        }

    # -- 内部方法 --

    def _determine_degradation_level(self, service: str) -> DegradationLevel:
        """根据故障严重程度决定降级级别。"""
        level = self._detector.get_level(service)
        match level:
            case FaultLevel.FAULTY:
                return DegradationLevel.HEAVY
            case FaultLevel.CRITICAL:
                return DegradationLevel.LIGHT
            case _:
                return DegradationLevel.LIGHT


# ---------------------------------------------------------------------------
# 预定义降级函数
# ---------------------------------------------------------------------------


async def degrade_database(level: DegradationLevel) -> None:
    """数据库降级策略。

    - LIGHT: 切换到只读模式（如果有读写分离）
    - HEAVY: 启用查询缓存，延长缓存 TTL
    - FULL: 所有写操作返回失败，读操作返回缓存数据
    """
    match level:
        case DegradationLevel.LIGHT:
            logger.info("[降级] 数据库切换到轻度降级: 启用读写分离只读模式")
        case DegradationLevel.HEAVY:
            logger.warning("[降级] 数据库切换到重度降级: 启用查询缓存")
        case DegradationLevel.FULL:
            logger.error("[降级] 数据库完全降级: 写操作暂停，读操作使用缓存")
        case _:
            pass


async def degrade_redis(level: DegradationLevel) -> None:
    """Redis 降级策略。

    - LIGHT: 缩短缓存 TTL，减少内存占用
    - HEAVY: 禁用非核心缓存，仅保留会话缓存
    - FULL: 完全禁用缓存，所有请求穿透到数据源
    """
    match level:
        case DegradationLevel.LIGHT:
            logger.info("[降级] Redis 切换到轻度降级: 缩短 TTL")
        case DegradationLevel.HEAVY:
            logger.warning("[降级] Redis 切换到重度降级: 仅保留会话缓存")
        case DegradationLevel.FULL:
            logger.error("[降级] Redis 完全降级: 禁用所有缓存")
        case _:
            pass


async def degrade_llm_service(level: DegradationLevel) -> None:
    """LLM 服务降级策略。

    - LIGHT: 切换到更小/更快的模型，降低质量换可用性
    - HEAVY: 禁用 LLM 润色，仅使用模板文案
    - FULL: 返回固定兜底文案，完全不调用 LLM
    """
    match level:
        case DegradationLevel.LIGHT:
            logger.info("[降级] LLM 切换到轻度降级: 使用轻量模型")
        case DegradationLevel.HEAVY:
            logger.warning("[降级] LLM 切换到重度降级: 禁用润色，仅模板文案")
        case DegradationLevel.FULL:
            logger.error("[降级] LLM 完全降级: 返回固定兜底文案")
        case _:
            pass


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_self_healing: SelfHealing | None = None


def get_self_healing() -> SelfHealing:
    """获取全局 SelfHealing 单例。"""
    global _self_healing
    if _self_healing is None:
        _self_healing = SelfHealing()
    return _self_healing
