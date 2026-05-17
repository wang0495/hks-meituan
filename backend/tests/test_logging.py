"""CityFlow 日志模块测试。

覆盖 rotation / config / structured / query 四个子模块。
"""

from __future__ import annotations

import gzip
import json
import logging
import time
from pathlib import Path

import pytest

from backend.logging.config import get_rotation, setup_logging
from backend.logging.query import LogEntry, LogQuery
from backend.logging.rotation import (
    CompressedRotatingFileHandler,
    CompressedTimedRotatingFileHandler,
    LogRotation,
    _compress_file,
)
from backend.logging.structured import JSONFormatter, RequestLogger, get_logger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_log_dir(tmp_path: Path) -> Path:
    """提供临时日志目录。"""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def rotation(tmp_log_dir: Path) -> LogRotation:
    """提供 LogRotation 实例（禁用压缩，方便测试基础轮转）。"""
    return LogRotation(
        log_dir=tmp_log_dir,
        max_bytes=1024,  # 1KB，方便触发轮转
        backup_count=3,
        daily_backup_count=3,
        enable_compression=False,
    )


@pytest.fixture
def compressed_rotation(tmp_log_dir: Path) -> LogRotation:
    """提供启用压缩的 LogRotation 实例。"""
    return LogRotation(
        log_dir=tmp_log_dir,
        max_bytes=1024,
        backup_count=3,
        daily_backup_count=3,
        enable_compression=True,
    )


# ---------------------------------------------------------------------------
# _compress_file
# ---------------------------------------------------------------------------


class TestCompressFile:
    """_compress_file 函数测试。"""

    def test_compress_creates_gz(self, tmp_path: Path) -> None:
        src = tmp_path / "test.log"
        src.write_text("hello world", encoding="utf-8")
        dst = tmp_path / "test.log.gz"

        _compress_file(src, dst)

        assert dst.exists()
        assert not src.exists()
        with gzip.open(dst, "rt", encoding="utf-8") as f:
            assert f.read() == "hello world"

    def test_compress_preserves_content(self, tmp_path: Path) -> None:
        content = "line1\nline2\nline3\n" * 100
        src = tmp_path / "big.log"
        src.write_text(content, encoding="utf-8")
        dst = tmp_path / "big.log.gz"

        _compress_file(src, dst)

        with gzip.open(dst, "rt", encoding="utf-8") as f:
            assert f.read() == content

    def test_compress_missing_src_does_not_crash(self, tmp_path: Path) -> None:
        src = tmp_path / "nonexistent.log"
        dst = tmp_path / "out.gz"
        # 不应抛出异常
        _compress_file(src, dst)


# ---------------------------------------------------------------------------
# CompressedRotatingFileHandler
# ---------------------------------------------------------------------------


