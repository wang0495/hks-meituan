"""备份管理器。

支持全量备份、增量备份、备份恢复和备份验证。
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BackupType(StrEnum):
    """备份类型枚举。"""

    FULL = "full"
    INCREMENTAL = "incremental"


@dataclass
class BackupMetadata:
    """备份元数据。"""

    name: str
    backup_type: BackupType
    timestamp: str
    files: list[str] = field(default_factory=list)
    file_count: int = 0
    total_size_bytes: int = 0
    checksums: dict[str, str] = field(default_factory=dict)
    parent_backup: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "name": self.name,
            "backup_type": self.backup_type.value,
            "timestamp": self.timestamp,
            "files": self.files,
            "file_count": self.file_count,
            "total_size_bytes": self.total_size_bytes,
            "checksums": self.checksums,
            "parent_backup": self.parent_backup,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupMetadata:
        """从字典创建。"""
        return cls(
            name=data["name"],
            backup_type=BackupType(data["backup_type"]),
            timestamp=data["timestamp"],
            files=data.get("files", []),
            file_count=data.get("file_count", 0),
            total_size_bytes=data.get("total_size_bytes", 0),
            checksums=data.get("checksums", {}),
            parent_backup=data.get("parent_backup"),
        )


class BackupError(Exception):
    """备份操作异常基类。"""


class BackupNotFoundError(BackupError):
    """备份不存在。"""


class BackupVerificationError(BackupError):
    """备份验证失败。"""


class BackupManager:
    """备份管理器。

    支持全量备份、增量备份、备份恢复和备份验证。

    Args:
        backup_dir: 备份存储目录。
        data_dir: 需要备份的数据目录。
        config_files: 需要备份的配置文件列表。
        max_backups: 最大保留备份数量，0 表示不限制。
        compress: 是否压缩备份文件。
    """

    def __init__(
        self,
        backup_dir: str = "backups",
        data_dir: str = "backend/data",
        config_files: list[str] | None = None,
        max_backups: int = 10,
        compress: bool = True,
    ) -> None:
        self._backup_dir = Path(backup_dir)
        self._data_dir = Path(data_dir)
        self._config_files = config_files or [".env", "config.yaml"]
        self._max_backups = max_backups
        self._compress = compress
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def _calculate_checksum(self, file_path: Path) -> str:
        """计算文件 MD5 校验和。"""
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def _collect_files(self, directory: Path) -> list[Path]:
        """收集目录下所有文件。"""
        if not directory.exists():
            return []
        return [f for f in directory.rglob("*") if f.is_file()]

    async def create_full_backup(self, name: str | None = None) -> BackupMetadata:
        """创建全量备份。

        Args:
            name: 备份名称，默认使用时间戳生成。

        Returns:
            备份元数据。

        Raises:
            BackupError: 备份创建失败。
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = name or f"full_{timestamp}"
        backup_path = self._backup_dir / backup_name

        try:
            backup_path.mkdir(parents=True, exist_ok=True)

            files: list[str] = []
            checksums: dict[str, str] = {}
            total_size = 0

            # 备份数据文件
            if self._data_dir.exists():
                data_backup = backup_path / "data"
                for file_path in self._collect_files(self._data_dir):
                    rel_path = file_path.relative_to(self._data_dir)
                    dest = data_backup / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)

                    if self._compress and file_path.suffix in (".json", ".txt", ".csv"):
                        # 压缩文本文件
                        compressed_dest = dest.with_suffix(dest.suffix + ".gz")
                        with open(file_path, "rb") as f_in:
                            with gzip.open(compressed_dest, "wb") as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        file_size = compressed_dest.stat().st_size
                        files.append(f"data/{rel_path}.gz")
                        checksums[f"data/{rel_path}.gz"] = self._calculate_checksum(
                            compressed_dest
                        )
                    else:
                        shutil.copy2(file_path, dest)
                        file_size = dest.stat().st_size
                        files.append(f"data/{rel_path}")
                        checksums[f"data/{rel_path}"] = self._calculate_checksum(dest)

                    total_size += file_size

            # 备份配置文件
            for config_file in self._config_files:
                config_path = Path(config_file)
                if config_path.exists():
                    dest = backup_path / config_file
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(config_path, dest)
                    files.append(config_file)
                    checksums[config_file] = self._calculate_checksum(dest)
                    total_size += dest.stat().st_size

            # 创建元数据
            metadata = BackupMetadata(
                name=backup_name,
                backup_type=BackupType.FULL,
                timestamp=timestamp,
                files=files,
                file_count=len(files),
                total_size_bytes=total_size,
                checksums=checksums,
            )

            # 保存元数据
            with open(backup_path / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(
                "全量备份创建成功: %s (%d 文件, %d 字节)",
                backup_name,
                len(files),
                total_size,
            )

            # 清理旧备份
            await self._cleanup_old_backups()

            return metadata

        except Exception as e:
            logger.error("备份创建失败: %s", e)
            # 清理失败的备份目录
            if backup_path.exists():
                shutil.rmtree(backup_path, ignore_errors=True)
            raise BackupError(f"备份创建失败: {e}") from e

    async def create_incremental_backup(
        self, since: str | datetime | None = None, parent_backup: str | None = None
    ) -> BackupMetadata:
        """创建增量备份。

        只备份自指定时间以来修改的文件。

        Args:
            since: 起始时间，可以是 ISO 格式字符串或 datetime 对象。
                   如果为 None，则使用最近一次备份的时间。
            parent_backup: 父备份名称，用于记录备份链。

        Returns:
            备份元数据。

        Raises:
            BackupError: 备份创建失败。
        """
        # 确定起始时间
        if since is None:
            last_backup = await self._get_last_backup_time()
            if last_backup is None:
                logger.info("没有找到之前的备份，将执行全量备份")
                return await self.create_full_backup()
            since_dt = last_backup
        elif isinstance(since, str):
            since_dt = datetime.fromisoformat(since)
        else:
            since_dt = since

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"incr_{timestamp}"
        backup_path = self._backup_dir / backup_name

        try:
            backup_path.mkdir(parents=True, exist_ok=True)

            files: list[str] = []
            checksums: dict[str, str] = {}
            total_size = 0

            # 只备份修改过的数据文件
            if self._data_dir.exists():
                data_backup = backup_path / "data"
                for file_path in self._collect_files(self._data_dir):
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime > since_dt:
                        rel_path = file_path.relative_to(self._data_dir)
                        dest = data_backup / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)

                        if self._compress and file_path.suffix in (
                            ".json",
                            ".txt",
                            ".csv",
                        ):
                            compressed_dest = dest.with_suffix(dest.suffix + ".gz")
                            with open(file_path, "rb") as f_in:
                                with gzip.open(compressed_dest, "wb") as f_out:
                                    shutil.copyfileobj(f_in, f_out)
                            file_size = compressed_dest.stat().st_size
                            files.append(f"data/{rel_path}.gz")
                            checksums[f"data/{rel_path}.gz"] = self._calculate_checksum(
                                compressed_dest
                            )
                        else:
                            shutil.copy2(file_path, dest)
                            file_size = dest.stat().st_size
                            files.append(f"data/{rel_path}")
                            checksums[f"data/{rel_path}"] = self._calculate_checksum(
                                dest
                            )

                        total_size += file_size

            # 备份修改过的配置文件
            for config_file in self._config_files:
                config_path = Path(config_file)
                if config_path.exists():
                    mtime = datetime.fromtimestamp(config_path.stat().st_mtime)
                    if mtime > since_dt:
                        dest = backup_path / config_file
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(config_path, dest)
                        files.append(config_file)
                        checksums[config_file] = self._calculate_checksum(dest)
                        total_size += dest.stat().st_size

            # 如果没有文件变更，跳过创建
            if not files:
                logger.info("没有文件变更，跳过增量备份")
                shutil.rmtree(backup_path, ignore_errors=True)
                # 返回最近一次备份的元数据
                last_meta = await self._get_last_backup_metadata()
                if last_meta:
                    return last_meta
                raise BackupError("没有可备份的文件变更")

            # 创建元数据
            metadata = BackupMetadata(
                name=backup_name,
                backup_type=BackupType.INCREMENTAL,
                timestamp=timestamp,
                files=files,
                file_count=len(files),
                total_size_bytes=total_size,
                checksums=checksums,
                parent_backup=parent_backup,
            )

            # 保存元数据
            with open(backup_path / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)

            logger.info(
                "增量备份创建成功: %s (%d 文件, %d 字节)",
                backup_name,
                len(files),
                total_size,
            )

            return metadata

        except BackupError:
            raise
        except Exception as e:
            logger.error("增量备份失败: %s", e)
            if backup_path.exists():
                shutil.rmtree(backup_path, ignore_errors=True)
            raise BackupError(f"增量备份失败: {e}") from e

    async def restore_backup(self, backup_name: str) -> bool:
        """恢复备份。

        Args:
            backup_name: 备份名称。

        Returns:
            恢复是否成功。

        Raises:
            BackupNotFoundError: 备份不存在。
            BackupError: 恢复失败。
        """
        backup_path = self._backup_dir / backup_name

        if not backup_path.exists():
            raise BackupNotFoundError(f"备份不存在: {backup_name}")

        try:
            # 先验证备份完整性
            is_valid = await self.verify_backup(backup_name)
            if not is_valid:
                raise BackupVerificationError(f"备份验证失败，拒绝恢复: {backup_name}")

            # 恢复数据文件
            data_backup = backup_path / "data"
            if data_backup.exists():
                if self._data_dir.exists():
                    shutil.rmtree(self._data_dir)

                # 解压并恢复文件
                self._data_dir.mkdir(parents=True, exist_ok=True)
                for file_path in data_backup.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(data_backup)
                        dest = self._data_dir / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)

                        if file_path.suffix == ".gz":
                            # 解压 gz 文件
                            original_dest = dest.with_suffix("")
                            with gzip.open(file_path, "rb") as f_in:
                                with open(original_dest, "wb") as f_out:
                                    shutil.copyfileobj(f_in, f_out)
                        else:
                            shutil.copy2(file_path, dest)

            # 恢复配置文件
            metadata = self._load_metadata(backup_path)
            if metadata:
                for config_file in self._config_files:
                    config_backup = backup_path / config_file
                    if config_backup.exists():
                        shutil.copy2(config_backup, config_file)

            logger.info("备份恢复成功: %s", backup_name)
            return True

        except (BackupNotFoundError, BackupVerificationError):
            raise
        except Exception as e:
            logger.error("备份恢复失败: %s", e)
            raise BackupError(f"备份恢复失败: {e}") from e

    async def verify_backup(self, backup_name: str) -> bool:
        """验证备份完整性。

        检查备份文件是否存在且校验和匹配。

        Args:
            backup_name: 备份名称。

        Returns:
            验证是否通过。

        Raises:
            BackupNotFoundError: 备份不存在。
        """
        backup_path = self._backup_dir / backup_name

        if not backup_path.exists():
            raise BackupNotFoundError(f"备份不存在: {backup_name}")

        metadata = self._load_metadata(backup_path)
        if not metadata:
            logger.error("备份元数据缺失: %s", backup_name)
            return False

        # 检查所有文件是否存在且校验和匹配
        errors: list[str] = []
        for file_rel_path in metadata.files:
            file_path = backup_path / file_rel_path
            if not file_path.exists():
                errors.append(f"文件缺失: {file_rel_path}")
                continue

            expected_checksum = metadata.checksums.get(file_rel_path)
            if expected_checksum:
                actual_checksum = self._calculate_checksum(file_path)
                if actual_checksum != expected_checksum:
                    errors.append(
                        f"校验和不匹配: {file_rel_path} "
                        f"(期望: {expected_checksum}, 实际: {actual_checksum})"
                    )

        if errors:
            for error in errors:
                logger.error("备份验证失败: %s", error)
            return False

        logger.info("备份验证通过: %s", backup_name)
        return True

    async def list_backups(self) -> list[BackupMetadata]:
        """列出所有备份。

        Returns:
            备份元数据列表，按时间倒序排列。
        """
        backups: list[BackupMetadata] = []

        for path in self._backup_dir.iterdir():
            if path.is_dir():
                metadata = self._load_metadata(path)
                if metadata:
                    backups.append(metadata)

        return sorted(backups, key=lambda x: x.timestamp, reverse=True)

    async def delete_backup(self, backup_name: str) -> bool:
        """删除备份。

        Args:
            backup_name: 备份名称。

        Returns:
            删除是否成功。

        Raises:
            BackupNotFoundError: 备份不存在。
        """
        backup_path = self._backup_dir / backup_name

        if not backup_path.exists():
            raise BackupNotFoundError(f"备份不存在: {backup_name}")

        try:
            shutil.rmtree(backup_path)
            logger.info("备份已删除: %s", backup_name)
            return True
        except Exception as e:
            logger.error("备份删除失败: %s", e)
            raise BackupError(f"备份删除失败: {e}") from e

    def _load_metadata(self, backup_path: Path) -> BackupMetadata | None:
        """加载备份元数据。"""
        metadata_file = backup_path / "metadata.json"
        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, encoding="utf-8") as f:
                data = json.load(f)
            return BackupMetadata.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("元数据解析失败: %s", e)
            return None

    async def _get_last_backup_time(self) -> datetime | None:
        """获取最近一次备份的时间。"""
        backups = await self.list_backups()
        if not backups:
            return None
        return datetime.fromisoformat(backups[0].timestamp)

    async def _get_last_backup_metadata(self) -> BackupMetadata | None:
        """获取最近一次备份的元数据。"""
        backups = await self.list_backups()
        return backups[0] if backups else None

    async def _cleanup_old_backups(self) -> None:
        """清理超出保留数量的旧备份。"""
        if self._max_backups <= 0:
            return

        backups = await self.list_backups()
        if len(backups) <= self._max_backups:
            return

        # 删除最旧的备份
        for old_backup in backups[self._max_backups :]:
            try:
                await self.delete_backup(old_backup.name)
                logger.info("已清理旧备份: %s", old_backup.name)
            except BackupError as e:
                logger.warning("清理旧备份失败: %s", e)
