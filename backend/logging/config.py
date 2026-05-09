"""CityFlow 日志配置。

整合结构化日志、轮转、清理、压缩四大能力。
这是日志系统的统一入口，替代原先分散在 structured.py 和 rotation.py 的初始化逻辑。

Usage:
    from backend.logging.config import setup_logging, get_rotation

    # 初始化日志（通常在应用启动时调用一次）
    setup_logging(level="INFO")

    # 获取轮转管理器（用于手动清理/压缩）
    rotation = get_rotation()
    rotation.cleanup_old_logs(max_age_days=30)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from backend.logging.rotation import (CompressedRotatingFileHandler,
                                      LogRotation, RotatingFileHandler)
from backend.logging.structured import JSONFormatter

# 默认日志目录：项目根目录/logs
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"

# 模块级单例
_rotation: LogRotation | None = None


def get_rotation() -> LogRotation:
    """获取全局 LogRotation 单例。

    如果尚未初始化，会使用默认配置创建。

    Returns:
        LogRotation 实例
    """
    global _rotation
    if _rotation is None:
        _rotation = LogRotation(log_dir=LOG_DIR)
    return _rotation


def setup_logging(
    level: str = "INFO",
    log_dir: Path | str | None = None,
    enable_console: bool = True,
    enable_file: bool = True,
    enable_compression: bool = True,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    daily_backup_count: int = 30,
    cleanup_days: int = 30,
) -> LogRotation:
    """初始化全局日志配置。

    配置层次：
    1. 控制台 -- JSON 格式（可通过 enable_console 关闭）
    2. 文件（按大小轮转）-- logs/cityflow.log，全量
    3. 文件（按大小轮转）-- logs/error.log，仅 ERROR 及以上
    4. 文件（按时间轮转）-- logs/cityflow_daily.log，每天一份

    Args:
        level: 根日志器级别，如 "DEBUG" / "INFO" / "WARNING"
        log_dir: 日志目录，默认为项目根目录下的 logs/
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出
        enable_compression: 是否启用日志自动压缩
        max_bytes: 单文件最大字节数，默认 10MB
        backup_count: 按大小轮转的备份文件数，默认 5
        daily_backup_count: 按时间轮转的备份文件数，默认 30
        cleanup_days: 启动时自动清理超过此天数的日志，默认 30

    Returns:
        LogRotation 实例，可用于后续手动管理
    """
    global _rotation

    log_path = Path(log_dir) if log_dir else LOG_DIR
    log_path.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # 避免重复添加处理器
    if root_logger.handlers:
        return get_rotation()

    formatter = JSONFormatter()

    # 控制台
    if enable_console:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        root_logger.addHandler(console)

    # 文件输出（使用轮转）
    if enable_file:
        _rotation = LogRotation(
            log_dir=log_path,
            max_bytes=max_bytes,
            backup_count=backup_count,
            daily_backup_count=daily_backup_count,
            enable_compression=enable_compression,
        )

        # 全量日志 -- 按大小轮转
        _rotation.size_handler.setFormatter(formatter)
        root_logger.addHandler(_rotation.size_handler)

        # 每日日志 -- 按时间轮转
        _rotation.time_handler.setFormatter(formatter)
        root_logger.addHandler(_rotation.time_handler)

        # 错误日志 -- 按大小轮转，仅 ERROR 及以上
        error_file = str(log_path / "error.log")
        if enable_compression:
            error_handler: RotatingFileHandler = CompressedRotatingFileHandler(
                error_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
        else:
            error_handler = RotatingFileHandler(
                error_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_handler)

        # 启动时自动清理旧日志
        if cleanup_days > 0:
            _rotation.cleanup_old_logs(max_age_days=cleanup_days)

    return _rotation if _rotation else get_rotation()
