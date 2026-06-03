"""CityFlow 数据备份服务。

提供自动备份、增量备份、版本管理、备份恢复和备份验证五大能力：

- **自动备份**：定时或手动创建数据快照，包含数据文件 + 配置文件 + 元数据。
- **增量备份**：只备份自上次备份以来修改的文件，节省存储空间。
- **版本管理**：每次备份生成时间戳版本，支持列出、清理旧版本。
- **备份恢复**：从指定版本恢复数据，带完整性校验。
- **备份验证**：验证备份文件的完整性和可用性。

使用方式::

    from backend.services.backup import get_backup

    backup = get_backup()

    # 创建全量备份
    name = await backup.create_backup()

    # 创建增量备份
    incr_name = await backup.create_incremental_backup()

    # 列出备份
    backups = await backup.list_backups()

    # 验证备份
    is_valid = await backup.verify_backup(name)

    # 恢复备份
    ok = await backup.restore_backup(name)

    # 清理旧版本（默认保留 10 个）
    await backup.cleanup_old_backups(keep_count=5)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from backend.errors import CityFlowException, ErrorCode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class BackupError(CityFlowException):
    """备份操作失败。"""

    def __init__(
        self,
        message: str = "备份操作失败",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            details=details,
        )


class BackupNotFoundError(CityFlowException):
    """指定备份不存在。"""

    def __init__(
        self,
        backup_name: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=f"备份不存在: {backup_name}",
            details=details or {"backup_name": backup_name},
        )


class BackupVerificationError(BackupError):
    """备份验证失败。"""

    def __init__(
        self,
        message: str = "备份验证失败",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, details=details)


# ---------------------------------------------------------------------------
# 常量与枚举
# ---------------------------------------------------------------------------


class BackupType(StrEnum):
    """备份类型枚举。"""

    FULL = "full"
    INCREMENTAL = "incremental"


_METADATA_FILE = "metadata.json"
_CHECKSUM_FILE = "checksum.sha256"
_DATA_SUBDIR = "data"
_CONFIG_FILES = (".env", "config.yaml", "config.yml")

# ---------------------------------------------------------------------------
# 核心
# ---------------------------------------------------------------------------


class DataBackup:
    """数据备份管理器。

    支持全量备份、增量备份、备份恢复和备份验证。

    Args:
        backup_dir: 备份存储根目录。
        data_dir: 需要备份的数据目录。
        keep_count: 自动清理时保留的备份数量。
    """

    def __init__(
        self,
        backup_dir: str = "backups",
        data_dir: str = "backend/data",
        keep_count: int = 10,
    ) -> None:
        self._backup_dir = Path(backup_dir)
        self._data_dir = Path(data_dir)
        self._keep_count = keep_count
        # 确保备份目录存在
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 创建备份
    # ------------------------------------------------------------------

    async def create_backup(self, name: str | None = None) -> str:
        """创建一个完整备份。

        在后台线程中执行文件 IO，不阻塞事件循环。

        Args:
            name: 自定义备份名称，默认使用时间戳。

        Returns:
            备份名称，可用于后续恢复。

        Raises:
            BackupError: 备份创建过程中发生错误。
        """
        return await asyncio.to_thread(self._create_backup_sync, name)

    def _create_backup_sync(self, name: str | None) -> str:
        """同步创建备份（在线程中运行）。"""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup_name = name or f"backup_{timestamp}"
        backup_path = self._backup_dir / backup_name

        try:
            backup_path.mkdir(parents=True, exist_ok=True)

            # 1. 备份数据目录
            files_count = 0
            if self._data_dir.exists():
                dest_data = backup_path / _DATA_SUBDIR
                shutil.copytree(self._data_dir, dest_data)
                files_count = sum(1 for _ in dest_data.rglob("*") if _.is_file())
                logger.info(
                    "数据目录备份完成: %s -> %s (%d 个文件)",
                    self._data_dir,
                    dest_data,
                    files_count,
                )

            # 2. 备份配置文件
            config_backed: list[str] = []
            for cfg_name in _CONFIG_FILES:
                cfg_path = Path(cfg_name)
                if cfg_path.exists():
                    shutil.copy(cfg_path, backup_path / cfg_name)
                    config_backed.append(cfg_name)

            # 3. 计算校验和（数据目录）
            checksum = self._compute_checksum(backup_path / _DATA_SUBDIR)
            (backup_path / _CHECKSUM_FILE).write_text(checksum, encoding="utf-8")

            # 4. 写入元数据
            total_size = self._dir_size(backup_path)
            metadata = {
                "name": backup_name,
                "timestamp": timestamp,
                "data_dir": str(self._data_dir),
                "files_count": files_count,
                "config_files": config_backed,
                "total_size_bytes": total_size,
                "checksum": checksum,
            }
            metadata_path = backup_path / _METADATA_FILE
            metadata_path.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            size_mb = total_size / (1024 * 1024)
            logger.info(
                "备份创建成功: %s (大小: %.2f MB, 文件: %d)",
                backup_name,
                size_mb,
                files_count,
            )
            return backup_name

        except Exception as exc:
            # 清理残留的不完整备份
            if backup_path.exists():
                shutil.rmtree(backup_path, ignore_errors=True)
            logger.error("备份创建失败: %s", exc)
            raise BackupError(
                message=f"备份创建失败: {exc}",
                details={"backup_name": backup_name},
            ) from exc

    # ------------------------------------------------------------------
    # 恢复备份
    # ------------------------------------------------------------------

    async def restore_backup(self, backup_name: str) -> bool:
        """从指定备份恢复数据。

        恢复前会校验备份完整性（SHA-256），校验失败则拒绝恢复。

        Args:
            backup_name: 备份名称（目录名）。

        Returns:
            恢复成功返回 True。

        Raises:
            BackupNotFoundError: 备份不存在。
            BackupError: 恢复失败或完整性校验不通过。
        """
        return await asyncio.to_thread(self._restore_backup_sync, backup_name)

    def _restore_backup_sync(self, backup_name: str) -> bool:
        """同步恢复备份（在线程中运行）。"""
        backup_path = self._backup_dir / backup_name

        if not backup_path.exists():
            raise BackupNotFoundError(backup_name)

        try:
            # 1. 完整性校验
            stored_checksum = self._read_checksum(backup_name)
            if stored_checksum is not None:
                current_checksum = self._compute_checksum(
                    backup_path / _DATA_SUBDIR,
                )
                if stored_checksum != current_checksum:
                    raise BackupError(
                        message="备份完整性校验失败，数据可能已损坏",
                        details={
                            "backup_name": backup_name,
                            "expected": stored_checksum[:16] + "...",
                            "actual": current_checksum[:16] + "...",
                        },
                    )
                logger.info("备份完整性校验通过: %s", backup_name)

            # 2. 恢复数据目录
            data_backup = backup_path / _DATA_SUBDIR
            if data_backup.exists():
                if self._data_dir.exists():
                    shutil.rmtree(self._data_dir)
                shutil.copytree(data_backup, self._data_dir)
                logger.info("数据目录恢复完成: %s", self._data_dir)
            else:
                logger.warning("备份中无数据目录，跳过恢复: %s", backup_name)

            # 3. 恢复配置文件
            for cfg_name in _CONFIG_FILES:
                cfg_backup = backup_path / cfg_name
                if cfg_backup.exists():
                    shutil.copy(cfg_backup, Path(cfg_name))
                    logger.info("配置文件恢复完成: %s", cfg_name)

            logger.info("备份恢复成功: %s", backup_name)
            return True

        except BackupError:
            raise
        except Exception as exc:
            logger.error("备份恢复失败: %s", exc)
            raise BackupError(
                message=f"备份恢复失败: {exc}",
                details={"backup_name": backup_name},
            ) from exc

    # ------------------------------------------------------------------
    # 版本管理
    # ------------------------------------------------------------------

    async def list_backups(self) -> list[dict[str, object]]:
        """列出所有备份，按时间倒序排列。

        Returns:
            备份元数据列表，每项包含 name / timestamp / total_size_bytes 等字段。
        """
        return await asyncio.to_thread(self._list_backups_sync)

    def _list_backups_sync(self) -> list[dict[str, object]]:
        """同步列出备份。"""
        backups: list[dict[str, object]] = []
        if not self._backup_dir.exists():
            return backups

        for path in self._backup_dir.iterdir():
            if not path.is_dir():
                continue
            metadata_path = path / _METADATA_FILE
            if metadata_path.exists():
                try:
                    data = json.loads(metadata_path.read_text(encoding="utf-8"))
                    backups.append(data)
                except (json.JSONDecodeError, OSError):
                    logger.warning("跳过损坏的备份元数据: %s", metadata_path)

        backups.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)
        return backups

    async def cleanup_old_backups(self, keep_count: int | None = None) -> int:
        """清理旧版本备份，保留最近 N 个。

        Args:
            keep_count: 保留数量，默认使用初始化时的 keep_count。

        Returns:
            删除的备份数量。
        """
        count = keep_count if keep_count is not None else self._keep_count
        return await asyncio.to_thread(self._cleanup_old_backups_sync, count)

    def _cleanup_old_backups_sync(self, keep_count: int) -> int:
        """同步清理旧备份。"""
        backups = self._list_backups_sync()

        if len(backups) <= keep_count:
            return 0

        removed = 0
        for backup in backups[keep_count:]:
            name = str(backup.get("name", ""))
            if not name:
                continue
            backup_path = self._backup_dir / name
            try:
                shutil.rmtree(backup_path)
                removed += 1
                logger.info("删除旧备份: %s", name)
            except OSError as exc:
                logger.warning("删除备份失败 %s: %s", name, exc)

        logger.info("清理完成，删除 %d 个旧备份，保留 %d 个", removed, keep_count)
        return removed

    async def delete_backup(self, backup_name: str) -> bool:
        """删除指定备份。

        Args:
            backup_name: 备份名称。

        Returns:
            删除成功返回 True。

        Raises:
            BackupNotFoundError: 备份不存在。
        """
        return await asyncio.to_thread(self._delete_backup_sync, backup_name)

    def _delete_backup_sync(self, backup_name: str) -> bool:
        backup_path = self._backup_dir / backup_name
        if not backup_path.exists():
            raise BackupNotFoundError(backup_name)
        shutil.rmtree(backup_path)
        logger.info("备份已删除: %s", backup_name)
        return True

    # ------------------------------------------------------------------
    # 增量备份
    # ------------------------------------------------------------------

    async def create_incremental_backup(
        self,
        since: datetime | None = None,
        parent_backup: str | None = None,
    ) -> str:
        """创建增量备份。

        只备份自指定时间以来修改的文件，节省存储空间。

        Args:
            since: 起始时间。如果为 None，则使用最近一次备份的时间。
                   如果没有任何备份，将执行全量备份。
            parent_backup: 父备份名称，用于记录备份链。

        Returns:
            备份名称。

        Raises:
            BackupError: 备份创建失败。
        """
        return await asyncio.to_thread(self._create_incremental_backup_sync, since, parent_backup)

    def _create_incremental_backup_sync(
        self,
        since: datetime | None,
        parent_backup: str | None,
    ) -> str:
        """同步创建增量备份。"""
        # 确定起始时间
        if since is None:
            last_backup_time = self._get_last_backup_time()
            if last_backup_time is None:
                logger.info("没有找到之前的备份，将执行全量备份")
                return self._create_backup_sync(None)
            since = last_backup_time

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup_name = f"incr_{timestamp}"
        backup_path = self._backup_dir / backup_name

        try:
            backup_path.mkdir(parents=True, exist_ok=True)

            # 收集修改过的文件
            changed_files: list[str] = []
            total_size = 0

            # 检查数据目录
            if self._data_dir.exists():
                dest_data = backup_path / _DATA_SUBDIR
                for file_path in self._collect_files(self._data_dir):
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC)
                    if mtime > since:
                        rel_path = file_path.relative_to(self._data_dir)
                        dest = dest_data / rel_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, dest)
                        changed_files.append(f"data/{rel_path}")
                        total_size += dest.stat().st_size

            # 检查配置文件
            for cfg_name in _CONFIG_FILES:
                cfg_path = Path(cfg_name)
                if cfg_path.exists():
                    mtime = datetime.fromtimestamp(cfg_path.stat().st_mtime, tz=UTC)
                    if mtime > since:
                        shutil.copy(cfg_path, backup_path / cfg_name)
                        changed_files.append(cfg_name)
                        total_size += (backup_path / cfg_name).stat().st_size

            # 没有变更则跳过
            if not changed_files:
                logger.info("没有文件变更，跳过增量备份")
                shutil.rmtree(backup_path, ignore_errors=True)
                # 返回最近备份名称
                last_name = self._get_last_backup_name()
                if last_name:
                    return last_name
                raise BackupError(message="没有可备份的文件变更")

            # 计算校验和
            checksum = self._compute_checksum(backup_path / _DATA_SUBDIR)
            (backup_path / _CHECKSUM_FILE).write_text(checksum, encoding="utf-8")

            # 写入元数据
            metadata: dict[str, Any] = {
                "name": backup_name,
                "backup_type": BackupType.INCREMENTAL.value,
                "timestamp": timestamp,
                "data_dir": str(self._data_dir),
                "files_count": len(changed_files),
                "files": changed_files,
                "total_size_bytes": total_size,
                "checksum": checksum,
                "parent_backup": parent_backup,
                "since": since.isoformat(),
            }
            metadata_path = backup_path / _METADATA_FILE
            metadata_path.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            logger.info(
                "增量备份创建成功: %s (%d 文件, %d 字节)",
                backup_name,
                len(changed_files),
                total_size,
            )
            return backup_name

        except BackupError:
            raise
        except Exception as exc:
            if backup_path.exists():
                shutil.rmtree(backup_path, ignore_errors=True)
            logger.error("增量备份失败: %s", exc)
            raise BackupError(
                message=f"增量备份失败: {exc}",
                details={"backup_name": backup_name},
            ) from exc

    def _get_last_backup_time(self) -> datetime | None:
        """获取最近一次备份的时间。"""
        backups = self._list_backups_sync()
        if not backups:
            return None
        timestamp_str = str(backups[0].get("timestamp", ""))
        if not timestamp_str:
            return None
        try:
            return datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S").replace(tzinfo=UTC)
        except ValueError:
            return None

    def _get_last_backup_name(self) -> str | None:
        """获取最近一次备份的名称。"""
        backups = self._list_backups_sync()
        if not backups:
            return None
        return str(backups[0].get("name", "")) or None

    def _collect_files(self, directory: Path) -> list[Path]:
        """收集目录下所有文件。"""
        if not directory.exists():
            return []
        return [f for f in directory.rglob("*") if f.is_file()]

    # ------------------------------------------------------------------
    # 备份验证
    # ------------------------------------------------------------------

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
        return await asyncio.to_thread(self._verify_backup_sync, backup_name)

    def _verify_backup_sync(self, backup_name: str) -> bool:
        """同步验证备份。"""
        backup_path = self._backup_dir / backup_name

        if not backup_path.exists():
            raise BackupNotFoundError(backup_name)

        # 读取元数据
        metadata_path = backup_path / _METADATA_FILE
        if not metadata_path.exists():
            logger.error("备份元数据缺失: %s", backup_name)
            return False

        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("元数据解析失败: %s", exc)
            return False

        # 检查数据目录
        data_backup = backup_path / _DATA_SUBDIR
        if not data_backup.exists():
            logger.error("备份数据目录缺失: %s", backup_name)
            return False

        # 验证校验和
        stored_checksum = self._read_checksum(backup_name)
        if stored_checksum is not None:
            current_checksum = self._compute_checksum(data_backup)
            if stored_checksum != current_checksum:
                logger.error(
                    "备份校验和不匹配: %s (期望: %s..., 实际: %s...)",
                    backup_name,
                    stored_checksum[:16],
                    current_checksum[:16],
                )
                return False

        # 检查文件数量
        expected_count = metadata.get("files_count", 0)
        actual_count = sum(1 for _ in data_backup.rglob("*") if _.is_file())
        if expected_count > 0 and actual_count != expected_count:
            logger.error(
                "备份文件数量不匹配: %s (期望: %d, 实际: %d)",
                backup_name,
                expected_count,
                actual_count,
            )
            return False

        logger.info("备份验证通过: %s", backup_name)
        return True

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_checksum(path: Path) -> str:
        """计算目录下所有文件的 SHA-256 校验和。

        对目录中每个文件（按路径排序）逐一计算哈希再合并，
        保证相同内容的目录始终得到相同的校验和。
        """
        sha256 = hashlib.sha256()
        if not path.exists():
            return sha256.hexdigest()
        for file in sorted(path.rglob("*")):
            if file.is_file():
                sha256.update(file.name.encode("utf-8"))
                sha256.update(file.read_bytes())
        return sha256.hexdigest()

    def _read_checksum(self, backup_name: str) -> str | None:
        """读取备份的校验和文件。"""
        checksum_path = self._backup_dir / backup_name / _CHECKSUM_FILE
        if checksum_path.exists():
            try:
                return checksum_path.read_text(encoding="utf-8").strip()
            except OSError:
                return None
        return None

    @staticmethod
    def _dir_size(path: Path) -> int:
        """计算目录总大小（字节）。"""
        if not path.exists():
            return 0
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

    @property
    def backup_dir(self) -> Path:
        """备份存储目录。"""
        return self._backup_dir


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_backup: DataBackup | None = None


def get_backup() -> DataBackup:
    """获取全局备份管理器实例。"""
    global _backup
    if _backup is None:
        _backup = DataBackup()
    return _backup


def reset_backup() -> None:
    """重置全局备份管理器（仅用于测试）。"""
    global _backup
    _backup = None
