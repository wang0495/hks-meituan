"""CityFlow 日志管理器。

统一门面，整合结构化日志、日志轮转、日志查询三大能力。
提供简洁的 API，避免使用者直接操作底层模块。

Usage:
    from backend.logging.manager import LogManager

    # 初始化（应用启动时调用一次）
    manager = LogManager(log_dir="logs", level="INFO")

    # 获取日志器
    logger = manager.get_logger("backend.api")
    logger.info("请求处理完成", extra={"extra": {"path": "/plan", "ms": 120}})

    # 查询日志
    results = manager.query.search("timeout", level="ERROR", max_results=50)

    # 统计
    stats = manager.query.get_statistics()
    print(stats)

    # 清理旧日志
    manager.cleanup_old_logs(max_age_days=30)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.logging.config import setup_logging
from backend.logging.query import LogQuery
from backend.logging.rotation import LogRotation
from backend.logging.structured import RequestLogger, get_logger


class LogManager:
    """日志管理器 -- 统一入口。

    封装结构化日志初始化、日志轮转、日志查询，
    让调用方只需面对一个对象。

    Args:
        log_dir: 日志文件目录，默认项目根目录下 logs/
        level: 根日志器级别，默认 INFO
        enable_console: 是否输出到控制台
        enable_file: 是否输出到文件
        enable_compression: 是否启用日志自动压缩
        max_bytes: 单文件最大字节数，默认 10MB
        backup_count: 按大小轮转的备份文件数，默认 5
        cleanup_days: 启动时自动清理超过此天数的日志，默认 30

    Attributes:
        rotation: 日志轮转管理器
        query: 日志查询器
    """

    def __init__(
        self,
        log_dir: str | Path | None = None,
        level: str = "INFO",
        enable_console: bool = True,
        enable_file: bool = True,
        enable_compression: bool = True,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        cleanup_days: int = 30,
    ) -> None:
        self._log_dir = Path(log_dir) if log_dir else None

        # 初始化全局日志配置，获取轮转管理器
        kwargs: dict[str, Any] = {
            "level": level,
            "enable_console": enable_console,
            "enable_file": enable_file,
            "enable_compression": enable_compression,
            "max_bytes": max_bytes,
            "backup_count": backup_count,
            "cleanup_days": cleanup_days,
        }
        if self._log_dir is not None:
            kwargs["log_dir"] = self._log_dir

        self.rotation: LogRotation = setup_logging(**kwargs)

        # 查询器使用同一日志目录
        self.query = LogQuery(log_dir=self.rotation.log_dir)

    @property
    def log_dir(self) -> Path:
        """日志目录路径。"""
        return self.rotation.log_dir

    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志器。

        代理到 structured.get_logger，保持一致行为。

        Args:
            name: 日志器名称，通常传 __name__

        Returns:
            logging.Logger 实例
        """
        return get_logger(name)

    def get_request_logger(self, name: str) -> RequestLogger:
        """获取请求级日志记录器。

        Args:
            name: 日志器名称

        Returns:
            RequestLogger 实例
        """
        return RequestLogger(get_logger(name))

    def cleanup_old_logs(self, max_age_days: int = 30) -> list[Path]:
        """清理超过指定天数的日志文件。

        Args:
            max_age_days: 最大保留天数，默认 30

        Returns:
            被删除的文件路径列表
        """
        return self.rotation.cleanup_old_logs(max_age_days=max_age_days)

    def compress_rotated_logs(self) -> list[Path]:
        """手动压缩所有未压缩的轮转日志文件。

        Returns:
            被压缩的文件路径列表
        """
        return self.rotation.compress_rotated_logs()

    def get_stats(self) -> dict[str, int | str]:
        """获取日志目录统计信息。

        Returns:
            包含文件数、总大小等信息的字典
        """
        return self.rotation.get_log_stats()
