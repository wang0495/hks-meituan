"""CityFlow 定时备份调度器。

在后台按固定间隔自动创建备份并清理旧版本。
支持全量备份和增量备份的混合策略。

使用方式::

    from backend.services.scheduled_backup import get_scheduled_backup

    scheduler = get_scheduled_backup()

    # 启动（通常在 app startup 中调用）
    await scheduler.start()

    # 停止（通常在 app shutdown 中调用）
    await scheduler.stop()
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from backend.services.backup import get_backup

logger = logging.getLogger(__name__)


class ScheduledBackup:
    """定时备份调度器。

    通过 asyncio.Task 在后台循环执行备份任务。
    支持全量备份和增量备份的混合策略。

    Args:
        full_backup_hours: 全量备份间隔（小时），默认 24。
        incremental_hours: 增量备份间隔（小时），默认 6。
        keep_count: 每次备份后保留的版本数量，默认 10。
        enable_incremental: 是否启用增量备份，默认 True。
    """

    def __init__(
        self,
        full_backup_hours: int = 24,
        incremental_hours: int = 6,
        keep_count: int = 10,
        enable_incremental: bool = True,
        interval_hours: int | None = None,
    ) -> None:
        # 兼容旧参数
        if interval_hours is not None:
            full_backup_hours = interval_hours
        self._full_interval = full_backup_hours * 3600
        self._incremental_interval = incremental_hours * 3600
        self._keep_count = keep_count
        self._enable_incremental = enable_incremental
        self._task: asyncio.Task[None] | None = None
        self._incremental_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """启动定时备份调度器。

        如果已经在运行则忽略重复调用。
        """
        if self._task is not None and not self._task.done():
            logger.warning("定时备份调度器已在运行，忽略重复启动")
            return

        self._task = asyncio.create_task(self._run_full_loop())
        logger.info(
            "定时全量备份调度器已启动（间隔: %d 小时, 保留: %d 个版本）",
            self._full_interval // 3600,
            self._keep_count,
        )

        if self._enable_incremental:
            self._incremental_task = asyncio.create_task(
                self._run_incremental_loop()
            )
            logger.info(
                "定时增量备份调度器已启动（间隔: %d 小时）",
                self._incremental_interval // 3600,
            )

    async def stop(self) -> None:
        """停止定时备份调度器。

        取消后台任务并等待其完成。
        """
        tasks_to_cancel: list[asyncio.Task[None]] = []
        if self._task is not None and not self._task.done():
            tasks_to_cancel.append(self._task)
        if self._incremental_task is not None and not self._incremental_task.done():
            tasks_to_cancel.append(self._incremental_task)

        for task in tasks_to_cancel:
            task.cancel()

        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        self._task = None
        self._incremental_task = None
        logger.info("定时备份调度器已停止")

    @property
    def is_running(self) -> bool:
        """调度器是否正在运行。"""
        return self._task is not None and not self._task.done()

    async def run_now(
        self, backup_type: Literal["full", "incremental"] = "full"
    ) -> str | None:
        """立即执行一次备份（不等待定时周期）。

        Args:
            backup_type: 备份类型，"full" 或 "incremental"。

        Returns:
            备份名称，失败返回 None。
        """
        try:
            backup = get_backup()
            if backup_type == "incremental":
                name = await backup.create_incremental_backup()
            else:
                name = await backup.create_backup()
            await backup.cleanup_old_backups(keep_count=self._keep_count)
            return name
        except Exception:
            logger.exception("手动触发备份失败 (%s)", backup_type)
            return None

    async def _run_full_loop(self) -> None:
        """全量备份主循环。"""
        logger.info("全量备份循环启动")
        while True:
            try:
                backup = get_backup()
                name = await backup.create_backup()
                await backup.cleanup_old_backups(keep_count=self._keep_count)
                logger.info("定时全量备份完成: %s", name)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("定时全量备份失败，将在下次周期重试")

            try:
                await asyncio.sleep(self._full_interval)
            except asyncio.CancelledError:
                break

        logger.info("全量备份循环退出")

    async def _run_incremental_loop(self) -> None:
        """增量备份循环。"""
        logger.info("增量备份循环启动")
        # 等待第一次全量备份完成后再开始增量备份
        await asyncio.sleep(min(60, self._incremental_interval))

        while True:
            try:
                backup = get_backup()
                name = await backup.create_incremental_backup()
                logger.info("定时增量备份完成: %s", name)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("定时增量备份失败，将在下次周期重试")

            try:
                await asyncio.sleep(self._incremental_interval)
            except asyncio.CancelledError:
                break

        logger.info("增量备份循环退出")


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_scheduled_backup: ScheduledBackup | None = None


def get_scheduled_backup() -> ScheduledBackup:
    """获取全局定时备份调度器实例。"""
    global _scheduled_backup
    if _scheduled_backup is None:
        _scheduled_backup = ScheduledBackup()
    return _scheduled_backup


def reset_scheduled_backup() -> None:
    """重置全局定时备份调度器（仅用于测试）。"""
    global _scheduled_backup
    _scheduled_backup = None
