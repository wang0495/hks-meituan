"""CityFlow 结构化日志模块。

提供 JSON 格式的结构化日志输出，支持控制台和文件两种处理器。
所有服务模块统一通过 get_logger() 获取日志器。
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# 日志目录
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"


class JSONFormatter(logging.Formatter):
    """将日志记录格式化为 JSON 字符串。"""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)

        # 合并自定义字段（通过 extra={"extra": {...}} 传入）
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_data.update(record.extra)

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    """初始化全局日志配置。

    - 控制台输出 JSON 格式
    - 文件输出到 logs/cityflow.log（全量）
    - 文件输出到 logs/error.log（仅 ERROR 及以上）

    Args:
        level: 根日志器级别，如 "DEBUG" / "INFO" / "WARNING"
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    formatter = JSONFormatter()

    # 控制台
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    # 全量文件
    file_handler = logging.FileHandler(LOG_DIR / "cityflow.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 错误文件
    error_handler = logging.FileHandler(LOG_DIR / "error.log", encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志器。"""
    return logging.getLogger(name)


class RequestLogger:
    """请求级日志记录器，封装常用的业务日志方法。"""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration: float,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """记录 HTTP 请求日志。"""
        extra = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration * 1000, 2),
            "user_id": user_id,
            "session_id": session_id,
        }
        self.logger.info(
            "%s %s %s %.3fs",
            method,
            path,
            status_code,
            duration,
            extra={"extra": extra},
        )

    def log_route_planning(
        self,
        user_input: str,
        user_type: str,
        poi_count: int,
        duration: float,
    ) -> None:
        """记录路线规划日志。"""
        extra = {
            "user_input": user_input,
            "user_type": user_type,
            "poi_count": poi_count,
            "duration_ms": round(duration * 1000, 2),
        }
        self.logger.info(
            "Route planned: %s, %d POIs",
            user_type,
            poi_count,
            extra={"extra": extra},
        )

    def log_error(
        self,
        error: Exception,
        context: str,
        **kwargs: Any,
    ) -> None:
        """记录错误日志。"""
        extra = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            **kwargs,
        }
        self.logger.error(
            "Error in %s: %s",
            context,
            error,
            extra={"extra": extra},
            exc_info=True,
        )