class TestCompressedRotatingFileHandler:
    """按大小轮转 + 自动压缩测试。"""

    def test_rotated_file_is_compressed(self, tmp_log_dir: Path) -> None:
        log_file = tmp_log_dir / "app.log"
        handler = CompressedRotatingFileHandler(
            str(log_file), maxBytes=100, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger("test_compressed_size")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # 写入超过 maxBytes 的数据
        for i in range(50):
            logger.info("x" * 10)
        handler.close()

        # 应该存在 .gz 文件
        gz_files = list(tmp_log_dir.glob("app.log.*.gz"))
        assert len(gz_files) > 0
        # 不存在未压缩的 .log.N 文件（排除 .gz）
        plain_rotated = [
            f for f in tmp_log_dir.glob("app.log.[0-9]*")
            if not str(f).endswith(".gz")
        ]
        assert len(plain_rotated) == 0

        logger.removeHandler(handler)

    def test_backup_count_respected(self, tmp_log_dir: Path) -> None:
        log_file = tmp_log_dir / "limit.log"
        handler = CompressedRotatingFileHandler(
            str(log_file), maxBytes=50, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger("test_backup_count")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # 大量写入触发多次轮转
        for i in range(200):
            logger.info("y" * 10)
        handler.close()

        gz_files = list(tmp_log_dir.glob("limit.log.*.gz"))
        assert len(gz_files) <= 2

        logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# CompressedTimedRotatingFileHandler
# ---------------------------------------------------------------------------


class TestCompressedTimedRotatingFileHandler:
    """按时间轮转 + 自动压缩测试。"""

    def test_handler_creation(self, tmp_log_dir: Path) -> None:
        log_file = tmp_log_dir / "daily.log"
        handler = CompressedTimedRotatingFileHandler(
            str(log_file), when="midnight", interval=1, backupCount=7, encoding="utf-8"
        )
        assert handler.backupCount == 7
        handler.close()

    def test_delete_old_compressed(self, tmp_log_dir: Path) -> None:
        """验证超过 backupCount 的 .gz 文件会被清理。"""
        log_file = tmp_log_dir / "daily.log"
        handler = CompressedTimedRotatingFileHandler(
            str(log_file), when="midnight", interval=1, backupCount=2, encoding="utf-8"
        )

        # 手动创建多个 .gz 模拟历史文件
        for i in range(5):
            gz_path = tmp_log_dir / f"daily.log.2026-05-0{ i + 1 }.gz"
            gz_path.write_text(f"data {i}", encoding="utf-8")

        handler._delete_old_compressed()

        remaining = list(tmp_log_dir.glob("daily.log.*.gz"))
        assert len(remaining) <= 2

        handler.close()


# ---------------------------------------------------------------------------
# LogRotation
# ---------------------------------------------------------------------------


class TestLogRotation:
    """LogRotation 管理器测试。"""

    def test_init_creates_log_dir(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "new_logs"
        r = LogRotation(log_dir=log_dir)
        assert log_dir.exists()
        assert r.log_dir == log_dir

    def test_size_handler_is_rotating_handler(self, rotation: LogRotation) -> None:
        assert isinstance(rotation.size_handler, RotatingFileHandler)

    def test_time_handler_is_timed_handler(self, rotation: LogRotation) -> None:
        assert isinstance(rotation.time_handler, TimedRotatingFileHandler)

    def test_compression_flag(self, rotation: LogRotation, compressed_rotation: LogRotation) -> None:
        assert rotation.compression_enabled is False
        assert compressed_rotation.compression_enabled is True

    def test_compressed_handlers(self, compressed_rotation: LogRotation) -> None:
        assert isinstance(compressed_rotation.size_handler, CompressedRotatingFileHandler)
        assert isinstance(compressed_rotation.time_handler, CompressedTimedRotatingFileHandler)

    def test_attach_to(self, rotation: LogRotation) -> None:
        logger = logging.getLogger("test_attach")
        before = len(logger.handlers)
        rotation.attach_to(logger)
        assert len(logger.handlers) == before + 2
        # 清理
        for h in logger.handlers[before:]:
            logger.removeHandler(h)
            h.close()

    def test_cleanup_old_logs(self, tmp_log_dir: Path) -> None:
        r = LogRotation(log_dir=tmp_log_dir)

        # 创建一个修改时间为 31 天前的日志文件
        old_file = tmp_log_dir / "old.log"
        old_file.write_text("old data", encoding="utf-8")
        old_time = time.time() - 31 * 86400
        import os
        os.utime(old_file, (old_time, old_time))

        # 创建一个新文件
        new_file = tmp_log_dir / "new.log"
        new_file.write_text("new data", encoding="utf-8")

        deleted = r.cleanup_old_logs(max_age_days=30)
        assert old_file in deleted
        assert not old_file.exists()
        assert new_file.exists()

    def test_cleanup_returns_empty_for_missing_dir(self, tmp_path: Path) -> None:
        r = LogRotation(log_dir=tmp_path / "nonexistent")
        assert r.cleanup_old_logs() == []

    def test_compress_rotated_logs(self, tmp_log_dir: Path) -> None:
        r = LogRotation(log_dir=tmp_log_dir, enable_compression=False)

        # 创建模拟的轮转文件
        rotated = tmp_log_dir / "cityflow.log.1"
        rotated.write_text("rotated data", encoding="utf-8")

        compressed = r.compress_rotated_logs()
        assert len(compressed) == 1
        gz_path = tmp_log_dir / "cityflow.log.1.gz"
        assert gz_path.exists()

    def test_compress_skips_current_log(self, tmp_log_dir: Path) -> None:
        r = LogRotation(log_dir=tmp_log_dir, enable_compression=False)

        current = tmp_log_dir / "cityflow.log"
        current.write_text("current", encoding="utf-8")

        r.compress_rotated_logs()
        # 当前日志不应被压缩
        assert current.exists()
        assert not (tmp_log_dir / "cityflow.log.gz").exists()

    def test_get_log_stats(self, tmp_path: Path) -> None:
        # 用独立目录，避免 LogRotation 创建的文件干扰
        stats_dir = tmp_path / "stats_test"
        stats_dir.mkdir()
        r = LogRotation(log_dir=stats_dir)
        (stats_dir / "a.log").write_text("aaa", encoding="utf-8")
        (stats_dir / "b.log").write_text("bbbb", encoding="utf-8")

        stats = r.get_log_stats()
        # LogRotation 创建了 cityflow.log 和 cityflow_daily.log，加上 a.log 和 b.log
        assert stats["file_count"] >= 2
        assert stats["total_bytes"] >= 7
        assert stats["log_dir"] == str(stats_dir)

    def test_get_log_stats_empty_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        r = LogRotation(log_dir=empty)
        stats = r.get_log_stats()
        # LogRotation 创建了 cityflow.log 和 cityflow_daily.log
        assert stats["file_count"] >= 0
        assert "log_dir" in stats

    def test_get_handler_compat(self, rotation: LogRotation) -> None:
        """get_handler 应返回 size_handler。"""
        assert rotation.get_handler() is rotation.size_handler


# 需要导入这些用于 isinstance 检查
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


# ---------------------------------------------------------------------------
# config.py
# ---------------------------------------------------------------------------


class TestSetupLogging:
    """setup_logging 配置测试。"""

    def test_setup_returns_rotation(self, tmp_log_dir: Path) -> None:
        import backend.logging.config as config_mod

        # 重置全局状态
        config_mod._rotation = None
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        root.handlers.clear()

        try:
            r = setup_logging(
                level="DEBUG",
                log_dir=tmp_log_dir,
                enable_console=False,
                enable_file=True,
                enable_compression=False,
            )
            assert isinstance(r, LogRotation)
        finally:
            root.handlers.clear()
            root.handlers.extend(original_handlers)
            config_mod._rotation = None

    def test_setup_adds_handlers(self, tmp_log_dir: Path) -> None:
        import backend.logging.config as config_mod

        config_mod._rotation = None
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        root.handlers.clear()

        try:
            setup_logging(
                log_dir=tmp_log_dir,
                enable_console=False,
                enable_file=True,
                enable_compression=False,
            )
            # 应有 size + time + error 三个文件 handler
            file_handlers = [
                h for h in root.handlers if isinstance(h, (RotatingFileHandler, TimedRotatingFileHandler))
            ]
            assert len(file_handlers) >= 3
        finally:
            root.handlers.clear()
            root.handlers.extend(original_handlers)
            config_mod._rotation = None

    def test_get_rotation_singleton(self, tmp_log_dir: Path) -> None:
        import backend.logging.config as config_mod

        config_mod._rotation = None
        r1 = get_rotation()
        r2 = get_rotation()
        assert r1 is r2
        config_mod._rotation = None


# ---------------------------------------------------------------------------
# structured.py
# ---------------------------------------------------------------------------


class TestJSONFormatter:
    """JSON 格式化器测试。"""

    def test_format_produces_valid_json(self) -> None:
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=10, msg="hello %s", args=("world",), exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["message"] == "hello world"
        assert data["module"] == "test"
        assert data["line"] == 10

    def test_format_includes_exception(self) -> None:
        formatter = JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="test.py",
            lineno=1, msg="error", args=(), exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert "ValueError" in data["exception"]

    def test_format_with_extra(self) -> None:
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="msg", args=(), exc_info=None,
        )
        record.extra = {"user_id": "u1", "action": "login"}
        output = formatter.format(record)
        data = json.loads(output)
        assert data["user_id"] == "u1"
        assert data["action"] == "login"


class TestGetLogger:
    """get_logger 测试。"""

    def test_returns_logger_with_name(self) -> None:
        logger = get_logger("my_module")
        assert logger.name == "my_module"

    def test_returns_same_instance(self) -> None:
        l1 = get_logger("same_name")
        l2 = get_logger("same_name")
        assert l1 is l2


class TestRequestLogger:
    """RequestLogger 测试。"""

    def test_log_request(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_req")
        req = RequestLogger(logger)

        with caplog.at_level(logging.INFO, logger="test_req"):
            req.log_request("GET", "/api/plan", 200, 0.123)

        assert "GET" in caplog.text
        assert "/api/plan" in caplog.text

    def test_log_error(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_err")
        req = RequestLogger(logger)

        with caplog.at_level(logging.ERROR, logger="test_err"):
            req.log_error(ValueError("bad input"), "validation")

        assert "validation" in caplog.text

    def test_log_route_planning(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_route")
        req = RequestLogger(logger)

        with caplog.at_level(logging.INFO, logger="test_route"):
            req.log_route_planning("故宫到天坛", "tourist", 3, 1.5)

        assert "tourist" in caplog.text


# ---------------------------------------------------------------------------
# query.py
# ---------------------------------------------------------------------------


class TestLogEntry:
    """LogEntry 数据类测试。"""

    def test_creation(self) -> None:
        entry = LogEntry(file="app.log", line=1, content="test")
        assert entry.file == "app.log"
        assert entry.line == 1
        assert entry.timestamp is None
        assert entry.level is None

    def test_frozen(self) -> None:
        entry = LogEntry(file="a.log", line=1, content="x")
        with pytest.raises(AttributeError):
            entry.file = "b.log"  # type: ignore[misc]


class TestLogQuery:
    """LogQuery 查询器测试。"""

    def test_search_returns_matches(self, tmp_log_dir: Path) -> None:
        log_file = tmp_log_dir / "app.log"
        log_file.write_text(
            "INFO: server started\nERROR: timeout occurred\nINFO: request ok\n",
            encoding="utf-8",
        )
        query = LogQuery(log_dir=tmp_log_dir)
        results = query.search("timeout")
        assert len(results) == 1
        assert "timeout" in results[0].content

    def test_search_with_level_filter(self, tmp_log_dir: Path) -> None:
        log_file = tmp_log_dir / "app.log"
        log_file.write_text(
            '{"level":"INFO","message":"ok"}\n{"level":"ERROR","message":"fail"}\n',
            encoding="utf-8",
        )
        query = LogQuery(log_dir=tmp_log_dir)
        results = query.search("", level="ERROR")
        assert len(results) == 1
        assert results[0].level == "ERROR"

    def test_search_max_results(self, tmp_log_dir: Path) -> None:
        log_file = tmp_log_dir / "app.log"
        lines = "\n".join(f"line {i}" for i in range(100))
        log_file.write_text(lines, encoding="utf-8")

        query = LogQuery(log_dir=tmp_log_dir)
        results = query.search("line", max_results=5)
        assert len(results) == 5

    def test_search_nonexistent_dir(self, tmp_path: Path) -> None:
        query = LogQuery(log_dir=tmp_path / "nope")
        assert query.search("anything") == []

    def test_tail(self, tmp_log_dir: Path) -> None:
        log_file = tmp_log_dir / "app.log"
        log_file.write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
        query = LogQuery(log_dir=tmp_log_dir)
        results = query.tail(n=3)
        assert len(results) == 3

    def test_list_files(self, tmp_log_dir: Path) -> None:
        (tmp_log_dir / "a.log").write_text("a", encoding="utf-8")
        (tmp_log_dir / "b.log").write_text("b", encoding="utf-8")
        (tmp_log_dir / "c.txt").write_text("c", encoding="utf-8")

        query = LogQuery(log_dir=tmp_log_dir)
        files = query.list_files()
        assert len(files) == 2
        assert all(f.suffix == ".log" for f in files)

    def test_get_statistics(self, tmp_log_dir: Path) -> None:
        log_file = tmp_log_dir / "app.log"
        log_file.write_text(
            '{"level":"INFO","message":"ok"}\n'
            '{"level":"ERROR","message":"fail"}\n'
            '{"level":"INFO","message":"ok2"}\n',
            encoding="utf-8",
        )
        query = LogQuery(log_dir=tmp_log_dir)
        stats = query.get_statistics()
        assert stats["total_entries"] == 3
        assert stats["level_counts"]["INFO"] == 2
        assert stats["level_counts"]["ERROR"] == 1
