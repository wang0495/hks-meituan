"""CityFlow 日志轮转、清理与压缩。

提供三种日志管理能力：
- 按大小轮转：单文件默认 10MB，保留 5 个备份
- 按时间轮转：每天午夜轮转，保留 30 天
- 旧日志清理：按天数清理过期日志文件
- 日志压缩：轮转后自动压缩旧日志为 .gz

Usage:
    from backend.logging.rotation import LogRotation

    rotation = LogRotation(log_dir="logs")

    # 挂载到日志器
    root_logger.addHandler(rotation.size_handler)
    root_logger.addHandler(rotation.time_handler)

    # 清理 30 天前的日志
    rotation.cleanup_old_logs(max_age_days=30)

    # 手动压缩所有未压缩的轮转日志
    rotation.compress_rotated_logs()
"""

from __future__ import annotations

import gzip
import logging
import shutil
import time
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path


class CompressedRotatingFileHandler(RotatingFileHandler):
    """轮转时自动压缩旧日志文件的 RotatingFileHandler。

    与标准 RotatingFileHandler 行为一致，区别在于轮转产生的备份文件
    会被 gzip 压缩为 .gz 格式，节省磁盘空间。
    """

    def doRollover(self) -> None:
        """执行轮转并压缩被轮转出的文件。"""
        if self.stream:
            self.stream.close()
            self.stream = None  # type: ignore[assignment]

        # 轮转已有备份文件 (app.log.5.gz -> app.log.6.gz, ...)
        for i in range(self.backupCount - 1, 0, -1):
            src_gz = f"{self.baseFilename}.{i}.gz"
            dst_gz = f"{self.baseFilename}.{i + 1}.gz"
            src_plain = f"{self.baseFilename}.{i}"
            if Path(src_gz).exists():
                if i + 1 >= self.backupCount:
                    Path(src_gz).unlink(missing_ok=True)
                else:
                    Path(src_gz).rename(dst_gz)
            elif Path(src_plain).exists():
                # 未压缩的旧备份也要处理
                if i + 1 >= self.backupCount:
                    Path(src_plain).unlink(missing_ok=True)
                else:
                    _compress_file(Path(src_plain), Path(dst_gz))

        # 当前日志 -> .1.gz
        dst_gz = f"{self.baseFilename}.1.gz"
        current = Path(self.baseFilename)
        if current.exists():
            _compress_file(current, Path(dst_gz))

        # 重新打开日志文件
        if not self.delay:
            self.stream = self._open()


