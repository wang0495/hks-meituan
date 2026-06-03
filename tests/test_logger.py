"""日志系统测试。"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING
from unittest.mock import patch

from backend.services.log_rotation import setup_log_rotation
from backend.services.logger import JSONFormatter, RequestLogger, get_logger, setup_logging

if TYPE_CHECKING:
    from pathlib import Path


class TestJSONFormatter:
    """JSON 格式化器测试。"""

    def test_basic_format(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        result = json.loads(formatter.format(record))
        assert result["level"] == "INFO"
        assert result["message"] == "hello"
        assert result["logger"] == "test"
        assert "timestamp" in result

    def test_exception_format(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )
        result = json.loads(formatter.format(record))
        assert "exception" in result
        assert "ValueError: boom" in result["exception"]

    def test_extra_fields(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="request",
            args=(),
            exc_info=None,
        )
        record.extra = {"method": "GET", "path": "/api/health"}
        result = json.loads(formatter.format(record))
        assert result["method"] == "GET"
        assert result["path"] == "/api/health"


class TestSetupLogging:
    """setup_logging 集成测试。"""

    def test_creates_log_dir(self, tmp_path: Path):
        with patch("backend.services.logger.LOG_DIR", tmp_path / "logs"):
            setup_logging("INFO")
            assert (tmp_path / "logs").exists()

    def test_logger_level(self):
        logger = get_logger("test_level")
        assert isinstance(logger, logging.Logger)


class TestRequestLogger:
    """RequestLogger 测试。"""

    def test_log_request(self, caplog):
        logger = logging.getLogger("test_req")
        req_logger = RequestLogger(logger)
        with caplog.at_level(logging.INFO, logger="test_req"):
            req_logger.log_request("GET", "/api/health", 200, 0.05)
        assert "GET" in caplog.text
        assert "/api/health" in caplog.text

    def test_log_error(self, caplog):
        logger = logging.getLogger("test_err")
        req_logger = RequestLogger(logger)
        with caplog.at_level(logging.ERROR, logger="test_err"):
            req_logger.log_error(ValueError("bad input"), "route_planning")
        assert "bad input" in caplog.text


class TestLogRotation:
    """日志轮转测试。"""

    def test_setup_returns_handlers(self, tmp_path: Path):
        with patch("backend.services.log_rotation.LOG_DIR", tmp_path / "logs"):
            (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
            size_h, time_h = setup_log_rotation()
            assert size_h.maxBytes == 10 * 1024 * 1024
            assert size_h.backupCount == 5
            assert time_h.when == "MIDNIGHT"
            assert time_h.backupCount == 30


class TestLogRotationNew:
    """新版 LogRotation（轮转 + 清理 + 压缩）测试。"""

    def test_rotation_creates_handlers(self, tmp_path: Path):
        from backend.logging.rotation import (
            CompressedRotatingFileHandler,
            CompressedTimedRotatingFileHandler,
            LogRotation,
        )

        r = LogRotation(log_dir=tmp_path, enable_compression=True)
        assert isinstance(r.size_handler, CompressedRotatingFileHandler)
        assert isinstance(r.time_handler, CompressedTimedRotatingFileHandler)
        assert r.compression_enabled is True
        r.size_handler.close()
        r.time_handler.close()

    def test_rotation_no_compression(self, tmp_path: Path):
        from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

        from backend.logging.rotation import LogRotation

        r = LogRotation(log_dir=tmp_path, enable_compression=False)
        assert isinstance(r.size_handler, RotatingFileHandler)
        assert isinstance(r.time_handler, TimedRotatingFileHandler)
        assert r.compression_enabled is False
        r.size_handler.close()
        r.time_handler.close()

    def test_cleanup_old_logs_returns_empty_when_no_files(self, tmp_path: Path):
        from backend.logging.rotation import LogRotation

        r = LogRotation(log_dir=tmp_path)
        deleted = r.cleanup_old_logs(max_age_days=30)
        assert deleted == []
        r.size_handler.close()
        r.time_handler.close()

    def test_cleanup_old_logs_removes_old_files(self, tmp_path: Path):
        import time as _time

        from backend.logging.rotation import LogRotation

        # Create an old log file
        old_file = tmp_path / "old.log"
        old_file.write_text("old data", encoding="utf-8")
        # Set mtime to 60 days ago
        old_ts = _time.time() - (60 * 86400)
        os.utime(old_file, (old_ts, old_ts))

        # Create a recent log file
        recent_file = tmp_path / "recent.log"
        recent_file.write_text("recent data", encoding="utf-8")

        r = LogRotation(log_dir=tmp_path)
        deleted = r.cleanup_old_logs(max_age_days=30)
        assert len(deleted) == 1
        assert old_file not in deleted or not old_file.exists()
        assert recent_file.exists()
        r.size_handler.close()
        r.time_handler.close()

    def test_compress_rotated_logs(self, tmp_path: Path):
        import gzip

        from backend.logging.rotation import LogRotation

        # Create simulated rotated log files
        for i in range(1, 4):
            f = tmp_path / f"cityflow.log.{i}"
            f.write_text(f"log data {i}\n" * 100, encoding="utf-8")

        r = LogRotation(log_dir=tmp_path, enable_compression=False)
        compressed = r.compress_rotated_logs()

        assert len(compressed) == 3
        # Verify .gz files exist and are valid
        for i in range(1, 4):
            gz = tmp_path / f"cityflow.log.{i}.gz"
            assert gz.exists()
            with gzip.open(gz, "rt", encoding="utf-8") as f:
                assert f"log data {i}" in f.read()
        r.size_handler.close()
        r.time_handler.close()

    def test_get_log_stats(self, tmp_path: Path):
        from backend.logging.rotation import LogRotation

        (tmp_path / "test.log").write_text("x" * 1024, encoding="utf-8")
        r = LogRotation(log_dir=tmp_path)
        stats = r.get_log_stats()
        assert stats["file_count"] >= 1
        assert stats["total_bytes"] >= 1024
        r.size_handler.close()
        r.time_handler.close()

    def test_attach_to(self, tmp_path: Path):
        import logging as _logging

        from backend.logging.rotation import LogRotation

        r = LogRotation(log_dir=tmp_path)
        test_logger = _logging.getLogger("test_attach")
        initial_count = len(test_logger.handlers)
        r.attach_to(test_logger)
        assert len(test_logger.handlers) == initial_count + 2
        # Cleanup
        for h in list(test_logger.handlers):
            h.close()
            test_logger.removeHandler(h)


class TestLogConfig:
    """日志配置（config.py）测试。"""

    def test_setup_logging_returns_rotation(self, tmp_path: Path):
        import logging as _logging

        from backend.logging.config import setup_logging

        # Clear root logger handlers first
        root = _logging.getLogger()
        root.handlers.clear()

        rotation = setup_logging(
            level="INFO",
            log_dir=tmp_path,
            enable_console=False,
            enable_file=True,
            enable_compression=True,
        )
        assert rotation is not None
        assert rotation.compression_enabled is True

        # Cleanup
        root.handlers.clear()

    def test_setup_logging_console_only(self, tmp_path: Path):
        import logging as _logging

        from backend.logging.config import setup_logging

        root = _logging.getLogger()
        root.handlers.clear()

        setup_logging(
            level="DEBUG",
            log_dir=tmp_path,
            enable_console=True,
            enable_file=False,
        )
        # Should have at least console handler
        assert len(root.handlers) >= 1
        root.handlers.clear()
