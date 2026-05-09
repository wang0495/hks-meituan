"""CityFlow 结构化日志模块。

提供 JSON 格式的结构化日志输出，支持控制台和文件两种处理器。
所有服务模块统一通过 get_logger() 获取日志器。

Features:
    - JSON 格式输出，便于日志采集系统解析
    - 自动包含 timestamp / level / logger / module / function / line
    - 支持 extra 字段扩展
    - 异常信息自动序列化
    - 请求级日志记录器 RequestLogger
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 日志目录
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"


class JSONFormatter(logging.Formatter):
    """将日志记录格式化为 JSON 字符串。

    输出示例:
        {"timestamp":"2026-05-09T10:00:00+00:00","level":"INFO","logger":"backend.main",
         "message":"服务启动","module":"main","function":"startup","line":42}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 异常信息
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)

        # 合并自定义字段（通过 extra={"extra": {...}} 传入）
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_data.update(record.extra)

        return json.dumps(log_data, ensure_ascii=False)


class _LevelFilter(logging.Filter):
    """只允许指定级别及以上的日志通过。"""

    def __init__(self, min_level: int) -> None:
        super().__init__()
        self._min_level = min_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= self._min_level


def setup_logging(
    level: str = "INFO",
    log_dir: Path | str | None = None,
    enable_console: bool = True,
    enable_file: bool = True,
) -> None:
    """初始化全局日志配置。

    - 控制台输出 JSON 格式（可关闭）
    - 文件输出到 logs/cityflow.log（全量）
    - 文件输出到 logs/error.log（仅 ERROR 及以上）

    Args:
        level: 根日志器级别，如 "DEBUG" / "INFO" / "WARNING"
        log_dir: 日志目录，默认为项目根目录下的 logs/
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出
    """
    log_path = Path(log_dir) if log_dir else LOG_DIR

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # 避免重复添加处理器
    if root_logger.handlers:
        return

    formatter = JSONFormatter()

    # 控制台
    if enable_console:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        root_logger.addHandler(console)

    # 文件输出
    if enable_file:
        log_path.mkdir(parents=True, exist_ok=True)

        # 全量文件
        file_handler = logging.FileHandler(log_path / "cityflow.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # 错误文件
        error_handler = logging.FileHandler(log_path / "error.log", encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志器。

    Args:
        name: 日志器名称，通常传 __name__

    Returns:
        logging.Logger 实例
    """
    return logging.getLogger(name)


class RequestLogger:
    """请求级日志记录器，封装常用的业务日志方法。

    Usage:
        req_logger = RequestLogger(get_logger("api"))
        req_logger.log_request("GET", "/api/plan", 200, 0.123)
        req_logger.log_error(exc, "route_planning")
    """

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
        """记录 HTTP 请求日志。

        Args:
            method: HTTP 方法
            path: 请求路径
            status_code: 响应状态码
            duration: 请求耗时（秒）
            user_id: 用户 ID
            session_id: 会话 ID
        """
        extra: dict[str, Any] = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration * 1000, 2),
        }
        if user_id:
            extra["user_id"] = user_id
        if session_id:
            extra["session_id"] = session_id

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
        """记录路线规划日志。

        Args:
            user_input: 用户输入
            user_type: 用户类型
            poi_count: POI 数量
            duration: 规划耗时（秒）
        """
        extra: dict[str, Any] = {
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
        """记录错误日志。

        Args:
            error: 异常对象
            context: 出错上下文描述
            **kwargs: 额外字段
        """
        extra: dict[str, Any] = {
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