class CompressedTimedRotatingFileHandler(TimedRotatingFileHandler):
    """轮转时自动压缩旧日志文件的 TimedRotatingFileHandler。

    在 midnight 轮转时，将前一天的日志压缩为 .gz 格式。
    """

    def doRollover(self) -> None:
        """执行轮转并压缩被轮转出的文件。"""
        if self.stream:
            self.stream.close()
            self.stream = None  # type: ignore[assignment]

        # 获取轮转后的文件名
        dst_name = self.rotation_filename(
            self.baseFilename + "." + self.suffix(self.rolloverAt),
        )

        # 执行标准轮转
        super().doRollover()

        # 压缩轮转出的文件
        dst_path = Path(dst_name)
        if dst_path.exists():
            _compress_file(dst_path, Path(str(dst_name) + ".gz"))

        # 清理超过 backupCount 的压缩文件
        self._delete_old_compressed()

    def _delete_old_compressed(self) -> None:
        """删除超过备份数量的压缩文件。

        标准 TimedRotatingFileHandler 只管理未压缩的备份文件，
        压缩后的 .gz 文件需要手动清理。
        """
        dir_name = Path(self.baseFilename).parent
        base_name = Path(self.baseFilename).name
        gz_files = sorted(
            dir_name.glob(f"{base_name}.*.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old_file in gz_files[self.backupCount:]:
            old_file.unlink(missing_ok=True)


def _compress_file(src: Path, dst: Path) -> None:
    """将文件压缩为 gzip 格式。

    Args:
        src: 源文件路径
        dst: 目标 .gz 文件路径
    """
    try:
        with open(src, "rb") as f_in, gzip.open(dst, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
        src.unlink(missing_ok=True)
    except OSError:
        # 压缩失败时保留原文件
        pass


class LogRotation:
    """日志轮转管理器。

    Args:
        log_dir: 日志文件目录
        max_bytes: 单文件最大字节数，默认 10MB
        backup_count: 按大小轮转的备份文件数，默认 5
        daily_backup_count: 按时间轮转的备份文件数，默认 30
        encoding: 文件编码，默认 utf-8
        enable_compression: 是否启用自动压缩，默认 True

    Attributes:
        size_handler: 按大小轮转的处理器
        time_handler: 按时间轮转的处理器
    """

    def __init__(
        self,
        log_dir: str | Path = "logs",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        daily_backup_count: int = 30,
        encoding: str = "utf-8",
        enable_compression: bool = True,
    ) -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._enable_compression = enable_compression

        # 按大小轮转
        if enable_compression:
            self.size_handler: RotatingFileHandler = CompressedRotatingFileHandler(
                self._log_dir / "cityflow.log",
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding=encoding,
            )
        else:
            self.size_handler = RotatingFileHandler(
                self._log_dir / "cityflow.log",
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding=encoding,
            )

        # 按时间轮转
        if enable_compression:
            self.time_handler: TimedRotatingFileHandler = (
                CompressedTimedRotatingFileHandler(
                    self._log_dir / "cityflow_daily.log",
                    when="midnight",
                    interval=1,
                    backupCount=daily_backup_count,
                    encoding=encoding,
                )
            )
        else:
            self.time_handler = TimedRotatingFileHandler(
                self._log_dir / "cityflow_daily.log",
                when="midnight",
                interval=1,
                backupCount=daily_backup_count,
                encoding=encoding,
            )

    @property
    def log_dir(self) -> Path:
        """日志目录路径。"""
        return self._log_dir

    @property
    def compression_enabled(self) -> bool:
        """是否启用了自动压缩。"""
        return self._enable_compression

    def attach_to(self, logger: logging.Logger) -> None:
        """将轮转处理器挂载到指定日志器。

        Args:
            logger: 目标日志器
        """
        logger.addHandler(self.size_handler)
        logger.addHandler(self.time_handler)

    def get_handler(self) -> RotatingFileHandler:
        """获取按大小轮转的处理器（兼容旧接口）。"""
        return self.size_handler

    def cleanup_old_logs(self, max_age_days: int = 30) -> list[Path]:
        """清理超过指定天数的日志文件。

        扫描日志目录下所有 .log、.log.*、.gz 文件，删除修改时间
        超过 max_age_days 天的文件。

        Args:
            max_age_days: 最大保留天数，默认 30

        Returns:
            被删除的文件路径列表
        """
        if not self._log_dir.exists():
            return []

        cutoff = time.time() - (max_age_days * 86400)
        deleted: list[Path] = []
        patterns = ("*.log", "*.log.*", "*.gz")

        for pattern in patterns:
            for log_file in self._log_dir.glob(pattern):
                try:
                    if log_file.stat().st_mtime < cutoff:
                        log_file.unlink()
                        deleted.append(log_file)
                        logging.info("删除旧日志: %s", log_file)
                except OSError:
                    # 文件可能正在被写入，跳过
                    continue

        return deleted

    def compress_rotated_logs(self) -> list[Path]:
        """手动压缩所有未压缩的轮转日志文件。

        扫描日志目录下的 .log.1、.log.2 等轮转文件，压缩为 .gz。
        不压缩当前正在写入的 .log 文件。

        Returns:
            被压缩的文件路径列表
        """
        if not self._log_dir.exists():
            return []

        compressed: list[Path] = []

        for log_file in self._log_dir.glob("*.log.*"):
            # 跳过已经是 .gz 的文件
            if str(log_file).endswith(".gz"):
                continue
            # 跳过目录
            if log_file.is_dir():
                continue

            gz_path = Path(str(log_file) + ".gz")
            if gz_path.exists():
                # 已有压缩版本，删除未压缩的
                log_file.unlink(missing_ok=True)
                compressed.append(log_file)
                continue

            _compress_file(log_file, gz_path)
            if gz_path.exists():
                compressed.append(log_file)

        return compressed

    def get_log_stats(self) -> dict[str, int | str]:
        """获取日志目录统计信息。

        Returns:
            包含文件数、总大小等信息的字典
        """
        if not self._log_dir.exists():
            return {"file_count": 0, "total_bytes": 0, "log_dir": str(self._log_dir)}

        file_count = 0
        total_bytes = 0

        for f in self._log_dir.iterdir():
            if f.is_file():
                file_count += 1
                total_bytes += f.stat().st_size

        return {
            "file_count": file_count,
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "log_dir": str(self._log_dir),
        }
