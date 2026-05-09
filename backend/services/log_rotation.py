"""CityFlow 日志轮转配置。

提供两种轮转策略：
- 按大小轮转：单文件 10MB，保留 5 个备份
- 按时间轮转：每天午夜轮转，保留 30 天
"""

from __future__ import annotations

from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"


def setup_log_rotation() -> tuple[RotatingFileHandler, TimedRotatingFileHandler]:
    """创建并返回两个轮转文件处理器。

    Returns:
        (size_handler, time_handler) -- 调用方自行挂载到日志器上
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 按大小轮转：单文件 10MB，保留 5 个备份
    size_handler = RotatingFileHandler(
        LOG_DIR / "cityflow.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )

    # 按时间轮转：每天午夜，保留 30 天
    time_handler = TimedRotatingFileHandler(
        LOG_DIR / "cityflow_daily.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )

    return size_handler, time_handler
