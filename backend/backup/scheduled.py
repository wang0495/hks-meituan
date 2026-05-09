"""定时备份任务。

支持定时全量备份和增量备份。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from backend.backup.manager import BackupError, BackupManager

logger = logging.getLogger(__name__)


class ScheduledBackup:
    """定时备份调度器。

    支持定时全量备份和增量备份，可配置备份策略。

    Args:
        backup_dir: 备份存储目录。
        full_backup_hours: 全量备份间隔（小时），默认 24。
        incremental_hours: 增量备份间隔（小时），默认 6。
        enable_full: 是否启用全量备份。
        enable_incremental: 是否启用增量备份。
        on_backup_complete: 备份完成回调。
        on_backup_error: 备份失败回调。
    """

    def __init__(
        self,
        backup_dir: str = "backups",
        full_backup_hours: int = 24,
        incremental_hours: int = 6,
        enable_full: bool = True,
        enable_incremental: bool = True,
        on_backup_complete: Callable[[str], Awaitable[None]] | None = None,
        on_backup_error: Callable[[str, Exception], Awaitable[None]] | None = None,
    ) -> None:
        self._backup_dir = backup_dir
        self._full_interval = full_backup_hours * 3600
        self._incremental_interval = incremental_hours * 3600
        self._enable_full = enable_full
        self._enable_incremental = enable_incremental
        self._on_backup_complete = on_backup_complete
        self._on_backup_error = on_backup_error
        self._running = False
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        """启动定时备份。

        同时启动全量备份和增量备份的定时任务。
        """
        if self._running:
            logger.warning("定时备份已在运行")
            return

        self._running = True
        logger.info(
            "启动定时备份 (全量: %s/%dh, 增量: %s/%dh)",
            "启用" if self._enable_full else "禁用",
            self._full_interval // 3600,
            "启用" if self._enable_incremental else "禁用",
            self._incremental_interval // 3600,
        )

        # 启动备份任务
        if self._enable_full:
            task = asyncio.create_task(self._run_full_backup_loop())
            self._tasks.append(task)

        if self._enable_incremental:
            task = asyncio.create_task(self._run_incremental_backup_loop())
            self._tasks.append(task)

    async def stop(self) -> None:
        """停止定时备份。"""
        if not self._running:
            return

        self._running = False
        logger.info("正在停止定时备份...")

        # 取消所有任务
        for task in self._tasks:
            task.cancel()

        # 等待任务结束
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks.clear()
        logger.info("定时备份已停止")

    async def run_now(self, backup_type: str = "full") -> str | None:
        """立即执行一次备份。

        Args:
            backup_type: 备份类型，"full" 或 "incremental"。

        Returns:
            备份名称，失败返回 None。
        """
        manager = BackupManager(backup_dir=self._backup_dir)

        try:
            if backup_type == "full":
                metadata = await manager.create_full_backup()
            else:
                metadata = await manager.create_incremental_backup()

            backup_name = metadata.name
            logger.info("手动备份完成: %s", backup_name)

            if self._on_backup_complete:
                await self._on_backup_complete(backup_name)

            return backup_name

        except BackupError as e:
            logger.error("手动备份失败: %s", e)
            if self._on_backup_error:
                await self._on_backup_error(backup_type, e)
            return None

    async def _run_full_backup_loop(self) -> None:
        """全量备份循环。"""
        while self._running:
            try:
                manager = BackupManager(backup_dir=self._backup_dir)
                metadata = await manager.create_full_backup()
                backup_name = metadata.name

                logger.info("定时全量备份完成: %s", backup_name)

                if self._on_backup_complete:
                    await self._on_backup_complete(backup_name)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("定时全量备份失败: %s", e)
                if self._on_backup_error:
                    await self._on_backup_error("full", e)

            # 等待下次备份
            try:
                await asyncio.sleep(self._full_interval)
            except asyncio.CancelledError:
                break

    async def _run_incremental_backup_loop(self) -> None:
        """增量备份循环。"""
        while self._running:
            try:
                manager = BackupManager(backup_dir=self._backup_dir)
                metadata = await manager.create_incremental_backup()
                backup_name = metadata.name

                logger.info("定时增量备份完成: %s", backup_name)

                if self._on_backup_complete:
                    await self._on_backup_complete(backup_name)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("定时增量备份失败: %s", e)
                if self._on_backup_error:
                    await self._on_backup_error("incremental", e)

            # 等待下次备份
            try:
                await asyncio.sleep(self._incremental_interval)
            except asyncio.CancelledError:
                break

    @property
    def is_running(self) -> bool:
        """定时备份是否正在运行。"""
        return self._running
