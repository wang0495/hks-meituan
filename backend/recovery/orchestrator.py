"""恢复编排器。

将故障检测、自动恢复和降级策略串联成完整的服务调用链路：
调用失败 → 记录故障 → 达到阈值触发自动恢复 → 恢复失败则降级。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from backend.recovery.auto_recovery import AutoRecovery
from backend.recovery.fallback import FallbackStrategy
from backend.recovery.fault_detector import FaultDetector

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 服务调用的类型签名
ServiceCall = Callable[..., Awaitable[T]]


class RecoveryOrchestrator:
    """恢复编排器。

    将三个核心组件组合成完整的服务调用链路：
    1. 正常调用服务
    2. 调用失败时记录故障
    3. 达到故障阈值时尝试自动恢复
    4. 恢复失败时执行降级策略

    Args:
        fault_detector: 故障检测器。
        auto_recovery: 自动恢复器。
        fallback_strategy: 降级策略管理器。
    """

    def __init__(
        self,
        fault_detector: FaultDetector | None = None,
        auto_recovery: AutoRecovery | None = None,
        fallback_strategy: FallbackStrategy | None = None,
    ) -> None:
        self.detector = fault_detector or FaultDetector()
        self.recovery = auto_recovery or AutoRecovery()
        self.fallback = fallback_strategy or FallbackStrategy()

    async def call(
        self,
        service: str,
        func: ServiceCall[T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """带恢复能力的服务调用。

        调用流程：
        1. 如果服务已处于故障状态，直接尝试恢复
        2. 恢复成功则继续调用，失败则走降级
        3. 正常调用失败时记录故障，达到阈值触发恢复

        Args:
            service: 服务名称。
            func: 要调用的异步函数。
            *args: 传递给 func 的位置参数。
            **kwargs: 传递给 func 的关键字参数。

        Returns:
            func 的返回值，或降级函数的返回值。

        Raises:
            Exception: 无降级策略且调用失败时抛出原始异常。
        """
        # 如果服务已处于故障状态，先尝试恢复
        if self.detector.is_faulty(service):
            logger.warning("服务 %s 处于故障状态，尝试恢复", service)
            recovered = await self.recovery.attempt_recovery(service)
            if not recovered:
                return await self._do_fallback(service, *args, **kwargs)
            # 恢复成功，重置故障状态
            self.detector.reset(service)

        # 正常调用
        try:
            result = await func(*args, **kwargs)
            self.detector.record_success(service)
            return result
        except Exception:
            logger.exception("服务 %s 调用失败", service)
            is_faulty = self.detector.record_failure(service)

            if is_faulty:
                recovered = await self.recovery.attempt_recovery(service)
                if recovered:
                    self.detector.reset(service)
                    # 恢复后重试一次
                    try:
                        result = await func(*args, **kwargs)
                        self.detector.record_success(service)
                        return result
                    except Exception:
                        logger.exception("服务 %s 恢复后重试仍失败", service)
                return await self._do_fallback(service, *args, **kwargs)

            # 未达到故障阈值，直接抛出
            raise

    async def _do_fallback(
        self,
        service: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """执行降级策略。

        Args:
            service: 服务名称。
            *args: 传递给降级函数的位置参数。
            **kwargs: 传递给降级函数的关键字参数。

        Returns:
            降级函数的返回值。

        Raises:
            Exception: 无降级策略时抛出。
        """
        if self.fallback.has_fallback(service):
            return await self.fallback.execute(service, *args, **kwargs)

        logger.error("服务 %s 无降级策略，抛出异常", service)
        raise RuntimeError(f"服务 {service} 故障且无降级策略")

    def register_service(
        self,
        service: str,
        recovery_action: Callable[[], Awaitable[None]],
        fallback_action: Callable[..., Awaitable[Any]],
    ) -> None:
        """一次性注册服务的恢复动作和降级策略。

        Args:
            service: 服务名称。
            recovery_action: 异步恢复函数。
            fallback_action: 异步降级函数。
        """
        self.recovery.register_recovery(service, recovery_action)
        self.fallback.register(service, fallback_action)
        logger.info("已注册服务: %s (恢复 + 降级)", service)
