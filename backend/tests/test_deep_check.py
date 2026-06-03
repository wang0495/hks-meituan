"""DeepHealthCheck 单元测试。

覆盖：
- 聚合状态判定逻辑（healthy / degraded / unhealthy）
- critical_only 模式
- 系统资源检查函数（disk_space、memory）
- 自定义检查项注册
"""

from __future__ import annotations

import types
from unittest.mock import patch

import pytest

from backend.health.deep_check import (
    AggregatedStatus,
    DeepHealthCheck,
    check_disk_space,
    check_memory,
)
from backend.services.health_checker import CheckResult, CheckStatus

# ---------------------------------------------------------------------------
# 辅助：构造 psutil mock 模块
# ---------------------------------------------------------------------------


def _make_psutil_mock(
    *,
    disk_percent: float = 50.0,
    disk_free: float = 100 * 1024**3,
    disk_total: float = 200 * 1024**3,
    mem_percent: float = 60.0,
    mem_available: float = 8 * 1024**3,
    mem_total: float = 16 * 1024**3,
) -> types.ModuleType:
    """构造一个 psutil mock 模块，避免真实系统调用。"""
    mock_psutil = types.ModuleType("psutil")

    mock_disk = type(
        "Disk",
        (),
        {"percent": disk_percent, "free": disk_free, "total": disk_total},
    )()
    mock_psutil.disk_usage = lambda path: mock_disk  # type: ignore[attr-defined]

    mock_mem = type(
        "Mem",
        (),
        {"percent": mem_percent, "available": mem_available, "total": mem_total},
    )()
    mock_psutil.virtual_memory = lambda: mock_mem  # type: ignore[attr-defined]

    return mock_psutil


# ---------------------------------------------------------------------------
# AggregatedStatus 枚举
# ---------------------------------------------------------------------------


class TestAggregatedStatus:
    def test_values(self) -> None:
        assert AggregatedStatus.HEALTHY.value == "healthy"
        assert AggregatedStatus.DEGRADED.value == "degraded"
        assert AggregatedStatus.UNHEALTHY.value == "unhealthy"


# ---------------------------------------------------------------------------
# check_disk_space
# ---------------------------------------------------------------------------


class TestCheckDiskSpace:
    @pytest.mark.asyncio
    async def test_healthy_when_below_90(self) -> None:
        mock_psutil = _make_psutil_mock(disk_percent=50.0)
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            result = await check_disk_space()

        assert result.status == CheckStatus.HEALTHY
        assert result.details["percent"] == 50.0

    @pytest.mark.asyncio
    async def test_degraded_when_90_to_95(self) -> None:
        mock_psutil = _make_psutil_mock(disk_percent=92.0)
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            result = await check_disk_space()

        assert result.status == CheckStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_unhealthy_when_above_95(self) -> None:
        mock_psutil = _make_psutil_mock(disk_percent=97.0)
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            result = await check_disk_space()

        assert result.status == CheckStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_graceful_when_psutil_missing(self) -> None:
        with patch.dict("sys.modules", {"psutil": None}):
            result = await check_disk_space()

        assert result.status == CheckStatus.HEALTHY
        assert "psutil not installed" in result.details.get("note", "")

    @pytest.mark.asyncio
    async def test_error_on_exception(self) -> None:
        mock_psutil = types.ModuleType("psutil")
        mock_psutil.disk_usage = lambda path: (_ for _ in ()).throw(OSError("permission denied"))  # type: ignore[attr-defined]
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            result = await check_disk_space()

        assert result.status == CheckStatus.ERROR
        assert "OSError" in result.error  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# check_memory
# ---------------------------------------------------------------------------


class TestCheckMemory:
    @pytest.mark.asyncio
    async def test_healthy_when_below_85(self) -> None:
        mock_psutil = _make_psutil_mock(mem_percent=60.0)
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            result = await check_memory()

        assert result.status == CheckStatus.HEALTHY
        assert result.details["percent"] == 60.0

    @pytest.mark.asyncio
    async def test_degraded_when_85_to_95(self) -> None:
        mock_psutil = _make_psutil_mock(mem_percent=90.0)
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            result = await check_memory()

        assert result.status == CheckStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_unhealthy_when_above_95(self) -> None:
        mock_psutil = _make_psutil_mock(mem_percent=96.0)
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            result = await check_memory()

        assert result.status == CheckStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_graceful_when_psutil_missing(self) -> None:
        with patch.dict("sys.modules", {"psutil": None}):
            result = await check_memory()

        assert result.status == CheckStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_error_on_exception(self) -> None:
        mock_psutil = types.ModuleType("psutil")
        mock_psutil.virtual_memory = lambda: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[attr-defined]
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            result = await check_memory()

        assert result.status == CheckStatus.ERROR


