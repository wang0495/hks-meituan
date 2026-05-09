"""自动恢复器。

为各服务注册恢复动作，在故障发生时按指数退避策略自动重试，
直至恢复成功或耗尽最大重试次数。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# 恢复动作的类型签名：无参数、返回 None 的异步可调用对象
RecoveryAction = Callable[[], Awaitable[None]]


class AutoRecovery:
    """自动恢复器。

    Args:
        max_retries: 最大重试次数。
        base_delay: 指数退避的基础延迟（秒）。
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 2.0,
    ) -> None:
        self._recovery_actions: dict[str, RecoveryAction] = {}
        self._max_retries = max_retries
        self._base_delay = base_delay

    def register_recovery(self, service: str, action: RecoveryAction) -> None:
        """注册恢复动作。

        Args:
            service: 服务名称。
            action: 异步恢复函数，无参数，返回 None。
        """
        self._recovery_actions[service] = action
        logger.info("已注册恢复动作: %s", service)

    async def attempt_recovery(self, service: str) -> bool:
        """尝试恢复指定服务。

        按指数退避策略重试，成功返回 True，全部失败返回 False。

        Args:
            service: 服务名称。

        Returns:
            True 表示恢复成功，False 表示所有重试均失败。
        """
        if service not in self._recovery_actions:
            logger.warning("未注册恢复动作: %s", service)
            return False

        action = self._recovery_actions[service]

        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(
                    "尝试恢复服务 %s (第%d/%d次)",
                    service,
                    attempt,
                    self._max_retries,
                )
                await action()
                logger.info("服务 %s 恢复成功", service)
                return True
            except Exception:
                logger.exception("服务 %s 第%d次恢复失败", service, attempt)
                if attempt < self._max_retries:
                    delay = self._base_delay**attempt
                    logger.info("%.1f 秒后重试...", delay)
                    await asyncio.sleep(delay)

        logger.error(
            "服务 %s 恢复失败，已耗尽 %d 次重试",
            service,
            self._max_retries,
        )
        return False

    def has_recovery(self, service: str) -> bool:
        """检查是否已为指定服务注册恢复动作。

        Args:
            service: 服务名称。

        Returns:
            True 表示已注册。
        """
        return service in self._recovery_actions

    def unregister_recovery(self, service: str) -> None:
        """移除指定服务的恢复动作。

        Args:
            service: 服务名称。
        """
        self._recovery_actions.pop(service, None)


# ---------------------------------------------------------------------------
# 预定义恢复动作
# ---------------------------------------------------------------------------


async def restart_db_pool() -> None:
    """重启数据库连接池。

    TODO: 接入实际的数据库连接池管理器后实现具体逻辑。
    """
    logger.info("正在重启数据库连接池...")
    # 示例：
    # from backend.database import db_pool
    # await db_pool.close()
    # await db_pool.open()
    raise NotImplementedError("请在接入数据库后实现此方法")


async def reconnect_redis() -> None:
    """重连 Redis。

    TODO: 接入实际的 Redis 客户端后实现具体逻辑。
    """
    logger.info("正在重连 Redis...")
    # 示例：
    # from backend.database import redis_client
    # await redis_client.close()
    # await redis_client.open()
    raise NotImplementedError("请在接入 Redis 后实现此方法")
