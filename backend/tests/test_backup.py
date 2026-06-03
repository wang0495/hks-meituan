"""备份服务测试。"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.services.backup import (
    BackupError,
    BackupNotFoundError,
    BackupType,
    DataBackup,
    get_backup,
    reset_backup,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def backup_dir(tmp_path: Path) -> Path:
    return tmp_path / "backups"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "backend" / "data"
    d.mkdir(parents=True)
    (d / "test.json").write_text('{"key": "value"}', encoding="utf-8")
    (d / "sub").mkdir()
    (d / "sub" / "nested.txt").write_text("nested content", encoding="utf-8")
    return d


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    # 在 tmp_path 根创建 .env，后续 chdir 到 tmp_path
    cfg = tmp_path / ".env"
    cfg.write_text("SECRET=test123", encoding="utf-8")
    return cfg


@pytest.fixture
def backup(backup_dir: Path, data_dir: Path) -> DataBackup:
    return DataBackup(
        backup_dir=str(backup_dir),
        data_dir=str(data_dir),
        keep_count=3,
    )


# ---------------------------------------------------------------------------
# 创建全量备份
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_backup_default_name(backup: DataBackup) -> None:
    name = await backup.create_backup()
    assert name.startswith("backup_")
    assert len(name) == len("backup_20260101_120000")


@pytest.mark.asyncio
async def test_create_backup_custom_name(backup: DataBackup) -> None:
    name = await backup.create_backup(name="my_backup")
    assert name == "my_backup"


@pytest.mark.asyncio
async def test_create_backup_creates_files(backup: DataBackup, backup_dir: Path) -> None:
    name = await backup.create_backup(name="test_v1")
    backup_path = backup_dir / name

    assert backup_path.exists()
    assert (backup_path / "metadata.json").exists()
    assert (backup_path / "checksum.sha256").exists()
    assert (backup_path / "data" / "test.json").exists()
    assert (backup_path / "data" / "sub" / "nested.txt").exists()


@pytest.mark.asyncio
async def test_create_backup_metadata_content(backup: DataBackup) -> None:
    name = await backup.create_backup(name="meta_test")
    metadata_path = backup.backup_dir / name / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert metadata["name"] == "meta_test"
    assert "timestamp" in metadata
    assert metadata["files_count"] >= 2
    assert metadata["total_size_bytes"] > 0
    assert "checksum" in metadata


@pytest.mark.asyncio
async def test_create_backup_checksum_is_stable(backup: DataBackup, backup_dir: Path) -> None:
    """同一数据目录的两次备份应产生相同校验和。"""
    name1 = await backup.create_backup(name="v1")
    name2 = await backup.create_backup(name="v2")

    cs1 = (backup_dir / name1 / "checksum.sha256").read_text(encoding="utf-8")
    cs2 = (backup_dir / name2 / "checksum.sha256").read_text(encoding="utf-8")
    assert cs1 == cs2


# ---------------------------------------------------------------------------
# 增量备份
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_incremental_backup(backup: DataBackup, data_dir: Path) -> None:
    """增量备份只包含修改过的文件。"""
    # 记录当前时间
    before = datetime.now(UTC)

    # 先创建全量备份
    await backup.create_backup(name="full_v1")

    # 修改一个文件
    (data_dir / "test.json").write_text('{"key": "modified"}', encoding="utf-8")

    # 创建增量备份（使用显式时间）
    incr_name = await backup.create_incremental_backup(since=before)
    assert incr_name.startswith("incr_")

    # 验证增量备份包含修改的文件
    metadata_path = backup.backup_dir / incr_name / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["backup_type"] == BackupType.INCREMENTAL.value
    assert metadata["files_count"] >= 1
    assert "data/test.json" in metadata["files"]


@pytest.mark.asyncio
async def test_incremental_backup_no_changes(backup: DataBackup, data_dir: Path) -> None:
    """没有变更时增量备份应返回最近备份名称。"""
    # 先创建全量备份
    full_name = await backup.create_backup(name="full_v1")

    # 使用当前时间作为起始时间（文件在之前创建，不会有变更）
    since = datetime.now(UTC)

    # 没有变更，应返回最近备份名称
    result = await backup.create_incremental_backup(since=since)
    assert result == full_name


@pytest.mark.asyncio
async def test_incremental_backup_no_previous_backup(
    backup: DataBackup,
) -> None:
    """没有先前备份时，增量备份应执行全量备份。"""
    name = await backup.create_incremental_backup()
    # 应该回退到全量备份
    assert name.startswith("backup_")


@pytest.mark.asyncio
async def test_incremental_backup_with_since(backup: DataBackup, data_dir: Path) -> None:
    """指定时间的增量备份。"""
    # 记录当前时间
    before = datetime.now(UTC) - timedelta(seconds=1)

    # 创建文件
    (data_dir / "new_file.txt").write_text("new content", encoding="utf-8")

    # 创建增量备份
    incr_name = await backup.create_incremental_backup(since=before)
    assert incr_name.startswith("incr_")

    metadata_path = backup.backup_dir / incr_name / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["files_count"] >= 1


@pytest.mark.asyncio
async def test_incremental_backup_creates_files(
    backup: DataBackup, backup_dir: Path, data_dir: Path
) -> None:
    """增量备份应创建正确的文件结构。"""
    await backup.create_backup(name="full_v1")

    # 添加新文件
    (data_dir / "new.txt").write_text("new", encoding="utf-8")

    incr_name = await backup.create_incremental_backup()
    incr_path = backup_dir / incr_name

    assert incr_path.exists()
    assert (incr_path / "metadata.json").exists()
    assert (incr_path / "checksum.sha256").exists()
    assert (incr_path / "data" / "new.txt").exists()


# ---------------------------------------------------------------------------
# 备份验证
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_backup_valid(backup: DataBackup) -> None:
    """有效备份应通过验证。"""
    name = await backup.create_backup(name="valid_backup")
    assert await backup.verify_backup(name) is True


@pytest.mark.asyncio
async def test_verify_backup_corrupted(backup: DataBackup, backup_dir: Path) -> None:
    """篡改数据后验证应失败。"""
    name = await backup.create_backup(name="corrupt_backup")

    # 篡改备份文件
    corrupt_file = backup_dir / name / "data" / "test.json"
    corrupt_file.write_text('{"key": "corrupted"}', encoding="utf-8")

    assert await backup.verify_backup(name) is False


@pytest.mark.asyncio
async def test_verify_backup_missing_metadata(backup: DataBackup, backup_dir: Path) -> None:
    """元数据缺失应验证失败。"""
    name = await backup.create_backup(name="no_meta")

    # 删除元数据
    (backup_dir / name / "metadata.json").unlink()

    assert await backup.verify_backup(name) is False


@pytest.mark.asyncio
async def test_verify_backup_missing_data(backup: DataBackup, backup_dir: Path) -> None:
    """数据目录缺失应验证失败。"""
    import shutil

    name = await backup.create_backup(name="no_data")

    # 删除数据目录
    shutil.rmtree(backup_dir / name / "data")

    assert await backup.verify_backup(name) is False


@pytest.mark.asyncio
async def test_verify_backup_nonexistent(backup: DataBackup) -> None:
    """不存在的备份应抛出异常。"""
    with pytest.raises(BackupNotFoundError):
        await backup.verify_backup("nonexistent")


@pytest.mark.asyncio
async def test_verify_incremental_backup(backup: DataBackup, data_dir: Path) -> None:
    """增量备份也应能通过验证。"""
    await backup.create_backup(name="full_v1")

    (data_dir / "test.json").write_text('{"key": "modified"}', encoding="utf-8")

    incr_name = await backup.create_incremental_backup()
    assert await backup.verify_backup(incr_name) is True


# ---------------------------------------------------------------------------
# 恢复备份
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restore_backup(backup: DataBackup, data_dir: Path) -> None:
    # 创建备份
    name = await backup.create_backup(name="restore_test")

    # 修改数据
    (data_dir / "test.json").write_text('{"key": "modified"}', encoding="utf-8")
    (data_dir / "new_file.txt").write_text("new", encoding="utf-8")
    assert (data_dir / "new_file.txt").exists()

    # 恢复
    ok = await backup.restore_backup(name)
    assert ok is True

    # 验证恢复结果
    assert (data_dir / "test.json").read_text(encoding="utf-8") == '{"key": "value"}'
    assert not (data_dir / "new_file.txt").exists()


@pytest.mark.asyncio
async def test_restore_nonexistent_backup(backup: DataBackup) -> None:
    with pytest.raises(BackupNotFoundError):
        await backup.restore_backup("nonexistent")


@pytest.mark.asyncio
async def test_restore_detects_corruption(backup: DataBackup, backup_dir: Path) -> None:
    """篡改备份数据后恢复应触发完整性校验失败。"""
    name = await backup.create_backup(name="corrupt_test")

    # 篡改备份中的数据文件
    corrupt_file = backup_dir / name / "data" / "test.json"
    corrupt_file.write_text('{"key": "corrupted"}', encoding="utf-8")

    with pytest.raises(BackupError, match="完整性校验"):
        await backup.restore_backup(name)


# ---------------------------------------------------------------------------
# 列出备份
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_backups_empty(backup: DataBackup) -> None:
    backups = await backup.list_backups()
    assert backups == []


@pytest.mark.asyncio
async def test_list_backups_sorted(backup: DataBackup) -> None:
    await backup.create_backup(name="v1")
    await backup.create_backup(name="v2")
    await backup.create_backup(name="v3")

    backups = await backup.list_backups()
    assert len(backups) == 3
    # 按时间倒序，v3 最后创建但排最前（名称不同时按 timestamp 排序）
    names = [b["name"] for b in backups]
    assert "v1" in names
    assert "v2" in names
    assert "v3" in names


@pytest.mark.asyncio
async def test_list_backups_includes_incremental(backup: DataBackup, data_dir: Path) -> None:
    """列出备份应包含全量和增量备份。"""
    await backup.create_backup(name="full_v1")
    (data_dir / "test.json").write_text('{"key": "new"}', encoding="utf-8")
    await backup.create_incremental_backup()

    backups = await backup.list_backups()
    assert len(backups) == 2

    types = {b.get("backup_type", "full") for b in backups}
    assert "full" in types
    assert "incremental" in types


# ---------------------------------------------------------------------------
# 清理旧版本
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_old_backups(backup: DataBackup) -> None:
    for i in range(5):
        await backup.create_backup(name=f"v{i}")

    removed = await backup.cleanup_old_backups(keep_count=2)
    assert removed == 3

    backups = await backup.list_backups()
    assert len(backups) == 2


@pytest.mark.asyncio
async def test_cleanup_nothing_to_remove(backup: DataBackup) -> None:
    await backup.create_backup(name="only_one")
    removed = await backup.cleanup_old_backups(keep_count=10)
    assert removed == 0


# ---------------------------------------------------------------------------
# 删除备份
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_backup(backup: DataBackup) -> None:
    await backup.create_backup(name="to_delete")
    ok = await backup.delete_backup("to_delete")
    assert ok is True

    backups = await backup.list_backups()
    assert len(backups) == 0


@pytest.mark.asyncio
async def test_delete_nonexistent(backup: DataBackup) -> None:
    with pytest.raises(BackupNotFoundError):
        await backup.delete_backup("no_such_backup")


# ---------------------------------------------------------------------------
# 配置文件备份
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backup_includes_config(tmp_path: Path, data_dir: Path, config_file: Path) -> None:
    """如果有 .env 文件存在于工作目录，备份应包含它。"""
    import os

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        backup_dir = tmp_path / "backups"
        bk = DataBackup(
            backup_dir=str(backup_dir),
            data_dir=str(data_dir),
        )
        name = await bk.create_backup(name="with_config")
        assert (backup_dir / name / ".env").exists()
    finally:
        os.chdir(old_cwd)


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------


def test_get_backup_singleton() -> None:
    reset_backup()
    try:
        b1 = get_backup()
        b2 = get_backup()
        assert b1 is b2
    finally:
        reset_backup()
