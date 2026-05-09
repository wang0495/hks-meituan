"""CityFlow 日志查询工具。

支持按关键词、日志级别、时间范围搜索日志文件。
适用于结构化 JSON 日志和普通文本日志。

Usage:
    from backend.logging.query import LogQuery

    query = LogQuery(log_dir="logs")

    # 按关键词搜索
    results = query.search("timeout")

    # 按级别过滤
    errors = query.search("error", level="ERROR")

    # 按时间范围搜索
    recent = query.search("planning", since="2026-05-09T00:00:00")

    # 搜索多个文件
    for result in results:
        print(f"{result['file']}:{result['line']} - {result['content']}")
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LogEntry:
    """单条日志查询结果。

    Attributes:
        file: 日志文件名
        line: 行号
        content: 原始内容
        timestamp: 解析后的时间戳（仅 JSON 日志）
        level: 日志级别（仅 JSON 日志）
    """

    file: str
    line: int
    content: str
    timestamp: str | None = None
    level: str | None = None


class LogQuery:
    """日志查询器。

    Args:
        log_dir: 日志文件目录，默认 logs/

    Attributes:
        log_dir: 日志目录路径
    """

    def __init__(self, log_dir: str | Path = "logs") -> None:
        self.log_dir = Path(log_dir)

    def search(
        self,
        keyword: str,
        level: str | None = None,
        since: str | datetime | None = None,
        until: str | datetime | None = None,
        file_pattern: str = "*.log",
        max_results: int = 100,
    ) -> list[LogEntry]:
        """搜索日志。

        Args:
            keyword: 搜索关键词（不区分大小写）
            level: 日志级别过滤，如 "ERROR" / "INFO"
            since: 起始时间（ISO 格式字符串或 datetime 对象）
            until: 结束时间（ISO 格式字符串或 datetime 对象）
            file_pattern: 文件匹配模式，默认 "*.log"
            max_results: 最大返回条数，默认 100

        Returns:
            匹配的日志条目列表
        """
        if not self.log_dir.exists():
            return []

        since_dt = self._parse_datetime(since)
        until_dt = self._parse_datetime(until)

        results: list[LogEntry] = []

        for log_file in sorted(self.log_dir.glob(file_pattern)):
            if len(results) >= max_results:
                break
            results.extend(
                self._search_file(
                    log_file,
                    keyword=keyword,
                    level=level,
                    since=since_dt,
                    until=until_dt,
                    remaining=max_results - len(results),
                )
            )

        return results

    def tail(self, n: int = 50, file_pattern: str = "*.log") -> list[LogEntry]:
        """获取最近 N 条日志。

        Args:
            n: 返回条数，默认 50
            file_pattern: 文件匹配模式，默认 "*.log"

        Returns:
            最近的日志条目列表
        """
        if not self.log_dir.exists():
            return []

        results: list[LogEntry] = []

        for log_file in sorted(self.log_dir.glob(file_pattern)):
            lines = log_file.read_text(encoding="utf-8").splitlines()
            for line_num, line in enumerate(lines[-n:], len(lines) - n + 1):
                entry = self._parse_line(log_file.name, line_num, line)
                if entry:
                    results.append(entry)

        return results[-n:]

    def list_files(self, file_pattern: str = "*.log") -> list[Path]:
        """列出日志文件。

        Args:
            file_pattern: 文件匹配模式，默认 "*.log"

        Returns:
            日志文件路径列表
        """
        if not self.log_dir.exists():
            return []
        return sorted(self.log_dir.glob(file_pattern))

    def _search_file(
        self,
        log_file: Path,
        keyword: str,
        level: str | None,
        since: datetime | None,
        until: datetime | None,
        remaining: int,
    ) -> list[LogEntry]:
        """搜索单个日志文件。"""
        results: list[LogEntry] = []
        keyword_lower = keyword.lower()

        try:
            with open(log_file, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if len(results) >= remaining:
                        break

                    line_stripped = line.strip()
                    if not line_stripped:
                        continue

                    # 关键词匹配
                    if keyword_lower not in line_stripped.lower():
                        continue

                    entry = self._parse_line(log_file.name, line_num, line_stripped)
                    if entry is None:
                        continue

                    # 级别过滤
                    if level and entry.level and entry.level.upper() != level.upper():
                        continue

                    # 时间过滤
                    if entry.timestamp:
                        try:
                            entry_dt = datetime.fromisoformat(entry.timestamp)
                            if since and entry_dt < since:
                                continue
                            if until and entry_dt > until:
                                continue
                        except ValueError:
                            pass

                    results.append(entry)
        except (OSError, UnicodeDecodeError):
            pass

        return results

    def _parse_line(self, filename: str, line_num: int, line: str) -> LogEntry | None:
        """解析单行日志，尝试 JSON 解析。"""
        timestamp: str | None = None
        level: str | None = None

        try:
            data = json.loads(line)
            timestamp = data.get("timestamp")
            level = data.get("level")
        except (json.JSONDecodeError, TypeError):
            pass

        return LogEntry(
            file=filename,
            line=line_num,
            content=line,
            timestamp=timestamp,
            level=level,
        )

    def get_statistics(
        self, file_pattern: str = "*.log"
    ) -> dict[str, int | dict[str, int]]:
        """获取日志统计信息。

        扫描所有日志文件，统计各级别日志条数。

        Args:
            file_pattern: 文件匹配模式，默认 "*.log"

        Returns:
            包含 total_entries 和 level_counts 的字典
        """
        level_counts: dict[str, int] = {}
        total_entries = 0

        for log_file in self.log_dir.glob(file_pattern):
            try:
                with open(log_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        total_entries += 1
                        entry = self._parse_line(log_file.name, 0, line)
                        if entry and entry.level:
                            level_counts[entry.level] = (
                                level_counts.get(entry.level, 0) + 1
                            )
            except (OSError, UnicodeDecodeError):
                continue

        return {
            "total_entries": total_entries,
            "level_counts": level_counts,
        }

    @staticmethod
    def _parse_datetime(value: str | datetime | None) -> datetime | None:
        """解析时间参数。"""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value)
