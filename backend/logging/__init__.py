"""CityFlow 日志模块。

提供结构化 JSON 日志、日志轮转、日志清理、日志压缩四大功能。

Usage:
    from backend.logging import get_logger, setup_logging
    from backend.logging.rotation import LogRotation
    from backend.logging.query import LogQuery

    # 初始化日志（应用启动时调用一次）
    rotation = setup_logging(level="INFO")

    # 获取日志器
    logger = get_logger(__name__)
    logger.info("服务启动", extra={"extra": {"port": 8000}})

    # 手动清理旧日志
    rotation.cleanup_old_logs(max_age_days=30)

    # 手动压缩轮转日志
    rotation.compress_rotated_logs()
"""

from __future__ import annotations

from backend.logging.config import setup_logging
from backend.logging.manager import LogManager
from backend.logging.query import LogQuery
from backend.logging.rotation import LogRotation
from backend.logging.structured import JSONFormatter, RequestLogger, get_logger

__all__ = [
    "JSONFormatter",
    "LogManager",
    "LogQuery",
    "LogRotation",
    "RequestLogger",
    "get_logger",
    "setup_logging",
]
