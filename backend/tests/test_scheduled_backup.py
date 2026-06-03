"""定时备份调度器测试。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from backend.services.backup import DataBackup, reset_backup
from backend.services.scheduled_backup import (
    ScheduledBackup,
    get_scheduled_backup,
    reset_scheduled_backup,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def backup_instance(tmp_path: Path) -> DataBackup:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "test.json").write_text("{}", encoding="utf-8")

    return DataBackup(
        backup_dir=str(tmp_path / "backups"),
        data_dir=str(data_dir),
        keep_count=5,
    )


@pytest.fixture(autouse=True)
def _reset_singletons() -> None:
    """每个测试后重置全局单例。"""
    yield
    reset_backup()
    reset_scheduled_backup()


# ---------------------------------------------------------------------------
# 启动 / 停止
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_and_stop(backup_instance: DataBackup) -> None:
    scheduler = ScheduledBackup(full_backup_hours=999, keep_count=3)
    # 替换内部 get_backup 返回的实例
    import backend.services.scheduled_backup as mod

    original = mod.get_backup
    mod.get_backup = lambda: backup_instance

    try:
        await scheduler.start()
        assert scheduler.is_running is True

        await scheduler.stop()
        assert scheduler.is_running is False
    finally:
        mod.get_backup = original


@pytest.mark.asyncio
async def test_double_start(backup_instance: DataBackup) -> None:
    """重复启动不应创建多个任务。"""
    scheduler = ScheduledBackup(full_backup_hours=999)
    import backend.services.scheduled_backup as mod

    original = mod.get_backup
    mod.get_backup = lambda: backup_instance

    try:
        await scheduler.start()
        task1 = scheduler._task

        await scheduler.start()  # 第二次启动应被忽略
        task2 = scheduler._task

        assert task1 is task2
        await scheduler.stop()
    finally:
        mod.get_backup = original


@pytest.mark.asyncio
async def test_stop_when_not_running() -> None:
    """未启动时调用 stop 不应报错。"""
    scheduler = ScheduledBackup()
    await scheduler.stop()  # 应直接返回，不抛异常
    assert scheduler.is_running is False


# ---------------------------------------------------------------------------
# 立即执行 - 全量备份
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_now_full(backup_instance: DataBackup) -> None:
    scheduler = ScheduledBackup(full_backup_hours=999, keep_count=3)
    import backend.services.scheduled_backup as mod

    original = mod.get_backup
    mod.get_backup = lambda: backup_instance

    try:
        name = await scheduler.run_now(backup_type="full")
        assert name is not None
        assert name.startswith("backup_")

        # 验证备份确实创建了
        backups = await backup_instance.list_backups()
        assert len(backups) == 1
    finally:
        mod.get_backup = original


@pytest.mark.asyncio
async def test_run_now_incremental(backup_instance: DataBackup) -> None:
    """立即执行增量备份。"""
    # 先创建全量备份
    await backup_instance.create_backup(name="full_v1")

    scheduler = ScheduledBackup(full_backup_hours=999, keep_count=3)
    import backend.services.scheduled_backup as mod

    original = mod.get_backup
    mod.get_backup = lambda: backup_instance

    try:
        # 修改文件以产生增量
        (backup_instance._data_dir / "test.json").write_text('{"key": "new"}', encoding="utf-8")
        name = await scheduler.run_now(backup_type="incremental")
        assert name is not None
        assert name.startswith("incr_")

        backups = await backup_instance.list_backups()
        assert len(backups) == 2
    finally:
        mod.get_backup = original


@pytest.mark.asyncio
async def test_run_now_failure_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """备份创建失败时 run_now 应返回 None，不抛异常。"""
    scheduler = ScheduledBackup()

    import backend.services.scheduled_backup as mod

    original = mod.get_backup

    class FakeBackup:
        async def create_backup(self) -> str:
            raise RuntimeError("boom")

        async def create_incremental_backup(self) -> str:
            raise RuntimeError("boom")

        async def cleanup_old_backups(self, keep_count: int = 10) -> int:
            return 0

    mod.get_backup = lambda: FakeBackup()  # type: ignore[assignment]

    try:
        result = await scheduler.run_now()
        assert result is None
    finally:
        mod.get_backup = original


# ---------------------------------------------------------------------------
# 自动备份循环
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_runs_backup(backup_instance: DataBackup) -> None:
    """调度器启动后应自动执行一次备份。"""
    # 使用极短间隔，让循环快速执行
    scheduler = ScheduledBackup(
        full_backup_hours=1,
        incremental_hours=1,
        keep_count=3,
        enable_incremental=False,
    )
    import backend.services.scheduled_backup as mod

    original = mod.get_backup
    mod.get_backup = lambda: backup_instance

    try:
        await scheduler.start()
        # 给循环一点时间执行
        await asyncio.sleep(0.1)
        await scheduler.stop()

        backups = await backup_instance.list_backups()
        assert len(backups) >= 1
    finally:
        mod.get_backup = original


@pytest.mark.asyncio
async def test_loop_with_incremental(backup_instance: DataBackup) -> None:
    """启用增量备份后应同时运行全量和增量循环。"""
    scheduler = ScheduledBackup(
        full_backup_hours=999,
        incremental_hours=1,
        keep_count=3,
        enable_incremental=True,
    )
    import backend.services.scheduled_backup as mod

    original = mod.get_backup
    mod.get_backup = lambda: backup_instance

    try:
        await scheduler.start()
        assert scheduler._incremental_task is not None

        await scheduler.stop()
        assert scheduler._incremental_task is None
    finally:
        mod.get_backup = original


# ---------------------------------------------------------------------------
# 兼容性
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_interval_hours_compat(backup_instance: DataBackup) -> None:
    """interval_hours 参数应兼容旧版本。"""
    scheduler = ScheduledBackup(interval_hours=999, keep_count=3)
    import backend.services.scheduled_backup as mod

    original = mod.get_backup
    mod.get_backup = lambda: backup_instance

    try:
        await scheduler.start()
        assert scheduler.is_running is True
        await scheduler.stop()
    finally:
        mod.get_backup = original


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------


def test_get_scheduled_backup_singleton() -> None:
    reset_scheduled_backup()
    try:
        s1 = get_scheduled_backup()
        s2 = get_scheduled_backup()
        assert s1 is s2
    finally:
        reset_scheduled_backup()
