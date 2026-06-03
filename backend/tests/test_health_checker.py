"""健康检查模块单元测试。"""

from __future__ import annotations

import asyncio

import pytest

from backend.services.health_checker import CheckResult, CheckStatus, HealthChecker, HealthReport


class TestCheckResult:
    def test_to_dict(self) -> None:
        result = CheckResult(
            name="test",
            status=CheckStatus.HEALTHY,
            latency_ms=12.5,
        )
        d = result.to_dict()
        assert d["name"] == "test"
        assert d["status"] == "healthy"
        assert d["latency_ms"] == 12.5
        assert "timestamp" in d

    def test_to_dict_with_error(self) -> None:
        result = CheckResult(
            name="test",
            status=CheckStatus.ERROR,
            error="boom",
        )
        d = result.to_dict()
        assert d["error"] == "boom"

    def test_to_dict_excludes_none_fields(self) -> None:
        result = CheckResult(name="test", status=CheckStatus.HEALTHY)
        d = result.to_dict()
        assert "error" not in d
        assert "details" not in d


class TestHealthReport:
    def test_overall_healthy_when_all_ok(self) -> None:
        report = HealthReport(
            results=[
                CheckResult(name="a", status=CheckStatus.HEALTHY),
                CheckResult(name="b", status=CheckStatus.HEALTHY),
            ]
        )
        assert report.overall_status == CheckStatus.HEALTHY

    def test_overall_degraded(self) -> None:
        report = HealthReport(
            results=[
                CheckResult(name="a", status=CheckStatus.HEALTHY),
                CheckResult(name="b", status=CheckStatus.DEGRADED),
            ]
        )
        assert report.overall_status == CheckStatus.DEGRADED

    def test_overall_unhealthy_on_error(self) -> None:
        report = HealthReport(
            results=[
                CheckResult(name="a", status=CheckStatus.HEALTHY),
                CheckResult(name="b", status=CheckStatus.ERROR, error="fail"),
            ]
        )
        assert report.overall_status == CheckStatus.UNHEALTHY

    def test_overall_unhealthy_on_unhealthy(self) -> None:
        report = HealthReport(
            results=[
                CheckResult(name="a", status=CheckStatus.UNHEALTHY),
            ]
        )
        assert report.overall_status == CheckStatus.UNHEALTHY

    def test_overall_healthy_when_empty(self) -> None:
        report = HealthReport(results=[])
        assert report.overall_status == CheckStatus.HEALTHY

    def test_unhealthy_names(self) -> None:
        report = HealthReport(
            results=[
                CheckResult(name="db", status=CheckStatus.HEALTHY),
                CheckResult(name="redis", status=CheckStatus.UNHEALTHY),
                CheckResult(name="llm", status=CheckStatus.ERROR),
            ]
        )
        assert set(report.unhealthy_names) == {"redis", "llm"}

    def test_to_dict(self) -> None:
        report = HealthReport(
            results=[CheckResult(name="a", status=CheckStatus.HEALTHY)],
            duration_ms=5.0,
        )
        d = report.to_dict()
        assert d["overall_status"] == "healthy"
        assert d["duration_ms"] == 5.0
        assert len(d["checks"]) == 1


class TestHealthChecker:
    @pytest.mark.asyncio
    async def test_run_all_empty(self) -> None:
        checker = HealthChecker()
        report = await checker.run_all()
        assert report.overall_status == CheckStatus.HEALTHY
        assert report.results == []

    @pytest.mark.asyncio
    async def test_run_check_registered(self) -> None:
        checker = HealthChecker()

        async def ok() -> bool:
            return True

        checker.register("test", ok)
        result = await checker.run_check("test")
        assert result.name == "test"
        assert result.status == CheckStatus.HEALTHY
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_run_check_unregistered(self) -> None:
        checker = HealthChecker()
        result = await checker.run_check("nonexistent")
        assert result.status == CheckStatus.ERROR
        assert "未注册" in result.error  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_run_check_returns_false(self) -> None:
        checker = HealthChecker()

        async def bad() -> bool:
            return False

        checker.register("test", bad)
        result = await checker.run_check("test")
        assert result.status == CheckStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_run_check_exception(self) -> None:
        checker = HealthChecker()

        async def blow_up() -> bool:
            raise ConnectionError("connection refused")

        checker.register("test", blow_up)
        result = await checker.run_check("test")
        assert result.status == CheckStatus.ERROR
        assert "ConnectionError" in result.error  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_run_check_returns_check_result(self) -> None:
        checker = HealthChecker()

        async def custom() -> CheckResult:
            return CheckResult(
                name="custom",
                status=CheckStatus.DEGRADED,
                details={"reason": "slow"},
            )

        checker.register("test", custom)
        result = await checker.run_check("test")
        assert result.status == CheckStatus.DEGRADED
        assert result.details == {"reason": "slow"}

    @pytest.mark.asyncio
    async def test_run_all_aggregates(self) -> None:
        checker = HealthChecker()

        async def ok() -> bool:
            return True

        async def fail() -> bool:
            return False

        checker.register("good", ok)
        checker.register("bad", fail)

        report = await checker.run_all()
        assert report.overall_status == CheckStatus.UNHEALTHY
        assert len(report.results) == 2

    @pytest.mark.asyncio
    async def test_history_recorded(self) -> None:
        checker = HealthChecker()

        async def ok() -> bool:
            return True

        checker.register("test", ok)

        assert checker.latest is None
        await checker.run_all()
        assert checker.latest is not None
        assert len(checker.history) == 1

    @pytest.mark.asyncio
    async def test_history_size_limit(self) -> None:
        checker = HealthChecker(history_size=3)

        async def ok() -> bool:
            return True

        checker.register("test", ok)

        for _ in range(5):
            await checker.run_all()

        assert len(checker.history) == 3

    @pytest.mark.asyncio
    async def test_unregister(self) -> None:
        checker = HealthChecker()

        async def ok() -> bool:
            return True

        checker.register("test", ok)
        assert "test" in checker.get_check_names()

        checker.unregister("test")
        assert "test" not in checker.get_check_names()

    @pytest.mark.asyncio
    async def test_on_unhealthy_callback(self) -> None:
        checker = HealthChecker()
        called_with: list[HealthReport] = []

        async def callback(report: HealthReport) -> None:
            called_with.append(report)

        checker.set_on_unhealthy(callback)

        async def fail() -> bool:
            return False

        checker.register("bad", fail)
        await checker.run_all()

        assert len(called_with) == 1
        assert called_with[0].overall_status == CheckStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_on_unhealthy_not_called_when_healthy(self) -> None:
        checker = HealthChecker()
        called = False

        async def callback(report: HealthReport) -> None:
            nonlocal called
            called = True

        checker.set_on_unhealthy(callback)

        async def ok() -> bool:
            return True

        checker.register("good", ok)
        await checker.run_all()

        assert not called

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        checker = HealthChecker()
        run_count = 0

        async def counting_check() -> bool:
            nonlocal run_count
            run_count += 1
            return True

        checker.register("test", counting_check)
        await checker.start(interval=1)

        await asyncio.sleep(2.5)
        checker.stop()

        # 2-3 次
        assert run_count >= 2

    @pytest.mark.asyncio
    async def test_start_idempotent(self) -> None:
        checker = HealthChecker()

        async def ok() -> bool:
            return True

        checker.register("test", ok)
        await checker.start(interval=1)
        await checker.start(interval=1)  # 不应报错

        await asyncio.sleep(0.5)
        checker.stop()
