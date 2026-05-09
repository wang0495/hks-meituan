"""CityFlow 日志分析器。

提供日志文件解析、关键词搜索、级别过滤和统计汇总功能。
支持标准 Python logging 格式的日志文件。

日志行格式::

    2026-05-09 10:30:00 - ERROR - Some error message
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 日志行正则
# ---------------------------------------------------------------------------
# 匹配格式: "2026-05-09 10:30:00 - LEVEL - message"
_LOG_PATTERN = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r"\s*-\s*(?P<level>\w+)"
    r"\s*-\s*(?P<message>.*)"
)


class LogLevel(StrEnum):
    """日志级别。"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class LogEntry:
    """单条日志记录。"""

    timestamp: str
    level: str
    message: str
    source_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "source_file": self.source_file,
        }

    @property
    def datetime(self) -> datetime | None:
        """尝试将 timestamp 解析为 datetime 对象。"""
        try:
            return datetime.strptime(self.timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


@dataclass
class LogStatistics:
    """日志统计结果。"""

    total_entries: int = 0
    level_counts: dict[str, int] = field(default_factory=dict)
    file_count: int = 0

    @property
    def error_count(self) -> int:
        """ERROR 级别日志数。"""
        return self.level_counts.get(LogLevel.ERROR, 0)

    @property
    def critical_count(self) -> int:
        """CRITICAL 级别日志数。"""
        return self.level_counts.get(LogLevel.CRITICAL, 0)

    @property
    def has_critical_issues(self) -> bool:
        """是否存在严重问题。"""
        return self.critical_count > 0 or self.error_count > 10

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "total_entries": self.total_entries,
            "level_counts": dict(self.level_counts),
            "file_count": self.file_count,
            "error_count": self.error_count,
            "critical_count": self.critical_count,
        }


class LogAnalyzer:
    """日志分析器。

    用法::

        analyzer = LogAnalyzer("logs")
        entries = analyzer.parse_log_file(Path("logs/app.log"))
        errors = analyzer.search_logs("timeout", level="ERROR")
        stats = analyzer.get_statistics()
    """

    def __init__(self, log_dir: str | Path = "logs") -> None:
        self._log_dir = Path(log_dir)

    @property
    def log_dir(self) -> Path:
        """日志目录路径。"""
        return self._log_dir

    def _log_files(self) -> list[Path]:
        """获取所有 .log 文件。"""
        if not self._log_dir.is_dir():
            return []
        return sorted(self._log_dir.glob("*.log"))

    # ------------------------------------------------------------------
    # 解析
    # ------------------------------------------------------------------

    def parse_log_line(self, line: str, source_file: str = "") -> LogEntry | None:
        """解析单行日志。

        Args:
            line: 原始日志行文本。
            source_file: 来源文件名（可选）。

        Returns:
            解析成功返回 LogEntry，否则返回 None。
        """
        match = _LOG_PATTERN.match(line.strip())
        if not match:
            return None

        return LogEntry(
            timestamp=match.group("timestamp"),
            level=match.group("level").upper(),
            message=match.group("message").strip(),
            source_file=source_file,
        )

    def parse_log_file(self, log_file: Path) -> list[LogEntry]:
        """解析整个日志文件。

        Args:
            log_file: 日志文件路径。

        Returns:
            解析成功的日志条目列表。解析失败的行会被跳过。

        Raises:
            FileNotFoundError: 文件不存在。
        """
        if not log_file.is_file():
            raise FileNotFoundError(f"日志文件不存在: {log_file}")

        entries: list[LogEntry] = []
        source = log_file.name

        with open(log_file, encoding="utf-8", errors="replace") as f:
            for line in f:
                entry = self.parse_log_line(line, source_file=source)
                if entry is not None:
                    entries.append(entry)

        return entries

    def parse_all(self) -> list[LogEntry]:
        """解析日志目录下所有 .log 文件。

        Returns:
            所有日志条目的合并列表。
        """
        entries: list[LogEntry] = []
        for log_file in self._log_files():
            entries.extend(self.parse_log_file(log_file))
        return entries

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------

    def search_logs(
        self,
        keyword: str,
        level: str | None = None,
        case_sensitive: bool = False,
    ) -> list[LogEntry]:
        """按关键词搜索日志。

        Args:
            keyword: 搜索关键词。
            level: 可选的日志级别过滤（如 "ERROR"）。
            case_sensitive: 是否区分大小写，默认不区分。

        Returns:
            匹配的日志条目列表。
        """
        results: list[LogEntry] = []

        for log_file in self._log_files():
            entries = self.parse_log_file(log_file)
            for entry in entries:
                # 级别过滤
                if level is not None and entry.level != level.upper():
                    continue
                # 关键词匹配
                if case_sensitive:
                    match = keyword in entry.message
                else:
                    match = keyword.lower() in entry.message.lower()
                if match:
                    results.append(entry)

        return results

    def search_by_time_range(
        self,
        start: datetime,
        end: datetime,
    ) -> list[LogEntry]:
        """按时间范围搜索日志。

        Args:
            start: 起始时间（含）。
            end: 结束时间（含）。

        Returns:
            时间范围内的日志条目列表。
        """
        results: list[LogEntry] = []

        for entry in self.parse_all():
            dt = entry.datetime
            if dt is not None and start <= dt <= end:
                results.append(entry)

        return results

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_statistics(self) -> LogStatistics:
        """获取日志统计信息。

        Returns:
            包含各级别计数和总数的统计对象。
        """
        level_counts: Counter[str] = Counter()
        total = 0
        file_count = 0

        for log_file in self._log_files():
            file_count += 1
            entries = self.parse_log_file(log_file)
            total += len(entries)
            for entry in entries:
                level_counts[entry.level] += 1

        return LogStatistics(
            total_entries=total,
            level_counts=dict(level_counts),
            file_count=file_count,
        )
