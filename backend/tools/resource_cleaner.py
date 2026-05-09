"""CityFlow 资源清理工具。

清理临时文件、缓存和过期日志，释放磁盘空间。

使用方式：
    from backend.tools.resource_cleaner import ResourceCleaner

    cleaner = ResourceCleaner()
    cleaner.clean_temp_files()
    cleaner.clean_cache()
    cleaner.clean_logs()
    print(cleaner.get_report())
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ResourceCleaner:
    """资源清理器。

    提供三类清理能力：
    - 临时文件：删除超过指定天数的文件
    - 缓存文件：当缓存总大小超过上限时，按修改时间从旧到新删除
    - 日志文件：删除超过指定天数的 .log 文件

    Attributes:
        _cleaned_count: 已清理的文件数量。
        _freed_space: 已释放的磁盘空间（字节）。
    """

    def __init__(self) -> None:
        self._cleaned_count: int = 0
        self._freed_space: int = 0

    def clean_temp_files(
        self,
        temp_dir: str = "temp",
        max_age_days: int = 7,
    ) -> None:
        """清理超过指定天数的临时文件。

        Args:
            temp_dir: 临时文件目录路径。
            max_age_days: 文件最大保留天数，默认 7 天。
        """
        temp_path = Path(temp_dir)

        if not temp_path.exists():
            logger.debug("临时目录不存在，跳过: %s", temp_path)
            return

        cutoff = datetime.now() - timedelta(days=max_age_days)

        for file_path in temp_path.rglob("*"):
            if not file_path.is_file():
                continue

            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

            if mtime < cutoff:
                size = file_path.stat().st_size
                file_path.unlink()
                self._cleaned_count += 1
                self._freed_space += size
                logger.info("删除临时文件: %s", file_path)

    def clean_cache(
        self,
        cache_dir: str = "cache",
        max_size_mb: int = 100,
    ) -> None:
        """清理缓存目录，使其总大小不超过指定上限。

        当缓存总大小超过 max_size_mb 时，按修改时间从旧到新依次删除文件，
        直到总大小降至上限以内。

        Args:
            cache_dir: 缓存目录路径。
            max_size_mb: 缓存大小上限（MB），默认 100。
        """
        cache_path = Path(cache_dir)

        if not cache_path.exists():
            logger.debug("缓存目录不存在，跳过: %s", cache_path)
            return

        max_size_bytes = max_size_mb * 1024 * 1024

        # 计算当前总大小
        total_size = sum(f.stat().st_size for f in cache_path.rglob("*") if f.is_file())

        if total_size <= max_size_bytes:
            logger.debug(
                "缓存大小 %.2f MB 未超限 (%d MB)，跳过",
                total_size / (1024 * 1024),
                max_size_mb,
            )
            return

        # 按修改时间排序，从最旧的开始删除
        files = sorted(
            [f for f in cache_path.rglob("*") if f.is_file()],
            key=lambda f: f.stat().st_mtime,
        )

        for file_path in files:
            if total_size <= max_size_bytes:
                break

            size = file_path.stat().st_size
            file_path.unlink()
            total_size -= size
            self._cleaned_count += 1
            self._freed_space += size
            logger.info("删除缓存文件: %s", file_path)

    def clean_logs(
        self,
        log_dir: str = "logs",
        max_age_days: int = 30,
    ) -> None:
        """清理超过指定天数的日志文件。

        Args:
            log_dir: 日志目录路径。
            max_age_days: 日志最大保留天数，默认 30 天。
        """
        log_path = Path(log_dir)

        if not log_path.exists():
            logger.debug("日志目录不存在，跳过: %s", log_path)
            return

        cutoff = datetime.now() - timedelta(days=max_age_days)

        for file_path in log_path.glob("*.log"):
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

            if mtime < cutoff:
                size = file_path.stat().st_size
                file_path.unlink()
                self._cleaned_count += 1
                self._freed_space += size
                logger.info("删除日志文件: %s", file_path)

    def get_report(self) -> dict[str, Any]:
        """获取清理报告。

        Returns:
            包含 cleaned_files 和 freed_space_mb 的字典。
        """
        return {
            "cleaned_files": self._cleaned_count,
            "freed_space_mb": round(self._freed_space / (1024 * 1024), 2),
        }

    def reset(self) -> None:
        """重置计数器，用于多次复用同一实例。"""
        self._cleaned_count = 0
        self._freed_space = 0