# ---------------------------------------------------------------------------
# DeepHealthCheck 聚合逻辑
# ---------------------------------------------------------------------------


class TestDeepHealthCheck:
    @pytest.mark.asyncio
    async def test_all_healthy(self) -> None:
        """所有检查通过时返回 healthy。"""
        checker = DeepHealthCheck()

        async def ok() -> bool:
            return True

        checker._checker._checks.clear()
        checker._critical.clear()
        checker._checker.register("a", ok)
        checker._checker.register("b", ok)
        checker._critical["a"] = False
        checker._critical["b"] = False

        result = await checker.run()
        assert result["status"] == "healthy"
        assert result["healthy"] == 2
        assert result["total"] == 2

    @pytest.mark.asyncio
    async def test_critical_failure_makes_unhealthy(self) -> None:
        """关键依赖失败时返回 unhealthy。"""
        checker = DeepHealthCheck()

        async def ok() -> bool:
            return True

        async def fail() -> bool:
            return False

        checker._checker._checks.clear()
        checker._critical.clear()
        checker._checker.register("db", fail)
        checker._checker.register("cache", ok)
        checker._critical["db"] = True
        checker._critical["cache"] = False

        result = await checker.run()
        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_non_critical_failure_makes_degraded(self) -> None:
        """非关键依赖失败时返回 degraded。"""
        checker = DeepHealthCheck()

        async def ok() -> bool:
            return True

        async def fail() -> bool:
            return False

        checker._checker._checks.clear()
        checker._critical.clear()
        checker._checker.register("db", ok)
        checker._checker.register("llm", fail)
        checker._critical["db"] = True
        checker._critical["llm"] = False

        result = await checker.run()
        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_degraded_resource_makes_degraded(self) -> None:
        """资源检查返回 degraded 时整体 degraded。"""
        checker = DeepHealthCheck()

        async def ok() -> bool:
            return True

        async def degraded() -> CheckResult:
            return CheckResult(name="mem", status=CheckStatus.DEGRADED, details={"percent": 90})

        checker._checker._checks.clear()
        checker._critical.clear()
        checker._checker.register("db", ok)
        checker._checker.register("mem", degraded)
        checker._critical["db"] = True
        checker._critical["mem"] = False

        result = await checker.run()
        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_critical_only_mode(self) -> None:
        """critical_only=True 时只注册关键依赖。"""
        checker = DeepHealthCheck(critical_only=True)
        names = checker._checker.get_check_names()

        assert "database" in names
        assert "redis" in names
        assert "llm_service" not in names
        assert "disk_space" not in names
        assert "memory" not in names

    @pytest.mark.asyncio
    async def test_full_mode_registers_all(self) -> None:
        """默认模式注册所有检查项。"""
        checker = DeepHealthCheck(critical_only=False)
        names = set(checker._checker.get_check_names())

        assert "database" in names
        assert "redis" in names
        assert "llm_service" in names
        assert "disk_space" in names
        assert "memory" in names

    @pytest.mark.asyncio
    async def test_register_custom_check(self) -> None:
        """可以注册自定义检查项。"""
        checker = DeepHealthCheck()
        initial_count = len(checker._checker.get_check_names())

        async def custom() -> bool:
            return True

        checker.register("custom_svc", custom, critical=True)
        assert len(checker._checker.get_check_names()) == initial_count + 1
        assert checker._critical["custom_svc"] is True

    @pytest.mark.asyncio
    async def test_run_returns_expected_keys(self) -> None:
        """run() 返回的字典包含所有预期字段。"""
        checker = DeepHealthCheck(critical_only=True)

        result = await checker.run()
        assert "status" in result
        assert "checks" in result
        assert "timestamp" in result
        assert "duration_ms" in result
        assert "total" in result
        assert "healthy" in result

    @pytest.mark.asyncio
    async def test_check_detail_has_critical_flag(self) -> None:
        """每个检查项结果中包含 critical 字段。"""
        checker = DeepHealthCheck(critical_only=True)
        result = await checker.run()

        for name, detail in result["checks"].items():
            assert "critical" in detail
            if name in ("database", "redis"):
                assert detail["critical"] is True

    @pytest.mark.asyncio
    async def test_empty_checks_returns_healthy(self) -> None:
        """无检查项时返回 healthy。"""
        checker = DeepHealthCheck()
        checker._checker._checks.clear()
        checker._critical.clear()

        result = await checker.run()
        assert result["status"] == "healthy"
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# run_deep_check 便捷函数
# ---------------------------------------------------------------------------


class TestRunDeepCheck:
    @pytest.mark.asyncio
    async def test_convenience_function(self) -> None:
        from backend.health.deep_check import run_deep_check

        result = await run_deep_check(critical_only=True)
        assert "status" in result
        assert result["status"] in ("healthy", "degraded", "unhealthy")
